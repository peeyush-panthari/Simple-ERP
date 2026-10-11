"""The production boot guard.

Every default in app/config.py is a local-development default, and several of
them are actively unsafe off this machine: JWT_SECRET and ENCRYPTION_SECRET are
published in .env.example, and FRONTEND_BASE_URL is baked into printed QR codes.
APP_ENV=production makes create_app() refuse to start while any of those is
still in place, rather than serving happily with a public signing key.
"""

import pytest

from app.main import ProductionConfigError, create_app
from app.core.config import Settings


def _settings(**values) -> Settings:
    """_env_file=None so these assertions describe app/config.py's declared
    defaults, not whatever the developer happens to have in backend_py/.env."""
    return Settings(_env_file=None, **values)


def _prod(**overrides) -> Settings:
    base = {
        "app_env": "production",
        "rate_limit_enabled": True,
        "jwt_secret": "x" * 48,
        "encryption_secret": "y" * 32,
        "frontend_base_url": "https://erp.example.com",
        "cors_allowed_origins": "https://erp.example.com",
        "trusted_proxy_hops": 1,
        "rate_limit_storage_uri": "redis://127.0.0.1:6379/0",
        "s3_bucket": "simple-erp-docs",
        "s3_access_key_id": "AKIA",
        "s3_secret_access_key": "secret",
        "pdf_engine": "gotenberg",
        "smtp_host": "smtp.example.com",
        "bootstrap_admin_password": "set-out-of-band",
    }
    return _settings(**{**base, **overrides})


def test_development_defaults_raise_nothing():
    """./start.sh must keep working with no environment at all."""
    dev = _settings()
    assert dev.is_production is False
    assert dev.production_config_errors == []
    assert dev.production_config_warnings == []


def test_a_fully_configured_production_env_is_clean():
    settings = _prod()
    assert settings.production_config_errors == []
    assert settings.production_config_warnings == []


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"jwt_secret": "dev-only-change-me"}, "JWT_SECRET"),
        ({"encryption_secret": "dev-only-change-me-encryption-secret-32b"}, "ENCRYPTION_SECRET"),
        ({"frontend_base_url": "http://localhost:3001"}, "FRONTEND_BASE_URL"),
        ({"frontend_base_url": "http://127.0.0.1:3001"}, "FRONTEND_BASE_URL"),
        # No scheme: urlsplit reads "localhost" as the scheme unless helped.
        ({"frontend_base_url": "localhost:3001"}, "FRONTEND_BASE_URL"),
        ({"db_backend": "sqlite"}, "DB_BACKEND"),
    ],
)
def test_each_unsafe_default_is_fatal(override, expected):
    errors = _prod(**override).production_config_errors
    assert len(errors) == 1, errors
    assert expected in errors[0]


def test_bigquery_placeholder_project_is_fatal_only_when_bigquery_is_selected():
    assert _prod().production_config_errors == []  # db_backend=postgres, placeholder unused
    errors = _prod(db_backend="bigquery").production_config_errors
    assert len(errors) == 1 and "GCP_PROJECT_ID" in errors[0]


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"cors_allowed_origins": "https://erp.example.com,http://localhost:3001"}, "CORS_ALLOWED_ORIGINS"),
        ({"trusted_proxy_hops": 0}, "TRUSTED_PROXY_HOPS"),
        ({"rate_limit_storage_uri": "", "redis_url": ""}, "RATE_LIMIT_STORAGE_URI"),
        ({"s3_bucket": ""}, "S3"),
        ({"pdf_engine": "html"}, "PDF_ENGINE"),
        ({"smtp_host": "127.0.0.1"}, "SMTP_HOST"),
        ({"bootstrap_admin_password": ""}, "BOOTSTRAP_ADMIN_PASSWORD"),
    ],
)
def test_probably_wrong_settings_warn_but_never_block_the_boot(override, expected):
    """A staging box legitimately hits some of these - warn, don't refuse."""
    settings = _prod(**override)
    assert settings.production_config_errors == []
    assert any(expected in w for w in settings.production_config_warnings), settings.production_config_warnings


def test_warnings_and_errors_are_silent_outside_production():
    """The same values that fail in production are the point of development."""
    dev = _settings(app_env="development", jwt_secret="dev-only-change-me")
    assert dev.production_config_errors == []
    assert dev.production_config_warnings == []


def test_create_app_refuses_to_boot_and_names_every_problem(monkeypatch):
    import app.main as app_module

    monkeypatch.setattr(app_module.settings, "app_env", "production")
    monkeypatch.setattr(app_module.settings, "jwt_secret", "dev-only-change-me")
    monkeypatch.setattr(app_module.settings, "frontend_base_url", "http://localhost:3001")

    with pytest.raises(ProductionConfigError) as excinfo:
        create_app()

    message = str(excinfo.value)
    assert "JWT_SECRET" in message
    assert "FRONTEND_BASE_URL" in message
    assert "DEPLOYMENT.md" in message


def _app_with_hops(monkeypatch, hops: int):
    """A second app instance configured for a given proxy depth, with a route
    that reports what the app believes the client's address to be."""
    import app.main as app_module

    monkeypatch.setattr(app_module.settings, "trusted_proxy_hops", hops)
    from starlette.requests import Request as _Request

    from tests import flaskcompat

    application = create_app()

    def whoami(request: _Request):
        return {"ip": request.client.host, "scheme": request.url.scheme}

    # This is about the proxy layer, not authentication: the route has no auth dependency.
    application.add_api_route("/api/v1/public/_test-whoami", whoami, methods=["GET"])
    flaskcompat.install(application)
    return application


def test_forwarded_headers_are_ignored_when_no_proxy_is_declared(monkeypatch):
    """Reachable directly, X-Forwarded-For is caller-controlled: believing it
    would let anyone pick a fresh identity per request and walk past both the
    login rate limiter and the public-intake throttle."""
    client = _app_with_hops(monkeypatch, 0).test_client()
    resp = client.get(
        "/api/v1/public/_test-whoami",
        headers={"X-Forwarded-For": "203.0.113.7"},
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )
    assert resp.get_json()["ip"] == "10.0.0.1"


def test_one_declared_proxy_hop_recovers_the_real_client_ip(monkeypatch):
    client = _app_with_hops(monkeypatch, 1).test_client()
    resp = client.get(
        "/api/v1/public/_test-whoami",
        headers={"X-Forwarded-For": "203.0.113.7", "X-Forwarded-Proto": "https"},
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )
    body = resp.get_json()
    assert body["ip"] == "203.0.113.7"
    assert body["scheme"] == "https", "the proxy terminates TLS; the app must know"


def test_only_the_declared_number_of_hops_is_trusted(monkeypatch):
    """With one proxy declared, a chain longer than one means the extra entries
    were supplied by the caller - take the last, not the first."""
    client = _app_with_hops(monkeypatch, 1).test_client()
    resp = client.get(
        "/api/v1/public/_test-whoami",
        headers={"X-Forwarded-For": "198.51.100.9, 203.0.113.7"},
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )
    assert resp.get_json()["ip"] == "203.0.113.7"


