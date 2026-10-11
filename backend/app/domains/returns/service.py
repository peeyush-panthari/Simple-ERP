from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.db import session
from app.core.errors import rule_violation
from app.core.money import decimal_str, to_decimal
from app.models.credit_note import CreditNote
from app.models.grn import Grn
from app.models.order import Order
from app.models.party import Party
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.returns import Rma, RmaLine, Rtv, RtvLine
from app.models.warehouse import Warehouse
from app.services import inventory_ledger
from app.services.inventory_ledger import LedgerPosting
from app.services.sequences import next_document_number


def create_customer_rma(
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    return_reason: str,
    lines_data: list[dict],
    order_id: uuid.UUID | None = None,
    carrier: str | None = None,
    tracking_number: str | None = None,
    notes: str | None = None,
    actor_email: str | None = None,
) -> Rma:
    customer = session.execute(
        select(Party).where(Party.tenant_id == tenant_id, Party.id == customer_id)
    ).scalar_one_or_none()
    if not customer:
        raise rule_violation("Customer party not found")

    warehouse = session.execute(
        select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.id == warehouse_id)
    ).scalar_one_or_none()
    if not warehouse:
        raise rule_violation("Warehouse not found")

    order = None
    if order_id:
        order = session.execute(
            select(Order).where(Order.tenant_id == tenant_id, Order.id == order_id)
        ).scalar_one_or_none()

    rma_number = next_document_number(tenant_id, "RMA")
    now = datetime.now(timezone.utc)

    rma = Rma(
        tenant_id=tenant_id,
        number=rma_number,
        customer_id=customer.id,
        customer_name=customer.legal_name,
        order_id=order.id if order else None,
        order_number=order.number if order else None,
        warehouse_id=warehouse.id,
        warehouse_code=warehouse.code,
        status="authorized",
        return_reason=return_reason,
        carrier=carrier,
        tracking_number=tracking_number,
        notes=notes,
        authorized_by=actor_email,
        authorized_at=now,
        created_by=actor_email,
    )
    session.add(rma)
    session.flush()

    for idx, l in enumerate(lines_data, start=1):
        product = session.execute(
            select(Product).where(Product.tenant_id == tenant_id, Product.id == l["product_id"])
        ).scalar_one_or_none()
        if not product:
            raise rule_violation(f"Product {l['product_id']} not found")

        rma_line = RmaLine(
            tenant_id=tenant_id,
            rma_id=rma.id,
            line_no=idx,
            product_id=product.id,
            sku=product.sku,
            order_line_id=l.get("order_line_id"),
            authorized_qty=to_decimal(l["authorized_qty"]),
            uom=l.get("uom", product.uom),
            unit_price=to_decimal(l.get("unit_price", 0)),
            batch_no=l.get("batch_no"),
            inspection_status="pending",
        )
        session.add(rma_line)

    session.commit()
    return rma


def receive_customer_rma(
    tenant_id: uuid.UUID,
    rma_id: uuid.UUID,
    lines_received: list[dict],
    carrier: str | None = None,
    tracking_number: str | None = None,
) -> Rma:
    rma = session.execute(
        select(Rma).where(Rma.tenant_id == tenant_id, Rma.id == rma_id)
    ).scalar_one_or_none()
    if not rma:
        raise rule_violation("RMA not found")
    if rma.status not in ("draft", "authorized"):
        raise rule_violation(f"Cannot receive RMA in '{rma.status}' status")

    lines = session.execute(select(RmaLine).where(RmaLine.rma_id == rma.id)).scalars().all()
    line_map = {l.line_no: l for l in lines}

    for item in lines_received:
        line_no = item["line_no"]
        if line_no in line_map:
            line_map[line_no].received_qty = to_decimal(item["received_qty"])

    if carrier:
        rma.carrier = carrier
    if tracking_number:
        rma.tracking_number = tracking_number

    rma.status = "goods_received"
    rma.received_at = datetime.now(timezone.utc)
    session.commit()
    return rma


