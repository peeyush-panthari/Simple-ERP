"""New test coverage for the BOM (bill of material) domain port (no direct
original-repo equivalent - see test_orders.py's docstring for the same
note). Covers BOM creation (auto-approved first version), the
duplicate/parent-eligibility guards, add-version retiring the predecessor,
the revise->patch->submit->approve lifecycle (cost rollup + effectivity
retirement), reject, and the cost-rollup/explode read endpoints - all
against a real Postgres.
"""

from __future__ import annotations

import uuid

from app.core.db import SessionLocal


def _auth_headers(client, admin):
    login = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def _second_admin(default_tenant_id):
    """BOM approval blocks self-approval, so tests that approve need an
    approver distinct from whoever created/revised the version - the same
    shortcut `fresh_admin` itself takes to create its one admin."""
    from app.core.security import hash_password
    from app.models.role import Role
    from app.models.user import User
    from app.models.user_role import UserRole

    email = f"test-approver-{uuid.uuid4().hex[:8]}@example.test"
    password = "TestApprover#Passw0rd"
    role = Role.query.filter_by(tenant_id=default_tenant_id, name="System Admin").first()
    user = User(tenant_id=default_tenant_id, email=email, display_name="Test Approver", status="active", password_hash=hash_password(password))
    SessionLocal.add(user)
    SessionLocal.flush()
    SessionLocal.add(UserRole(user_id=user.id, role_id=role.id))
    SessionLocal.commit()
    return {"email": email, "password": password, "id": str(user.id)}


