"""New test coverage for the GRN receiving domain port (no direct
original-repo equivalent - see test_orders.py's docstring for the same
note). Covers the full physical intake loop this session's earlier tests
had to fake: create a PO, receive against it (GRN under_qc), QC-decide
(lot-level, non-serialised), auto-post on QC completion, verify the PO's
received quantities and the stock ledger both updated, then put the
accepted stock away into a real bin. Also covers a serialised (UNIT-uom)
line producing one InventoryItem per piece, and the cancel-after-post
reversal. All against a real Postgres.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.core.db import SessionLocal


def _auth_headers(client, fresh_admin):
    login = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def _cleanup_grn(grn_id: str) -> None:
    from app.models.grn import Grn
    from app.models.grn_line import GrnLine
    from app.models.inventory_item import InventoryItem
    from app.models.putaway_task import PutawayTask
    from app.models.stock_ledger import StockLedger

    gid = uuid.UUID(grn_id)
    PutawayTask.query.filter_by(grn_id=gid).delete(synchronize_session=False)
    StockLedger.query.filter(StockLedger.reference_id.like(f"{gid}%")).delete(synchronize_session=False)
    InventoryItem.query.filter_by(grn_id=gid).delete(synchronize_session=False)
    GrnLine.query.filter_by(grn_id=gid).delete(synchronize_session=False)
    Grn.query.filter_by(id=gid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_po(po_id: str) -> None:
    from app.models.grn import Grn
    from app.models.po_approval_record import PoApprovalRecord
    from app.models.po_line import PoLine
    from app.models.po_receipt import PoReceipt
    from app.models.purchase_order import PurchaseOrder

    pid = uuid.UUID(po_id)
    for grn in Grn.query.filter_by(po_id=pid).all():
        _cleanup_grn(str(grn.id))
    PoReceipt.query.filter_by(po_id=pid).delete(synchronize_session=False)
    PoApprovalRecord.query.filter_by(po_id=pid).delete(synchronize_session=False)
    PoLine.query.filter_by(po_id=pid).delete(synchronize_session=False)
    PurchaseOrder.query.filter_by(id=pid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_vendor(vendor_id: str) -> None:
    from app.models.party import Party
    from app.models.party_version import PartyVersion
    from app.models.purchase_order import PurchaseOrder

    vid = uuid.UUID(vendor_id)
    for po in PurchaseOrder.query.filter_by(vendor_id=vid).all():
        _cleanup_po(str(po.id))
    PartyVersion.query.filter_by(party_id=vid).delete(synchronize_session=False)
    Party.query.filter_by(id=vid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_warehouse(warehouse_id: str) -> None:
    from app.models.location import Location
    from app.models.reservation import Reservation
    from app.models.stock_balance import StockBalance
    from app.models.stock_ledger import StockLedger
    from app.models.warehouse import Warehouse

    wid = uuid.UUID(warehouse_id)
    Reservation.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
    StockLedger.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
    StockBalance.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
    Location.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
    Warehouse.query.filter_by(id=wid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_product(product_id: str) -> None:
    from app.models.po_line import PoLine
    from app.models.product import Product
    from app.models.reservation import Reservation
    from app.models.stock_balance import StockBalance
    from app.models.stock_ledger import StockLedger

    pid = uuid.UUID(product_id)
    PoLine.query.filter_by(product_id=pid).delete(synchronize_session=False)
    Reservation.query.filter_by(product_id=pid).delete(synchronize_session=False)
    StockLedger.query.filter_by(product_id=pid).delete(synchronize_session=False)
    StockBalance.query.filter_by(product_id=pid).delete(synchronize_session=False)
    Product.query.filter_by(id=pid).delete(synchronize_session=False)
    SessionLocal.commit()


def _setup(client, headers, *, uom: str = "KG", product_type: str = "raw_material"):
    vendor = client.post("/api/v1/parties", headers=headers, json={"legalName": f"GRN Test Vendor {uuid.uuid4().hex[:8]}", "type": "vendor"}).json()
    from app.models.party import Party

    Party.query.filter_by(id=uuid.UUID(vendor["id"])).update({"status": "active"}, synchronize_session=False)
    SessionLocal.commit()

    warehouse = client.post("/api/v1/warehouses", headers=headers, json={"name": f"GRN Test WH {uuid.uuid4().hex[:6]}"}).json()
    product = client.post(
        "/api/v1/products",
        headers=headers,
        json={"sku": f"GRN-TEST-{uuid.uuid4().hex[:8].upper()}", "name": f"GRN Test Material {uuid.uuid4().hex[:8]}", "make": "TestCo", "type": product_type, "uom": uom, "purchasable": True},
    ).json()
    po = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={"vendorId": vendor["id"], "warehouseId": warehouse["id"], "expectedDate": "2026-12-01", "lines": [{"productId": product["id"], "quantity": "20", "uom": uom, "unitPrice": "100", "taxCode": "GST0"}]},
    ).json()
    return vendor, warehouse, product, po


def _teardown(vendor, warehouse, product):
    _cleanup_vendor(vendor["id"])
    _cleanup_warehouse(warehouse["id"])
    _cleanup_product(product["id"])


def test_receive_qc_autopost_and_putaway_full_loop(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product, po = _setup(client, headers)
    po_line_id = po["lines"][0]["id"]

    create = client.post(
        "/api/v1/grns",
        headers=headers,
        json={"poId": po["id"], "invoiceNumber": f"INV-{uuid.uuid4().hex[:8]}", "lines": [{"poLineId": po_line_id, "receivedQty": "12"}]},
    )
    assert create.status_code == 201, create.text
    grn = create.json()
    assert grn["status"] == "under_qc"
    grn_line_id = grn["lines"][0]["id"]

    # Lot-level QC: 10 accepted, 2 rejected -> resolves every unit, so the
    # GRN auto-posts to inventory the moment this call completes.
    qc = client.post(
        f"/api/v1/grns/{grn['id']}/qc",
        headers=headers,
        json={"items": [], "lines": [{"lineId": grn_line_id, "acceptedQty": "10", "rejectedQty": "2", "rejectionCode": "DAMAGED", "rejectionNote": "Packaging crushed in transit"}]},
    )
    assert qc.status_code == 200, qc.text
    assert qc.json()["status"] == "posted"

    # PO received quantities updated via procurement_repo.apply_grn_receipt.
    # PoLine.received_qty tracks the *accepted* portion only - rejected is
    # its own separate column - so 10 accepted + 2 rejected here reads back
    # as receivedQty=10, rejectedQty=2 (together, what physically arrived).
    po_after = client.get(f"/api/v1/purchase-orders/{po['id']}", headers=headers).json()
    assert po_after["lines"][0]["receivedQty"] == "10.000000"
    assert po_after["lines"][0]["rejectedQty"] == "2.000000"
    assert po_after["receiptStatus"] == "partial"

    # Stock ledger: accepted -> available, rejected -> quarantine.
    balances = client.get("/api/v1/inventory/balances", headers=headers, params={"productId": product["id"], "warehouseId": warehouse["id"]}).json()["data"]
    by_bucket_totals = {"available": 0.0, "quarantine": 0.0}
    for row in balances:
        by_bucket_totals["available"] += float(row["available"])
        by_bucket_totals["quarantine"] += float(row["quarantine"])
    assert by_bucket_totals["available"] == 10.0
    assert by_bucket_totals["quarantine"] == 2.0

    # Put the accepted stock away into a real bin.
    location = client.post(f"/api/v1/warehouses/{warehouse['id']}/locations", headers=headers, json={"code": "BIN-A1", "type": "bin"}).json()
    putaway = client.post(
        f"/api/v1/grns/{grn['id']}/putaway",
        headers=headers,
        json={"lines": [{"grnLineId": grn_line_id, "toLocationId": location["id"]}]},
    )
    assert putaway.status_code == 201, putaway.text
    assert putaway.json()["moves"][0]["quantity"] == "10.000000"

    putaway_status = client.get(f"/api/v1/grns/{grn['id']}/putaway", headers=headers)
    assert putaway_status.json()["complete"] is True

    _cleanup_grn(grn["id"])
    _teardown(vendor, warehouse, product)


def test_serialised_unit_line_creates_one_inventory_item_per_piece(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product, po = _setup(client, headers, uom="UNIT", product_type="finished_good")
    po_line_id = po["lines"][0]["id"]

    create = client.post(
        "/api/v1/grns",
        headers=headers,
        json={"poId": po["id"], "invoiceNumber": f"INV-{uuid.uuid4().hex[:8]}", "lines": [{"poLineId": po_line_id, "receivedQty": "3"}]},
    )
    assert create.status_code == 201, create.text
    grn = create.json()

    items = client.get(f"/api/v1/grns/{grn['id']}/items", headers=headers)
    assert items.status_code == 200
    assert len(items.json()["data"]) == 3
    assert all(i["kind"] == "piece" and i["status"] == "under_qc" for i in items.json()["data"])

    _cleanup_grn(grn["id"])
    _teardown(vendor, warehouse, product)


def test_over_tolerance_receipt_rejected(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product, po = _setup(client, headers)
    po_line_id = po["lines"][0]["id"]

    # Ordered 20, tolerance is 2% by default (settings.po_receipt_tolerance_percent)
    # - receiving 100 blows well past the ceiling.
    resp = client.post(
        "/api/v1/grns",
        headers=headers,
        json={"poId": po["id"], "invoiceNumber": f"INV-{uuid.uuid4().hex[:8]}", "lines": [{"poLineId": po_line_id, "receivedQty": "100"}]},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "GRN_VALIDATION_FAILED"

    _teardown(vendor, warehouse, product)


def test_cancel_posted_grn_reverses_ledger_and_po(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product, po = _setup(client, headers)
    po_line_id = po["lines"][0]["id"]

    create = client.post(
        "/api/v1/grns",
        headers=headers,
        json={"poId": po["id"], "invoiceNumber": f"INV-{uuid.uuid4().hex[:8]}", "lines": [{"poLineId": po_line_id, "receivedQty": "5"}]},
    )
    grn = create.json()
    grn_line_id = grn["lines"][0]["id"]

    qc = client.post(f"/api/v1/grns/{grn['id']}/qc", headers=headers, json={"items": [], "lines": [{"lineId": grn_line_id, "acceptedQty": "5", "rejectedQty": "0"}]})
    assert qc.json()["status"] == "posted"

    cancel = client.post(f"/api/v1/grns/{grn['id']}/cancel", headers=headers, json={"reason": "Wrong material delivered, returning to vendor"})
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"

    balances = client.get("/api/v1/inventory/balances", headers=headers, params={"productId": product["id"], "warehouseId": warehouse["id"], "includeZero": "true"}).json()["data"]
    available = sum(float(r["available"]) for r in balances)
    assert available == 0.0

    po_after = client.get(f"/api/v1/purchase-orders/{po['id']}", headers=headers).json()
    assert po_after["lines"][0]["receivedQty"] == "0.000000"

    _cleanup_grn(grn["id"])
    _teardown(vendor, warehouse, product)


def test_inventory_item_qr_roundtrip_zip_sheet_and_vendor_qr_guard(client, fresh_admin):
    """Renders an item's QR PNG, then feeds that exact image back through the
    photo-decode endpoint and gets the same Inventory ID back (proving the
    qrcode -> zxing-cpp pipeline end to end), plus the zip/sticker-sheet
    downloads and the vendor-QR guard for a GRN received without it."""
    import base64
    import io
    import zipfile

    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product, po = _setup(client, headers, uom="UNIT", product_type="finished_good")
    grn = client.post(
        "/api/v1/grns",
        headers=headers,
        json={"poId": po["id"], "invoiceNumber": f"INV-{uuid.uuid4().hex[:8]}", "lines": [{"poLineId": po["lines"][0]["id"], "receivedQty": "2"}]},
    ).json()
    items = client.get(f"/api/v1/grns/{grn['id']}/items", headers=headers).json()["data"]
    assert len(items) == 2
    item = items[0]

    qr = client.get(f"/api/v1/inventory-items/{item['id']}/qr", headers=headers)
    assert qr.status_code == 200 and qr.headers["content-type"] == "image/png"
    assert qr.content[:8] == b"\x89PNG\r\n\x1a\n"

    decoded = client.post("/api/v1/inventory-items/decode-qr", headers=headers, json={"imageBase64": base64.b64encode(qr.content).decode()})
    assert decoded.status_code == 200, decoded.text
    assert decoded.json()["id"] == item["id"] and decoded.json()["inventoryId"] == item["inventoryId"]

    labelled = client.get(f"/api/v1/inventory-items/{item['id']}/qr", headers=headers, params={"label": "1"})
    assert labelled.status_code == 200 and len(labelled.content) > len(qr.content) // 2

    not_a_qr = client.post("/api/v1/inventory-items/decode-qr", headers=headers, json={"imageBase64": base64.b64encode(b"nope").decode()})
    assert not_a_qr.status_code == 400 and not_a_qr.json()["code"] == "QR_IMAGE_INVALID"

    archive = client.get(f"/api/v1/grns/{grn['id']}/qr-codes", headers=headers)
    assert archive.status_code == 200
    assert sorted(zipfile.ZipFile(io.BytesIO(archive.content)).namelist()) == sorted(f"{i['inventoryId']}.png" for i in items)

    sheet = client.get(f"/api/v1/grns/{grn['id']}/qr-codes/pdf", headers=headers)
    assert sheet.status_code == 200
    assert all(i["inventoryId"] in sheet.text for i in items)  # default engine: HTML sheet

    vendor_qr = client.post(f"/api/v1/inventory-items/{item['id']}/vendor-qr", headers=headers, json={"vendorInventoryId": "VENDOR-1"})
    assert vendor_qr.status_code == 422 and vendor_qr.json()["code"] == "VENDOR_QR_NOT_ENABLED"

    _cleanup_grn(grn["id"])
    _teardown(vendor, warehouse, product)


def test_a_posted_grn_settles_the_vendor_shipment_and_cancelling_it_reopens_it(client, fresh_admin):
    """PO -> vendor dispatch documentation -> GRN: goods received against the PO mark the matching shipment delivered."""
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product, po = _setup(client, headers)
    po_line_id = po["lines"][0]["id"]
    dispatch = client.post(f"/api/v1/purchase-orders/{po['id']}/dispatches", headers=headers, json={"dispatchDate": date.today().isoformat(), "transporter": "Test Carrier", "lines": [{"poLineId": po_line_id, "quantity": "5"}]})
    assert dispatch.status_code == 201, dispatch.text

    def shipment_status():
        return client.get(f"/api/v1/purchase-orders/{po['id']}/vendor-tracking", headers=headers).json()["dispatches"][0]["status"]

    assert shipment_status() == "in_transit"
    grn = client.post("/api/v1/grns", headers=headers, json={"poId": po["id"], "invoiceNumber": f"INV-{uuid.uuid4().hex[:8]}", "lines": [{"poLineId": po_line_id, "receivedQty": "5"}]}).json()
    assert shipment_status() == "in_transit"  # still with QC
    qc = client.post(f"/api/v1/grns/{grn['id']}/qc", headers=headers, json={"items": [], "lines": [{"lineId": grn['lines'][0]['id'], "acceptedQty": "5", "rejectedQty": "0"}]})
    assert qc.json()["status"] == "posted"
    assert shipment_status() == "delivered"
    assert client.get(f"/api/v1/purchase-orders/{po['id']}/vendor-tracking", headers=headers).json()["dispatches"][0]["autoDelivered"] is True

    assert client.post(f"/api/v1/grns/{grn['id']}/cancel", headers=headers, json={"reason": "Wrong material delivered, returning to vendor"}).status_code == 200
    assert shipment_status() == "in_transit"

    _cleanup_grn(grn["id"])
    _teardown(vendor, warehouse, product)
