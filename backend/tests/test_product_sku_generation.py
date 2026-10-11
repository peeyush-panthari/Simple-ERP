"""SKU handling on product creation.

`POST /products` (the manual "New product" form) now requires the caller to
supply a SKU - it's rejected outright if omitted (see products.py's
create_product() route). Auto-generation (<TYPE prefix>-<AA01-style counter>,
independent per product type, via next_sku()/_create_product()) still exists
as a real code path - it's what bulk_upload_products() falls back to for a
CSV row with a blank sku column - so it's covered here by calling
_create_product() directly rather than through the now-manual-only route.

Note: `fresh_admin` reuses one shared tenant for the whole test session (see
conftest.py) against the real dev DB, not an isolated/rolled-back one, so
assertions here are relative (each product's suffix vs. the next one for the
same type) rather than assuming a fresh AA01 start. `_created` tracks and
deletes every product this module creates so re-runs don't accumulate rows.
"""

import re
import uuid

import pytest


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


@pytest.fixture
def _created(app):
    """There's no DELETE /products route (products aren't hard-deletable via the
    API by design) - clean up directly via the ORM so this test module doesn't
    leave permanent rows in the shared dev DB (tests here run with no
    transaction rollback - see conftest.py's session-scoped `app` fixture)."""
    ids: list[str] = []
    yield ids
    if not ids:
        return
    import uuid as _uuid

    from tests.flaskcompat import db as _db
    from app.models.product import Product

    with app.app_context():
        Product.query.filter(Product.id.in_([_uuid.UUID(i) for i in ids])).delete(synchronize_session=False)
        _db.session.commit()


def _create_product(client, admin_access, _created, **over):
    body = {
        "sku": f"SKU-{uuid.uuid4().hex[:10].upper()}",
        "name": "SKU generation test product",
        "make": f"Test Make {uuid.uuid4().hex[:8]}",
        "type": "raw_material",
        "uom": "KG",
    }
    body.update(over)
    resp = client.post("/api/v1/products", json=body, headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    _created.append(data["id"])
    return data


def _create_product_via_service(app, default_tenant_id, fresh_admin, _created, **over):
    """Calls the shared _create_product()/next_sku() code path directly -
    bulk_upload_products() is the only remaining HTTP caller that can omit
    sku, and building a real CSV bulk-upload request (which also needs a
    valid category) is more machinery than this needs."""
    from app.domains.products.router import CreateProductBody, _create_product

    body_kwargs = {
        "name": "SKU generation test product",
        "make": f"Test Make {uuid.uuid4().hex[:8]}",
        "type": "raw_material",
        "uom": "KG",
    }
    body_kwargs.update(over)
    with app.app_context():
        product = _create_product(
            default_tenant_id,
            {"user_id": uuid.UUID(fresh_admin["id"]), "email": fresh_admin["email"]},
            CreateProductBody(**body_kwargs),
        )
        _created.append(str(product.id))
        return {"sku": product.sku}


_SKU_RE = re.compile(r"^([A-Z]{2})-([A-Z]{2})(\d{2})$")


def _suffix_index(sku: str) -> int:
    """Inverse of the AA01-style mapping, for asserting strict incrementing order."""
    m = _SKU_RE.match(sku)
    assert m, f"unexpected SKU shape: {sku}"
    _prefix, letters, number = m.groups()
    letter_index = (ord(letters[0]) - ord("A")) * 26 + (ord(letters[1]) - ord("A"))
    return letter_index * 99 + int(number)


def test_manual_create_without_sku_is_rejected(client, admin_access, _created):
    resp = client.post(
        "/api/v1/products",
        json={"name": "No SKU product", "make": "Acme", "type": "raw_material", "uom": "KG"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "SKU_REQUIRED"


def test_client_supplied_sku_still_honoured(client, admin_access, _created):
    product = _create_product(client, admin_access, _created, sku="RM-EXPLICIT-01")
    assert product["sku"] == "RM-EXPLICIT-01"


def test_duplicate_sku_is_rejected(client, admin_access, _created):
    first = _create_product(client, admin_access, _created, sku=f"RM-DUPE-{uuid.uuid4().hex[:6].upper()}")
    dupe = client.post(
        "/api/v1/products",
        json={"sku": first["sku"], "name": "Different product", "make": "Different make", "type": "raw_material", "uom": "KG"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert dupe.status_code == 409, dupe.get_json()
    assert dupe.get_json()["code"] == "SKU_TAKEN"


def test_sku_auto_generated_when_omitted_via_service(app, default_tenant_id, fresh_admin, _created):
    product = _create_product_via_service(app, default_tenant_id, fresh_admin, _created)
    assert _SKU_RE.match(product["sku"]), product["sku"]
    assert product["sku"].startswith("RM-")


def test_sku_counter_increments_by_one_per_type_via_service(app, default_tenant_id, fresh_admin, _created):
    first = _create_product_via_service(app, default_tenant_id, fresh_admin, _created, type="raw_material", uom="KG")
    second = _create_product_via_service(app, default_tenant_id, fresh_admin, _created, type="raw_material", uom="KG")
    assert _suffix_index(second["sku"]) == _suffix_index(first["sku"]) + 1


def test_sku_counter_independent_across_types_via_service(app, default_tenant_id, fresh_admin, _created):
    _create_product_via_service(app, default_tenant_id, fresh_admin, _created, type="raw_material", uom="KG")
    fg1 = _create_product_via_service(app, default_tenant_id, fresh_admin, _created, type="finished_good", uom="UNIT")
    fg2 = _create_product_via_service(app, default_tenant_id, fresh_admin, _created, type="finished_good", uom="UNIT")
    _create_product_via_service(app, default_tenant_id, fresh_admin, _created, type="consumable", uom="UNIT")
    _create_product_via_service(app, default_tenant_id, fresh_admin, _created, type="service", uom="UNIT")

    assert fg1["sku"].startswith("FG-") and fg2["sku"].startswith("FG-")
    # finished_good's own counter is untouched by the raw_material/consumable/service calls in between.
    assert _suffix_index(fg2["sku"]) == _suffix_index(fg1["sku"]) + 1
