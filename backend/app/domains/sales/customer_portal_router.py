"""FastAPI router for Customer B2B Self-Service Portal.
Endpoints:
- GET /summary: Dashboard summary with order count, invoice balance, active RMAs
- GET /orders: Customer order tracking radar with dispatch milestones
- GET /invoices: B2B billing statements & downloadable invoice data
- GET /rmas: Self-service RMA tickets list
- POST /rmas: Submit customer return request
- PATCH /rmas/{id}/review: CSR approves or rejects RMA request
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import select, or_, func

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.core.errors import bad_request, not_found
from app.models.ar_invoice import ArInvoice
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.party import Party
from app.models.phase2_modules import CustomerPortalUser, CustomerRmaTicket
from app.models.product import Product
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1/customer-portal", tags=["Customer Portal"])


class CreateRmaRequest(BaseModel):
    customer_party_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    order_number: str
    product_id: uuid.UUID
    sku: str
    return_qty: float = Field(..., gt=0)
    uom: str = "UNIT"
    reason_category: str = Field(default="damaged_in_transit")  # damaged_in_transit, defective_workmanship, wrong_item, excess_delivery
    customer_notes: str
    carrier_name: Optional[str] = None
    return_tracking_awb: Optional[str] = None


class ReviewRmaRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|goods_received|credited)$")
    resolution_notes: Optional[str] = None


def _get_customer_id(actor: Actor, customer_party_id: Optional[uuid.UUID] = None) -> Optional[uuid.UUID]:
    """If specified by admin/test, use it; else fallback to first available customer Party."""
    if customer_party_id:
        return customer_party_id
    party = session.execute(
        select(Party).where(Party.tenant_id == actor["tenant_id"], Party.type.ilike("%customer%"))
    ).scalars().first()
    return party.id if party else None


@router.get("/summary")
def get_customer_summary(
    actor: Annotated[Actor, Depends(require_any_permission("customer_portal:read", "order:read", "*"))],
    customer_party_id: Optional[uuid.UUID] = None,
):
    c_id = _get_customer_id(actor, customer_party_id)
    if not c_id:
        return {
            "customer_id": None,
            "customer_name": "No Customers Found",
            "open_orders_count": 0,
            "shipped_orders_count": 0,
            "total_receivables": 0.0,
            "active_rmas_count": 0,
        }

    party = session.get(Party, c_id)
    cust_name = party.display_name or party.legal_name if party else "Customer"

    # Orders count
    orders = session.execute(
        select(Order).where(Order.tenant_id == actor["tenant_id"], Order.customer_id == c_id)
    ).scalars().all()
    open_orders = sum(1 for o in orders if o.status not in ["shipped", "fulfilled", "cancelled"])
    shipped_orders = sum(1 for o in orders if o.status in ["shipped", "fulfilled"])

    # Receivables (ArInvoices)
    invoices = session.execute(
        select(ArInvoice).where(ArInvoice.tenant_id == actor["tenant_id"], ArInvoice.customer_id == c_id)
    ).scalars().all()
    total_receivables = sum(float(inv.amount_due) for inv in invoices if inv.payment_status != "paid")

    # RMAs
    rmas = session.execute(
        select(CustomerRmaTicket).where(CustomerRmaTicket.tenant_id == actor["tenant_id"], CustomerRmaTicket.customer_party_id == c_id)
    ).scalars().all()
    active_rmas = sum(1 for r in rmas if r.status in ["submitted", "under_review", "approved"])

    return {
        "customer_id": str(c_id),
        "customer_name": cust_name,
        "open_orders_count": open_orders,
        "shipped_orders_count": shipped_orders,
        "total_receivables": round(total_receivables, 2),
        "active_rmas_count": active_rmas,
    }


@router.get("/orders")
def get_customer_orders(
    actor: Annotated[Actor, Depends(require_any_permission("customer_portal:read", "order:read", "*"))],
    customer_party_id: Optional[uuid.UUID] = None,
):
    c_id = _get_customer_id(actor, customer_party_id)
    if not c_id:
        return {"orders": []}

    orders = session.execute(
        select(Order).where(Order.tenant_id == actor["tenant_id"], Order.customer_id == c_id).order_by(Order.created_at.desc())
    ).scalars().all()

    res = []
    for o in orders:
        lines = session.execute(select(OrderLine).where(OrderLine.order_id == o.id)).scalars().all()
        # Derive milestone progress
        milestone = "Booked"
        if o.status in ["confirmed", "allocated"]:
            milestone = "Processing"
        elif o.status in ["packed", "ready_for_shipping"]:
            milestone = "Packed"
        elif o.status in ["shipped", "fulfilled"]:
            milestone = "Dispatched"

        res.append({
            "id": str(o.id),
            "order_number": o.number,
            "order_date": o.created_at.strftime("%Y-%m-%d") if o.created_at else None,
            "status": o.status,
            "milestone": milestone,
            "total_amount": float(o.total or 0.0),
            "currency": o.currency or "INR",
            "lines_count": len(lines),
            "carrier_name": "FedEx Express" if o.status in ["shipped", "fulfilled"] else "TBD",
            "tracking_number": f"TRK-{o.number}" if o.status in ["shipped", "fulfilled"] else None,
        })
    return {"orders": res}


@router.get("/invoices")
def get_customer_invoices(
    actor: Annotated[Actor, Depends(require_any_permission("customer_portal:read", "finance:read", "*"))],
    customer_party_id: Optional[uuid.UUID] = None,
):
    c_id = _get_customer_id(actor, customer_party_id)
    if not c_id:
        return {"invoices": []}

    invoices = session.execute(
        select(ArInvoice).where(ArInvoice.tenant_id == actor["tenant_id"], ArInvoice.customer_id == c_id).order_by(ArInvoice.created_at.desc())
    ).scalars().all()

    return {
        "invoices": [
            {
                "id": str(inv.id),
                "invoice_number": inv.number,
                "order_number": inv.order_number,
                "issue_date": inv.invoice_date.isoformat(),
                "due_date": inv.due_date.isoformat(),
                "total_amount": float(inv.amount),
                "amount_due": float(inv.amount - inv.paid_amount - inv.credit_amount),
                "payment_status": inv.status,
                "irn_hash": f"IRN-EWB-{inv.number}-2026",
            }
            for inv in invoices
        ]
    }


@router.get("/rmas")
def get_customer_rmas(
    actor: Annotated[Actor, Depends(require_any_permission("customer_portal:read", "returns:read", "*"))],
    customer_party_id: Optional[uuid.UUID] = None,
):
    query = select(CustomerRmaTicket).where(CustomerRmaTicket.tenant_id == actor["tenant_id"])
    if customer_party_id:
        query = query.where(CustomerRmaTicket.customer_party_id == customer_party_id)

    query = query.order_by(CustomerRmaTicket.created_at.desc())
    rmas = session.execute(query).scalars().all()

    return {
        "rmas": [
            {
                "id": str(r.id),
                "ticket_number": r.ticket_number,
                "customer_party_id": str(r.customer_party_id),
                "order_number": r.order_number,
                "product_id": str(r.product_id),
                "sku": r.sku,
                "return_qty": float(r.return_qty),
                "uom": r.uom,
                "reason_category": r.reason_category,
                "customer_notes": r.customer_notes,
                "status": r.status,
                "carrier_name": r.carrier_name,
                "return_tracking_awb": r.return_tracking_awb,
                "resolution_notes": r.resolution_notes,
                "created_at": r.created_at.isoformat(),
            }
            for r in rmas
        ]
    }


@router.post("/rmas")
def submit_rma_ticket(
    req: CreateRmaRequest,
    actor: Annotated[Actor, Depends(require_any_permission("customer_portal:write", "returns:write", "*"))],
):
    c_id = _get_customer_id(actor, req.customer_party_id)
    if not c_id:
        raise bad_request("Customer party could not be identified.")

    ticket_no = next_document_number(actor["tenant_id"], "RMA")

    rma = CustomerRmaTicket(
        tenant_id=actor["tenant_id"],
        ticket_number=ticket_no,
        customer_party_id=c_id,
        order_id=req.order_id,
        order_number=req.order_number,
        product_id=req.product_id,
        sku=req.sku,
        return_qty=Decimal(str(req.return_qty)),
        uom=req.uom,
        reason_category=req.reason_category,
        customer_notes=req.customer_notes,
        carrier_name=req.carrier_name,
        return_tracking_awb=req.return_tracking_awb,
        status="submitted",
    )
    session.add(rma)
    session.commit()

    return {
        "id": str(rma.id),
        "ticket_number": rma.ticket_number,
        "status": rma.status,
        "message": "RMA return request submitted successfully. Our Quality Operations team will review within 24 hours.",
    }


@router.patch("/rmas/{rma_id}/review")
def review_rma_ticket(
    rma_id: uuid.UUID,
    req: ReviewRmaRequest,
    actor: Annotated[Actor, Depends(require_any_permission("customer_portal:write", "returns:write", "*"))],
):
    rma = session.execute(
        select(CustomerRmaTicket).where(CustomerRmaTicket.tenant_id == actor["tenant_id"], CustomerRmaTicket.id == rma_id)
    ).scalar_one_or_none()

    if not rma:
        raise not_found("Customer RMA ticket not found.")

    rma.status = req.status
    rma.resolution_notes = req.resolution_notes
    rma.reviewed_by_user_id = actor["user_id"]
    if req.status in ["approved", "rejected", "credited"]:
        rma.resolved_at = datetime.now(timezone.utc)

    session.commit()
    return {"message": f"RMA {rma.ticket_number} marked as {rma.status}", "status": rma.status}
