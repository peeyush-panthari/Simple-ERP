"""After the PO: vendor acknowledgement, vendor documents, dispatch documentation - and their link to goods receipts."""

from __future__ import annotations

import base64
import uuid
from datetime import date, timedelta

import pytest

from app.core.db import SessionLocal
from tests.test_purchase_orders import _cleanup_po, _cleanup_product, _cleanup_vendor, _cleanup_warehouse, _setup

PDF = base64.b64encode(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF").decode()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def world(client, fresh_admin):
    admin = _h(client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]}).json()["accessToken"])
    made = {"users": [], "roles": []}

    def user(perms, name):
        r = client.post("/api/v1/roles", headers=admin, json={"name": f"PoV Role {uuid.uuid4().hex[:8]}", "permissions": perms}).json()
        made["roles"].append(r["id"])
        email = f"pov-{uuid.uuid4().hex[:8]}@example.test"
        u = client.post("/api/v1/users", headers=admin, json={"email": email, "displayName": name, "password": "TestPov#Passw0rd1", "status": "active", "roles": [{"roleId": r["id"], "warehouseIds": [], "factoryIds": []}]}).json()
        made["users"].append(u["id"])
        return _h(client.post("/api/v1/auth/login", json={"email": email, "password": "TestPov#Passw0rd1"}).json()["accessToken"])

    vendor, warehouse, product = _setup(client, admin)
    product2 = client.post("/api/v1/products", headers=admin, json={"sku": f"POV-{uuid.uuid4().hex[:8].upper()}", "name": f"Pov Second {uuid.uuid4().hex[:6]}", "make": "TestCo", "type": "raw_material", "uom": "KG", "purchasable": True}).json()
    po = client.post("/api/v1/purchase-orders", headers=admin, json={
        "vendorId": vendor["id"], "warehouseId": warehouse["id"], "expectedDate": (date.today() + timedelta(days=30)).isoformat(),
        "lines": [{"productId": product["id"], "quantity": "100", "uom": "KG", "unitPrice": "600", "taxCode": "GST18"}, {"productId": product2["id"], "quantity": "10", "uom": "KG", "unitPrice": "100", "taxCode": "GST0"}],
    }).json()
    w = {"admin": admin, "po": po, "buyer": user(["po:read", "po:vendor"], "Bela Buyer"), "reader": user(["po:read"], "Rita Reader"), "store": user(["warehouse:read"], "Sam Store")}
    yield w

    from app.models.document import Document
    from app.models.password_history import PasswordHistory
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.session import Session
    from app.models.user import User
    from app.models.user_role import UserRole
    uids, rids = [uuid.UUID(i) for i in made["users"]], [uuid.UUID(i) for i in made["roles"]]
    SessionLocal.rollback()
    _cleanup_po(po["id"])  # cascades the shipment and document rows, which frees the stored documents
    Document.query.filter_by(related_type="purchase-order", related_id=po["id"]).delete(synchronize_session=False)
    UserRole.query.filter(UserRole.user_id.in_(uids) | UserRole.role_id.in_(rids)).delete(synchronize_session=False)
    Session.query.filter(Session.user_id.in_(uids)).delete(synchronize_session=False)
    PasswordHistory.query.filter(PasswordHistory.user_id.in_(uids)).delete(synchronize_session=False)
    User.query.filter(User.id.in_(uids)).delete(synchronize_session=False)
    RolePermission.query.filter(RolePermission.role_id.in_(rids)).delete(synchronize_session=False)
    Role.query.filter(Role.id.in_(rids)).delete(synchronize_session=False)
    SessionLocal.commit()
    _cleanup_vendor(vendor["id"])
    _cleanup_warehouse(warehouse["id"])
    _cleanup_product(product["id"])
    _cleanup_product(product2["id"])


def _url(w, tail=""):
    return f"/api/v1/purchase-orders/{w['po']['id']}{tail}"


