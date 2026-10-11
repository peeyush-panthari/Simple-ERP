"""Product 'make' field + the name+make uniqueness rule.

Note: tests run against the shared dev DB with no rollback (see conftest.py) -
`_created` deletes what it creates directly via the ORM (no DELETE /products route).
"""

import uuid

import pytest


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


@pytest.fixture
def _created(app):
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
        "name": "Name+Make test product",
        "make": "Acme",
        "type": "raw_material",
        "uom": "KG",
    }
    body.update(over)
    resp = client.post("/api/v1/products", json=body, headers={"Authorization": f"Bearer {admin_access}"})
    if resp.status_code == 201:
        _created.append(resp.get_json()["id"])
    return resp


def test_make_is_stored_and_returned(client, admin_access, _created):
    resp = _create_product(client, admin_access, _created, make="Bosch")
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["make"] == "Bosch"


def test_same_name_and_make_is_rejected(client, admin_access, _created):
    first = _create_product(client, admin_access, _created, name="Steel Rod", make="Acme")
    assert first.status_code == 201, first.get_json()

    dupe = _create_product(client, admin_access, _created, name="Steel Rod", make="Acme")
    assert dupe.status_code == 409, dupe.get_json()
    assert dupe.get_json()["code"] == "PRODUCT_NAME_MAKE_TAKEN"


def test_same_name_different_make_is_allowed(client, admin_access, _created):
    first = _create_product(client, admin_access, _created, name="Steel Rod 2", make="Acme")
    second = _create_product(client, admin_access, _created, name="Steel Rod 2", make="Bosch")
    assert first.status_code == 201, first.get_json()
    assert second.status_code == 201, second.get_json()


def test_same_make_different_name_is_allowed(client, admin_access, _created):
    first = _create_product(client, admin_access, _created, name="Steel Rod 3", make="Acme")
    second = _create_product(client, admin_access, _created, name="Steel Rod 4", make="Acme")
    assert first.status_code == 201, first.get_json()
    assert second.status_code == 201, second.get_json()


def test_case_insensitive_match_is_still_rejected(client, admin_access, _created):
    first = _create_product(client, admin_access, _created, name="Steel Rod 5", make="Acme")
    assert first.status_code == 201, first.get_json()

    dupe = _create_product(client, admin_access, _created, name="STEEL ROD 5", make="acme")
    assert dupe.status_code == 409, dupe.get_json()


def test_patch_to_a_taken_name_make_is_rejected(client, admin_access, _created):
    a = _create_product(client, admin_access, _created, name="Steel Rod 6", make="Acme")
    b = _create_product(client, admin_access, _created, name="Steel Rod 7", make="Acme")
    assert a.status_code == 201 and b.status_code == 201

    resp = client.patch(
        f"/api/v1/products/{b.get_json()['id']}",
        json={"name": "Steel Rod 6"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 409, resp.get_json()
    assert resp.get_json()["code"] == "PRODUCT_NAME_MAKE_TAKEN"


def test_patch_own_product_without_changing_name_make_is_fine(client, admin_access, _created):
    resp = _create_product(client, admin_access, _created, name="Steel Rod 8", make="Acme")
    assert resp.status_code == 201

    patch_resp = client.patch(
        f"/api/v1/products/{resp.get_json()['id']}",
        json={"name": "Steel Rod 8", "make": "Acme"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert patch_resp.status_code == 200, patch_resp.get_json()
