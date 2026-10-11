"""FastAPI router for Blanket Purchase Agreements (BPAs) & Long-Term Rate Contracts.
Endpoints:
- GET /blanket-pos: List rate contracts with commitment utilization
- POST /blanket-pos: Create new long-term BPA contract
- GET /blanket-pos/{id}: Detail with lines & release orders
- POST /blanket-pos/{id}/release: Issue Call-Off / Release Purchase Order against BPA
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import select, func

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.core.errors import bad_request, not_found
from app.models.party import Party
from app.models.phase1_modules import BlanketPoLine, BlanketPurchaseOrder
from app.models.po_line import PoLine
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.warehouse import Warehouse
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1/blanket-pos", tags=["Blanket Purchase Orders"])


class BlanketPoLineItem(BaseModel):
    product_id: uuid.UUID
    agreed_rate: float = Field(..., gt=0)
    committed_qty: float = Field(..., gt=0)
    uom: str = "UNIT"


class CreateBlanketPoRequest(BaseModel):
    vendor_id: uuid.UUID
    warehouse_id: Optional[uuid.UUID] = None
    start_date: date
    end_date: date
    currency: str = "INR"
    target_amount: float = Field(..., gt=0)
    payment_terms: Optional[str] = "Net 45 Days"
    notes: Optional[str] = None
    lines: List[BlanketPoLineItem]


class ReleasePoLineRequest(BaseModel):
    bpa_line_id: uuid.UUID
    release_qty: float = Field(..., gt=0)


class ReleasePoRequest(BaseModel):
    warehouse_id: uuid.UUID
    expected_delivery_date: date
    notes: Optional[str] = None
    lines: List[ReleasePoLineRequest]


@router.get("")
def list_blanket_pos(
    actor: Annotated[Actor, Depends(require_any_permission("blanket_po:read", "po:read", "*"))],
    vendor_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
):
    query = (
        select(BlanketPurchaseOrder, Party)
        .join(Party, Party.id == BlanketPurchaseOrder.vendor_id)
        .where(BlanketPurchaseOrder.tenant_id == actor["tenant_id"])
    )
    if vendor_id:
        query = query.where(BlanketPurchaseOrder.vendor_id == vendor_id)
    if status:
        query = query.where(BlanketPurchaseOrder.status == status)

    bpas = list(session.execute(query.order_by(BlanketPurchaseOrder.created_at.desc())).all())
    return {
        "blanket_pos": [
            {
                "id": str(b.id),
                "bpa_number": b.bpa_number,
                "vendor_name": party.display_name or party.legal_name,
                "vendor_id": str(party.id),
                "start_date": b.start_date.isoformat(),
                "end_date": b.end_date.isoformat(),
                "currency": b.currency,
                "target_amount": float(b.target_amount),
                "released_amount": float(b.released_amount),
                "utilization_pct": min(100.0, round((float(b.released_amount) / float(b.target_amount)) * 100, 2)) if b.target_amount else 0.0,
                "status": b.status,
                "lines_count": len(b.lines),
                "created_at": b.created_at.isoformat(),
            }
            for b, party in bpas
        ]
    }


@router.post("")
def create_blanket_po(
    req: CreateBlanketPoRequest,
    actor: Annotated[Actor, Depends(require_any_permission("blanket_po:write", "po:write", "*"))],
):
    vendor = session.get(Party, req.vendor_id)
    if not vendor or vendor.tenant_id != actor["tenant_id"]:
        raise not_found("Vendor not found")

    bpa_num = next_document_number(actor["tenant_id"], "BPA")

    bpa = BlanketPurchaseOrder(
        tenant_id=actor["tenant_id"],
        bpa_number=bpa_num,
        vendor_id=req.vendor_id,
        warehouse_id=req.warehouse_id,
        start_date=req.start_date,
        end_date=req.end_date,
        currency=req.currency,
        target_amount=Decimal(str(req.target_amount)),
        status="active",
        payment_terms=req.payment_terms,
        notes=req.notes,
    )
    session.add(bpa)
    session.flush()

    for l in req.lines:
        line = BlanketPoLine(
            tenant_id=actor["tenant_id"],
            bpa_id=bpa.id,
            product_id=l.product_id,
            agreed_rate=Decimal(str(l.agreed_rate)),
            committed_qty=Decimal(str(l.committed_qty)),
            released_qty=Decimal("0.00"),
            uom=l.uom,
        )
        session.add(line)

    session.commit()
    return {"id": str(bpa.id), "bpa_number": bpa.bpa_number, "message": "Blanket Purchase Agreement established"}


@router.get("/{id}")
def get_blanket_po_detail(
    id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("blanket_po:read", "po:read", "*"))],
):
    bpa = session.execute(
        select(BlanketPurchaseOrder).where(
            BlanketPurchaseOrder.tenant_id == actor["tenant_id"],
            BlanketPurchaseOrder.id == id,
        )
    ).scalar_one_or_none()
    if not bpa:
        raise not_found("BPA not found")

    vendor = session.get(Party, bpa.vendor_id)
    lines_data = list(
        session.execute(
            select(BlanketPoLine, Product)
            .join(Product, Product.id == BlanketPoLine.product_id)
            .where(BlanketPoLine.bpa_id == id)
        ).all()
    )

    return {
        "bpa": {
            "id": str(bpa.id),
            "bpa_number": bpa.bpa_number,
            "vendor_name": vendor.display_name or vendor.legal_name if vendor else "Supplier",
            "vendor_id": str(bpa.vendor_id),
            "start_date": bpa.start_date.isoformat(),
            "end_date": bpa.end_date.isoformat(),
            "currency": bpa.currency,
            "target_amount": float(bpa.target_amount),
            "released_amount": float(bpa.released_amount),
            "status": bpa.status,
            "payment_terms": bpa.payment_terms,
            "notes": bpa.notes,
        },
        "lines": [
            {
                "id": str(l.id),
                "product_id": str(p.id),
                "sku": p.sku,
                "name": p.name,
                "agreed_rate": float(l.agreed_rate),
                "committed_qty": float(l.committed_qty),
                "released_qty": float(l.released_qty),
                "remaining_qty": float(l.committed_qty - l.released_qty),
                "uom": l.uom,
            }
            for l, p in lines_data
        ],
    }


@router.post("/{id}/release")
def release_call_off_po(
    id: uuid.UUID,
    req: ReleasePoRequest,
    actor: Annotated[Actor, Depends(require_any_permission("blanket_po:write", "po:write", "*"))],
):
    bpa = session.execute(
        select(BlanketPurchaseOrder).where(
            BlanketPurchaseOrder.tenant_id == actor["tenant_id"],
            BlanketPurchaseOrder.id == id,
        )
    ).scalar_one_or_none()
    if not bpa:
        raise not_found("BPA not found")
    if bpa.status != "active":
        raise bad_request("Blanket Agreement is not in active state")

    vendor = session.get(Party, bpa.vendor_id)
    wh = session.get(Warehouse, req.warehouse_id)
    if not wh:
        raise not_found("Warehouse not found")

    po_number = next_document_number(actor["tenant_id"], "PO")
    total_release_val = Decimal("0.00")

    # Generate standard PurchaseOrder
    po = PurchaseOrder(
        tenant_id=actor["tenant_id"],
        number=po_number,
        vendor_id=bpa.vendor_id,
        vendor_name=vendor.display_name or vendor.legal_name if vendor else "Vendor",
        warehouse_id=wh.id,
        warehouse_code=wh.code,
        status="approved",
        po_date=date.today(),
        expected_date=req.expected_delivery_date,
        currency=bpa.currency,
        notes=f"Released against Blanket Agreement {bpa.bpa_number}. {req.notes or ''}",
    )
    session.add(po)
    session.flush()

    line_no = 1
    for item in req.lines:
        bpa_line = session.get(BlanketPoLine, item.bpa_line_id)
        if not bpa_line or bpa_line.bpa_id != id:
            continue
        prod = session.get(Product, bpa_line.product_id)
        rel_qty = Decimal(str(item.release_qty))
        net_amt = rel_qty * bpa_line.agreed_rate

        po_line = PoLine(
            tenant_id=actor["tenant_id"],
            po_id=po.id,
            line_no=line_no,
            product_id=bpa_line.product_id,
            sku=prod.sku if prod else "SKU",
            description=prod.name if prod else "Product",
            quantity=rel_qty,
            uom=bpa_line.uom,
            unit_price=bpa_line.agreed_rate,
            tax_code="GST18",
            tax_rate=Decimal("18.00"),
            net_amount=net_amt,
            gross_amount=net_amt * Decimal("1.18"),
            status="open",
        )
        session.add(po_line)

        # Update BPA line and agreement released amounts
        bpa_line.released_qty += rel_qty
        total_release_val += net_amt
        line_no += 1

    po.subtotal = total_release_val
    po.total = total_release_val * Decimal("1.18")
    bpa.released_amount += total_release_val

    session.commit()
    return {
        "message": f"Call-off Purchase Order {po.number} generated against BPA {bpa.bpa_number}",
        "po_id": str(po.id),
        "po_number": po.number,
        "release_total": float(total_release_val),
        "bpa_remaining_amount": float(bpa.target_amount - bpa.released_amount),
    }