def _dispatch(client, w, qty1="40", qty2=None, **over):
    lines = [{"poLineId": w["po"]["lines"][0]["id"], "quantity": qty1}]
    if qty2:
        lines.append({"poLineId": w["po"]["lines"][1]["id"], "quantity": qty2})
    body = {"dispatchDate": date.today().isoformat(), "transporter": "Blue Dart Freight", "vehicleNo": "mh12 ab 1234", "lrNo": "LR-8891", "packages": 4, "lines": lines}
    body.update(over)
    return client.post(_url(w, "/dispatches"), headers=w["buyer"], json=body)


# ---- acknowledgement ---------------------------------------------------------------------------------------------------


def test_new_orders_wait_for_the_vendor(client, world):
    t = client.get(_url(world, "/vendor-tracking"), headers=world["buyer"]).json()
    assert t["acknowledgement"]["status"] == "pending" and t["documents"] == [] and t["dispatches"] == []
    assert {d["poLineId"]: d["canDispatch"] for d in t["dispatchable"]}[world["po"]["lines"][0]["id"]] == "100.000000"


def test_record_the_vendors_acknowledgement(client, world):
    soon = (date.today() + timedelta(days=20)).isoformat()
    r = client.put(_url(world, "/acknowledgement"), headers=world["buyer"], json={"status": "acknowledged", "ackRef": "ACK-771", "confirmedDate": soon})
    assert r.status_code == 200, r.text
    ack = r.json()["acknowledgement"]
    assert ack["status"] == "acknowledged" and ack["ref"] == "ACK-771" and ack["confirmedDate"] == soon and ack["date"] == date.today().isoformat() and ack["recordedBy"] == "Bela Buyer"
    po = client.get(_url(world), headers=world["buyer"]).json()
    assert po["ackStatus"] == "acknowledged" and po["ackConfirmedDate"] == soon
    listed = client.get("/api/v1/purchase-orders", headers=world["buyer"], params={"q": world["po"]["number"]}).json()["data"][0]
    assert listed["ackStatus"] == "acknowledged" and listed["dispatchStatus"] == "none"
    cleared = client.delete(_url(world, "/acknowledgement"), headers=world["buyer"]).json()
    assert cleared["acknowledgement"]["status"] == "pending" and cleared["acknowledgement"]["ref"] is None


def test_acknowledgement_rules(client, world):
    put = lambda **b: client.put(_url(world, "/acknowledgement"), headers=world["buyer"], json=b)
    assert put(status="declined").json()["code"] == "ACK_NOTES_REQUIRED"
    assert put(status="acknowledged_with_changes").json()["code"] == "ACK_NOTES_REQUIRED"
    assert put(status="maybe").json()["code"] == "ACK_STATUS_INVALID"
    assert put(status="acknowledged", ackDate=(date.today() + timedelta(days=2)).isoformat()).json()["code"] == "ACK_DATE_FUTURE"
    assert put(status="acknowledged", ackDate="2000-01-01").json()["code"] == "ACK_DATE_BEFORE_PO"
    assert put(status="acknowledged", confirmedDate="2000-01-01").json()["code"] == "ACK_DELIVERY_DATE_INVALID"
    ok = put(status="acknowledged_with_changes", confirmedDate=(date.today() + timedelta(days=40)).isoformat(), notes="Delivery moves out by ten days")
    assert ok.status_code == 200 and ok.json()["acknowledgement"]["notes"] == "Delivery moves out by ten days"
    assert put(status="declined", notes="Cannot supply this grade").json()["acknowledgement"]["status"] == "declined"


def test_permissions_and_cancelled_orders(client, world):
    assert client.put(_url(world, "/acknowledgement"), headers=world["reader"], json={"status": "acknowledged"}).status_code == 403
    assert client.get(_url(world, "/vendor-tracking"), headers=world["reader"]).status_code == 200
    assert client.get(_url(world, "/vendor-tracking"), headers=world["store"]).status_code == 200  # the receiving team sees what is coming
    assert client.post(_url(world, "/dispatches"), headers=world["store"], json={}).status_code == 403
    client.post(_url(world, "/cancel"), headers=world["admin"], json={"reason": "Vendor cannot deliver at all"})
    r = client.put(_url(world, "/acknowledgement"), headers=world["buyer"], json={"status": "acknowledged"})
    assert r.status_code == 422 and r.json()["code"] == "PO_NOT_OPEN"


