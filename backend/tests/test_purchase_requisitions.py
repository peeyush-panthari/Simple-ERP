"""Procurement > Purchase requisitions: an employee raises one, Purchase reviews it. Real Postgres, real roles.

Covers who can see what, the status rules, the self-review block, catalogue and free-text lines, validation that is
collected rather than first-error, the link to a purchase order, and the audit trail."""

from __future__ import annotations

import uuid

import pytest

from app.core.db import SessionLocal


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def world(client, fresh_admin, app):
    """An admin, an employee (pr:read/pr:write), a second employee, and a Purchase reviewer (pr:approve), plus a product and warehouse."""
    admin = _h(client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]}).json()["accessToken"])
    made = {"users": [], "roles": []}

    def role(perms):
        r = client.post("/api/v1/roles", headers=admin, json={"name": f"PR Test Role {uuid.uuid4().hex[:8]}", "permissions": perms})
        assert r.status_code == 201, r.text
        made["roles"].append(r.json()["id"])
        return r.json()

    def user(role_id, name, manager_id=None):
        email = f"pr-test-{uuid.uuid4().hex[:8]}@example.test"
        r = client.post("/api/v1/users", headers=admin, json={"email": email, "displayName": name, "password": "TestPr#Passw0rd1", "status": "active", "managerId": manager_id, "roles": [{"roleId": role_id, "warehouseIds": [], "factoryIds": []}]})
        assert r.status_code == 201, r.text
        made["users"].append(r.json()["id"])
        token = client.post("/api/v1/auth/login", json={"email": email, "password": "TestPr#Passw0rd1"}).json()["accessToken"]
        return {"id": r.json()["id"], "h": _h(token)}

    employee_role = role(["pr:read", "pr:write"])
    reviewer_role = role(["pr:read", "pr:approve", "po:read"])
    manager_role = role(["pr:read", "pr:write", "pr:team_approve"])
    manager = user(manager_role["id"], "Maya Manager")
    world = {
        "admin": admin,
        "manager": manager,
        "other_manager": user(manager_role["id"], "Omar OtherManager"),
        "report": user(employee_role["id"], "Ravi Report", manager["id"]),
        "alice": user(employee_role["id"], "Alice Employee"),
        "bob": user(employee_role["id"], "Bob Employee"),
        "purchase": user(reviewer_role["id"], "Priya Purchase"),
        "product": client.post("/api/v1/products", headers=admin, json={"sku": f"PR-{uuid.uuid4().hex[:8].upper()}", "name": f"PR Test Item {uuid.uuid4().hex[:6]}", "make": "TestCo", "type": "raw_material", "uom": "KG", "purchasable": True}).json(),
        "warehouse": client.post("/api/v1/warehouses", headers=admin, json={"name": f"PR Test WH {uuid.uuid4().hex[:6]}"}).json(),
    }
    yield world

    from app.models.password_history import PasswordHistory
    from app.models.product import Product
    from app.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionLine
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.session import Session
    from app.models.user import User
    from app.models.user_role import UserRole
    from app.models.location import Location
    from app.models.warehouse import Warehouse

    user_ids = [uuid.UUID(i) for i in made["users"]]
    role_ids = [uuid.UUID(i) for i in made["roles"]]
    req_ids = [r.id for r in PurchaseRequisition.query.filter(PurchaseRequisition.requester_id.in_(user_ids)).all()]
    PurchaseRequisitionLine.query.filter(PurchaseRequisitionLine.requisition_id.in_(req_ids)).delete(synchronize_session=False)
    PurchaseRequisition.query.filter(PurchaseRequisition.id.in_(req_ids)).delete(synchronize_session=False)
    UserRole.query.filter(UserRole.user_id.in_(user_ids) | UserRole.role_id.in_(role_ids)).delete(synchronize_session=False)
    Session.query.filter(Session.user_id.in_(user_ids)).delete(synchronize_session=False)
    PasswordHistory.query.filter(PasswordHistory.user_id.in_(user_ids)).delete(synchronize_session=False)
    User.query.filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    RolePermission.query.filter(RolePermission.role_id.in_(role_ids)).delete(synchronize_session=False)
    Role.query.filter(Role.id.in_(role_ids)).delete(synchronize_session=False)
    Product.query.filter_by(id=uuid.UUID(world["product"]["id"])).delete(synchronize_session=False)
    Location.query.filter_by(warehouse_id=uuid.UUID(world["warehouse"]["id"])).delete(synchronize_session=False)
    Warehouse.query.filter_by(id=uuid.UUID(world["warehouse"]["id"])).delete(synchronize_session=False)
    SessionLocal.commit()


