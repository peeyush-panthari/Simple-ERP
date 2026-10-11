"""Procurement > Sourcing: RFQ from an approved requisition, recording quotations, the comparison, the award rules, and the
purchase orders that follow. Real Postgres, real roles."""

from __future__ import annotations

import uuid

import pytest

from app.core.db import SessionLocal


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def world(client, fresh_admin, app):
    admin = _h(client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]}).json()["accessToken"])
    made = {"users": [], "roles": [], "vendors": [], "products": []}

    def role(perms):
        r = client.post("/api/v1/roles", headers=admin, json={"name": f"Src Test Role {uuid.uuid4().hex[:8]}", "permissions": perms})
        assert r.status_code == 201, r.text
        made["roles"].append(r.json()["id"])
        return r.json()["id"]

    def user(role_id, name):
        email = f"src-test-{uuid.uuid4().hex[:8]}@example.test"
        r = client.post("/api/v1/users", headers=admin, json={"email": email, "displayName": name, "password": "TestSrc#Passw0rd1", "status": "active", "roles": [{"roleId": role_id, "warehouseIds": [], "factoryIds": []}]})
        assert r.status_code == 201, r.text
        made["users"].append(r.json()["id"])
        return {"id": r.json()["id"], "h": _h(client.post("/api/v1/auth/login", json={"email": email, "password": "TestSrc#Passw0rd1"}).json()["accessToken"])}

    def vendor(name, email=None):
        from app.models.party import Party
        body = {"legalName": f"{name} {uuid.uuid4().hex[:6]}", "type": "vendor", "paymentTerms": "Net 30"}
        if email:
            body["contacts"] = [{"name": "Sales Desk", "email": email, "isPrimary": True}]
        v = client.post("/api/v1/parties", headers=admin, json=body).json()
        Party.query.filter_by(id=uuid.UUID(v["id"])).update({"status": "active"}, synchronize_session=False)
        SessionLocal.commit()
        made["vendors"].append(v["id"])
        return v

    def product(label):
        p = client.post("/api/v1/products", headers=admin, json={"sku": f"SRC-{uuid.uuid4().hex[:8].upper()}", "name": f"Src {label} {uuid.uuid4().hex[:5]}", "make": "TestCo", "type": "raw_material", "uom": "KG", "purchasable": True}).json()
        made["products"].append(p["id"])
        return p

    buyer_role = role(["pr:read", "pr:approve", "po:read", "po:write", "sourcing:read", "sourcing:write", "sourcing:award", "party:read", "warehouse:read"])
    w = {
        "admin": admin,
        "alice": user(role(["pr:read", "pr:write"]), "Alice Employee"),
        "buyer": user(buyer_role, "Bela Buyer"),
        "clerk": user(role(["sourcing:read", "sourcing:write", "pr:read"]), "Cy Clerk"),  # runs RFQs, may not award
        "va": vendor("Alpha Vendor", "alpha@vendor-a.example"),
        "vb": vendor("Bravo Vendor"),
        "vc": vendor("Charlie Vendor"),
        "p1": product("Bearing"),
        "p2": product("Grease"),
        "warehouse": client.post("/api/v1/warehouses", headers=admin, json={"name": f"Src WH {uuid.uuid4().hex[:6]}"}).json(),
    }
    yield w

    from app.models.location import Location
    from app.models.party import Party
    from app.models.party_version import PartyVersion
    from app.models.password_history import PasswordHistory
    from app.models.po_line import PoLine
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionLine
    from app.models.purchase_rfq import PurchaseQuotation, PurchaseQuotationLine, PurchaseRfq, PurchaseRfqLine, PurchaseRfqVendor
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.session import Session
    from app.models.user import User
    from app.models.user_role import UserRole
    from app.models.warehouse import Warehouse

    uids = [uuid.UUID(i) for i in made["users"]]
    rids = [uuid.UUID(i) for i in made["roles"]]
    vids = [uuid.UUID(i) for i in made["vendors"]]
    reqs = [r.id for r in PurchaseRequisition.query.filter(PurchaseRequisition.requester_id.in_(uids)).all()]
    rfqs = [r.id for r in PurchaseRfq.query.filter(PurchaseRfq.requisition_id.in_(reqs)).all()] if reqs else []
    if rfqs:
        qids = [q.id for q in PurchaseQuotation.query.filter(PurchaseQuotation.rfq_id.in_(rfqs)).all()]
        PurchaseQuotationLine.query.filter(PurchaseQuotationLine.quotation_id.in_(qids)).delete(synchronize_session=False)
        PurchaseQuotation.query.filter(PurchaseQuotation.rfq_id.in_(rfqs)).delete(synchronize_session=False)
        PurchaseRfqVendor.query.filter(PurchaseRfqVendor.rfq_id.in_(rfqs)).delete(synchronize_session=False)
        PurchaseRfqLine.query.filter(PurchaseRfqLine.rfq_id.in_(rfqs)).delete(synchronize_session=False)
        PurchaseRfq.query.filter(PurchaseRfq.id.in_(rfqs)).delete(synchronize_session=False)
    pos = [p.id for p in PurchaseOrder.query.filter(PurchaseOrder.vendor_id.in_(vids)).all()]
    PurchaseRequisitionLine.query.filter(PurchaseRequisitionLine.requisition_id.in_(reqs)).delete(synchronize_session=False)
    PurchaseRequisition.query.filter(PurchaseRequisition.id.in_(reqs)).delete(synchronize_session=False)
    from tests.test_purchase_orders import _cleanup_po
    for pid in pos:
        _cleanup_po(str(pid))
    UserRole.query.filter(UserRole.user_id.in_(uids) | UserRole.role_id.in_(rids)).delete(synchronize_session=False)
    Session.query.filter(Session.user_id.in_(uids)).delete(synchronize_session=False)
    PasswordHistory.query.filter(PasswordHistory.user_id.in_(uids)).delete(synchronize_session=False)
    User.query.filter(User.id.in_(uids)).delete(synchronize_session=False)
    RolePermission.query.filter(RolePermission.role_id.in_(rids)).delete(synchronize_session=False)
    Role.query.filter(Role.id.in_(rids)).delete(synchronize_session=False)
    PartyVersion.query.filter(PartyVersion.party_id.in_(vids)).delete(synchronize_session=False)
    Party.query.filter(Party.id.in_(vids)).delete(synchronize_session=False)
    PoLine.query.filter(PoLine.product_id.in_([uuid.UUID(i) for i in made["products"]])).delete(synchronize_session=False)
    Product.query.filter(Product.id.in_([uuid.UUID(i) for i in made["products"]])).delete(synchronize_session=False)
    Location.query.filter_by(warehouse_id=uuid.UUID(w["warehouse"]["id"])).delete(synchronize_session=False)
    Warehouse.query.filter_by(id=uuid.UUID(w["warehouse"]["id"])).delete(synchronize_session=False)
    SessionLocal.commit()


