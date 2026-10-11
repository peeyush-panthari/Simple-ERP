"""New test coverage for the foundation/master-data domains (no direct
original-repo equivalent - see test_orders.py's docstring for the same
note): factories (incl. CSV bulk upload), auth policy, party types, sticker
sizes (layout-fits validation), product categories (tree + in-use delete
guard), business entities (default-flag handling) and party children
(addresses/contacts/bank accounts) - all against a real Postgres.
"""

from __future__ import annotations

import uuid

from app.core.db import SessionLocal


def _auth_headers(client, admin):
    login = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def _delete(model, **filters) -> None:
    model.query.filter_by(**filters).delete(synchronize_session=False)
    SessionLocal.commit()


def test_factory_create_duplicate_code_patch_and_bulk_upload(client, fresh_admin):
    from app.models.factory import Factory

    headers = _auth_headers(client, fresh_admin)
    code = f"TF-{uuid.uuid4().hex[:6].upper()}"
    create = client.post("/api/v1/factories", headers=headers, json={"code": code.lower(), "name": "Test Factory One"})
    assert create.status_code == 201, create.text
    assert create.json()["code"] == code  # normalised to upper-case
    factory_id = create.json()["id"]

    dupe = client.post("/api/v1/factories", headers=headers, json={"code": code, "name": "Another"})
    assert dupe.status_code == 409
    assert dupe.json()["code"] == "FACTORY_CODE_TAKEN"

    patch = client.patch(f"/api/v1/factories/{factory_id}", headers=headers, json={"city": "Pune", "status": "inactive"})
    assert patch.status_code == 200
    assert patch.json()["city"] == "Pune" and patch.json()["status"] == "inactive"

    bulk_code = f"TB-{uuid.uuid4().hex[:6].upper()}"
    csv_content = f"name,code\nBulk Factory,{bulk_code}\nBad Row,x\n"
    bulk = client.post("/api/v1/factories/bulk-upload", headers=headers, json={"csvContent": csv_content})
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["summary"] == {"totalRows": 2, "successCount": 1, "errorCount": 1}

    listed = client.get("/api/v1/factories", headers=headers, params={"q": "TF-"})
    assert listed.status_code == 200
    assert any(f["id"] == factory_id and f["warehouseCount"] == 0 for f in listed.json()["data"])

    _delete(Factory, code=bulk_code)
    _delete(Factory, id=uuid.UUID(factory_id))


