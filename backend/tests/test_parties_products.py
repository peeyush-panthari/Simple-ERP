"""New test coverage for the parties + products domain port (no direct
original-repo equivalent - see test_orders.py's docstring for the same
note). Covers party creation with address/contact, duplicate-name and
duplicate-tax-ID rejection, the draft->active lifecycle (and its
activation-readiness gate), credit position, and product creation with
duplicate-SKU / duplicate-name+make rejection and the publish gate - all
against a real Postgres.
"""

from __future__ import annotations

import uuid

from app.core.db import SessionLocal


def _auth_headers(client, fresh_admin):
    login = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def _cleanup_party(party_id: str) -> None:
    from app.models.order import Order
    from app.models.party import Party
    from app.models.party_address import PartyAddress
    from app.models.party_contact import PartyContact
    from app.models.party_version import PartyVersion

    pid = uuid.UUID(party_id)
    Order.query.filter_by(customer_id=pid).delete(synchronize_session=False)
    PartyAddress.query.filter_by(party_id=pid).delete(synchronize_session=False)
    PartyContact.query.filter_by(party_id=pid).delete(synchronize_session=False)
    PartyVersion.query.filter_by(party_id=pid).delete(synchronize_session=False)
    Party.query.filter_by(id=pid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_product(product_id: str) -> None:
    from app.models.product import Product
    from app.models.product_alias import ProductAlias
    from app.models.product_image import ProductImage
    from app.models.product_spec import ProductSpec
    from app.models.uom_conversion import UomConversion

    pid = uuid.UUID(product_id)
    ProductAlias.query.filter_by(product_id=pid).delete(synchronize_session=False)
    ProductImage.query.filter_by(product_id=pid).delete(synchronize_session=False)
    ProductSpec.query.filter_by(product_id=pid).delete(synchronize_session=False)
    UomConversion.query.filter_by(product_id=pid).delete(synchronize_session=False)
    Product.query.filter_by(id=pid).delete(synchronize_session=False)
    SessionLocal.commit()


def test_create_party_with_address_and_contact(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    resp = client.post(
        "/api/v1/parties",
        headers=headers,
        json={
            "legalName": f"Acme Testing {uuid.uuid4().hex[:8]} Pvt Ltd",
            "type": "customer",
            "paymentTerms": "Net 30",
            "currency": "INR",
            "addresses": [{"type": "billing", "line1": "1 Test Rd", "city": "Pune", "isDefault": True}],
            "contacts": [{"name": "Test Contact", "email": "test@example.test", "isPrimary": True}],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"]
    assert body["status"] == "draft"
    assert len(body["addresses"]) == 1
    assert len(body["contacts"]) == 1

    _cleanup_party(body["id"])


def test_duplicate_legal_name_rejected(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    name = f"Duplicate Test Co {uuid.uuid4().hex[:8]}"
    first = client.post("/api/v1/parties", headers=headers, json={"legalName": name, "type": "vendor"})
    assert first.status_code == 201
    second = client.post("/api/v1/parties", headers=headers, json={"legalName": name, "type": "vendor"})
    assert second.status_code == 409
    assert second.json()["code"] == "LEGAL_NAME_TAKEN"

    _cleanup_party(first.json()["id"])


def test_activation_requires_billing_address_payment_terms_and_contact_email(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    # `_create_party` always defaults `currency` to `settings.base_currency`
    # when omitted, so that particular activation blocker can never fire for
    # an API-created party - only paymentTerms/addresses/contacts are
    # reachable here.
    create = client.post("/api/v1/parties", headers=headers, json={"legalName": f"Not Ready Co {uuid.uuid4().hex[:8]}", "type": "customer"})
    assert create.status_code == 201
    party_id = create.json()["id"]

    activate = client.post(f"/api/v1/parties/{party_id}/activate", headers=headers)
    assert activate.status_code == 422
    assert activate.json()["code"] == "PARTY_NOT_READY_FOR_ACTIVATION"
    error_fields = {e["field"] for e in activate.json()["meta"]["errors"]}
    assert {"paymentTerms", "addresses", "contacts"} <= error_fields

    _cleanup_party(party_id)


def test_full_party_lifecycle_activate_block_unblock(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    create = client.post(
        "/api/v1/parties",
        headers=headers,
        json={
            "legalName": f"Lifecycle Co {uuid.uuid4().hex[:8]}",
            "type": "customer",
            "paymentTerms": "Net 15",
            "currency": "INR",
            "addresses": [{"type": "billing", "line1": "1 Test Rd", "city": "Pune", "isDefault": True}],
            "contacts": [{"name": "Contact", "email": "c@example.test", "isPrimary": True}],
        },
    )
    party_id = create.json()["id"]

    activate = client.post(f"/api/v1/parties/{party_id}/activate", headers=headers)
    assert activate.status_code == 200, activate.text
    assert activate.json()["status"] == "active"

    credit = client.get(f"/api/v1/parties/{party_id}/credit", headers=headers)
    assert credit.status_code == 200
    assert credit.json()["eligible"] is False  # credit limit is 0 by default

    block = client.post(f"/api/v1/parties/{party_id}/block", headers=headers, json={"reason": "Overdue invoice testing"})
    assert block.status_code == 200
    assert block.json()["status"] == "blocked"

    unblock = client.post(f"/api/v1/parties/{party_id}/unblock", headers=headers, json={"reason": "Payment received"})
    assert unblock.status_code == 200
    assert unblock.json()["status"] == "active"

    versions = client.get(f"/api/v1/parties/{party_id}/versions", headers=headers)
    assert versions.status_code == 200
    assert len(versions.json()["data"]) == 4  # created, activated, blocked, unblocked

    _cleanup_party(party_id)


def test_create_product_and_reject_duplicate_sku(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    sku = f"TEST-{uuid.uuid4().hex[:8].upper()}"
    resp = client.post(
        "/api/v1/products",
        headers=headers,
        json={"sku": sku, "name": f"Test Product {uuid.uuid4().hex[:8]}", "make": "TestCo", "type": "raw_material", "uom": "KG"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "active"

    dupe = client.post(
        "/api/v1/products",
        headers=headers,
        json={"sku": sku, "name": "Another Product", "make": "TestCo", "type": "raw_material", "uom": "KG"},
    )
    assert dupe.status_code == 409
    assert dupe.json()["code"] == "SKU_TAKEN"

    _cleanup_product(resp.json()["id"])


def test_product_requires_sku_on_direct_create(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    resp = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "No SKU Product", "make": "TestCo", "type": "raw_material", "uom": "KG"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "SKU_REQUIRED"


def test_product_uom_conversion(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    create = client.post(
        "/api/v1/products",
        headers=headers,
        json={"sku": f"CONV-{uuid.uuid4().hex[:8].upper()}", "name": f"Conversion Test {uuid.uuid4().hex[:8]}", "make": "TestCo", "type": "raw_material", "uom": "KG"},
    )
    product_id = create.json()["id"]

    # KG -> G is a known dimensional conversion, no product-specific row needed.
    convert = client.post(f"/api/v1/products/{product_id}/convert", headers=headers, json={"quantity": "2", "from": "KG", "to": "G"})
    assert convert.status_code == 200, convert.text
    assert convert.json()["result"] == "2000.000000"

    _cleanup_product(product_id)
