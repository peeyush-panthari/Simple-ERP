"""FastAPI router for Vendor Self-Service Collaboration Portal.
Endpoints:
- GET /vendor-summary: Metrics for suppliers
- GET /pos: List purchase orders for vendor review
- POST /pos/{id}/acknowledge: Supplier acknowledges PO & commits ship date
- GET /asns: List Advance Shipping Notices
- POST /asns: Create new ASN manifest with items
- POST /asns/{id}/submit: Confirm and submit ASN
- GET /asns/{id}/packing-slip: Detailed GS1-128 pallet barcode manifest data
- GET /invoices-status: 3-Way match reconciliation status for supplier invoices
"""
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import select, func

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.core.errors import bad_request, not_found
from app.models.ap_invoice import ApInvoice
from app.models.long_term_modules import AdvanceShippingNotice, AsnLine, VendorPortalUser
from app.models.party import Party
from app.models.po_line import PoLine
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1/vendor-portal", tags=["Vendor Portal"])


class AcknowledgePoRequest(BaseModel):
    committed_delivery_date: date
    vendor_notes: Optional[str] = None


class AsnLineItem(BaseModel):
    product_id: uuid.UUID
    shipped_qty: float = Field(..., gt=0)
    vendor_batch_number: str
    mfg_date: Optional[date] = None
    expiry_date: Optional[date] = None


class CreateAsnRequest(BaseModel):
    po_id: uuid.UUID
    vendor_party_id: uuid.UUID
    carrier_name: str
    tracking_number: Optional[str] = None
    vehicle_number: Optional[str] = None
    dispatch_date: date
    estimated_delivery_date: date
    package_count: int = 1
    total_weight_kg: float = 0.0
    notes: Optional[str] = None
    lines: List[AsnLineItem]


@router.get("/vendor-summary")
def get_vendor_summary(
    actor: Annotated[Actor, Depends(require_any_permission("vendor_portal:read", "po:read"))],
    vendor_party_id: Optional[uuid.UUID] = None,
):
    po_query = select(func.count(PurchaseOrder.id)).where(PurchaseOrder.tenant_id == actor["tenant_id"])
    asn_query = select(func.count(AdvanceShippingNotice.id)).where(AdvanceShippingNotice.tenant_id == actor["tenant_id"])
    inv_query = select(func.count(ApInvoice.id)).where(ApInvoice.tenant_id == actor["tenant_id"])

    if vendor_party_id:
        po_query = po_query.where(PurchaseOrder.vendor_id == vendor_party_id)
        asn_query = asn_query.where(AdvanceShippingNotice.vendor_party_id == vendor_party_id)
        inv_query = inv_query.where(ApInvoice.vendor_id == vendor_party_id)

    open_pos = session.execute(
        po_query.where(PurchaseOrder.status.in_(["approved", "issued", "partially_received"]))
    ).scalar() or 0

    active_asns = session.execute(
        asn_query.where(AdvanceShippingNotice.status.in_(["submitted", "in_transit"]))
    ).scalar() or 0

    pending_invoices = session.execute(
        inv_query.where(ApInvoice.status.in_(["draft", "open", "partially_paid"]))
    ).scalar() or 0

    return {
        "open_pos_count": open_pos,
        "active_asns_count": active_asns,
        "pending_invoices_count": pending_invoices,
    }


