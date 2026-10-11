"""Copy the original repo's tests into tests/ with the import paths rewritten.

    python scripts/port_original_tests.py "<path to Simple ERP>/backend_py/tests"

Assertions are copied untouched apart from the few PATCHES below, each of which fixes a test that only
passed in the original by accident (see the comment on each). Only module paths change otherwise
(app.errors -> app.core.errors, app.extensions -> tests.flaskcompat, ...). Tests written fresh for this
stack (OWN) and the BigQuery-specific ones are not overwritten. Re-runnable: it regenerates the copies.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Written for this stack; never overwritten by a copy of a same-named original.
OWN = {
    "test_auth.py", "test_bom.py", "test_documents_notifications.py", "test_foundation.py", "test_grn.py", "test_infra.py",
    "test_logistics_finance.py", "test_orders.py", "test_parties_products.py", "test_production.py", "test_purchase_orders.py", "test_warehouses_inventory.py",
}
SKIP = {"conftest.py", "__init__.py"}
# Same name as one of ours: keep both.
RENAME = {"test_auth.py": "test_auth_original.py"}
SUBS = [
    (r"from app\.extensions import db\b", "from tests.flaskcompat import db"),
    (r"from app\.errors import", "from app.core.errors import"),
    (r"from app\.config import", "from app.core.config import"),
    (r"from app\.services\.money import", "from app.core.money import"),
    (r"from app\.services\.password import", "from app.core.security import"),
    (r"from app import ProductionConfigError, create_app", "from app.main import ProductionConfigError, create_app"),
    (r"from app\.routes\.grns import", "from app.domains.grn.qr_router import"),
    (r"app\.routes\.business_entities", "app.domains.foundation.masters_router"),
    (r"app\.routes\.product_categories", "app.domains.foundation.masters_router"),
    (r"app\.routes\.party_types", "app.domains.foundation.router"),
    (r"app\.routes\.purchase_orders", "app.domains.procurement.router"),
    (r"app\.services\.audit\b", "app.core.audit"),
    (r"from app\.routes\.products import CreateProductBody, _create_product", "from app.domains.products.router import CreateProductBody, _create_product"),
]
# (file, old, new, why)
PATCHES = [
    (
        "test_grn_sticker_size.py",
        'assert "210mm 297mm" in body',
        'assert re.search(r"210(\\.00)?mm 297(\\.00)?mm", body)',
        "the original read the page size back from an object still cached in the shared session as Decimal('210'); a fresh load returns the NUMERIC(8,2) value 210.00 - the same in both apps",
    ),
    (
        "test_grn_sticker_size.py",
        'assert "grid-template-columns: repeat(3, 50mm)" in body',
        'assert re.search(r"grid-template-columns: repeat\\(3, 50(\\.00)?mm\\)", body)',
        "same NUMERIC(8,2) rendering as the page size above",
    ),
    ("test_grn_sticker_size.py", "\nimport uuid\n", "\nimport re\nimport uuid\n", "the patch above uses `re`"),
    (
        "test_production_config.py",
        '"app_env": "production",',
        '"app_env": "production",\n        "rate_limit_enabled": True,',
        "this checkout's .env (loaded by pytest-dotenv) turns the limiter off for the suite, which would silence the limiter warning",
    ),
    ("test_production_config.py", "import app as app_module", "import app.main as app_module", "settings live on app.main here"),
    ("test_production_config.py", "import app as app_module", "import app.main as app_module", "settings live on app.main here"),
    (
        "test_production_config.py",
        '({"rate_limit_storage_uri": ""}, "RATE_LIMIT_STORAGE_URI"),',
        '({"rate_limit_storage_uri": "", "redis_url": ""}, "RATE_LIMIT_STORAGE_URI"),',
        "an empty RATE_LIMIT_STORAGE_URI falls back to REDIS_URL here, so the in-process-counters warning needs both empty",
    ),
    (
        "test_production_config.py",
        '''    application = create_app()
    application.config["TESTING"] = True

    def whoami():
        from flask import jsonify, request

        return jsonify({"ip": request.remote_addr, "scheme": request.scheme})

    # Under the public prefix so auth_guard.load_actor lets it through without
    # a bearer token - this is about the WSGI layer, not authentication.
    application.add_url_rule("/api/v1/public/_test-whoami", "whoami", whoami)
    return application''',
        '''    from starlette.requests import Request as _Request

    from tests import flaskcompat

    application = create_app()

    def whoami(request: _Request):
        return {"ip": request.client.host, "scheme": request.url.scheme}

    # This is about the proxy layer, not authentication: the route has no auth dependency.
    application.add_api_route("/api/v1/public/_test-whoami", whoami, methods=["GET"])
    flaskcompat.install(application)
    return application''',
        "Flask's WSGI ProxyFix becomes the ASGI ProxyFixMiddleware; the probe route reports what the app believes",
    ),
    (
        "test_foundation_factory_business_entity.py",
        'listed = client.get("/api/v1/factories", headers=_headers(admin_access))',
        'listed = client.get("/api/v1/factories", query_string={"q": factory["code"]}, headers=_headers(admin_access))',
        "the list is ordered by code and paged at 25, so on a database that has accumulated more factories the new one falls off page 1",
    ),
]


def main(src: Path, dst: Path) -> None:
    for f in sorted(src.glob("test_*.py")):
        if f.name in SKIP or (f.name in OWN and f.name not in RENAME):
            continue
        text = f.read_text()
        for pat, rep in SUBS:
            text = re.sub(pat, rep, text)
        for name, old, new, _why in PATCHES:
            if name == f.name:
                assert old in text, f"patch no longer applies: {name}: {old}"
                text = text.replace(old, new, 1)
        if not text.lstrip().startswith('"""'):
            text = f'"""Ported from backend_py/tests/{f.name} (import paths only)."""\n' + text
        (dst / RENAME.get(f.name, f.name)).write_text(text)
        print("ported", f.name)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(__file__).resolve().parent.parent / "tests")