# ---- documents ---------------------------------------------------------------------------------------------------------


def test_vendor_documents_upload_list_download_delete(client, world):
    up = client.post(_url(world, "/documents"), headers=world["buyer"], json={"docType": "proforma_invoice", "filename": "PI-2231.pdf", "contentType": "application/pdf", "contentBase64": PDF, "referenceNo": "PI-2231", "description": "Advance 30%"})
    assert up.status_code == 201, up.text
    doc = up.json()
    assert doc["docTypeLabel"] == "Proforma invoice" and doc["stage"] == "vendor" and doc["referenceNo"] == "PI-2231" and doc["uploadedByName"] == "Bela Buyer"
    client.post(_url(world, "/documents"), headers=world["buyer"], json={"docType": "technical_document", "filename": "datasheet.pdf", "contentType": "application/pdf", "contentBase64": PDF})
    t = client.get(_url(world, "/vendor-tracking"), headers=world["store"]).json()
    assert [d["docType"] for d in t["documents"]] == ["proforma_invoice", "technical_document"]
    dl = client.get(_url(world, f"/documents/{doc['id']}/download"), headers=world["store"])
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF") and dl.headers["content-type"] == "application/pdf"
    assert client.get("/api/v1/purchase-orders", headers=world["buyer"], params={"q": world["po"]["number"]}).json()["data"][0]["documentCount"] == 2
    left = client.delete(_url(world, f"/documents/{doc['id']}"), headers=world["buyer"]).json()
    assert [d["docType"] for d in left["documents"]] == ["technical_document"]
    assert client.get(_url(world, f"/documents/{doc['id']}/download"), headers=world["buyer"]).status_code == 404


def test_document_validation(client, world):
    post = lambda **b: client.post(_url(world, "/documents"), headers=world["buyer"], json={"docType": "technical_document", "filename": "x.pdf", "contentType": "application/pdf", "contentBase64": PDF, **b})
    assert post(docType="nonsense").json()["code"] == "DOC_TYPE_INVALID"
    assert post(contentType="application/x-msdownload").json()["code"] == "ATTACHMENT_TYPE_INVALID"
    assert post(contentBase64=base64.b64encode(b"not a pdf at all").decode()).json()["code"] == "ATTACHMENT_TYPE_MISMATCH"
    assert post(docType="packing_list").json()["code"] == "DOC_NEEDS_DISPATCH"  # belongs to a shipment
    assert post(dispatchId=str(uuid.uuid4()), docType="packing_list").status_code == 404
    assert client.post(_url(world, "/documents"), headers=world["reader"], json={"docType": "other", "filename": "x.pdf", "contentType": "application/pdf", "contentBase64": PDF}).status_code == 403


# ---- dispatches --------------------------------------------------------------------------------------------------------


def test_record_a_dispatch_with_transport_and_papers(client, world):
    r = _dispatch(client, world, "40", "4", invoiceNo="INV-118", invoiceDate=date.today().isoformat(), invoiceValue="30000", packingListNo="PL-55", deliveryChallanNo="DC-909", deliveryChallanDate=date.today().isoformat(),
                  ewayBillNo="1234 5678 9012", ewayBillValidUntil=(date.today() + timedelta(days=3)).isoformat(), expectedArrival=(date.today() + timedelta(days=2)).isoformat(), driverName="Ramesh", driverPhone="+91 98765 43210", grossWeightKg="512.5")
    assert r.status_code == 201, r.text
    d = r.json()["dispatches"][0]
    assert d["number"] == f"{world['po']['number']}/S1" and d["status"] == "in_transit"
    assert d["vehicleNo"] == "MH12 AB 1234" and d["ewayBillNo"] == "123456789012" and d["packingListNo"] == "PL-55" and d["deliveryChallanNo"] == "DC-909" and d["grossWeightKg"] == "512.500000"
    assert [(l["sku"] is not None, l["quantity"]) for l in d["lines"]] == [(True, "40.000000"), (True, "4.000000")] and d["warning"] is None
    room = {x["poLineId"]: x["canDispatch"] for x in r.json()["dispatchable"]}
    assert room[world["po"]["lines"][0]["id"]] == "60.000000" and room[world["po"]["lines"][1]["id"]] == "6.000000"
    listed = client.get("/api/v1/purchase-orders", headers=world["buyer"], params={"q": world["po"]["number"]}).json()["data"][0]
    assert listed["dispatchStatus"] == "in_transit" and listed["inTransitCount"] == 1