def _cleanup_admin(user_id: str) -> None:
    from app.models.password_history import PasswordHistory
    from app.models.session import Session
    from app.models.user import User
    from app.models.user_role import UserRole

    uid = uuid.UUID(user_id)
    for model in (Session, PasswordHistory, UserRole):
        model.query.filter_by(user_id=uid).delete(synchronize_session=False)
    User.query.filter_by(id=uid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_bom(bom_id: str) -> None:
    from app.models.bom import Bom
    from app.models.bom_approval import BomApproval
    from app.models.bom_component import BomComponent
    from app.models.bom_version import BomVersion

    bid = uuid.UUID(bom_id)
    version_ids = [v.id for v in BomVersion.query.filter_by(bom_id=bid).all()]
    if version_ids:
        BomComponent.query.filter(BomComponent.bom_version_id.in_(version_ids)).delete(synchronize_session=False)
        BomApproval.query.filter(BomApproval.version_id.in_(version_ids)).delete(synchronize_session=False)
    BomVersion.query.filter_by(bom_id=bid).delete(synchronize_session=False)
    Bom.query.filter_by(id=bid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_product(product_id: str) -> None:
    from app.models.product import Product

    Product.query.filter_by(id=uuid.UUID(product_id)).delete(synchronize_session=False)
    SessionLocal.commit()


def _make_products(client, headers):
    """One finished good + two raw-material components, via the real API."""
    suffix = uuid.uuid4().hex[:8]
    fg = client.post(
        "/api/v1/products",
        headers=headers,
        json={"sku": f"BOM-FG-{suffix}", "name": f"BOM Test Assembly {suffix}", "make": "TestCo", "type": "finished_good", "uom": "UNIT"},
    ).json()
    rm1 = client.post(
        "/api/v1/products",
        headers=headers,
        json={"sku": f"BOM-RM1-{suffix}", "name": f"BOM Test Material One {suffix}", "make": "TestCo", "type": "raw_material", "uom": "KG"},
    ).json()
    rm2 = client.post(
        "/api/v1/products",
        headers=headers,
        json={"sku": f"BOM-RM2-{suffix}", "name": f"BOM Test Material Two {suffix}", "make": "TestCo", "type": "consumable", "uom": "UNIT"},
    ).json()
    return fg, rm1, rm2


def _create_bom(client, headers, fg, rm1, rm2, **overrides):
    body = {
        "productId": fg["id"],
        "effectiveFrom": "2026-01-01",
        "components": [
            {"componentProductId": rm1["id"], "quantity": "2", "uom": "KG", "scrapPercent": "5"},
            {"componentProductId": rm2["id"], "quantity": "1", "uom": "UNIT"},
        ],
    }
    body.update(overrides)
    return client.post("/api/v1/boms", headers=headers, json=body)


def test_create_bom_auto_approves_first_version(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    fg, rm1, rm2 = _make_products(client, headers)

    resp = _create_bom(client, headers, fg, rm1, rm2)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["productId"] == fg["id"]
    assert body["version"]["version"] == 1
    assert body["version"]["state"] == "approved"

    get_resp = client.get(f"/api/v1/boms/{body['id']}", headers=headers)
    assert get_resp.status_code == 200
    got = get_resp.json()
    assert got["activeVersionId"] == body["version"]["id"]
    assert len(got["versions"][0]["components"]) == 2

    _cleanup_bom(body["id"])
    for p in (fg, rm1, rm2):
        _cleanup_product(p["id"])


def test_create_bom_rejects_duplicate_and_non_finished_good_parent(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    fg, rm1, rm2 = _make_products(client, headers)

    first = _create_bom(client, headers, fg, rm1, rm2)
    assert first.status_code == 201

    dupe = _create_bom(client, headers, fg, rm1, rm2)
    assert dupe.status_code == 409
    assert dupe.json()["code"] == "BOM_EXISTS"

    wrong_parent = _create_bom(client, headers, rm1, rm2, fg)
    assert wrong_parent.status_code == 422
    assert wrong_parent.json()["code"] == "BOM_PARENT_NOT_FINISHED_GOOD"

    _cleanup_bom(first.json()["id"])
    for p in (fg, rm1, rm2):
        _cleanup_product(p["id"])


def test_add_version_retires_predecessor(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    fg, rm1, rm2 = _make_products(client, headers)
    bom_id = _create_bom(client, headers, fg, rm1, rm2).json()["id"]

    add = client.post(
        f"/api/v1/boms/{bom_id}/versions",
        headers=headers,
        json={"effectiveFrom": "2026-02-01", "components": [{"componentProductId": rm1["id"], "quantity": "3", "uom": "KG"}]},
    )
    assert add.status_code == 201, add.text
    v2 = add.json()
    assert v2["version"] == 2
    assert v2["state"] == "approved"

    versions = client.get(f"/api/v1/boms/{bom_id}/versions", headers=headers).json()["data"]
    by_version = {v["version"]: v for v in versions}
    assert by_version[1]["state"] == "retired"
    assert by_version[2]["state"] == "approved"

    _cleanup_bom(bom_id)
    for p in (fg, rm1, rm2):
        _cleanup_product(p["id"])


def test_revise_patch_submit_approve_computes_cost_rollup(client, fresh_admin, default_tenant_id):
    headers = _auth_headers(client, fresh_admin)
    fg, rm1, rm2 = _make_products(client, headers)
    bom_id = _create_bom(client, headers, fg, rm1, rm2).json()["id"]
    v1_id = client.get(f"/api/v1/boms/{bom_id}", headers=headers).json()["versions"][0]["id"]

    revise = client.post(f"/api/v1/boms/{bom_id}/versions/{v1_id}/revise", headers=headers, json={"effectiveFrom": "2026-03-01", "notes": "Revised for cost test"})
    assert revise.status_code == 201, revise.text
    draft = revise.json()
    assert draft["state"] == "draft"
    assert draft["version"] == 2

    patch = client.patch(f"/api/v1/boms/{bom_id}/versions/{draft['id']}", headers=headers, json={"yieldPercent": "95"})
    assert patch.status_code == 200, patch.text
    assert patch.json()["yieldPercent"] == "95.000000"

    submit = client.post(f"/api/v1/boms/{bom_id}/versions/{draft['id']}/submit", headers=headers)
    assert submit.status_code == 200, submit.text
    assert submit.json()["state"] == "pending_approval"

    approver = _second_admin(default_tenant_id)
    approver_headers = _auth_headers(client, approver)
    approve = client.post(f"/api/v1/boms/{bom_id}/versions/{draft['id']}/approve", headers=approver_headers, json={"reason": "Looks correct"})
    assert approve.status_code == 200, approve.text
    approved = approve.json()
    assert approved["state"] == "approved"
    # Leaf raw-material/consumable lines have no nested BOM to price from, so
    # the rollup is faithfully "0 cost, both skus unpriced" (see bom_cost.py).
    assert approved["costRollup"]["unitCost"] == "0.000000"
    assert set(approved["costRollup"]["unpricedSkus"]) == {rm1["sku"], rm2["sku"]}
    # v1 has no effectiveTo, so it overlaps rather than being fully
    # superseded - approve_version truncates it to end the day before v2
    # starts instead of retiring it outright (see bom_effectivity.py).
    assert approved["retiredVersions"] == []
    assert approved["truncatedVersions"] == [{"version": 1, "effectiveTo": "2026-02-28"}]

    _cleanup_admin(approver["id"])
    _cleanup_bom(bom_id)
    for p in (fg, rm1, rm2):
        _cleanup_product(p["id"])


def test_reject_version(client, fresh_admin, default_tenant_id):
    headers = _auth_headers(client, fresh_admin)
    fg, rm1, rm2 = _make_products(client, headers)
    bom_id = _create_bom(client, headers, fg, rm1, rm2).json()["id"]
    v1_id = client.get(f"/api/v1/boms/{bom_id}", headers=headers).json()["versions"][0]["id"]

    draft = client.post(f"/api/v1/boms/{bom_id}/versions/{v1_id}/revise", headers=headers, json={"effectiveFrom": "2026-04-01"}).json()
    client.post(f"/api/v1/boms/{bom_id}/versions/{draft['id']}/submit", headers=headers)

    approver = _second_admin(default_tenant_id)
    approver_headers = _auth_headers(client, approver)
    reject = client.post(f"/api/v1/boms/{bom_id}/versions/{draft['id']}/reject", headers=approver_headers, json={"reason": "Component pricing not final yet"})
    assert reject.status_code == 200, reject.text
    assert reject.json()["state"] == "rejected"
    assert reject.json()["rejectedReason"] == "Component pricing not final yet"

    _cleanup_admin(approver["id"])
    _cleanup_bom(bom_id)
    for p in (fg, rm1, rm2):
        _cleanup_product(p["id"])


def test_cost_rollup_and_explode_endpoints(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    fg, rm1, rm2 = _make_products(client, headers)
    bom_id = _create_bom(client, headers, fg, rm1, rm2).json()["id"]

    rollup = client.get(f"/api/v1/boms/{bom_id}/cost-rollup", headers=headers)
    assert rollup.status_code == 200, rollup.text
    assert rollup.json()["unitCost"] == "0.000000"
    assert len(rollup.json()["lines"]) == 2

    explode = client.get(f"/api/v1/boms/{bom_id}/explode", headers=headers, params={"quantity": "10"})
    assert explode.status_code == 200, explode.text
    body = explode.json()
    assert body["productId"] == fg["id"]
    requirements_by_sku = {r["sku"]: r for r in body["requirements"]}
    # 2 KG/unit * 10 units * 1.05 scrap factor = 21 KG.
    assert requirements_by_sku[rm1["sku"]]["quantity"] == "21.000000"
    assert requirements_by_sku[rm2["sku"]]["quantity"] == "10.000000"

    _cleanup_bom(bom_id)
    for p in (fg, rm1, rm2):
        _cleanup_product(p["id"])
