"""New coverage for the two new Foundation modules: Factory & Warehouse
(factories + Warehouse.factory_id mapping) and PO & Invoice (business
entities - Simple's own legal entities used as the seller identity on a
PO/invoice)."""

import uuid

import pytest


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


@pytest.fixture
def _created(app):
    """Cleans up factories/business_entities/warehouses this module creates -
    no DELETE routes for any of them (status flips to inactive in real use),
    so cleanup goes straight through the ORM."""
    ids: dict[str, list[str]] = {"factories": [], "business_entities": [], "warehouses": []}
    yield ids
    from tests.flaskcompat import db as _db
    from app.models.business_entity import BusinessEntity
    from app.models.factory import Factory
    from app.models.location import Location
    from app.models.warehouse import Warehouse

    with app.app_context():
        if ids["warehouses"]:
            warehouse_ids = [uuid.UUID(i) for i in ids["warehouses"]]
            Location.query.filter(Location.warehouse_id.in_(warehouse_ids)).delete(synchronize_session=False)
            Warehouse.query.filter(Warehouse.id.in_(warehouse_ids)).delete(synchronize_session=False)
        if ids["factories"]:
            Factory.query.filter(Factory.id.in_([uuid.UUID(i) for i in ids["factories"]])).delete(synchronize_session=False)
        if ids["business_entities"]:
            BusinessEntity.query.filter(BusinessEntity.id.in_([uuid.UUID(i) for i in ids["business_entities"]])).delete(synchronize_session=False)
        _db.session.commit()


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_factory_created_with_auto_code_and_listed(client, admin_access, _created):
    resp = client.post("/api/v1/factories", json={"name": f"Test Factory {uuid.uuid4().hex[:6]}", "city": "Pune", "stateCode": "MH"}, headers=_headers(admin_access))
    assert resp.status_code == 201, resp.get_json()
    factory = resp.get_json()
    _created["factories"].append(factory["id"])
    assert factory["code"].startswith("FAC-")
    assert factory["status"] == "active"

    listed = client.get("/api/v1/factories", query_string={"q": factory["code"]}, headers=_headers(admin_access))
    assert listed.status_code == 200
    assert any(f["id"] == factory["id"] for f in listed.get_json()["data"])


def test_warehouse_can_be_mapped_to_a_factory(client, admin_access, _created):
    factory_resp = client.post("/api/v1/factories", json={"name": f"Mapped Factory {uuid.uuid4().hex[:6]}"}, headers=_headers(admin_access))
    assert factory_resp.status_code == 201
    factory_id = factory_resp.get_json()["id"]
    _created["factories"].append(factory_id)

    warehouse_resp = client.post(
        "/api/v1/warehouses",
        json={"code": f"WH-{uuid.uuid4().hex[:6].upper()}", "name": "Warehouse inside factory", "factoryId": factory_id},
        headers=_headers(admin_access),
    )
    assert warehouse_resp.status_code == 201, warehouse_resp.get_json()
    warehouse = warehouse_resp.get_json()
    _created["warehouses"].append(warehouse["id"])
    assert warehouse["factoryId"] == factory_id
    assert warehouse["factoryName"] is not None


def test_warehouse_code_auto_generated_when_omitted(client, admin_access, _created):
    first = client.post("/api/v1/warehouses", json={"name": f"Auto-coded warehouse {uuid.uuid4().hex[:6]}"}, headers=_headers(admin_access))
    assert first.status_code == 201, first.get_json()
    _created["warehouses"].append(first.get_json()["id"])
    assert first.get_json()["code"].startswith("WH-")

    second = client.post("/api/v1/warehouses", json={"name": f"Auto-coded warehouse {uuid.uuid4().hex[:6]}"}, headers=_headers(admin_access))
    assert second.status_code == 201, second.get_json()
    _created["warehouses"].append(second.get_json()["id"])
    assert second.get_json()["code"] != first.get_json()["code"]


def test_warehouse_client_supplied_code_still_honoured(client, admin_access, _created):
    code = f"WH-{uuid.uuid4().hex[:6].upper()}"
    resp = client.post("/api/v1/warehouses", json={"code": code, "name": "Explicit code warehouse"}, headers=_headers(admin_access))
    assert resp.status_code == 201, resp.get_json()
    _created["warehouses"].append(resp.get_json()["id"])
    assert resp.get_json()["code"] == code


def test_warehouse_rejects_unknown_factory(client, admin_access, _created):
    resp = client.post(
        "/api/v1/warehouses",
        json={"code": f"WH-{uuid.uuid4().hex[:6].upper()}", "name": "Bad mapping", "factoryId": str(uuid.uuid4())},
        headers=_headers(admin_access),
    )
    assert resp.status_code == 404