def _raise(client, w, who="alice", *, submit=True, **over):
    body = {
        "priority": "normal",
        "department": "Maintenance",
        "warehouseId": w["warehouse"]["id"],
        "justification": "Line 2 conveyor bearings are worn out",
        "lines": [{"productId": w["product"]["id"], "quantity": "25"}],
        "submit": submit,
    }
    body.update(over)
    return client.post("/api/v1/purchase-requisitions", headers=w[who]["h"], json=body)


def test_employee_raises_and_it_goes_to_purchase(client, world):
    r = _raise(client, world)
    assert r.status_code == 201, r.text
    pr = r.json()
    assert pr["number"].startswith("PR-")
    assert pr["status"] == "submitted"
    assert pr["requesterName"] == "Alice Employee"
    assert pr["submittedAt"]
    assert pr["lines"][0]["uom"] == "KG"  # defaults to the product's own unit
    assert pr["lines"][0]["inCatalogue"] is True
    assert pr["lines"][0]["itemName"] == world["product"]["name"]
    assert pr["warehouseCode"] == world["warehouse"]["code"]


def test_draft_stays_private_until_submitted(client, world):
    pr = _raise(client, world, submit=False).json()
    assert pr["status"] == "draft"
    # Purchase does not see other people's drafts, and cannot even open one.
    assert client.get(f"/api/v1/purchase-requisitions/{pr['id']}", headers=world["purchase"]["h"]).status_code == 404
    listed = client.get("/api/v1/purchase-requisitions", headers=world["purchase"]["h"]).json()["data"]
    assert pr["id"] not in [x["id"] for x in listed]
    assert client.post(f"/api/v1/purchase-requisitions/{pr['id']}/submit", headers=world["purchase"]["h"]).status_code in (403, 404)

    sub = client.post(f"/api/v1/purchase-requisitions/{pr['id']}/submit", headers=world["alice"]["h"])
    assert sub.status_code == 200 and sub.json()["status"] == "submitted"
    assert pr["id"] in [x["id"] for x in client.get("/api/v1/purchase-requisitions", headers=world["purchase"]["h"]).json()["data"]]


def test_employees_only_see_their_own(client, world):
    mine = _raise(client, world, "alice").json()
    theirs = _raise(client, world, "bob").json()
    ids = [x["id"] for x in client.get("/api/v1/purchase-requisitions", headers=world["alice"]["h"]).json()["data"]]
    assert mine["id"] in ids and theirs["id"] not in ids
    assert client.get(f"/api/v1/purchase-requisitions/{theirs['id']}", headers=world["alice"]["h"]).status_code == 404
    # ...and cannot review anything.
    assert client.post(f"/api/v1/purchase-requisitions/{mine['id']}/approve", headers=world["alice"]["h"], json={}).status_code == 403


def test_free_text_item_not_in_catalogue(client, world):
    r = _raise(client, world, lines=[{"itemName": "  Ergonomic office chair  ", "quantity": "2", "uom": "UNIT", "notes": "Black, with armrests"}])
    assert r.status_code == 201, r.text
    line = r.json()["lines"][0]
    assert line["itemName"] == "Ergonomic office chair"
    assert line["productId"] is None and line["inCatalogue"] is False
    assert line["notes"] == "Black, with armrests"


def test_validation_reports_every_problem(client, world):
    r = _raise(client, world, priority="asap", requiredBy="2020-01-01", lines=[{"quantity": "1"}, {"productId": str(uuid.uuid4()), "quantity": "1"}, {"itemName": "Ok", "quantity": "0"}])
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "PR_VALIDATION_FAILED"
    fields = {e["field"] for e in body["meta"]["errors"]}
    assert {"priority", "requiredBy", "lines.0.itemName", "lines.1", "lines.2.quantity"} <= fields
    assert "5 problems" in body["detail"]


def test_negative_or_missing_quantity_is_rejected(client, world):
    assert _raise(client, world, lines=[{"itemName": "X", "quantity": "-3"}]).status_code == 400
    assert _raise(client, world, lines=[]).status_code == 400