@pytest.fixture(autouse=True)
def _built_in_templates(app):
    from app.services.notification_templates import seed_templates
    seed_templates()


def _approved_requisition(client, w, *, free_text=False):
    lines = [{"productId": w["p1"]["id"], "quantity": "10"}, {"productId": w["p2"]["id"], "quantity": "5"}]
    if free_text:
        lines.append({"itemName": "Custom jig", "quantity": "1", "uom": "UNIT"})
    pr = client.post("/api/v1/purchase-requisitions", headers=w["alice"]["h"], json={"priority": "high", "warehouseId": w["warehouse"]["id"], "justification": "Line maintenance", "lines": lines, "submit": True}).json()
    ok = client.post(f"/api/v1/purchase-requisitions/{pr['id']}/approve", headers=w["buyer"]["h"], json={})
    assert ok.status_code == 200, ok.text
    return pr


def _start(client, w, pr, vendors=("va", "vb", "vc"), **over):
    body = {"requisitionId": pr["id"], "vendorIds": [w[v]["id"] for v in vendors], "send": False}
    body.update(over)
    r = client.post("/api/v1/purchase-rfqs", headers=w["buyer"]["h"], json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _quote(client, w, rfq, vendor, prices, **over):
    """prices: {line_no: (unit_price, tax_code)} - an omitted line is left without a price."""
    lines = []
    for l in rfq["lines"]:
        p = prices.get(l["lineNo"])
        lines.append({"rfqLineId": l["id"], "unitPrice": p[0] if p else None, "taxCode": p[1] if p else "GST0"})
    body = {"quoteRef": f"Q-{vendor}", "paymentTerms": "Net 45", "deliveryDays": 7, "charges": "0", "lines": lines}
    body.update(over)
    r = client.put(f"/api/v1/purchase-rfqs/{rfq['id']}/quotations/{w[vendor]['id']}", headers=w["buyer"]["h"], json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _three_quotes(client, w, rfq):
    _quote(client, w, rfq, "va", {1: ("100", "GST18"), 2: ("200", "GST18")}, charges="50")
    _quote(client, w, rfq, "vb", {1: ("95", "GST18"), 2: ("190", "GST18")})
    _quote(client, w, rfq, "vc", {1: ("98", "GST0")})  # C quotes only the bearing, without tax


def test_only_an_approved_requisition_can_go_out_for_quotation(client, world):
    w = world
    pr = client.post("/api/v1/purchase-requisitions", headers=w["alice"]["h"], json={"justification": "x need", "lines": [{"itemName": "Thing", "quantity": "1"}], "submit": True}).json()
    r = client.post("/api/v1/purchase-rfqs", headers=w["buyer"]["h"], json={"requisitionId": pr["id"], "vendorIds": [w["va"]["id"]], "send": False})
    assert r.status_code == 422 and r.json()["code"] == "RFQ_REQUISITION_NOT_APPROVED"


def test_start_sourcing_copies_the_items_and_moves_the_requisition(client, world):
    w = world
    pr = _approved_requisition(client, w, free_text=True)
    rfq = _start(client, w, pr, dueDate="2030-01-01", terms="Delivery included")
    assert rfq["number"].startswith("PRFQ-") and rfq["status"] == "open" and rfq["requisitionNumber"] == pr["number"]
    assert [l["itemName"] for l in rfq["lines"]][2] == "Custom jig" and rfq["lines"][2]["inCatalogue"] is False
    assert {v["vendorName"].split()[0] for v in rfq["vendors"]} == {"Alpha", "Bravo", "Charlie"}
    assert rfq["warehouseCode"] == w["warehouse"]["code"]
    assert client.get(f"/api/v1/purchase-requisitions/{pr['id']}", headers=w["buyer"]["h"]).json()["status"] == "sourcing"
    detail = client.get(f"/api/v1/purchase-requisitions/{pr['id']}", headers=w["buyer"]["h"]).json()
    assert detail["rfqNumber"] == rfq["number"]
    # It cannot be started twice, and the requisition cannot be cancelled underneath the RFQ.
    again = client.post("/api/v1/purchase-rfqs", headers=w["buyer"]["h"], json={"requisitionId": pr["id"], "vendorIds": [w["va"]["id"]], "send": False})
    assert again.status_code == 422
    assert client.post(f"/api/v1/purchase-requisitions/{pr['id']}/cancel", headers=w["buyer"]["h"], json={"reason": "no longer"}).json()["code"] == "PR_INVALID_STATE"


def test_vendors_must_be_real_active_vendors(client, world):
    w = world
    pr = _approved_requisition(client, w)
    r = client.post("/api/v1/purchase-rfqs", headers=w["buyer"]["h"], json={"requisitionId": pr["id"], "vendorIds": [str(uuid.uuid4())], "send": False})
    assert r.status_code == 422 and r.json()["code"] == "RFQ_VENDOR_INVALID"
    r = client.post("/api/v1/purchase-rfqs", headers=w["buyer"]["h"], json={"requisitionId": pr["id"], "vendorIds": [w["va"]["id"]], "dueDate": "2020-01-01", "send": False})
    assert r.json()["code"] == "RFQ_DUE_DATE_PAST"


def test_request_emails_are_recorded_per_vendor_and_never_block(client, world):
    w = world
    pr = _approved_requisition(client, w)
    rfq = _start(client, w, pr, vendors=("va", "vb"), send=True)
    by = {v["vendorName"].split()[0]: v for v in rfq["vendors"]}
    assert by["Bravo"]["emailState"] == "skipped" and "No email address" in by["Bravo"]["emailError"]
    assert by["Alpha"]["emailState"] in ("sent", "queued", "failed")  # depends on the mail server available to the test run
    assert "Template" not in (by["Alpha"]["emailError"] or "")  # the built-in template exists and renders
    assert rfq["status"] == "open"


def test_quotation_validation(client, world):
    w = world
    rfq = _start(client, w, _approved_requisition(client, w))
    url = f"/api/v1/purchase-rfqs/{rfq['id']}/quotations/{w['va']['id']}"
    empty = client.put(url, headers=w["buyer"]["h"], json={"lines": [{"rfqLineId": rfq["lines"][0]["id"]}]})
    assert empty.status_code == 422 and empty.json()["code"] == "QUOTATION_VALIDATION_FAILED"
    bad = client.put(url, headers=w["buyer"]["h"], json={"lines": [{"rfqLineId": str(uuid.uuid4()), "unitPrice": "5"}, {"rfqLineId": rfq["lines"][0]["id"], "unitPrice": "5", "taxCode": "NOPE"}]})
    assert bad.status_code == 422 and len(bad.json()["meta"]["errors"]) == 2
    assert client.put(url, headers=w["buyer"]["h"], json={"lines": [{"rfqLineId": rfq["lines"][0]["id"], "unitPrice": "-5"}]}).status_code == 400
    stranger = client.put(f"/api/v1/purchase-rfqs/{rfq['id']}/quotations/{uuid.uuid4()}", headers=w["buyer"]["h"], json={"lines": [{"rfqLineId": rfq["lines"][0]["id"], "unitPrice": "5"}]})
    assert stranger.json()["code"] == "RFQ_VENDOR_NOT_INVITED"


def test_comparison_puts_offers_side_by_side_with_tax_and_freight(client, world):
    w = world
    rfq = _start(client, w, _approved_requisition(client, w))
    _three_quotes(client, w, rfq)
    comp = client.get(f"/api/v1/purchase-rfqs/{rfq['id']}/comparison", headers=w["buyer"]["h"]).json()
    va, vb, vc = w["va"]["id"], w["vb"]["id"], w["vc"]["id"]
    bearing, grease = comp["lines"]
    # Bearing, 10 kg: A 100 + 18% = 1180.00, B 95 + 18% = 1121.00, C 98 with no tax = 980.00 -> C is lowest landed.
    assert [bearing["offers"][v]["grossAmount"] for v in (va, vb, vc)] == ["1180.000000", "1121.000000", "980.000000"]
    assert bearing["offers"][vc]["isLowest"] and not bearing["offers"][va]["isLowest"]
    assert bearing["offers"][va]["overLowestPct"] == "20.400000"
    assert bearing["suggestedVendorId"] == vc and bearing["quoteCount"] == 3
    # Grease, 5 kg: A 1180.00, B 1121.00; C did not quote.
    assert grease["suggestedVendorId"] == vb and vc not in grease["offers"] and grease["quoteCount"] == 2
    rows = {v["vendorId"]: v for v in comp["vendors"]}
    assert rows[va]["basketTotal"] == "2410.000000" and rows[va]["coversAllLines"]  # 1180 + 1180 + 50 freight
    assert rows[vb]["basketTotal"] == "2242.000000" and rows[vc]["coversAllLines"] is False
    assert comp["cheapestSingleVendorId"] == vb and comp["cheapestSingleVendorTotal"] == "2242.000000"
    assert comp["suggestedTotal"] == "2101.000000"  # C's bearings 980 + B's grease 1121


def test_award_rules(client, world):
    w = world
    rfq = _start(client, w, _approved_requisition(client, w))
    _three_quotes(client, w, rfq)
    va, vb, vc = w["va"]["id"], w["vb"]["id"], w["vc"]["id"]
    l1, l2 = rfq["lines"][0]["id"], rfq["lines"][1]["id"]
    url = f"/api/v1/purchase-rfqs/{rfq['id']}/award"
    # The clerk may run the RFQ but not award it.
    assert client.post(url, headers=w["clerk"]["h"], json={"awards": [{"rfqLineId": l1, "vendorId": vc}]}).status_code == 403
    # Every quoted item needs a winner.
    missing = client.post(url, headers=w["buyer"]["h"], json={"awards": [{"rfqLineId": l1, "vendorId": vc}]})
    assert missing.status_code == 422 and "Choose a vendor for" in missing.json()["detail"]
    # Not the lowest -> a reason; and a vendor that did not quote the item cannot win it.
    r = client.post(url, headers=w["buyer"]["h"], json={"awards": [{"rfqLineId": l1, "vendorId": va}, {"rfqLineId": l2, "vendorId": vc}]})
    assert r.status_code == 422 and r.json()["code"] == "AWARD_VALIDATION_FAILED"
    msgs = " ".join(e["message"] for e in r.json()["meta"]["errors"])
    assert "not the lowest price" in msgs and "did not quote" in msgs
    # The suggestion (lowest per item) needs no reason.
    ok = client.post(url, headers=w["buyer"]["h"], json={"awards": [{"rfqLineId": l1, "vendorId": vc}, {"rfqLineId": l2, "vendorId": vb}]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "awarded" and ok.json()["awardedByName"] == "Bela Buyer"
    assert [l["awardedVendorName"].split()[0] for l in ok.json()["lines"]] == ["Charlie", "Bravo"]
    # Quotations are frozen while awarded; reopening clears the award, and a considered exception is allowed with a reason.
    assert client.put(f"/api/v1/purchase-rfqs/{rfq['id']}/quotations/{va}", headers=w["buyer"]["h"], json={"lines": [{"rfqLineId": l1, "unitPrice": "1"}]}).json()["code"] == "RFQ_INVALID_STATE"
    assert client.post(f"/api/v1/purchase-rfqs/{rfq['id']}/reopen", headers=w["buyer"]["h"]).json()["status"] == "open"
    exc = client.post(url, headers=w["buyer"]["h"], json={"awards": [{"rfqLineId": l1, "vendorId": va, "reason": "Only Alpha stocks the certified grade"}, {"rfqLineId": l2, "vendorId": va, "reason": "Keep it with one supplier"}]})
    assert exc.status_code == 200 and exc.json()["lines"][0]["awardReason"] == "Only Alpha stocks the certified grade"


def test_a_single_quote_needs_a_reason_too(client, world):
    w = world
    rfq = _start(client, w, _approved_requisition(client, w), vendors=("va",))
    _quote(client, w, rfq, "va", {1: ("10", "GST0"), 2: ("10", "GST0")})
    url = f"/api/v1/purchase-rfqs/{rfq['id']}/award"
    awards = [{"rfqLineId": l["id"], "vendorId": w["va"]["id"]} for l in rfq["lines"]]
    r = client.post(url, headers=w["buyer"]["h"], json={"awards": awards})
    assert r.status_code == 422 and "only one vendor quoted" in " ".join(e["message"] for e in r.json()["meta"]["errors"])
    ok = client.post(url, headers=w["buyer"]["h"], json={"awards": [{**a, "reason": "Sole source for this part"} for a in awards]})
    assert ok.status_code == 200


def test_award_then_purchase_orders_one_per_winning_vendor(client, world):
    w = world
    pr = _approved_requisition(client, w)
    rfq = _start(client, w, pr)
    _three_quotes(client, w, rfq)
    vb, vc = w["vb"]["id"], w["vc"]["id"]
    l1, l2 = rfq["lines"][0]["id"], rfq["lines"][1]["id"]
    pos_url = f"/api/v1/purchase-rfqs/{rfq['id']}/purchase-orders"
    assert client.post(pos_url, headers=w["buyer"]["h"], json={}).json()["code"] == "RFQ_INVALID_STATE"  # not awarded yet
    client.post(f"/api/v1/purchase-rfqs/{rfq['id']}/award", headers=w["buyer"]["h"], json={"awards": [{"rfqLineId": l1, "vendorId": vc}, {"rfqLineId": l2, "vendorId": vb}]})
    assert client.post(pos_url, headers=w["clerk"]["h"], json={}).status_code == 403

    done = client.post(pos_url, headers=w["buyer"]["h"], json={})
    assert done.status_code == 200, done.text
    body = done.json()
    assert len(body["created"]) == 2 and body["status"] == "ordered" and body["skippedFreeTextItems"] == []
    assert all(l["purchaseOrderNumber"] for l in body["lines"])

    pos = {}
    for c in body["created"]:
        po = client.get(f"/api/v1/purchase-orders/{c['id']}", headers=w["admin"]).json()
        pos[po["vendorId"]] = po
    # Priced from each vendor's quotation, with its tax, terms and a pointer back to the RFQ.
    charlie, bravo = pos[vc], pos[vb]
    assert charlie["lines"][0]["unitPrice"] == "98.000000" and charlie["taxTotal"] == "0.000000" and charlie["total"] == "980.000000"
    assert bravo["lines"][0]["unitPrice"] == "190.000000" and bravo["total"] == "1121.000000"
    assert charlie["paymentTerms"] == "Net 45" and rfq["number"] in charlie["notes"] and pr["number"] in charlie["notes"]
    assert charlie["warehouseId"] == w["warehouse"]["id"]

    # The requisition is now ordered and lists both purchase orders; nothing can be raised twice.
    after = client.get(f"/api/v1/purchase-requisitions/{pr['id']}", headers=w["buyer"]["h"]).json()
    assert after["status"] == "ordered" and charlie["number"] in after["purchaseOrderNumber"] and bravo["number"] in after["purchaseOrderNumber"]
    assert client.post(pos_url, headers=w["buyer"]["h"], json={}).json()["code"] == "RFQ_INVALID_STATE"
    assert client.post(f"/api/v1/purchase-rfqs/{rfq['id']}/cancel", headers=w["buyer"]["h"], json={"reason": "too late"}).json()["code"] == "RFQ_INVALID_STATE"
    from app.models.audit_log import AuditLog
    actions = {a.action for a in AuditLog.query.filter_by(entity_type="purchase-rfq", entity_id=rfq["id"]).all()}
    assert {"rfq.created", "rfq.quotation_recorded", "rfq.awarded", "rfq.po_created"} <= actions


def test_a_free_text_item_cannot_be_ordered_but_is_reported(client, world):
    w = world
    pr = _approved_requisition(client, w, free_text=True)
    rfq = _start(client, w, pr, vendors=("va", "vb"))
    lines = {l["lineNo"]: l for l in rfq["lines"]}
    _quote(client, w, rfq, "va", {1: ("100", "GST18"), 3: ("500", "GST18")})
    _quote(client, w, rfq, "vb", {1: ("110", "GST18"), 2: ("50", "GST18")})
    awards = [
        {"rfqLineId": lines[1]["id"], "vendorId": w["va"]["id"]},
        {"rfqLineId": lines[2]["id"], "vendorId": w["vb"]["id"], "reason": "Only Bravo quoted"},
        {"rfqLineId": lines[3]["id"], "vendorId": w["va"]["id"], "reason": "Only Alpha quoted"},
    ]
    assert client.post(f"/api/v1/purchase-rfqs/{rfq['id']}/award", headers=w["buyer"]["h"], json={"awards": awards}).status_code == 200
    done = client.post(f"/api/v1/purchase-rfqs/{rfq['id']}/purchase-orders", headers=w["buyer"]["h"], json={}).json()
    assert done["skippedFreeTextItems"] == ["Custom jig"] and len(done["created"]) == 2


def test_cancelling_the_rfq_sends_the_requisition_back(client, world):
    w = world
    pr = _approved_requisition(client, w)
    rfq = _start(client, w, pr)
    url = f"/api/v1/purchase-rfqs/{rfq['id']}/cancel"
    assert client.post(url, headers=w["buyer"]["h"], json={"reason": "x"}).status_code == 400
    done = client.post(url, headers=w["buyer"]["h"], json={"reason": "Requirement withdrawn by the plant"})
    assert done.status_code == 200 and done.json()["status"] == "cancelled"
    assert client.get(f"/api/v1/purchase-requisitions/{pr['id']}", headers=w["buyer"]["h"]).json()["status"] == "approved"
    # ...so a fresh RFQ can be started.
    assert _start(client, w, pr, vendors=("va",))["status"] == "open"


def test_invite_withdraw_and_decline(client, world):
    w = world
    rfq = _start(client, w, _approved_requisition(client, w), vendors=("va",))
    base = f"/api/v1/purchase-rfqs/{rfq['id']}"
    more = client.post(f"{base}/vendors", headers=w["buyer"]["h"], json={"vendorIds": [w["vb"]["id"], w["vc"]["id"]], "send": False})
    assert more.status_code == 200 and len(more.json()["vendors"]) == 3
    assert client.post(f"{base}/vendors", headers=w["buyer"]["h"], json={"vendorIds": [w["vb"]["id"]], "send": False}).json()["vendors"].__len__() == 3  # no duplicate
    assert len(client.delete(f"{base}/vendors/{w['vc']['id']}", headers=w["buyer"]["h"]).json()["vendors"]) == 2
    declined = client.post(f"{base}/vendors/{w['vb']['id']}/decline", headers=w["buyer"]["h"]).json()
    assert {v["vendorName"].split()[0]: v["status"] for v in declined["vendors"]}["Bravo"] == "declined"
    _quote(client, w, rfq, "va", {1: ("1", "GST0")})
    assert client.delete(f"{base}/vendors/{w['va']['id']}", headers=w["buyer"]["h"]).json()["code"] == "RFQ_VENDOR_HAS_QUOTATION"
    listed = client.get("/api/v1/purchase-rfqs", headers=w["buyer"]["h"], params={"q": rfq["number"]}).json()["data"]
    assert listed[0]["vendorCount"] == 2 and listed[0]["quotedCount"] == 1 and listed[0]["lineCount"] == 2


def test_permissions(client, world):
    w = world
    assert client.get("/api/v1/purchase-rfqs", headers=w["alice"]["h"]).status_code == 403
    assert client.get("/api/v1/purchase-rfqs", headers=w["clerk"]["h"]).status_code == 200
    pr = _approved_requisition(client, w)
    body = {"requisitionId": pr["id"], "vendorIds": [w["va"]["id"]], "send": False}
    assert client.post("/api/v1/purchase-rfqs", headers=w["alice"]["h"], json=body).status_code == 403
    # sourcing:read alone (no write) cannot start one; the vendor picker still works for the clerk.
    assert client.get("/api/v1/parties", headers=w["clerk"]["h"], params={"type": "vendor"}).status_code == 200
    assert client.get("/api/v1/warehouses", headers=w["clerk"]["h"]).status_code == 200
