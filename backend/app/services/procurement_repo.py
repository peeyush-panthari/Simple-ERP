"""PO queries + API projections. Ported from
backend_py/app/services/procurement_repo.py - `apply_grn_receipt`/
`reverse_grn_receipt` are the exact integration points the GRN domain will
call into once it's ported (not yet - see the migration plan's phasing);
kept here now since they belong with the rest of this file and don't depend
on anything GRN-specific beyond the already-ported PoReceipt model.
"""

from __future__ import annotations

import uuid

from sqlalchemy import distinct, func

from app.core.config import settings
from app.core.db import session
from app.core.errors import not_found
from app.core.money import decimal_str, to_decimal
from app.models.po_line import PoLine
from app.models.po_receipt import PoReceipt
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.core import audit as audit_service
from app.services import po_vendor_repo
from app.services.po_state import is_receivable
from app.services.po_tolerance import LineReceipt, ReceiptDelta, assert_within_tolerance, document_receipt_status, line_receipt_status, open_quantity


def find_po(tenant_id: uuid.UUID, po_id: uuid.UUID) -> PurchaseOrder | None:
    return PurchaseOrder.query.filter_by(tenant_id=tenant_id, id=po_id).first()


def require_po(tenant_id: uuid.UUID, po_id: uuid.UUID) -> PurchaseOrder:
    po = find_po(tenant_id, po_id)
    if not po:
        raise not_found("Purchase order")
    return po


def lock_po(tenant_id: uuid.UUID, po_id: uuid.UUID) -> PurchaseOrder | None:
    """Row-locks the header so concurrent receipts and approvals serialise."""
    return session.query(PurchaseOrder).filter_by(tenant_id=tenant_id, id=po_id).with_for_update().first()


def lines_of(po_id: uuid.UUID) -> list[PoLine]:
    return PoLine.query.filter_by(po_id=po_id).order_by(PoLine.line_no).all()


def _to_receipt_line(line: PoLine) -> LineReceipt:
    return LineReceipt(line_id=str(line.id), sku=line.sku, ordered_qty=decimal_str(line.quantity), received_qty=decimal_str(line.received_qty), rejected_qty=decimal_str(line.rejected_qty))


# ---- API projections --------------------------------------------------------


def to_po_api(row: PurchaseOrder, lines: list[PoLine] | None = None, *, outstanding_value: str | None = None) -> dict:
    result = {
        "id": str(row.id),
        "number": row.number,
        "revision": row.revision,
        "supersedesId": str(row.supersedes_id) if row.supersedes_id else None,
        "vendorId": str(row.vendor_id),
        "vendorName": row.vendor_name,
        "warehouseId": str(row.warehouse_id),
        "warehouseCode": row.warehouse_code,
        "businessEntityId": str(row.business_entity_id) if row.business_entity_id else None,
        "status": row.status,
        "poDate": row.po_date.isoformat() if row.po_date else None,
        "expectedDate": row.expected_date.isoformat() if row.expected_date else None,
        "currency": row.currency,
        "exchangeRate": decimal_str(row.exchange_rate),
        "subtotal": decimal_str(row.subtotal),
        "taxTotal": decimal_str(row.tax_total),
        "cgst": decimal_str(row.cgst),
        "sgst": decimal_str(row.sgst),
        "igst": decimal_str(row.igst),
        "charges": decimal_str(row.charges),
        "total": decimal_str(row.total),
        "paymentTerms": row.payment_terms,
        "paymentMode": row.payment_mode,
        "incoterms": row.incoterms,
        "notes": row.notes,
        "approvalTier": row.approval_tier,
        "approvedBy": row.approved_by,
        "approvedAt": row.approved_at.isoformat() if row.approved_at else None,
        "issuedAt": row.issued_at.isoformat() if row.issued_at else None,
        "emailState": row.email_state,
        "emailSentAt": row.email_sent_at.isoformat() if row.email_sent_at else None,
        "emailError": row.email_error,
        "pdfDocumentId": row.pdf_document_id,
        "receiptStatus": row.receipt_status,
        "ackStatus": row.ack_status,
        "ackDate": row.ack_date.isoformat() if row.ack_date else None,
        "ackRef": row.ack_ref,
        "ackConfirmedDate": row.ack_confirmed_date.isoformat() if row.ack_confirmed_date else None,
        "ackNotes": row.ack_notes,
        "outstandingValue": outstanding_value,
        "cancelledReason": row.cancelled_reason,
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }
    if lines is not None:
        product_ids = {l.product_id for l in lines}
        products_by_id = (
            {p.id: p for p in Product.query.filter(Product.tenant_id == row.tenant_id, Product.id.in_(product_ids)).all()}
            if product_ids
            else {}
        )
        result["lines"] = [
            to_line_api(l, products_by_id[l.product_id].batch_tracked if l.product_id in products_by_id else False, products_by_id[l.product_id].name if l.product_id in products_by_id else None)
            for l in lines
        ]
    return result


