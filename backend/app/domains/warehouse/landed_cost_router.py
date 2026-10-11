from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.domains.warehouse.landed_cost_schemas import (
    GlEntryOut,
    LandedCostCalculateRequest,
    LandedCostChargeOut,
    LandedCostItemOut,
    LandedCostReceiptOut,
    LandedCostVoucherCreateRequest,
    LandedCostVoucherOut,
)
from app.models.landed_cost import LandedCostCharge, LandedCostItem, LandedCostReceipt, LandedCostVoucher
from app.services.landed_cost import (
    calculate_apportionment,
    create_landed_cost_voucher,
    get_eligible_grns,
    post_landed_cost_voucher,
)

router = APIRouter(prefix="/api/v1/landed-costs", tags=["landed-costs"])


def _serialize_voucher(voucher: LandedCostVoucher) -> LandedCostVoucherOut:
    receipts = session.scalars(
        select(LandedCostReceipt).where(LandedCostReceipt.voucher_id == voucher.id)
    ).all()
    charges = session.scalars(
        select(LandedCostCharge).where(LandedCostCharge.voucher_id == voucher.id)
    ).all()
    items = session.scalars(
        select(LandedCostItem).where(LandedCostItem.voucher_id == voucher.id)
    ).all()

    # Generate GL journal entries
    charges_dict = [
        {
            "charge_type": c.charge_type,
            "amount": c.amount,
            "vendor_name": c.vendor_name,
            "invoice_ref": c.invoice_ref,
        }
        for c in charges
    ]
    items_dict = [
        {
            "quantity": itm.quantity,
            "base_unit_price": itm.base_unit_price,
            "base_total_amount": itm.base_total_amount,
            "weight_kg": itm.weight_kg,
            "volume_cbm": itm.volume_cbm,
        }
        for itm in items
    ]
    calc = calculate_apportionment(items_dict, charges_dict)
    gl_entries = [
        GlEntryOut(
            account_code=e["account_code"],
            account_name=e["account_name"],
            debit=float(e["debit"]),
            credit=float(e["credit"]),
            vendor=e["vendor"],
            ref=e["ref"],
        )
        for e in calc["gl_entries"]
    ]

    return LandedCostVoucherOut(
        id=voucher.id,
        voucher_no=voucher.voucher_no,
        posting_date=voucher.posting_date,
        status=voucher.status,
        currency=voucher.currency,
        total_charges=float(voucher.total_charges),
        notes=voucher.notes,
        created_by=voucher.created_by,
        posted_by=voucher.posted_by,
        posted_at=voucher.posted_at,
        created_at=voucher.created_at,
        receipts=[
            LandedCostReceiptOut(
                id=r.id,
                grn_id=r.grn_id,
                grn_number=r.grn_number,
                receipt_date=r.receipt_date,
                vendor_name=r.vendor_name,
                grand_total=float(r.grand_total),
            )
            for r in receipts
        ],
        charges=[
            LandedCostChargeOut(
                id=c.id,
                charge_type=c.charge_type,
                description=c.description,
                vendor_id=c.vendor_id,
                vendor_name=c.vendor_name,
                invoice_ref=c.invoice_ref,
                amount=float(c.amount),
                apportion_by=c.apportion_by,
            )
            for c in charges
        ],
        items=[
            LandedCostItemOut(
                id=itm.id,
                grn_id=itm.grn_id,
                grn_number=itm.grn_number,
                grn_line_id=itm.grn_line_id,
                product_id=itm.product_id,
                sku=itm.sku,
                product_name=itm.product_name,
                quantity=float(itm.quantity),
                uom=itm.uom,
                weight_kg=float(itm.weight_kg),
                volume_cbm=float(itm.volume_cbm),
                base_unit_price=float(itm.base_unit_price),
                base_total_amount=float(itm.base_total_amount),
                allocated_charges=float(itm.allocated_charges),
                final_unit_cost=float(itm.final_unit_cost),
                cost_variance_pct=float(itm.cost_variance_pct),
            )
            for itm in items
        ],
        gl_entries=gl_entries,
    )


