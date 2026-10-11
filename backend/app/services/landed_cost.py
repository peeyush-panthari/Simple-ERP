from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import session as db_session
from app.models.audit_log import AuditLog
from app.models.doc_sequence import DocSequence
from app.models.grn import Grn
from app.models.grn_line import GrnLine
from app.models.landed_cost import LandedCostCharge, LandedCostItem, LandedCostReceipt, LandedCostVoucher
from app.models.party import Party
from app.models.product import Product


def _quantize(val: Decimal | float | int, decimals: int = 2) -> Decimal:
    d = Decimal(str(val))
    target = Decimal("10") ** (-decimals)
    return d.quantize(target, rounding=ROUND_HALF_UP)


def calculate_apportionment(
    items: list[dict[str, Any]],
    charges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate proportional landed cost allocation across line items.

    Supports apportionment by:
      - 'value' (Ad Valorem, ratio of base total line value)
      - 'weight' (Ratio of total line gross weight)
      - 'volume' (Ratio of total line cubic volume)
      - 'quantity' (Ratio of unit quantity)

    Returns:
      - calculated_items: list with allocated_charges, final_unit_cost, and variance_pct
      - total_charges: sum of all charge amounts
      - gl_entries: simulated double-entry accounting journal
    """
    if not items or not charges:
        return {
            "calculated_items": items,
            "total_charges": Decimal("0.00"),
            "gl_entries": [],
        }

    # Initialize item accumulators
    item_allocations: dict[int, Decimal] = {i: Decimal("0.00") for i in range(len(items))}
    total_charges_sum = Decimal("0.00")

    # Compute basis totals across items
    total_val = sum(Decimal(str(item.get("base_total_amount") or Decimal(str(item.get("base_unit_price", 0))) * Decimal(str(item.get("quantity", 1))))) for item in items)
    total_wt = sum(Decimal(str(item.get("weight_kg", 1.0))) * Decimal(str(item.get("quantity", 1))) for item in items)
    total_vol = sum(Decimal(str(item.get("volume_cbm", 0.01))) * Decimal(str(item.get("quantity", 1))) for item in items)
    total_qty = sum(Decimal(str(item.get("quantity", 1))) for item in items)

    gl_entries: list[dict[str, Any]] = []

    for charge in charges:
        charge_amt = Decimal(str(charge.get("amount", 0)))
        if charge_amt <= 0:
            continue
        total_charges_sum += charge_amt
        apportion_by = (charge.get("apportion_by") or "value").lower()
        charge_type = charge.get("charge_type") or "other"

        # Determine denominator
        if apportion_by == "weight":
            denom = total_wt if total_wt > 0 else total_qty
        elif apportion_by == "volume":
            denom = total_vol if total_vol > 0 else total_qty
        elif apportion_by == "quantity":
            denom = total_qty if total_qty > 0 else Decimal("1")
        else:  # value
            denom = total_val if total_val > 0 else total_qty

        # Apportion charge across each item
        charge_distributed = Decimal("0.00")
        for i, item in enumerate(items):
            qty = Decimal(str(item.get("quantity", 1)))
            if apportion_by == "weight":
                numerator = Decimal(str(item.get("weight_kg", 1.0))) * qty
            elif apportion_by == "volume":
                numerator = Decimal(str(item.get("volume_cbm", 0.01))) * qty
            elif apportion_by == "quantity":
                numerator = qty
            else:
                numerator = Decimal(str(item.get("base_total_amount") or Decimal(str(item.get("base_unit_price", 0))) * qty))

            share = (numerator / denom) * charge_amt if denom > 0 else Decimal("0.00")
            item_allocations[i] += share
            charge_distributed += share

        # Create GL journal credit entry for this charge
        gl_entries.append({
            "account_code": f"CLEARING-{charge_type.upper()}",
            "account_name": f"{charge_type.replace('_', ' ').title()} Clearing Account",
            "debit": Decimal("0.00"),
            "credit": _quantize(charge_amt),
            "vendor": charge.get("vendor_name") or "Carrier / Broker",
            "ref": charge.get("invoice_ref") or "N/A",
        })

    # Add balancing GL debit entry to Inventory Asset
    gl_entries.insert(0, {
        "account_code": "ASSET-INV-VALUATION",
        "account_name": "Inventory Inbound Valuation Asset",
        "debit": _quantize(total_charges_sum),
        "credit": Decimal("0.00"),
        "vendor": "Company Stock Ledger",
        "ref": "Landed Cost Capitalization",
    })

    # Build final line items
    calculated_items: list[dict[str, Any]] = []
    for i, item in enumerate(items):
        qty = Decimal(str(item.get("quantity", 1)))
        base_unit = Decimal(str(item.get("base_unit_price", 0)))
        base_total = Decimal(str(item.get("base_total_amount") or base_unit * qty))
        allocated = _quantize(item_allocations[i])
        final_unit = _quantize((base_total + allocated) / qty if qty > 0 else base_unit, 4)
        variance_pct = _quantize(((final_unit - base_unit) / base_unit * 100) if base_unit > 0 else Decimal("0.00"), 2)

        calculated_items.append({
            **item,
            "allocated_charges": allocated,
            "final_unit_cost": final_unit,
            "cost_variance_pct": variance_pct,
        })

    return {
        "calculated_items": calculated_items,
        "total_charges": _quantize(total_charges_sum),
        "gl_entries": gl_entries,
    }


def get_eligible_grns(tenant_id: uuid.UUID, db: Session | None = None) -> list[dict[str, Any]]:
    """Return posted GRNs that are ready for landed cost allocation."""
    s = db or db_session
    stmt = (
        select(Grn)
        .where(Grn.tenant_id == tenant_id, Grn.status == "posted")
        .order_by(Grn.received_date.desc(), Grn.created_at.desc())
        .limit(50)
    )
    grns = s.scalars(stmt).all()
    results = []
    for g in grns:
        # Get line items
        lines_stmt = select(GrnLine).where(GrnLine.grn_id == g.id, GrnLine.deleted_at.is_(None))
        lines = s.scalars(lines_stmt).all()
        grand_total = sum((l.accepted_qty if l.accepted_qty > 0 else l.received_qty) * l.unit_price for l in lines)
        results.append({
            "id": str(g.id),
            "number": g.number,
            "po_number": g.po_number,
            "vendor_name": g.vendor_name,
            "received_date": g.received_date.isoformat(),
            "lines_count": len(lines),
            "grand_total": float(_quantize(grand_total)),
            "lines": [
                {
                    "grn_line_id": str(l.id),
                    "grn_id": str(g.id),
                    "grn_number": g.number,
                    "product_id": str(l.product_id),
                    "sku": l.sku,
                    "quantity": float(l.accepted_qty if l.accepted_qty > 0 else l.received_qty),
                    "uom": l.uom,
                    "base_unit_price": float(l.unit_price),
                    "base_total_amount": float(_quantize((l.accepted_qty if l.accepted_qty > 0 else l.received_qty) * l.unit_price)),
                    "weight_kg": 1.0,
                    "volume_cbm": 0.01,
                }
                for l in lines
                if (l.accepted_qty if l.accepted_qty > 0 else l.received_qty) > 0
            ],
        })
    return results


def create_landed_cost_voucher(
    tenant_id: uuid.UUID,
    data: dict[str, Any],
    user_email: str | None = None,
    db: Session | None = None,
) -> LandedCostVoucher:
    """Create a new Landed Cost Voucher with receipts, charges, and calculated item lines."""
    s = db or db_session

    # Generate sequential voucher number
    prefix = "LCV"
    today_str = date.today().strftime("%Y%m")
    seq_name = f"lcv_{today_str}"
    seq = s.query(DocSequence).filter_by(tenant_id=tenant_id, name=seq_name).with_for_update().first()
    if seq is None:
        seq = DocSequence(tenant_id=tenant_id, name=seq_name, next_val=1)
        s.add(seq)
        s.flush()
    voucher_no = f"{prefix}-{today_str}-{seq.next_val:04d}"
    seq.next_val += 1

    # Extract payloads
    receipts_in = data.get("receipts", [])
    charges_in = data.get("charges", [])
    items_in = data.get("items", [])

    # Calculate allocations
    calc = calculate_apportionment(items_in, charges_in)
    total_charges = calc["total_charges"]
    calculated_items = calc["calculated_items"]

    voucher = LandedCostVoucher(
        tenant_id=tenant_id,
        voucher_no=voucher_no,
        posting_date=data.get("posting_date") or date.today(),
        status="draft",
        currency=data.get("currency") or "INR",
        total_charges=total_charges,
        notes=data.get("notes"),
        created_by=user_email,
    )
    s.add(voucher)
    s.flush()

    # Add receipts
    for r in receipts_in:
        receipt = LandedCostReceipt(
            tenant_id=tenant_id,
            voucher_id=voucher.id,
            grn_id=uuid.UUID(str(r["grn_id"])),
            grn_number=r.get("grn_number") or "",
            receipt_date=r.get("receipt_date") or date.today(),
            vendor_name=r.get("vendor_name"),
            grand_total=Decimal(str(r.get("grand_total", 0))),
        )
        s.add(receipt)

    # Add charges
    for c in charges_in:
        charge = LandedCostCharge(
            tenant_id=tenant_id,
            voucher_id=voucher.id,
            charge_type=c.get("charge_type") or "freight",
            description=c.get("description"),
            vendor_id=uuid.UUID(str(c["vendor_id"])) if c.get("vendor_id") else None,
            vendor_name=c.get("vendor_name"),
            invoice_ref=c.get("invoice_ref"),
            amount=Decimal(str(c.get("amount", 0))),
            apportion_by=c.get("apportion_by") or "value",
        )
        s.add(charge)

    # Add items
    for itm in calculated_items:
        item = LandedCostItem(
            tenant_id=tenant_id,
            voucher_id=voucher.id,
            grn_id=uuid.UUID(str(itm["grn_id"])),
            grn_number=itm.get("grn_number") or "",
            grn_line_id=uuid.UUID(str(itm["grn_line_id"])),
            product_id=uuid.UUID(str(itm["product_id"])),
            sku=itm.get("sku") or "",
            product_name=itm.get("product_name"),
            quantity=Decimal(str(itm.get("quantity", 1))),
            uom=itm.get("uom") or "PCS",
            weight_kg=Decimal(str(itm.get("weight_kg", 1.0))),
            volume_cbm=Decimal(str(itm.get("volume_cbm", 0.01))),
            base_unit_price=Decimal(str(itm.get("base_unit_price", 0))),
            base_total_amount=Decimal(str(itm.get("base_total_amount", 0))),
            allocated_charges=Decimal(str(itm.get("allocated_charges", 0))),
            final_unit_cost=Decimal(str(itm.get("final_unit_cost", 0))),
            cost_variance_pct=Decimal(str(itm.get("cost_variance_pct", 0))),
        )
        s.add(item)

    # Audit log
    s.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_email=user_email or "system",
            action="landed_cost:create",
            entity_type="landed_cost_voucher",
            entity_id=str(voucher.id),
            details={"voucher_no": voucher_no, "total_charges": float(total_charges), "status": "draft"},
        )
    )

    s.flush()
    return voucher


def post_landed_cost_voucher(
    tenant_id: uuid.UUID,
    voucher_id: uuid.UUID,
    user_email: str | None = None,
    db: Session | None = None,
) -> LandedCostVoucher:
    """Post an approved Landed Cost Voucher, adjusting inventory unit cost."""
    s = db or db_session
    voucher = s.query(LandedCostVoucher).filter_by(tenant_id=tenant_id, id=voucher_id).with_for_update().first()
    if not voucher:
        raise ValueError("Landed Cost Voucher not found")
    if voucher.status != "draft":
        raise ValueError(f"Cannot post voucher in status '{voucher.status}'")

    # Load items and adjust GRN lines
    items = s.query(LandedCostItem).filter_by(voucher_id=voucher.id).all()
    for itm in items:
        grn_line = s.query(GrnLine).filter_by(id=itm.grn_line_id).first()
        if grn_line:
            # Update line unit price to reflect true landed valuation
            grn_line.unit_price = itm.final_unit_cost

    voucher.status = "posted"
    voucher.posted_by = user_email
    voucher.posted_at = datetime.utcnow()

    # Audit log
    s.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_email=user_email or "system",
            action="landed_cost:post",
            entity_type="landed_cost_voucher",
            entity_id=str(voucher.id),
            details={
                "voucher_no": voucher.voucher_no,
                "total_charges": float(voucher.total_charges),
                "items_updated": len(items),
            },
        )
    )

    s.flush()
    return voucher