def test_dispatch_validation_reports_everything(client, world):
    r = _dispatch(client, world, "500", vehicleNo="!!", ewayBillNo="123", driverPhone="abc", dispatchDate=(date.today() + timedelta(days=3)).isoformat())
    assert r.status_code == 422 and r.json()["code"] == "DISPATCH_VALIDATION_FAILED"
    fields = {e["field"] for e in r.json()["meta"]["errors"]}
    assert {"vehicleNo", "ewayBillNo", "driverPhone", "dispatchDate"} <= fields
    r = _dispatch(client, world, "500")
    assert "more than can still be shipped" in r.json()["detail"]
    bad = client.post(_url(world, "/dispatches"), headers=world["buyer"], json={"dispatchDate": date.today().isoformat(), "lines": [{"poLineId": str(uuid.uuid4()), "quantity": "1"}]})
    assert bad.status_code == 422
    assert _dispatch(client, world, "10", ewayBillValidUntil=date.today().isoformat()).json()["meta"]["errors"][0]["field"] == "ewayBillNo"


def test_partial_shipments_share_the_order_and_cancelling_frees_the_room(client, world):
    first = _dispatch(client, world, "70").json()
    assert _dispatch(client, world, "40").status_code == 422  # only 30 left on the road-adjusted balance
    second = _dispatch(client, world, "30")
    assert second.status_code == 201 and [d["number"][-2:] for d in second.json()["dispatches"]] == ["S1", "S2"]
    d1 = first["dispatches"][0]
    gone = client.post(_url(world, f"/dispatches/{d1['id']}/cancel"), headers=world["buyer"], json={"reason": "Vendor re-packed the load"})
    assert gone.status_code == 200 and {d["number"][-2:]: d["status"] for d in gone.json()["dispatches"]} == {"S1": "cancelled", "S2": "in_transit"}
    assert _dispatch(client, world, "70").status_code == 201  # the 70 is available again


def test_e_way_bill_warning_for_valuable_consignments(client, world):
    # 100 kg at 600 + 18% = 70,800: over the e-way bill threshold.
    d = _dispatch(client, world, "100").json()["dispatches"][0]
    assert d["warning"] and "e-way bill" in d["warning"]
    url = _url(world, f"/dispatches/{d['id']}")
    fixed = client.patch(url, headers=world["buyer"], json={"ewayBillNo": "987654321098", "ewayBillValidUntil": (date.today() + timedelta(days=2)).isoformat()})
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["dispatches"][0]["warning"] is None and fixed.json()["dispatches"][0]["ewayBillNo"] == "987654321098"
    # A dispatch of little value carries no warning.
    small = client.post(_url(world, "/dispatches"), headers=world["buyer"], json={"dispatchDate": date.today().isoformat(), "lines": [{"poLineId": world["po"]["lines"][1]["id"], "quantity": "5"}]})
    assert small.json()["dispatches"][1]["warning"] is None