def to_line_api(line: PoLine, batch_tracked: bool = False, product_name: str | None = None) -> dict:
    return {
        "id": str(line.id),
        "lineNo": line.line_no,
        "productId": str(line.product_id),
        "sku": line.sku,
        "productName": product_name,
        "description": line.description,
        "quantity": decimal_str(line.quantity),
        "uom": line.uom,
        "unitPrice": decimal_str(line.unit_price),
        "discount": decimal_str(line.discount),
        "taxCode": line.tax_code,
        "taxRate": decimal_str(line.tax_rate),
        "netAmount": decimal_str(line.net_amount),
        "taxAmount": decimal_str(line.tax_amount),
        "grossAmount": decimal_str(line.gross_amount),
        "expectedDate": line.expected_date.isoformat() if line.expected_date else None,
        "receivedQty": decimal_str(line.received_qty),
        "rejectedQty": decimal_str(line.rejected_qty),
        "status": line.status,
        "batchTracked": batch_tracked,
    }


# ---- direct-call equivalent of /internal/purchase-orders/:id/receivable -----


def get_receivable_po(tenant_id: uuid.UUID, po_id: uuid.UUID) -> dict | None:
    po = find_po(tenant_id, po_id)
    if not po:
        return None
    lines = lines_of(po_id)
    product_ids = {l.product_id for l in lines}
    batch_tracked_by_product = (
        dict(session.query(Product.id, Product.batch_tracked).filter(Product.tenant_id == tenant_id, Product.id.in_(product_ids)).all())
        if product_ids
        else {}
    )
    return {
        "id": str(po.id),
        "number": po.number,
        "status": po.status,
        "receivable": is_receivable(po.status),
        "vendorId": str(po.vendor_id),
        "vendorName": po.vendor_name,
        "warehouseId": str(po.warehouse_id),
        "warehouseCode": po.warehouse_code,
        "tolerancePercent": settings.po_receipt_tolerance_percent,
        "currency": po.currency,
        "lines": [
            {
                "id": str(l.id),
                "productId": str(l.product_id),
                "sku": l.sku,
                "uom": l.uom,
                "orderedQty": decimal_str(l.quantity),
                "receivedQty": decimal_str(l.received_qty),
                "rejectedQty": decimal_str(l.rejected_qty),
                "openQty": decimal_str(open_quantity(_to_receipt_line(l))),
                "unitPrice": decimal_str(l.unit_price),
                "taxCode": l.tax_code,
                "status": l.status,
                "batchTracked": bool(batch_tracked_by_product.get(l.product_id, False)),
            }
            for l in lines
        ],
    }


def get_open_document_count(tenant_id: uuid.UUID, product_id: uuid.UUID) -> int:
    """Direct-call equivalent of /internal/open-documents - product's
    deprecate-check dependency."""
    return (
        session.query(func.count(distinct(PurchaseOrder.id)))
        .join(PoLine, PoLine.po_id == PurchaseOrder.id)
        .filter(
            PurchaseOrder.tenant_id == tenant_id,
            PoLine.product_id == product_id,
            PurchaseOrder.status.in_(("draft", "pending_approval", "approved", "issued", "partially_received")),
        )
        .scalar()
        or 0
    )


# ---- direct-call equivalent of procurement's GRNPosted consumer -------------


