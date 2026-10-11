"""Integration coverage for the product routes over a real test client + DB.

Guards against the ProductImage.created_at regression: GET /products/:id used
to crash with AttributeError at query-build time because the model had no
created_at column, even for a product with zero images.
"""

import uuid

import pytest


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


@pytest.fixture
def _created(app):
    """No DELETE /products route (products aren't hard-deletable via the API by
    design) - clean up directly via the ORM so this module doesn't leave
    permanent rows in the shared dev DB (tests here run with no transaction
    rollback - see conftest.py's session-scoped `app` fixture)."""
    ids: list[str] = []
    yield ids
    if not ids:
        return
    from tests.flaskcompat import db as _db
    from app.models.product import Product

    with app.app_context():
        Product.query.filter(Product.id.in_([uuid.UUID(i) for i in ids])).delete(synchronize_session=False)
        _db.session.commit()


def _create_product(client, admin_access, _created, **over):
    body = {
        "sku": f"RM-{uuid.uuid4().hex[:8].upper()}",
        "name": f"Test Steel Rod {uuid.uuid4().hex[:8]}",
        "make": "Test Make",
        "type": "raw_material",
        "uom": "KG",
    }
    body.update(over)
    resp = client.post("/api/v1/products", json=body, headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 201, resp.get_json()
    product_id = resp.get_json()["id"]
    _created.append(product_id)
    return product_id


def test_get_product_without_images(client, admin_access, _created):
    product_id = _create_product(client, admin_access, _created)

    resp = client.get(f"/api/v1/products/{product_id}", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["images"] == []


def test_get_product_with_images_is_ordered_by_sort_order(client, admin_access, _created):
    product_id = _create_product(client, admin_access, _created)

    client.post(
        f"/api/v1/products/{product_id}/images",
        json={"url": "https://example.test/a.png", "sortOrder": 1},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    client.post(
        f"/api/v1/products/{product_id}/images",
        json={"url": "https://example.test/b.png", "sortOrder": 0},
        headers={"Authorization": f"Bearer {admin_access}"},
    )

    resp = client.get(f"/api/v1/products/{product_id}", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 200
    images = resp.get_json()["images"]
    assert [i["url"] for i in images] == ["https://example.test/b.png", "https://example.test/a.png"]
