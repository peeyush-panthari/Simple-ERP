"""New test coverage for the procurement (purchase orders) domain port (no
direct original-repo equivalent - see test_orders.py's docstring for the
same note). Covers PO creation with GST computation (auto-issued, no draft
stage), cancel-blocked-after-receipt, short-close, and the amend->successor
flow, all against a real Postgres. GRN receiving itself isn't ported yet
(see the router's module docstring), so "already received" is simulated by
writing PoLine.received_qty directly, the same way test_orders.py seeds
stock via inventory_ledger.post() directly ahead of the warehouse domain
existing.
"""

from __future__ import annotations

import uuid

from app.core.db import SessionLocal


def _auth_headers(client, fresh_admin):
    login = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def _cleanup_po(po_id: str) -> None:
    from app.models.po_approval_record import PoApprovalRecord
    from app.models.po_line import PoLine
    from app.models.po_receipt import PoReceipt
    from app.models.po_revision import PoRevision
    from app.models.purchase_order import PurchaseOrder

    pid = uuid.UUID(po_id)
    PoReceipt.query.filter_by(po_id=pid).delete(synchronize_session=False)
    PoApprovalRecord.query.filter_by(po_id=pid).delete(synchronize_session=False)
    PoRevision.query.filter_by(po_id=pid).delete(synchronize_session=False)
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
    from app.models.warehouse import Warehouse

    wid = uuid.UUID(warehouse_id)
    Location.query.filter_by(warehouse_id=wid).delete(synchronize_session=False)
    Warehouse.query.filter_by(id=wid).delete(synchronize_session=False)
    SessionLocal.commit()


def _cleanup_product(product_id: str) -> None:
    from app.models.po_line import PoLine
    from app.models.product import Product

    pid = uuid.UUID(product_id)
    PoLine.query.filter_by(product_id=pid).delete(synchronize_session=False)
    Product.query.filter_by(id=pid).delete(synchronize_session=False)
    SessionLocal.commit()


def _setup(client, headers, *, activate_vendor: bool = True):
    """Vendor + warehouse + purchasable raw-material product, via the real API.

    New parties are created in the "draft" lifecycle status (see
    party_lifecycle.py) - _validate_po requires an "active" vendor, and
    reaching "active" through the real activation flow needs a billing
    address, payment terms, currency and a contact email, none of which
    this test cares about. Set directly via the DB, the same shortcut
    test_orders.py's `customer` fixture takes.
    """
    vendor = client.post(
        "/api/v1/parties",
        headers=headers,
        json={"legalName": f"PO Test Vendor {uuid.uuid4().hex[:8]}", "type": "vendor", "paymentTerms": "Net 45"},
    ).json()
    if activate_vendor:
        from app.models.party import Party

        Party.query.filter_by(id=uuid.UUID(vendor["id"])).update({"status": "active"}, synchronize_session=False)
        SessionLocal.commit()
        vendor["status"] = "active"
    warehouse = client.post("/api/v1/warehouses", headers=headers, json={"name": f"PO Test WH {uuid.uuid4().hex[:6]}"}).json()
    product = client.post(
        "/api/v1/products",
        headers=headers,
        json={"sku": f"PO-TEST-{uuid.uuid4().hex[:8].upper()}", "name": f"PO Test Material {uuid.uuid4().hex[:8]}", "make": "TestCo", "type": "raw_material", "uom": "KG", "purchasable": True},
    ).json()
    return vendor, warehouse, product