def inspect_and_disposition_rma(
    tenant_id: uuid.UUID,
    rma_id: uuid.UUID,
    dispositions: list[dict],
    notes: str | None = None,
    actor_email: str | None = None,
) -> Rma:
    rma = session.execute(
        select(Rma).where(Rma.tenant_id == tenant_id, Rma.id == rma_id)
    ).scalar_one_or_none()
    if not rma:
        raise rule_violation("RMA not found")
    if rma.status not in ("goods_received", "authorized"):
        raise rule_violation(f"Cannot inspect RMA in '{rma.status}' status")

    lines = session.execute(select(RmaLine).where(RmaLine.rma_id == rma.id)).scalars().all()
    line_map = {l.line_no: l for l in lines}

    total_credit_amount = Decimal(0)

    for d in dispositions:
        line_no = d["line_no"]
        line = line_map.get(line_no)
        if not line:
            continue

        restocked = to_decimal(d.get("restocked_qty", 0))
        scrapped = to_decimal(d.get("scrapped_qty", 0))
        repaired = to_decimal(d.get("repaired_qty", 0))

        if (restocked + scrapped + repaired) != (line.received_qty or Decimal(0)):
            raise rule_violation(f"Disposition quantities for line {line_no} do not match received quantity")

        line.restocked_qty = restocked
        line.scrapped_qty = scrapped
        line.repaired_qty = repaired
        line.disposition_notes = d.get("disposition_notes")
        line.inspection_status = d.get("inspectionStatus", "passed")

        # Inventory Ledger Movements
        common = {
            "tenant_id": tenant_id,
            "product_id": line.product_id,
            "sku": line.sku,
            "warehouse_id": rma.warehouse_id,
            "uom": line.uom,
            "reference_type": "rma",
            "batch_no": line.batch_no,
            "unit_cost": decimal_str(line.unit_price),
            "actor_id": actor_email,
        }

        # 1. Restock to available stock
        if restocked > 0:
            inventory_ledger.post(
                LedgerPosting(
                    quantity=decimal_str(restocked),
                    bucket="available",
                    movement_type="receipt",
                    reference_id=f"{rma.number}:restock:{line.line_no}",
                    reference_no=rma.number,
                    reason=f"RMA Customer Return Restock ({rma.return_reason})",
                    **common,
                )
            )

        # 2. Scrapped to damaged bucket
        if scrapped > 0:
            inventory_ledger.post(
                LedgerPosting(
                    quantity=decimal_str(scrapped),
                    bucket="damaged",
                    movement_type="scrap",
                    reference_id=f"{rma.number}:scrap:{line.line_no}",
                    reference_no=rma.number,
                    reason=f"RMA Customer Return Damaged/Scrap ({rma.return_reason})",
                    **common,
                )
            )

        # 3. Repaired to quarantine bucket for rework
        if repaired > 0:
            inventory_ledger.post(
                LedgerPosting(
                    quantity=decimal_str(repaired),
                    bucket="quarantine",
                    movement_type="receipt",
                    reference_id=f"{rma.number}:repair:{line.line_no}",
                    reference_no=rma.number,
                    reason=f"RMA Customer Return Rework ({rma.return_reason})",
                    **common,
                )
            )

        total_credit_amount += (restocked + repaired) * line.unit_price

    # Generate draft CreditNote for finance review if eligible amount > 0
    if total_credit_amount > 0:
        cn_number = next_document_number(tenant_id, "CN")
        credit_note = CreditNote(
            tenant_id=tenant_id,
            number=cn_number,
            direction="outbound",  # AR credit note to customer
            party_id=rma.customer_id,
            party_name=rma.customer_name,
            amount=total_credit_amount,
            currency="INR",
            period=datetime.now(timezone.utc).strftime("%Y-%m"),
            reason=f"Customer Return under {rma.number}: {rma.return_reason}",
            status="applied",
            created_by=actor_email,
        )
        session.add(credit_note)
        session.flush()

        rma.credit_note_id = credit_note.id
        rma.credit_note_number = credit_note.number

    rma.status = "completed"
    rma.inspected_by = actor_email
    rma.inspected_at = datetime.now(timezone.utc)
    if notes:
        rma.notes = f"{rma.notes or ''}\n{notes}".strip()

    session.commit()
    return rma