def test_auth_policy_read_and_patch_roundtrip(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    before = client.get("/api/v1/auth-policy", headers=headers).json()
    original = before["sessionIdleMinutes"]

    patched = client.patch("/api/v1/auth-policy", headers=headers, json={"sessionIdleMinutes": 45})
    assert patched.status_code == 200, patched.text
    assert patched.json()["sessionIdleMinutes"] == 45

    client.patch("/api/v1/auth-policy", headers=headers, json={"sessionIdleMinutes": original})

    bad = client.patch("/api/v1/auth-policy", headers=headers, json={"passwordMinLength": 2})
    assert bad.status_code == 400 and bad.json()["code"] == "VALIDATION_FAILED"

    tenant = client.get("/api/v1/tenants/current", headers=headers)
    assert tenant.status_code == 200 and tenant.json()["baseCurrency"]

    roles = client.get("/api/v1/system-roles", headers=headers)
    assert roles.status_code == 200
    assert any(r["name"] == "System Admin" for r in roles.json()["data"])


def test_party_types_create_duplicate_and_patch(client, fresh_admin, default_tenant_id):
    from app.models.party_type import PartyType

    headers = _auth_headers(client, fresh_admin)
    label = f"Test Type {uuid.uuid4().hex[:6]}"
    create = client.post("/api/v1/party-types", headers=headers, json={"label": label, "baseType": "vendor"})
    assert create.status_code == 201, create.text
    code = create.json()["code"]

    dupe = client.post("/api/v1/party-types", headers=headers, json={"label": label, "baseType": "vendor"})
    assert dupe.status_code == 409 and dupe.json()["code"] == "PARTY_TYPE_TAKEN"

    patch = client.patch(f"/api/v1/party-types/{code}", headers=headers, json={"status": "inactive"})
    assert patch.status_code == 200 and patch.json()["status"] == "inactive"

    active_only = client.get("/api/v1/party-types", headers=headers, params={"status": "active"}).json()["data"]
    assert code not in {t["code"] for t in active_only}

    _delete(PartyType, tenant_id=default_tenant_id, code=code)


def test_sticker_size_layout_validation_and_crud(client, fresh_admin):
    from app.models.sticker_size import StickerSize

    headers = _auth_headers(client, fresh_admin)
    name = f"Test Sticker {uuid.uuid4().hex[:6]}"
    body = {
        "name": name, "pageSize": "A4", "stickerWidthMm": 50, "stickerHeightMm": 25, "columns": 3, "rows": 10,
        "marginLeftMm": 5, "marginRightMm": 5, "marginTopMm": 5, "marginBottomMm": 5, "gapHorizontalMm": 2, "gapVerticalMm": 2,
    }
    create = client.post("/api/v1/sticker-sizes", headers=headers, json=body)
    assert create.status_code == 201, create.text
    created = create.json()
    assert created["pageWidthMm"] == "210.00" and created["totalStickersPerPage"] == 30

    too_wide = client.post("/api/v1/sticker-sizes", headers=headers, json={**body, "name": name + " wide", "columns": 5})
    assert too_wide.status_code == 422 and too_wide.json()["code"] == "STICKER_LAYOUT_INVALID"

    dupe = client.post("/api/v1/sticker-sizes", headers=headers, json=body)
    assert dupe.status_code == 409 and dupe.json()["code"] == "STICKER_SIZE_NAME_TAKEN"

    patch = client.patch(f"/api/v1/sticker-sizes/{created['id']}", headers=headers, json={"columns": 2})
    assert patch.status_code == 200 and patch.json()["totalStickersPerPage"] == 20

    delete = client.delete(f"/api/v1/sticker-sizes/{created['id']}", headers=headers)
    assert delete.status_code == 204
    _delete(StickerSize, name=name)


def test_product_category_tree_reparent_cycle_and_in_use_delete(client, fresh_admin):
    from app.models.product import Product
    from app.models.product_category import ProductCategory

    headers = _auth_headers(client, fresh_admin)
    suffix = uuid.uuid4().hex[:6]
    parent = client.post("/api/v1/product-categories", headers=headers, json={"productCategory": f"Parent {suffix}", "productTypes": ["raw_material"]}).json()
    child = client.post("/api/v1/product-categories", headers=headers, json={"productCategory": f"Child {suffix}", "parentId": parent["id"]}).json()
    assert child["parentId"] == parent["id"]

    tree = client.get("/api/v1/product-categories/tree", headers=headers).json()["data"]
    parent_node = next(n for n in tree if n["id"] == parent["id"])
    assert [c["id"] for c in parent_node["children"]] == [child["id"]]

    cycle = client.patch(f"/api/v1/product-categories/{parent['id']}", headers=headers, json={"parentId": child["id"]})
    assert cycle.status_code == 422, cycle.text

    in_use = client.delete(f"/api/v1/product-categories/{parent['id']}", headers=headers)
    assert in_use.status_code == 409 and in_use.json()["code"] == "CATEGORY_IN_USE"

    assert client.delete(f"/api/v1/product-categories/{child['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/product-categories/{parent['id']}", headers=headers).status_code == 204
    assert ProductCategory.query.filter_by(id=uuid.UUID(parent["id"])).first() is None
    assert Product.query.filter_by(category_id=uuid.UUID(parent["id"])).count() == 0


def test_business_entity_default_flag_moves_between_entities(client, fresh_admin, default_tenant_id):
    from app.models.business_entity import BusinessEntity

    headers = _auth_headers(client, fresh_admin)
    suffix = uuid.uuid4().hex[:6].upper()
    first = client.post("/api/v1/business-entities", headers=headers, json={"code": f"BE1-{suffix}", "name": "Entity One", "stateCode": "27"}).json()
    second = client.post("/api/v1/business-entities", headers=headers, json={"code": f"BE2-{suffix}", "name": "Entity Two", "isDefault": True}).json()
    assert second["isDefault"] is True

    listed = {e["id"]: e for e in client.get("/api/v1/business-entities", headers=headers, params={"limit": 200}).json()["data"]}
    assert listed[first["id"]]["isDefault"] is False

    dupe = client.post("/api/v1/business-entities", headers=headers, json={"code": f"be1-{suffix}", "name": "Dup"})
    assert dupe.status_code == 409 and dupe.json()["code"] == "BUSINESS_ENTITY_CODE_TAKEN"

    bad_pan = client.patch(f"/api/v1/business-entities/{first['id']}", headers=headers, json={"pan": "nope"})
    assert bad_pan.status_code == 400

    swap = client.patch(f"/api/v1/business-entities/{first['id']}", headers=headers, json={"isDefault": True})
    assert swap.status_code == 200 and swap.json()["isDefault"] is True

    for e in (first, second):
        _delete(BusinessEntity, id=uuid.UUID(e["id"]))


def test_party_children_address_contact_bank_account(client, fresh_admin):
    from app.models.party import Party
    from app.models.party_address import PartyAddress
    from app.models.party_bank_account import PartyBankAccount
    from app.models.party_contact import PartyContact
    from app.models.party_version import PartyVersion

    headers = _auth_headers(client, fresh_admin)
    party = client.post("/api/v1/parties", headers=headers, json={"legalName": f"Children Test Co {uuid.uuid4().hex[:8]}", "type": "vendor"}).json()
    pid = party["id"]

    addr = client.post(f"/api/v1/parties/{pid}/addresses", headers=headers, json={"type": "billing", "line1": "1 Test Road", "city": "Pune", "isDefault": True})
    assert addr.status_code == 201, addr.text
    addr2 = client.post(f"/api/v1/parties/{pid}/addresses", headers=headers, json={"type": "billing", "line1": "2 Test Road", "city": "Pune", "isDefault": True})
    assert addr2.status_code == 201
    addresses = client.get(f"/api/v1/parties/{pid}", headers=headers).json()["addresses"]
    assert [a["isDefault"] for a in sorted(addresses, key=lambda a: a["line1"])] == [False, True]

    contact = client.post(f"/api/v1/parties/{pid}/contacts", headers=headers, json={"name": "Test Person", "email": "person@example.test", "isPrimary": True})
    assert contact.status_code == 201, contact.text

    bank = client.post(
        f"/api/v1/parties/{pid}/bank-accounts",
        headers=headers,
        json={"accountName": "Test Co", "accountNumber": "1234567890", "ifsc": "hdfc0001234", "bankName": "HDFC"},
    )
    assert bank.status_code == 201, bank.text
    assert bank.json()["status"] == "approved"
    assert bank.json()["ifsc"] == "HDFC0001234"
    assert bank.json()["accountNumberMasked"] == "****7890"

    approve = client.post(f"/api/v1/parties/{pid}/bank-accounts/{bank.json()['id']}/approve", headers=headers, json={})
    assert approve.status_code == 409 and approve.json()["code"] == "BANK_ACCOUNT_ALREADY_APPROVED"

    no_route = client.post(f"/api/v1/parties/{pid}/bank-accounts", headers=headers, json={"accountName": "X Co", "accountNumber": "999999", "bankName": "Some Bank"})
    assert no_route.status_code == 400

    assert client.delete(f"/api/v1/parties/{pid}/contacts/{contact.json()['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/parties/{pid}/addresses/{addr.json()['id']}", headers=headers).status_code == 204

    party_uuid = uuid.UUID(pid)
    for model in (PartyBankAccount, PartyAddress, PartyContact, PartyVersion):
        model.query.filter_by(party_id=party_uuid).delete(synchronize_session=False)
    Party.query.filter_by(id=party_uuid).delete(synchronize_session=False)
    SessionLocal.commit()
