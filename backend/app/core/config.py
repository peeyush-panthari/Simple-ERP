"""Configuration settings powered by pydantic_settings."""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


def _is_loopback(value: str) -> bool:
    """True for a URL, a bare hostname, or a "host:port" pointing at this
    machine. urlsplit needs a scheme (or at least "//") before it will treat
    anything as a netloc, hence the prefix on the second branch - without it
    "localhost:3001" parses as scheme "localhost" and slips through."""
    value = value.strip()
    host = urlsplit(value if "//" in value else f"//{value}").hostname
    return (host or "").lower() in _LOOPBACK_HOSTS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- deployment -------------------------------------------------------
    app_env: str = "development"  # "development" | "production"
    host: str = "127.0.0.1"

    # Number of trusted reverse proxies in front of this app. 0 means the app
    # is reached directly, so X-Forwarded-* headers are attacker-controlled
    # and must be ignored.
    trusted_proxy_hops: int = 0

    database_url: str = (
        "postgresql+psycopg://axon_py:axon_py@127.0.0.1:5433/axon_erp_py"
    )

    # Connection pool - see app/core/db.py.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle_seconds: int = 1800
    db_pool_timeout_seconds: int = 30

    port: int = 8000

    jwt_secret: str = "dev-only-change-me"
    jwt_issuer: str = "axon-identity-py"
    jwt_audience: str = "axon-erp"
    access_token_ttl: int = 900
    refresh_token_ttl: int = 2592000

    mfa_issuer: str = "Simple ERP"
    bootstrap_admin_email: str = "admin@axon-erp.local"
    bootstrap_admin_password: str = ""

    default_tenant_id: str = "00000000-0000-4000-8000-000000000001"
    default_tenant_name: str = "Simple ERP Demo Tenant"
    default_tenant_slug: str = "axon-demo"

    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rate_limit_login_per_minute: int = 20
    rate_limit_enabled: bool = True
    # Redis-backed (see app/core/rate_limit.py) - unlike the Flask original
    # (in-process-memory default), this is required, not optional, since the
    # new stack has Redis available from the start.
    redis_url: str = "redis://127.0.0.1:6379/0"
    # Overrides redis_url for the rate limiter only (e.g. "memory://" for a
    # single-process dev run without Redis); empty means "use redis_url".
    rate_limit_storage_uri: str = ""
    rabbitmq_url: str = "amqp://guest:guest@127.0.0.1:5672/"

    # ---- async work (RabbitMQ worker) ----------------------------------------
    # False (default) keeps the original behaviour exactly: notification
    # emails/SMS are delivered inline, inside the request. True queues them
    # (the row is committed as status="queued", then a message is published
    # AFTER the commit) and the `python -m app.worker` process delivers them,
    # so a slow SMTP server can never hold an API worker or fail a request.
    async_notifications: bool = False
    notification_queue: str = "simple.notifications"
    # Same idea for PDFs. False (default): a generated document (invoice, PO copy, reprint) is rendered
    # inside the request, as in the original. True: the request stores the document row and its
    # render data and returns at once; the worker renders the PDF afterwards (see
    # document_repo.complete_render), and a download that arrives before the worker has finished
    # renders it on the spot - so correctness never depends on the worker being up. Only helps when a
    # real engine is configured (PDF_ENGINE=gotenberg|weasyprint); the "html" engine is instant anyway.
    async_pdf: bool = False
    document_queue: str = "simple.documents"
    # How often the worker re-scans for queued notifications whose message was
    # lost (broker down at publish time) or whose retry delay has elapsed.
    worker_sweep_seconds: int = 30

    # Redis-cached /dashboard, per tenant. 0 disables (recompute live, as the
    # original does); the compose file turns it on.
    dashboard_cache_seconds: int = 0

    frontend_base_url: str = "http://localhost:5173"

    # party module
    base_currency: str = "INR"
    party_code_prefix: str = "PTY"
    party_home_country: str = "IN"
    encryption_secret: str = "dev-only-change-me-encryption-secret-32b"

    # product module
    category_max_depth: int = 5

    # bom module
    allow_nested_bom: bool = False
    bom_max_depth: int = 12

    # warehouse module
    grn_number_prefix: str = "GRN"
    quarantine_location_code: str = "QUARANTINE"

    # inventory module
    allocation_strategy: str = "fefo"  # "fefo" | "fifo"

    # procurement module
    po_approval_threshold_l1: str = "100000"
    po_approval_threshold_l2: str = "1000000"
    po_approval_threshold_l3: str = "5000000"
    po_receipt_tolerance_percent: str = "2"
    po_number_prefix: str = "PO"

    # order module
    so_number_prefix: str = "SO"
    invoice_number_prefix: str = "INV"
    default_payment_days: int = 30

    # logistics module
    rfq_min_invitations: int = 2
    rfq_response_hours: int = 48
    lr_number_prefix: str = "LR"
    rfq_number_prefix: str = "RFQ"
    public_request_rate_per_hour: int = 10

    # finance module
    overpayment_policy: str = "block"  # "block" | "credit"
    payment_approval_threshold: str = "500000"
    finance_match_tolerance_percent: str = "2"
    ap_number_prefix: str = "AP"
    cn_number_prefix: str = "CN"
    pay_number_prefix: str = "PAY"

    # document module
    pdf_engine: str = "html"  # "gotenberg" | "weasyprint" | "html"
    gotenberg_url: str = ""
    document_local_dir: str = "/tmp/axon-documents"
    presigned_url_ttl_seconds: int = 900
    company_name: str = "Simple ERP Industries"
    company_address: str = "Plot 22, Hinjawadi Phase II, Pune 411057, India"
    company_gstin: str = "27AAPFU0939F1ZV"
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_endpoint: str = ""
    s3_region: str = "ap-south-1"
    malware_scanner_url: str = ""

    # notification module
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_secure: bool = False  # implicit TLS (port 465)
    smtp_starttls: bool = False  # upgrade a plain connection with STARTTLS (port 587)
    smtp_from: str = "Simple ERP <no-reply@simple-erp.dev>"
    max_delivery_attempts: int = 5
    retry_base_seconds: int = 30
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def production_config_errors(self) -> list[str]:
        """Settings still at their local-development default that would be
        unsafe or broken in a live deployment. main.py refuses to boot on any
        of these when app_env is "production"."""
        if not self.is_production:
            return []

        errors: list[str] = []
        if "dev-only" in self.jwt_secret:
            errors.append(
                "JWT_SECRET is still the development placeholder - anyone with the "
                "repo can mint valid tokens. Generate one: python -c "
                "'import secrets; print(secrets.token_urlsafe(48))'"
            )
        if "dev-only" in self.encryption_secret:
            errors.append(
                "ENCRYPTION_SECRET is still the development placeholder - encrypted "
                "party tax IDs would be readable by anyone with the repo. Generate "
                "one: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        if _is_loopback(self.frontend_base_url):
            errors.append(
                f"FRONTEND_BASE_URL is {self.frontend_base_url!r} - inventory-item QR "
                "codes are printed and scanned from other devices, so this must be the "
                "web app's public URL."
            )
        return errors

    @property
    def production_config_warnings(self) -> list[str]:
        """Settings that boot fine in production but are almost certainly not
        what was intended. Logged at WARNING, never fatal."""
        if not self.is_production:
            return []

        warnings: list[str] = []
        loopback_origins = [o for o in self.cors_origins_list if _is_loopback(o)]
        if loopback_origins:
            warnings.append(
                f"CORS_ALLOWED_ORIGINS still lists local origins ({', '.join(loopback_origins)})."
            )
        if self.trusted_proxy_hops == 0:
            warnings.append(
                "TRUSTED_PROXY_HOPS=0: X-Forwarded-* headers are ignored, so behind a "
                "load balancer every recorded client IP will be the proxy's."
            )
        if self.rate_limit_enabled and not (self.rate_limit_storage_uri or self.redis_url):
            warnings.append(
                "RATE_LIMIT_STORAGE_URI and REDIS_URL are both unset: rate limits are counted per "
                "worker process and reset on restart."
            )
        if not (self.s3_bucket and self.s3_access_key_id and self.s3_secret_access_key):
            warnings.append(
                f"No S3 credentials: generated documents are written to "
                f"{self.document_local_dir}, which is lost when the container restarts."
            )
        if self.pdf_engine == "html":
            warnings.append("PDF_ENGINE=html: documents are served as HTML, not real PDFs.")
        if _is_loopback(self.smtp_host):
            warnings.append(f"SMTP_HOST is {self.smtp_host!r}: notification emails will not leave the host.")
        if not self.bootstrap_admin_password:
            warnings.append(
                "BOOTSTRAP_ADMIN_PASSWORD is blank: a random one is generated and written "
                "to the application log on first boot."
            )
        return warnings

    @property
    def sqlalchemy_database_uri(self) -> str:
        """The engine URI for PostgreSQL."""
        return self.database_url


settings = Settings()