@router.get("/pos")
def list_vendor_pos(
    actor: Annotated[Actor, Depends(require_any_permission("vendor_portal:read", "po:read"))],
    vendor_party_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = (
        select(PurchaseOrder, Party)
        .join(Party, Party.id == PurchaseOrder.vendor_id)
        .where(PurchaseOrder.tenant_id == actor["tenant_id"])
    )
    if vendor_party_id:
        query = query.where(PurchaseOrder.vendor_id == vendor_party_id)
    orders = list(session.execute(query.order_by(PurchaseOrder.created_at.desc()).limit(limit).offset(offset)).all())

    po_ids = [po.id for po, _ in orders]
    line_counts = {}
    if po_ids:
        counts = session.execute(
            select(PoLine.po_id, func.count(PoLine.id))
            .where(PoLine.po_id.in_(po_ids))
            .group_by(PoLine.po_id)
        ).all()
        line_counts = {p_id: int(c) for p_id, c in counts}

    return {
        "purchase_orders": [
            {
                "id": str(po.id),
                "po_number": po.number,
                "vendor_party_id": str(party.id),
                "vendor_name": party.display_name or party.legal_name,
                "status": po.status,
                "order_date": po.po_date.isoformat() if po.po_date else None,
                "expected_delivery_date": po.expected_date.isoformat() if po.expected_date else None,
                "total_amount": float(po.total or 0),
                "lines_count": line_counts.get(po.id, 0),
            }
            for po, party in orders
        ]
    }


@router.post("/pos/{po_id}/acknowledge")
def acknowledge_po(
    po_id: uuid.UUID,
    req: AcknowledgePoRequest,
    actor: Annotated[Actor, Depends(require_any_permission("vendor_portal:write", "po:write"))],
):
    po = session.execute(
        select(PurchaseOrder).where(PurchaseOrder.tenant_id == actor["tenant_id"], PurchaseOrder.id == po_id)
    ).scalar_one_or_none()
    if not po:
        raise not_found("Purchase order not found")

    po.expected_date = req.committed_delivery_date
    po.ack_status = "acknowledged"
    po.ack_confirmed_date = req.committed_delivery_date
    if req.vendor_notes:
        po.ack_notes = req.vendor_notes
        po.notes = f"Vendor Ack: {req.vendor_notes}\n" + (po.notes or "")
    session.commit()
    return {"message": "Purchase order acknowledged with committed delivery date", "po_number": po.number}


@router.get("/asns")
def list_asns(
    actor: Annotated[Actor, Depends(require_any_permission("vendor_portal:read", "po:read"))],
    vendor_party_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = (
        select(AdvanceShippingNotice, Party, PurchaseOrder)
        .join(Party, Party.id == AdvanceShippingNotice.vendor_party_id)
        .join(PurchaseOrder, PurchaseOrder.id == AdvanceShippingNotice.po_id)
        .where(AdvanceShippingNotice.tenant_id == actor["tenant_id"])
    )
    if vendor_party_id:
        query = query.where(AdvanceShippingNotice.vendor_party_id == vendor_party_id)
    if status:
        query = query.where(AdvanceShippingNotice.status == status)

    asns = list(session.execute(query.order_by(AdvanceShippingNotice.created_at.desc()).limit(limit).offset(offset)).all())
    return {
        "asns": [
            {
                "id": str(asn.id),
                "asn_number": asn.asn_number,
                "po_id": str(po.id),
                "po_number": po.number,
                "vendor_name": party.display_name or party.legal_name,
                "carrier_name": asn.carrier_name,
                "tracking_number": asn.tracking_number,
                "vehicle_number": asn.vehicle_number,
                "dispatch_date": asn.dispatch_date.isoformat(),
                "estimated_delivery_date": asn.estimated_delivery_date.isoformat(),
                "status": asn.status,
                "package_count": asn.package_count,
                "total_weight_kg": float(asn.total_weight_kg),
                "lines_count": len(asn.lines),
            }
            for asn, party, po in asns
        ]
    }


@router.post("/asns")
def create_asn(
    req: CreateAsnRequest,
    actor: Annotated[Actor, Depends(require_any_permission("vendor_portal:write", "po:write"))],
):
    po = session.execute(
        select(PurchaseOrder).where(PurchaseOrder.tenant_id == actor["tenant_id"], PurchaseOrder.id == req.po_id)
    ).scalar_one_or_none()
    if not po:
        raise not_found("Purchase order not found")

    asn_number = next_document_number(actor["tenant_id"], "ASN")

    asn = AdvanceShippingNotice(
        tenant_id=actor["tenant_id"],
        asn_number=asn_number,
        po_id=req.po_id,
        vendor_party_id=req.vendor_party_id,
        carrier_name=req.carrier_name,
        tracking_number=req.tracking_number,
        vehicle_number=req.vehicle_number,
        dispatch_date=req.dispatch_date,
        estimated_delivery_date=req.estimated_delivery_date,
        package_count=req.package_count,
        total_weight_kg=req.total_weight_kg,
        status="submitted",
        notes=req.notes,
    )
    session.add(asn)
    session.flush()

    for line_item in req.lines:
        line = AsnLine(
            tenant_id=actor["tenant_id"],
            asn_id=asn.id,
            product_id=line_item.product_id,
            shipped_qty=line_item.shipped_qty,
            vendor_batch_number=line_item.vendor_batch_number,
            mfg_date=line_item.mfg_date,
            expiry_date=line_item.expiry_date,
        )
        session.add(line)

    session.commit()
    return {"id": str(asn.id), "asn_number": asn.asn_number, "message": "Advance Shipping Notice generated"}


@router.get("/asns/{asn_id}/packing-slip")
def get_asn_packing_slip(
    asn_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("vendor_portal:read", "po:read"))],
):
    asn = session.execute(
        select(AdvanceShippingNotice).where(
            AdvanceShippingNotice.tenant_id == actor["tenant_id"],
            AdvanceShippingNotice.id == asn_id,
        )
    ).scalar_one_or_none()
    if not asn:
        raise not_found("ASN not found")

    po = session.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.tenant_id == actor["tenant_id"],
            PurchaseOrder.id == asn.po_id
        )
    ).scalar_one_or_none()
    vendor = session.execute(
        select(Party).where(
            Party.tenant_id == actor["tenant_id"],
            Party.id == asn.vendor_party_id
        )
    ).scalar_one_or_none()

    lines = list(
        session.execute(
            select(AsnLine, Product)
            .join(Product, Product.id == AsnLine.product_id)
            .where(AsnLine.asn_id == asn_id)
        ).all()
    )

    return {
        "asn_number": asn.asn_number,
        "po_number": po.number if po else "N/A",
        "vendor_name": (vendor.display_name or vendor.legal_name) if vendor else "Supplier",
        "carrier_name": asn.carrier_name,
        "tracking_number": asn.tracking_number,
        "dispatch_date": asn.dispatch_date.isoformat(),
        "package_count": asn.package_count,
        "total_weight_kg": float(asn.total_weight_kg),
        "items": [
            {
                "sku": prod.sku,
                "name": prod.name,
                "shipped_qty": float(l.shipped_qty),
                "batch_number": l.vendor_batch_number,
                "gs1_ai_payload": f"(01){prod.sku[:14]}(10){l.vendor_batch_number}(30){int(l.shipped_qty)}",
                "mfg_date": l.mfg_date.isoformat() if l.mfg_date else None,
                "expiry_date": l.expiry_date.isoformat() if l.expiry_date else None,
            }
            for l, prod in lines
        ],
    }


@router.get("/invoices-status")
def get_invoices_status(
    actor: Annotated[Actor, Depends(require_any_permission("vendor_portal:read", "po:read"))],
    vendor_party_id: Optional[uuid.UUID] = None,
):
    query = (
        select(ApInvoice, Party)
        .join(Party, Party.id == ApInvoice.vendor_id)
        .where(ApInvoice.tenant_id == actor["tenant_id"])
    )
    if vendor_party_id:
        query = query.where(ApInvoice.vendor_id == vendor_party_id)

    invoices = list(session.execute(query.order_by(ApInvoice.created_at.desc()).limit(50)).all())
    return {
        "invoices": [
            {
                "id": str(inv.id),
                "invoice_number": inv.number,
                "vendor_name": party.display_name or party.legal_name,
                "issue_date": inv.created_at.isoformat() if inv.created_at else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "total_amount": float(inv.amount or 0),
                "paid_amount": float(inv.paid_amount or 0),
                "status": inv.status,
                "three_way_match_status": inv.match_status,
            }
            for inv, party in invoices
        ]
    }