def test_business_entity_created_with_auto_code(client, admin_access, _created):
    resp = client.post(
        "/api/v1/business-entities",
        json={"name": f"Test Vertical {uuid.uuid4().hex[:6]}", "addressLine1": "Plot 1", "city": "Pune", "stateCode": "MH", "postalCode": "411057", "taxId": "27AAPFU0939F1ZV", "pan": "aapfu0939f"},
        headers=_headers(admin_access),
    )
    assert resp.status_code == 201, resp.get_json()
    entity = resp.get_json()
    _created["business_entities"].append(entity["id"])
    assert entity["code"].startswith("ENT-")
    assert entity["taxId"] == "27AAPFU0939F1ZV"
    assert entity["pan"] == "AAPFU0939F"


def test_business_entity_rejects_malformed_pan(client, admin_access, _created):
    resp = client.post(
        "/api/v1/business-entities",
        json={"name": f"Bad PAN Vertical {uuid.uuid4().hex[:6]}", "pan": "NOTAPAN"},
        headers=_headers(admin_access),
    )
    assert resp.status_code == 400, resp.get_json()


def test_setting_default_unsets_the_previous_default(client, admin_access, _created):
    """Doesn't assume a pristine tenant (the shared dev DB may already hold a
    real default entity) - only asserts the mutual-exclusivity behavior."""
    first = client.post("/api/v1/business-entities", json={"name": f"First Vertical {uuid.uuid4().hex[:6]}", "isDefault": True}, headers=_headers(admin_access))
    assert first.status_code == 201
    first_id = first.get_json()["id"]
    _created["business_entities"].append(first_id)
    assert first.get_json()["isDefault"] is True

    second = client.post("/api/v1/business-entities", json={"name": f"Second Vertical {uuid.uuid4().hex[:6]}", "isDefault": True}, headers=_headers(admin_access))
    assert second.status_code == 201
    second_id = second.get_json()["id"]
    _created["business_entities"].append(second_id)
    assert second.get_json()["isDefault"] is True

    refreshed_first = client.get("/api/v1/business-entities", headers=_headers(admin_access)).get_json()["data"]
    first_row = next(e for e in refreshed_first if e["id"] == first_id)
    assert first_row["isDefault"] is False


def test_business_entity_created_with_bank_details(client, admin_access, _created):
    resp = client.post(
        "/api/v1/business-entities",
        json={
            "name": f"Bank Details Vertical {uuid.uuid4().hex[:6]}",
            "bankName": "HDFC Bank",
            "bankBranch": "MG Road",
            "bankAccountNumber": "000123456789",
            "bankIfsc": "hdfc0001234",
        },
        headers=_headers(admin_access),
    )
    assert resp.status_code == 201, resp.get_json()
    entity = resp.get_json()
    _created["business_entities"].append(entity["id"])
    assert entity["bankName"] == "HDFC Bank"
    assert entity["bankBranch"] == "MG Road"
    assert entity["bankAccountNumber"] == "000123456789"
    assert entity["bankIfsc"] == "HDFC0001234"  # uppercased


def test_business_entity_rejects_malformed_ifsc(client, admin_access, _created):
    resp = client.post(
        "/api/v1/business-entities",
        json={"name": f"Bad IFSC Vertical {uuid.uuid4().hex[:6]}", "bankIfsc": "NOTIFSC"},
        headers=_headers(admin_access),
    )
    assert resp.status_code == 400, resp.get_json()


def test_business_entity_bank_details_can_be_added_via_patch(client, admin_access, _created):
    created = client.post("/api/v1/business-entities", json={"name": f"Patch Bank Vertical {uuid.uuid4().hex[:6]}"}, headers=_headers(admin_access))
    assert created.status_code == 201
    entity_id = created.get_json()["id"]
    _created["business_entities"].append(entity_id)
    assert created.get_json()["bankName"] is None

    patched = client.patch(
        f"/api/v1/business-entities/{entity_id}",
        json={"bankName": "ICICI Bank", "bankBranch": "Koramangala", "bankAccountNumber": "998877665544", "bankIfsc": "icic0009988"},
        headers=_headers(admin_access),
    )
    assert patched.status_code == 200, patched.get_json()
    updated = patched.get_json()
    assert updated["bankName"] == "ICICI Bank"
    assert updated["bankBranch"] == "Koramangala"
    assert updated["bankAccountNumber"] == "998877665544"
    assert updated["bankIfsc"] == "ICIC0009988"


def test_duplicate_business_entity_code_is_conflict(client, admin_access, _created):
    code = f"DUPE-{uuid.uuid4().hex[:6].upper()}"
    first = client.post("/api/v1/business-entities", json={"name": "Dupe test 1", "code": code}, headers=_headers(admin_access))
    assert first.status_code == 201
    _created["business_entities"].append(first.get_json()["id"])

    dupe = client.post("/api/v1/business-entities", json={"name": "Dupe test 2", "code": code}, headers=_headers(admin_access))
    assert dupe.status_code == 409
    assert dupe.get_json()["code"] == "BUSINESS_ENTITY_CODE_TAKEN"