def create_supplier_rtv(
    tenant_id: uuid.UUID,
    vendor_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    return_reason: str,
    lines_data: list[dict],
    po_id: uuid.UUID | None = None,
    grn_id: uuid.UUID | None = None,
    notes: str | None = None,
    actor_email: str | None = None,
) -> Rtv:
    vendor = session.execute(
        select(Party).where(Party.tenant_id == tenant_id, Party.id == vendor_id)
    ).scalar_one_or_none()
    if not vendor:
        raise rule_violation("Vendor party not found")

    warehouse = session.execute(
        select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.id == warehouse_id)
    ).scalar_one_or_none()
    if not warehouse:
        raise rule_violation("Warehouse not found")

    po = None
    if po_id:
        po = session.execute(
            select(PurchaseOrder).where(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.id == po_id)
        ).scalar_one_or_none()

    grn = None
    if grn_id:
        grn = session.execute(
            select(Grn).where(Grn.tenant_id == tenant_id, Grn.id == grn_id)
        ).scalar_one_or_none()

    rtv_number = next_document_number(tenant_id, "RTV")
    now = datetime.now(timezone.utc)

    rtv = Rtv(
        tenant_id=tenant_id,
        number=rtv_number,
        vendor_id=vendor.id,
        vendor_name=vendor.legal_name,
        po_id=po.id if po else None,
        po_number=po.number if po else None,
        grn_id=grn.id if grn else None,
        grn_number=grn.number if grn else None,
        warehouse_id=warehouse.id,
        warehouse_code=warehouse.code,
        status="approved",
        return_reason=return_reason,
        notes=notes,
        approved_by=actor_email,
        approved_at=now,
        created_by=actor_email,
    )
    session.add(rtv)
    session.flush()

    for idx, l in enumerate(lines_data, start=1):
        product = session.execute(
            select(Product).where(Product.tenant_id == tenant_id, Product.id == l["product_id"])
        ).scalar_one_or_none()
        if not product:
            raise rule_violation(f"Product {l['product_id']} not found")

        rtv_line = RtvLine(
            tenant_id=tenant_id,
            rtv_id=rtv.id,
            line_no=idx,
            product_id=product.id,
            sku=product.sku,
            quantity=to_decimal(l["quantity"]),
            uom=l.get("uom", product.uom),
            unit_price=to_decimal(l.get("unit_price", 0)),
            batch_no=l.get("batch_no"),
            rejection_code=l.get("rejection_code"),
            reason=l.get("reason"),
        )
        session.add(rtv_line)

    session.commit()
    return rtv


def dispatch_supplier_rtv(
    tenant_id: uuid.UUID,
    rtv_id: uuid.UUID,
    transporter: str | None = None,
    vehicle_no: str | None = None,
    lr_no: str | None = None,
    notes: str | None = None,
    actor_email: str | None = None,
) -> Rtv:
    rtv = session.execute(
        select(Rtv).where(Rtv.tenant_id == tenant_id, Rtv.id == rtv_id)
    ).scalar_one_or_none()
    if not rtv:
        raise rule_violation("RTV not found")
    if rtv.status != "approved":
        raise rule_violation(f"Cannot dispatch RTV in '{rtv.status}' status")

    lines = session.execute(select(RtvLine).where(RtvLine.rtv_id == rtv.id)).scalars().all()
    total_debit_amount = Decimal(0)

    for line in lines:
        qty = line.quantity
        total_debit_amount += qty * line.unit_price

        # Issue stock out of warehouse (quarantine or damaged or available)
        inventory_ledger.post(
            LedgerPosting(
                tenant_id=tenant_id,
                product_id=line.product_id,
                sku=line.sku,
                warehouse_id=rtv.warehouse_id,
                quantity=decimal_str(-qty),
                uom=line.uom,
                bucket="quarantine",
                movement_type="issue",
                reference_type="rtv",
                reference_id=f"{rtv.number}:{line.line_no}",
                reference_no=rtv.number,
                batch_no=line.batch_no,
                unit_cost=decimal_str(line.unit_price),
                reason=f"Return to Vendor {rtv.vendor_name} ({rtv.return_reason})",
                actor_id=actor_email,
            )
        )

    # Create draft AP Debit Note in credit_notes table (inbound direction)
    if total_debit_amount > 0:
        dn_number = next_document_number(tenant_id, "DN")
        debit_note = CreditNote(
            tenant_id=tenant_id,
            number=dn_number,
            direction="inbound",  # AP debit note from vendor
            party_id=rtv.vendor_id,
            party_name=rtv.vendor_name,
            amount=total_debit_amount,
            currency="INR",
            period=datetime.now(timezone.utc).strftime("%Y-%m"),
            reason=f"Return to Vendor under {rtv.number}: {rtv.return_reason}",
            status="applied",
            created_by=actor_email,
        )
        session.add(debit_note)
        session.flush()

        rtv.debit_note_id = debit_note.id
        rtv.debit_note_number = debit_note.number

    rtv.status = "completed"
    rtv.transporter = transporter
    rtv.vehicle_no = vehicle_no
    rtv.lr_no = lr_no
    rtv.dispatched_at = datetime.now(timezone.utc)
    rtv.completed_at = datetime.now(timezone.utc)
    if notes:
        rtv.notes = f"{rtv.notes or ''}\n{notes}".strip()

    session.commit()
    return rtv