def apply_grn_receipt(tenant_id: uuid.UUID, payload: dict) -> None:
    """Warehouse owns the goods receipt; procurement owns what it means for the
    PO. Idempotent through po_receipts: a retried call cannot double-count a
    receipt (each (grn_id, po_line_id) pair is claimed at most once)."""
    po = lock_po(tenant_id, payload["poId"])
    if not po:
        return

    lines = lines_of(payload["poId"])
    by_id = {str(l.id): l for l in lines}
    tolerance = settings.po_receipt_tolerance_percent
    applied = 0

    for incoming in payload["lines"]:
        line = by_id.get(str(incoming["poLineId"]))
        if not line:
            continue

        existing = PoReceipt.query.filter_by(grn_id=payload["grnId"], po_line_id=line.id).first()
        if existing:
            continue
        session.add(
            PoReceipt(
                tenant_id=tenant_id,
                po_id=payload["poId"],
                po_line_id=line.id,
                grn_id=payload["grnId"],
                accepted_qty=incoming["acceptedQty"],
                rejected_qty=incoming["rejectedQty"],
            )
        )
        session.flush()

        assert_within_tolerance(
            _to_receipt_line(line),
            ReceiptDelta(line_id=str(line.id), accepted_qty=incoming["acceptedQty"], rejected_qty=incoming["rejectedQty"]),
            tolerance,
        )

        received = to_decimal(line.received_qty) + to_decimal(incoming["acceptedQty"])
        rejected = to_decimal(line.rejected_qty) + to_decimal(incoming["rejectedQty"])
        status = line_receipt_status(LineReceipt(line_id=str(line.id), sku=line.sku, ordered_qty=decimal_str(line.quantity), received_qty=decimal_str(received), rejected_qty=decimal_str(rejected)), tolerance)

        line.received_qty = received
        line.rejected_qty = rejected
        line.status = "closed" if status == "full" else ("partial" if status == "partial" else "open")
        applied += 1

    if not applied:
        return

    receipt_status = document_receipt_status([_to_receipt_line(l) for l in lines], tolerance)
    next_status = "received" if receipt_status == "full" else ("partially_received" if receipt_status == "partial" else po.status)

    po.receipt_status = receipt_status
    po.status = next_status
    session.flush()
    po_vendor_repo.reconcile(tenant_id, payload["poId"])

    audit_service.audit(
        tenant_id=tenant_id,
        actor_id=None,
        actor_email=None,
        action="po.receipt.applied",
        entity_type="purchase-order",
        entity_id=str(payload["poId"]),
        meta={"grn": payload["grnNumber"], "receiptStatus": receipt_status, "status": next_status, "linesApplied": applied},
    )


def reverse_grn_receipt(tenant_id: uuid.UUID, grn_id: uuid.UUID) -> None:
    """Undoes apply_grn_receipt()'s effect on the PO - used when cancelling an
    already-posted GRN."""
    receipts = PoReceipt.query.filter_by(tenant_id=tenant_id, grn_id=grn_id).all()
    if not receipts:
        return

    po = lock_po(tenant_id, receipts[0].po_id)
    if not po:
        return

    lines = {l.id: l for l in lines_of(po.id)}
    tolerance = settings.po_receipt_tolerance_percent

    for r in receipts:
        line = lines.get(r.po_line_id)
        if line:
            line.received_qty = to_decimal(line.received_qty) - to_decimal(r.accepted_qty)
            line.rejected_qty = to_decimal(line.rejected_qty) - to_decimal(r.rejected_qty)
            status = line_receipt_status(_to_receipt_line(line), tolerance)
            line.status = "closed" if status == "full" else ("partial" if status == "partial" else "open")
        session.delete(r)

    receipt_status = document_receipt_status([_to_receipt_line(l) for l in lines.values()], tolerance)
    po.receipt_status = receipt_status
    po.status = "received" if receipt_status == "full" else ("partially_received" if receipt_status == "partial" else "issued")
    session.flush()
    po_vendor_repo.reconcile(tenant_id, po.id)

    audit_service.audit(
        tenant_id=tenant_id,
        actor_id=None,
        actor_email=None,
        action="po.receipt.reversed",
        entity_type="purchase-order",
        entity_id=str(po.id),
        meta={"grnId": str(grn_id), "receiptStatus": receipt_status, "status": po.status},
    )
