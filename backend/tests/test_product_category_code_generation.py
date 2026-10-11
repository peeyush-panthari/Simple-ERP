"""Auto-generated product category code: PROD-<AA01-style counter>, one
counter per tenant shared across all categories.

Note: `fresh_admin` reuses one shared tenant for the whole test session (see
conftest.py) against the real dev DB, so assertions here are relative (each
category's suffix vs. the next one) rather than assuming a fresh AA01 start.
There's no DELETE /product-categories route for an unused category with no
children, so `_created` cleans up directly via the ORM.
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
    ids: list[str] = []
    yield ids
    if not ids:
        return
    from tests.flaskcompat import db as _db
    from app.models.product_category import ProductCategory

    with app.app_context():
        ProductCategory.query.filter(ProductCategory.id.in_([uuid.UUID(i) for i in ids])).delete(synchronize_session=False)
        _db.session.commit()


def _create_category(client, admin_access, _created, **over):
    body = {"productCategory": f"Test category {uuid.uuid4().hex[:8]}"}
    body.update(over)
    resp = client.post("/api/v1/product-categories", json=body, headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    _created.append(data["id"])
    return data


_CODE_RE = re.compile(r"^PROD-([A-Z]{2})(\d{2})$")


def _suffix_index(code: str) -> int:
    m = _CODE_RE.match(code)
    assert m, f"unexpected category code shape: {code}"
    letters, number = m.groups()
    letter_index = (ord(letters[0]) - ord("A")) * 26 + (ord(letters[1]) - ord("A"))
    return letter_index * 99 + int(number)


def test_code_auto_generated_when_omitted(client, admin_access, _created):
    category = _create_category(client, admin_access, _created)
    assert _CODE_RE.match(category["code"]), category["code"]


def test_code_counter_increments_by_one(client, admin_access, _created):
    first = _create_category(client, admin_access, _created)
    second = _create_category(client, admin_access, _created)
    assert _suffix_index(second["code"]) == _suffix_index(first["code"]) + 1


def test_client_supplied_code_still_honoured(client, admin_access, _created):
    category = _create_category(client, admin_access, _created, code=f"CUSTOM-{uuid.uuid4().hex[:6].upper()}")
    assert category["code"].startswith("CUSTOM-")