def test_create_po_computes_igst_and_auto_issues(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product = _setup(client, headers)

    resp = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={
            "vendorId": vendor["id"],
            "warehouseId": warehouse["id"],
            "expectedDate": "2026-12-01",
            "lines": [{"productId": product["id"], "quantity": "10", "uom": "KG", "unitPrice": "500", "taxCode": "GST18"}],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # 10 * 500 = 5000 net, 18% GST = 900 tax. No business entity resolves
    # (no default set up), so seller state is unknown -> inter-state -> IGST.
    assert body["subtotal"] == "5000.000000"
    assert body["taxTotal"] == "900.000000"
    assert body["total"] == "5900.000000"
    assert body["igst"] == "900.000000"
    assert body["cgst"] == "0.000000"
    assert body["status"] == "issued"  # no draft stage, matches orders.py's auto-confirm

    _cleanup_po(body["id"])
    _cleanup_vendor(vendor["id"])
    _cleanup_warehouse(warehouse["id"])
    _cleanup_product(product["id"])


def test_cancel_blocked_once_received(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product = _setup(client, headers)

    create = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={"vendorId": vendor["id"], "warehouseId": warehouse["id"], "expectedDate": "2026-12-01", "lines": [{"productId": product["id"], "quantity": "5", "uom": "KG", "unitPrice": "100", "taxCode": "GST0"}]},
    )
    po_id = create.json()["id"]

    # Simulate a GRN receipt having posted against this line (GRN receiving
    # itself isn't ported yet - see the router's module docstring).
    from app.models.po_line import PoLine

    line = PoLine.query.filter_by(po_id=uuid.UUID(po_id)).first()
    line.received_qty = "2"
    line.status = "partial"
    SessionLocal.commit()

    cancel = client.post(f"/api/v1/purchase-orders/{po_id}/cancel", headers=headers, json={"reason": "Testing cancel-after-receipt block"})
    assert cancel.status_code == 422
    assert cancel.json()["code"] == "RECEIPT_EXISTS"

    _cleanup_po(po_id)
    _cleanup_vendor(vendor["id"])
    _cleanup_warehouse(warehouse["id"])
    _cleanup_product(product["id"])


def test_short_close_requires_outstanding_balance(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product = _setup(client, headers)

    create = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={"vendorId": vendor["id"], "warehouseId": warehouse["id"], "expectedDate": "2026-12-01", "lines": [{"productId": product["id"], "quantity": "5", "uom": "KG", "unitPrice": "100", "taxCode": "GST0"}]},
    )
    po_id = create.json()["id"]

    # Fully received already - nothing outstanding to short-close.
    from app.models.po_line import PoLine

    line = PoLine.query.filter_by(po_id=uuid.UUID(po_id)).first()
    line.received_qty = "5"
    line.status = "closed"
    SessionLocal.commit()

    short_close = client.post(f"/api/v1/purchase-orders/{po_id}/short-close", headers=headers, json={"reason": "Testing short-close guard"})
    assert short_close.status_code == 422
    assert short_close.json()["code"] == "PO_FULLY_RECEIVED"

    _cleanup_po(po_id)
    _cleanup_vendor(vendor["id"])
    _cleanup_warehouse(warehouse["id"])
    _cleanup_product(product["id"])


def test_amend_creates_successor_and_closes_original(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product = _setup(client, headers)

    create = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={"vendorId": vendor["id"], "warehouseId": warehouse["id"], "expectedDate": "2026-12-01", "lines": [{"productId": product["id"], "quantity": "5", "uom": "KG", "unitPrice": "100", "taxCode": "GST0"}]},
    )
    po_id = create.json()["id"]
    original_number = create.json()["number"]

    amend = client.post(
        f"/api/v1/purchase-orders/{po_id}/amend",
        headers=headers,
        json={"charges": "50", "reason": "Vendor renegotiated freight charges"},
    )
    assert amend.status_code == 201, amend.text
    successor = amend.json()
    assert successor["number"] == original_number  # same document number, new revision
    assert successor["revision"] == 1
    assert successor["charges"] == "50.000000"

    original = client.get(f"/api/v1/purchase-orders/{po_id}", headers=headers)
    assert original.json()["status"] == "closed"

    _cleanup_po(successor["id"])
    _cleanup_po(po_id)
    _cleanup_vendor(vendor["id"])
    _cleanup_warehouse(warehouse["id"])
    _cleanup_product(product["id"])


def test_po_validation_rejects_inactive_vendor(client, fresh_admin):
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product = _setup(client, headers, activate_vendor=False)
    # New vendors are "draft" by default, not "active" - see party lifecycle.

    resp = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={"vendorId": vendor["id"], "warehouseId": warehouse["id"], "expectedDate": "2026-12-01", "lines": [{"productId": product["id"], "quantity": "1", "uom": "KG", "unitPrice": "10", "taxCode": "GST0"}]},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "PO_VALIDATION_FAILED"

    _cleanup_vendor(vendor["id"])
    _cleanup_warehouse(warehouse["id"])
    _cleanup_product(product["id"])


def test_po_pdf_download_and_email_dispatch_records_state(client, fresh_admin):
    """PDF download renders fresh from the PO's current data (HTML tier by
    default); send-email with no vendor email on file records a failed
    email_state instead of raising, and never un-issues the PO."""
    headers = _auth_headers(client, fresh_admin)
    vendor, warehouse, product = _setup(client, headers)
    create = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={"vendorId": vendor["id"], "warehouseId": warehouse["id"], "expectedDate": "2026-12-01", "lines": [{"productId": product["id"], "quantity": "5", "uom": "KG", "unitPrice": "100", "taxCode": "GST0"}]},
    )
    po = create.json()

    pdf = client.get(f"/api/v1/purchase-orders/{po['id']}/pdf", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert po["number"] in pdf.text
    assert pdf.headers["content-disposition"] == f'attachment; filename="{po["number"]}.html"'

    send = client.post(f"/api/v1/purchase-orders/{po['id']}/send-email", headers=headers, json={})
    assert send.status_code == 200, send.text
    assert send.json()["emailState"] == "failed" and "No vendor email" in send.json()["error"]

    after = client.get(f"/api/v1/purchase-orders/{po['id']}", headers=headers).json()
    assert after["status"] == "issued"

    _cleanup_po(po["id"])
    _cleanup_vendor(vendor["id"])
    _cleanup_warehouse(warehouse["id"])
    _cleanup_product(product["id"])