def test_submit_needs_a_reason(client, world):
    r = _raise(client, world, justification="")
    assert r.status_code == 422 and r.json()["code"] == "PR_JUSTIFICATION_REQUIRED"
    # As a draft it is fine, and can be completed and sent later.
    d = _raise(client, world, submit=False, justification=None).json()
    assert client.post(f"/api/v1/purchase-requisitions/{d['id']}/submit", headers=world["alice"]["h"]).json()["code"] == "PR_JUSTIFICATION_REQUIRED"
    fixed = client.patch(f"/api/v1/purchase-requisitions/{d['id']}", headers=world["alice"]["h"], json={"justification": "Needed for the audit", "submit": True})
    assert fixed.status_code == 200 and fixed.json()["status"] == "submitted"


def test_edit_is_owner_only_and_draft_or_rejected_only(client, world):
    pr = _raise(client, world, submit=False).json()
    url = f"/api/v1/purchase-requisitions/{pr['id']}"
    assert client.patch(url, headers=world["bob"]["h"], json={"priority": "high"}).status_code == 404  # bob cannot even see alice's draft
    ok = client.patch(url, headers=world["alice"]["h"], json={"priority": "urgent", "lines": [{"itemName": "Gloves", "quantity": "10", "uom": "BOX"}]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["priority"] == "urgent" and [l["itemName"] for l in ok.json()["lines"]] == ["Gloves"]
    client.post(f"{url}/submit", headers=world["alice"]["h"])
    locked = client.patch(url, headers=world["alice"]["h"], json={"priority": "low"})
    assert locked.status_code == 422 and locked.json()["code"] == "PR_NOT_EDITABLE"


def test_approve_reject_and_resubmit(client, world):
    pr = _raise(client, world).json()
    url = f"/api/v1/purchase-requisitions/{pr['id']}"
    assert client.post(f"{url}/reject", headers=world["purchase"]["h"], json={"reason": "x"}).status_code == 400  # a reason is required
    rej = client.post(f"{url}/reject", headers=world["purchase"]["h"], json={"reason": "Use the stock we already have in WH-2"})
    assert rej.status_code == 200 and rej.json()["status"] == "rejected"
    assert rej.json()["reviewNote"] == "Use the stock we already have in WH-2" and rej.json()["reviewedByName"] == "Priya Purchase"
    # The requester sees why, edits, and sends it again - the old decision is cleared.
    again = client.patch(url, headers=world["alice"]["h"], json={"justification": "Stock in WH-2 is expired", "submit": True})
    assert again.status_code == 200 and again.json()["status"] == "submitted" and again.json()["reviewNote"] is None
    ok = client.post(f"{url}/approve", headers=world["purchase"]["h"], json={"note": "Go ahead"})
    assert ok.status_code == 200 and ok.json()["status"] == "approved" and ok.json()["reviewNote"] == "Go ahead"
    bad = client.post(f"{url}/approve", headers=world["purchase"]["h"], json={})
    assert bad.status_code == 422 and bad.json()["code"] == "PR_INVALID_STATE"


def test_nobody_reviews_their_own_requisition(client, world, app):
    """A Purchase person raising their own needs someone else to approve it."""
    from app.models.role import Role
    role = client.post("/api/v1/roles", headers=world["admin"], json={"name": f"PR Both {uuid.uuid4().hex[:6]}", "permissions": ["pr:read", "pr:write", "pr:approve"]}).json()
    email = f"pr-both-{uuid.uuid4().hex[:6]}@example.test"
    u = client.post("/api/v1/users", headers=world["admin"], json={"email": email, "displayName": "Both Hats", "password": "TestPr#Passw0rd1", "status": "active", "roles": [{"roleId": role["id"], "warehouseIds": [], "factoryIds": []}]}).json()
    h = _h(client.post("/api/v1/auth/login", json={"email": email, "password": "TestPr#Passw0rd1"}).json()["accessToken"])
    pr = client.post("/api/v1/purchase-requisitions", headers=h, json={"justification": "Need it", "lines": [{"itemName": "Toner", "quantity": "1"}], "submit": True}).json()
    r = client.post(f"/api/v1/purchase-requisitions/{pr['id']}/approve", headers=h, json={})
    assert r.status_code == 422 and r.json()["code"] == "SELF_APPROVAL_BLOCKED"
    assert client.post(f"/api/v1/purchase-requisitions/{pr['id']}/approve", headers=world["purchase"]["h"], json={}).status_code == 200

    from app.models.password_history import PasswordHistory
    from app.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionLine
    from app.models.role_permission import RolePermission
    from app.models.session import Session
    from app.models.user import User
    from app.models.user_role import UserRole
    uid, rid = uuid.UUID(u["id"]), uuid.UUID(role["id"])
    ids = [r_.id for r_ in PurchaseRequisition.query.filter_by(requester_id=uid).all()]
    PurchaseRequisitionLine.query.filter(PurchaseRequisitionLine.requisition_id.in_(ids)).delete(synchronize_session=False)
    PurchaseRequisition.query.filter(PurchaseRequisition.id.in_(ids)).delete(synchronize_session=False)
    UserRole.query.filter_by(user_id=uid).delete(synchronize_session=False)
    Session.query.filter_by(user_id=uid).delete(synchronize_session=False)
    PasswordHistory.query.filter_by(user_id=uid).delete(synchronize_session=False)
    User.query.filter_by(id=uid).delete(synchronize_session=False)
    RolePermission.query.filter_by(role_id=rid).delete(synchronize_session=False)
    Role.query.filter_by(id=rid).delete(synchronize_session=False)
    SessionLocal.commit()


def test_cancel_rules(client, world):
    draft = _raise(client, world, submit=False).json()
    assert client.post(f"/api/v1/purchase-requisitions/{draft['id']}/cancel", headers=world["alice"]["h"], json={}).json()["status"] == "cancelled"  # a draft needs no reason

    sub = _raise(client, world).json()
    url = f"/api/v1/purchase-requisitions/{sub['id']}/cancel"
    assert client.post(url, headers=world["bob"]["h"], json={"reason": "not mine"}).status_code == 404
    no_reason = client.post(url, headers=world["alice"]["h"], json={})
    assert no_reason.status_code == 422 and no_reason.json()["code"] == "PR_REASON_REQUIRED"
    done = client.post(url, headers=world["alice"]["h"], json={"reason": "Found it in the store"})
    assert done.status_code == 200 and done.json()["cancelledReason"] == "Found it in the store"
    assert client.post(url, headers=world["alice"]["h"], json={"reason": "again"}).json()["code"] == "PR_INVALID_STATE"

    # Purchase can also withdraw a submitted one, with a reason.
    other = _raise(client, world).json()
    assert client.post(f"/api/v1/purchase-requisitions/{other['id']}/cancel", headers=world["purchase"]["h"], json={"reason": "Duplicate of PR-1"}).status_code == 200


def test_link_purchase_order_marks_it_ordered(client, world):
    from app.models.purchase_order import PurchaseOrder

    pr = _raise(client, world).json()
    url = f"/api/v1/purchase-requisitions/{pr['id']}"
    admin = world["admin"]
    vendor = client.post("/api/v1/parties", headers=admin, json={"legalName": f"PR Vendor {uuid.uuid4().hex[:6]}", "type": "vendor", "paymentTerms": "Net 30"}).json()
    from app.models.party import Party
    Party.query.filter_by(id=uuid.UUID(vendor["id"])).update({"status": "active"}, synchronize_session=False)
    SessionLocal.commit()
    po = client.post("/api/v1/purchase-orders", headers=admin, json={"vendorId": vendor["id"], "warehouseId": world["warehouse"]["id"], "expectedDate": "2030-01-01", "lines": [{"productId": world["product"]["id"], "quantity": "25", "uom": "KG", "unitPrice": "10", "taxCode": "GST0"}]}).json()

    early = client.post(f"{url}/link-po", headers=world["purchase"]["h"], json={"purchaseOrderId": po["id"]})
    assert early.status_code == 422 and early.json()["code"] == "PR_INVALID_STATE"  # not approved yet
    client.post(f"{url}/approve", headers=world["purchase"]["h"], json={})
    assert client.post(f"{url}/link-po", headers=world["purchase"]["h"], json={"purchaseOrderId": str(uuid.uuid4())}).status_code == 404
    done = client.post(f"{url}/link-po", headers=world["purchase"]["h"], json={"purchaseOrderId": po["id"]})
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "ordered" and done.json()["purchaseOrderNumber"] == po["number"]
    assert client.post(f"{url}/cancel", headers=world["alice"]["h"], json={"reason": "too late"}).json()["code"] == "PR_INVALID_STATE"

    from tests.test_purchase_orders import _cleanup_po, _cleanup_vendor
    from app.models.purchase_requisition import PurchaseRequisition
    PurchaseRequisition.query.filter_by(id=uuid.UUID(pr["id"])).update({"purchase_order_id": None}, synchronize_session=False)
    SessionLocal.commit()
    _cleanup_po(po["id"])
    _cleanup_vendor(vendor["id"])


def test_list_filters_search_and_counts(client, world):
    a = _raise(client, world, priority="urgent", lines=[{"itemName": "Zebra label printer", "quantity": "1"}]).json()
    _raise(client, world, submit=False)
    h = world["alice"]["h"]
    only_sub = client.get("/api/v1/purchase-requisitions", headers=h, params={"status": "submitted"}).json()["data"]
    assert a["id"] in [x["id"] for x in only_sub] and all(x["status"] == "submitted" for x in only_sub)
    found = client.get("/api/v1/purchase-requisitions", headers=h, params={"q": "zebra"}).json()["data"]
    assert [x["id"] for x in found] == [a["id"]] and found[0]["itemsSummary"] == "Zebra label printer"
    assert client.get("/api/v1/purchase-requisitions", headers=h, params={"priority": "urgent"}).json()["data"][0]["id"] == a["id"]
    c = client.get("/api/v1/purchase-requisitions/counts", headers=h).json()
    assert c["mine"]["submitted"] >= 1 and c["mine"]["draft"] >= 1 and c["awaitingReview"] is None
    assert client.get("/api/v1/purchase-requisitions/counts", headers=world["purchase"]["h"]).json()["awaitingReview"] >= 1


def test_employee_role_can_reach_the_pickers_but_not_purchase_orders_or_anonymous(client, world):
    h = world["alice"]["h"]
    assert client.get("/api/v1/products", headers=h).status_code == 200
    assert client.get("/api/v1/warehouses", headers=h).status_code == 200
    assert client.get("/api/v1/purchase-orders", headers=h).status_code == 403
    assert client.get("/api/v1/purchase-requisitions", headers={}).status_code == 401


def test_every_step_is_audited(client, world):
    pr = _raise(client, world).json()
    url = f"/api/v1/purchase-requisitions/{pr['id']}"
    client.post(f"{url}/approve", headers=world["purchase"]["h"], json={"note": "ok"})
    from app.models.audit_log import AuditLog
    actions = [a.action for a in AuditLog.query.filter_by(entity_type="purchase-requisition", entity_id=pr["id"]).order_by(AuditLog.created_at).all()]
    assert actions == ["pr.created", "pr.approved"]


# ---- manager approval ------------------------------------------------------------------------------------------------


def test_a_requisition_from_a_team_member_goes_to_their_manager_first(client, world):
    pr = _raise(client, world, "report").json()
    assert pr["status"] == "pending_manager" and pr["managerName"] == "Maya Manager"
    url = f"/api/v1/purchase-requisitions/{pr['id']}"
    # Purchase does not see it yet, the manager does.
    assert client.get(url, headers=world["purchase"]["h"]).status_code == 404
    assert pr["id"] not in [x["id"] for x in client.get("/api/v1/purchase-requisitions", headers=world["purchase"]["h"]).json()["data"]]
    team = client.get("/api/v1/purchase-requisitions", headers=world["manager"]["h"], params={"team": "true", "status": "pending_manager"}).json()["data"]
    assert pr["id"] in [x["id"] for x in team]
    assert client.get("/api/v1/purchase-requisitions/counts", headers=world["manager"]["h"]).json()["awaitingMyApproval"] >= 1
    # Purchase cannot skip the manager.
    assert client.post(f"{url}/approve", headers=world["purchase"]["h"], json={}).status_code == 404

    ok = client.post(f"{url}/manager-approve", headers=world["manager"]["h"], json={"note": "Team needs it"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "submitted" and ok.json()["managerNote"] == "Team needs it" and ok.json()["managerDecidedAt"]
    # Now it is Purchase's to decide, and it carries the manager's approval.
    seen = client.get(url, headers=world["purchase"]["h"]).json()
    assert seen["managerName"] == "Maya Manager" and seen["status"] == "submitted"
    assert client.post(f"{url}/approve", headers=world["purchase"]["h"], json={}).json()["status"] == "approved"


def test_manager_rejection_goes_back_to_the_requester_and_never_reaches_purchase(client, world):
    pr = _raise(client, world, "report").json()
    url = f"/api/v1/purchase-requisitions/{pr['id']}"
    assert client.post(f"{url}/manager-reject", headers=world["manager"]["h"], json={"reason": "x"}).status_code == 400
    rej = client.post(f"{url}/manager-reject", headers=world["manager"]["h"], json={"reason": "Not in this quarter's budget"})
    assert rej.status_code == 200 and rej.json()["status"] == "rejected" and rej.json()["rejectedStage"] == "manager"
    assert rej.json()["managerNote"] == "Not in this quarter's budget"
    assert client.get(url, headers=world["purchase"]["h"]).status_code == 404
    # The requester fixes it and sends it again - back to the manager, decision cleared.
    again = client.patch(url, headers=world["report"]["h"], json={"justification": "Budget approved by finance", "submit": True})
    assert again.status_code == 200 and again.json()["status"] == "pending_manager"
    assert again.json()["managerNote"] is None and again.json()["rejectedStage"] is None


def test_only_the_actual_manager_can_decide(client, world):
    pr = _raise(client, world, "report").json()
    url = f"/api/v1/purchase-requisitions/{pr['id']}"
    # Another manager (not theirs) cannot even open it; the requester cannot decide on their own.
    assert client.post(f"{url}/manager-approve", headers=world["other_manager"]["h"], json={}).status_code == 404
    assert client.post(f"{url}/manager-approve", headers=world["report"]["h"], json={}).status_code == 403  # no pr:team_approve
    # A manager's own requisition needs *their* manager: with none on file it goes straight to Purchase.
    mine = _raise(client, world, "manager").json()
    assert mine["status"] == "submitted"
    # A wrong-state decision is explained.
    assert client.post(f"/api/v1/purchase-requisitions/{mine['id']}/manager-approve", headers=world["manager"]["h"], json={}).status_code in (404, 422)
    done = client.post(f"{url}/manager-approve", headers=world["manager"]["h"], json={})
    assert done.status_code == 200
    again = client.post(f"{url}/manager-approve", headers=world["manager"]["h"], json={})
    assert again.status_code == 422 and again.json()["code"] == "PR_INVALID_STATE"


def test_changing_the_manager_reroutes_what_is_waiting(client, world):
    pr = _raise(client, world, "report").json()
    url = f"/api/v1/purchase-requisitions/{pr['id']}"
    r = client.patch(f"/api/v1/users/{world['report']['id']}", headers=world["admin"], json={"managerId": world["other_manager"]["id"]})
    assert r.status_code == 200, r.text
    assert client.post(f"{url}/manager-approve", headers=world["manager"]["h"], json={}).status_code == 404
    assert client.get(url, headers=world["other_manager"]["h"]).json()["managerName"] == "Omar OtherManager"
    assert client.post(f"{url}/manager-approve", headers=world["other_manager"]["h"], json={}).status_code == 200


def test_manager_must_be_a_sensible_choice(client, world):
    admin, uid = world["admin"], world["report"]["id"]
    self_ = client.patch(f"/api/v1/users/{uid}", headers=admin, json={"managerId": uid})
    assert self_.status_code == 422 and self_.json()["code"] == "MANAGER_SELF"
    # The manager reports to the report: a loop.
    client.patch(f"/api/v1/users/{world['other_manager']['id']}", headers=admin, json={"managerId": uid})
    loop = client.patch(f"/api/v1/users/{uid}", headers=admin, json={"managerId": world["other_manager"]["id"]})
    assert loop.status_code == 422 and loop.json()["code"] == "MANAGER_LOOP"
    assert client.patch(f"/api/v1/users/{uid}", headers=admin, json={"managerId": str(uuid.uuid4())}).json()["code"] == "MANAGER_NOT_FOUND"
    cleared = client.patch(f"/api/v1/users/{uid}", headers=admin, json={"managerId": None})
    assert cleared.status_code == 200
    detail = client.get(f"/api/v1/users/{uid}", headers=admin).json()
    assert detail["managerId"] is None
    client.patch(f"/api/v1/users/{uid}", headers=admin, json={"managerId": world["manager"]["id"]})
    assert client.get(f"/api/v1/users/{uid}", headers=admin).json()["managerName"] == "Maya Manager"