@router.get("", response_model=list[LandedCostVoucherOut])
def list_vouchers(
    actor: Annotated[Actor, Depends(require_any_permission("landed_cost:read", "warehouse:read", "analytics:read", "*"))],
    status: str | None = None,
):
    """List landed cost vouchers for the tenant."""
    query = select(LandedCostVoucher).where(LandedCostVoucher.tenant_id == actor["tenant_id"])
    if status:
        query = query.where(LandedCostVoucher.status == status)
    query = query.order_by(desc(LandedCostVoucher.posting_date), desc(LandedCostVoucher.created_at))
    vouchers = session.scalars(query).all()
    return [_serialize_voucher(v) for v in vouchers]


@router.get("/eligible-grns")
def list_eligible_grns(
    actor: Annotated[Actor, Depends(require_any_permission("landed_cost:read", "warehouse:read", "*"))],
):
    """List posted GRNs ready for cost apportionment."""
    return get_eligible_grns(actor["tenant_id"], session)


@router.post("/calculate")
def preview_calculate(
    req: LandedCostCalculateRequest,
    actor: Annotated[Actor, Depends(require_any_permission("landed_cost:read", "warehouse:read", "*"))],
):
    """Dry-run calculation of proportional landed cost allocation."""
    items_dict = [itm.model_dump() for itm in req.items]
    charges_dict = [c.model_dump() for c in req.charges]
    calc = calculate_apportionment(items_dict, charges_dict)

    # Format numbers for JSON response
    calc["total_charges"] = float(calc["total_charges"])
    for itm in calc["calculated_items"]:
        itm["allocated_charges"] = float(itm["allocated_charges"])
        itm["final_unit_cost"] = float(itm["final_unit_cost"])
        itm["cost_variance_pct"] = float(itm["cost_variance_pct"])
    for gl in calc["gl_entries"]:
        gl["debit"] = float(gl["debit"])
        gl["credit"] = float(gl["credit"])
    return calc


@router.get("/{voucher_id}", response_model=LandedCostVoucherOut)
def get_voucher(
    voucher_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("landed_cost:read", "warehouse:read", "*"))],
):
    """Retrieve detailed voucher with receipts, charges, line items, and GL journal."""
    voucher = session.query(LandedCostVoucher).filter_by(tenant_id=actor["tenant_id"], id=voucher_id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Landed Cost Voucher not found")
    return _serialize_voucher(voucher)


@router.post("", response_model=LandedCostVoucherOut)
def create_voucher_endpoint(
    req: LandedCostVoucherCreateRequest,
    actor: Annotated[Actor, Depends(require_any_permission("landed_cost:write", "warehouse:write", "*"))],
):
    """Create a new draft Landed Cost Voucher."""
    voucher = create_landed_cost_voucher(
        tenant_id=actor["tenant_id"],
        data=req.model_dump(),
        user_email=actor.get("email"),
        db=session,
    )
    session.commit()
    return _serialize_voucher(voucher)


@router.post("/{voucher_id}/post", response_model=LandedCostVoucherOut)
def post_voucher_endpoint(
    voucher_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("landed_cost:write", "warehouse:write", "*"))],
):
    """Post voucher and apply moving average unit cost adjustments to inventory."""
    try:
        voucher = post_landed_cost_voucher(
            tenant_id=actor["tenant_id"],
            voucher_id=voucher_id,
            user_email=actor.get("email"),
            db=session,
        )
        session.commit()
        return _serialize_voucher(voucher)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{voucher_id}/cancel", response_model=LandedCostVoucherOut)
def cancel_voucher_endpoint(
    voucher_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("landed_cost:write", "warehouse:write", "*"))],
):
    """Cancel a draft Landed Cost Voucher."""
    voucher = session.query(LandedCostVoucher).filter_by(tenant_id=actor["tenant_id"], id=voucher_id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Landed Cost Voucher not found")
    if voucher.status != "draft":
        raise HTTPException(status_code=400, detail=f"Cannot cancel voucher in status '{voucher.status}'")
    voucher.status = "cancelled"
    session.commit()
    return _serialize_voucher(voucher)