def test_dispatch_documents_attach_to_the_shipment(client, world):
    d = _dispatch(client, world).json()["dispatches"][0]
    for typ in ("packing_list", "delivery_challan", "eway_bill", "transport_document"):
        r = client.post(_url(world, "/documents"), headers=world["buyer"], json={"docType": typ, "filename": f"{typ}.pdf", "contentType": "application/pdf", "contentBase64": PDF, "dispatchId": d["id"]})
        assert r.status_code == 201, r.text
        assert r.json()["stage"] == "dispatch" and r.json()["dispatchId"] == d["id"]
    wrong = client.post(_url(world, "/documents"), headers=world["buyer"], json={"docType": "proforma_invoice", "filename": "x.pdf", "contentType": "application/pdf", "contentBase64": PDF, "dispatchId": d["id"]})
    assert wrong.json()["code"] == "DOC_TYPE_INVALID"
    t = client.get(_url(world, "/vendor-tracking"), headers=world["buyer"]).json()
    assert [x["docType"] for x in t["dispatches"][0]["documents"]] == ["packing_list", "delivery_challan", "eway_bill", "transport_document"] and t["documents"] == []


def test_edit_deliver_and_state_rules(client, world):
    d = _dispatch(client, world, "20").json()["dispatches"][0]
    url = _url(world, f"/dispatches/{d['id']}")
    edited = client.patch(url, headers=world["buyer"], json={"lrNo": "LR-CORRECTED", "lines": [{"poLineId": world["po"]["lines"][0]["id"], "quantity": "25"}]}).json()["dispatches"][0]
    assert edited["lrNo"] == "LR-CORRECTED" and edited["lines"][0]["quantity"] == "25.000000" and edited["transporter"] == "Blue Dart Freight"
    done = client.post(url + "/deliver", headers=world["buyer"], json={"notes": "Unloaded at gate 2"})
    assert done.status_code == 200 and done.json()["dispatches"][0]["status"] == "delivered" and "Unloaded" in done.json()["dispatches"][0]["notes"]
    assert client.patch(url, headers=world["buyer"], json={"lrNo": "X"}).json()["code"] == "DISPATCH_INVALID_STATE"
    assert client.post(url + "/cancel", headers=world["buyer"], json={"reason": "too late now"}).json()["code"] == "DISPATCH_INVALID_STATE"
    assert client.post(url + "/cancel", headers=world["buyer"], json={"reason": "x"}).status_code == 400


def test_receipts_against_the_po_settle_shipments_and_reverse(client, world):
    """Goods receipts share out over shipments oldest-first: covered shipments become delivered, and go back if a GRN is undone."""
    from app.models.po_line import PoLine
    from app.services import po_vendor_repo

    d1 = _dispatch(client, world, "60").json()["dispatches"][0]
    d2 = _dispatch(client, world, "40").json()["dispatches"][1]
    line_id = uuid.UUID(world["po"]["lines"][0]["id"])
    tenant = uuid.UUID(world["po"]["lines"][0]["id"]) and __import__("app.models.purchase_order", fromlist=["PurchaseOrder"]).PurchaseOrder.query.filter_by(id=uuid.UUID(world["po"]["id"])).one().tenant_id
    po_id = uuid.UUID(world["po"]["id"])

    def set_received(qty):
        PoLine.query.filter_by(id=line_id).update({"received_qty": qty}, synchronize_session=False)
        SessionLocal.commit()
        po_vendor_repo.reconcile(tenant, po_id)
        SessionLocal.commit()
        t = client.get(_url(world, "/vendor-tracking"), headers=world["buyer"]).json()
        return {x["number"][-2:]: x["status"] for x in t["dispatches"]}

    assert set_received(59) == {"S1": "in_transit", "S2": "in_transit"}
    assert set_received(60) == {"S1": "delivered", "S2": "in_transit"}
    assert set_received(100) == {"S1": "delivered", "S2": "delivered"}
    assert set_received(30) == {"S1": "in_transit", "S2": "in_transit"}  # a GRN was cancelled
    # A shipment marked delivered by hand stays delivered, but still uses up its share of what was received.
    client.post(_url(world, f"/dispatches/{d1['id']}/deliver"), headers=world["buyer"], json={})
    assert set_received(40) == {"S1": "delivered", "S2": "in_transit"}
    assert set_received(100) == {"S1": "delivered", "S2": "delivered"}
    assert d2["number"].endswith("S2")
