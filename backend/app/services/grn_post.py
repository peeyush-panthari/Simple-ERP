"""post_grn_tx() - the shared posting routine both the manual /post endpoint
and the auto-post branch of /qc call. Ported from
backend_py/app/services/grn_post.py.

Posting is the moment stock exists: inventory ledger entries and the PO's
received quantities both update inside this same transaction - a failure in
either rolls the whole GRN post back.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.db import session
from app.core.errors import rule_violation
from app.core.money import decimal_str, is_positive, to_decimal
from app.models.finished_good_item import FinishedGoodItem
from app.models.grn import Grn
from app.models.grn_line import GrnLine
from app.models.inventory_item import InventoryItem
from app.models.location import Location
from app.models.product import Product
from app.services import finance_repo, inventory_ledger, procurement_repo, warehouse_repo
from app.core.audit import audit


def post_grn_tx(tenant_id: uuid.UUID, grn: Grn, lines: list[GrnLine], actor_user_id: str | None) -> None:
    quarantine = (
        Location.query.filter_by(tenant_id=tenant_id, warehouse_id=grn.warehouse_id, type="quarantine", status="active")
        .order_by(Location.code)
        .first()
    )
    rejected_total = sum((to_decimal(l.rejected_qty) for l in lines), to_decimal(0))
    if is_positive(rejected_total) and not quarantine:
        raise rule_violation(
            f"{grn.warehouse_code} has no active quarantine location — QC-failed material has nowhere to go. "
            "Create one before completing QC on this receipt",
            code="QUARANTINE_LOCATION_MISSING",
        )

    grn.status = "posted"
    grn.posted_by = actor_user_id
    grn.posted_at = datetime.now(timezone.utc)

    if lines:
        from sqlalchemy import select
        from app.services import grn_repo

        line_ids = [l.id for l in lines]
        items = session.scalars(
            select(InventoryItem).where(
                InventoryItem.grn_line_id.in_(line_ids),
                InventoryItem.deleted_at.is_(None)
            )
        ).all()

        lines_by_id = {l.id: l for l in lines}

        for item in items:
            l = lines_by_id.get(item.grn_line_id)
            if not l:
                continue

            if is_positive(item.accepted_qty) and is_positive(item.rejected_qty):
                rejected_qty = item.rejected_qty

                item.quantity = item.accepted_qty
                item.rejected_qty = to_decimal(0)
                item.status = "accepted"
                if l.location_code:
                    item.location_id = l.location_id
                    item.location_code = l.location_code

                if quarantine:
                    new_inv_id = grn_repo.reserve_inventory_ids(tenant_id, 1)[0]
                    rejected_item = InventoryItem(
                        tenant_id=item.tenant_id,
                        inventory_id=new_inv_id,
                        grn_id=item.grn_id,
                        grn_line_id=item.grn_line_id,
                        po_id=item.po_id,
                        po_number=item.po_number,
                        product_id=item.product_id,
                        sku=item.sku,
                        warehouse_id=item.warehouse_id,
                        status="rejected",
                        kind=item.kind,
                        quantity=rejected_qty,
                        uom=item.uom,
                        received_date=item.received_date,
                        accepted_qty=to_decimal(0),
                        rejected_qty=rejected_qty,
                        batch_no=item.batch_no,
                        qc_by=item.qc_by,
                        qc_at=item.qc_at,
                        rejection_code=item.rejection_code,
                        rejection_note=item.rejection_note,
                        location_id=quarantine.id,
                        location_code=quarantine.code,
                        vendor_qr_enabled=item.vendor_qr_enabled,
                        vendor_inventory_id=item.vendor_inventory_id
                    )
                    session.add(rejected_item)
            else:
                if is_positive(item.accepted_qty) and l.location_code:
                    item.location_id = l.location_id
                    item.location_code = l.location_code
                elif is_positive(item.rejected_qty) and quarantine:
                    item.location_id = quarantine.id
                    item.location_code = quarantine.code

    accepted_total = sum((to_decimal(l.accepted_qty) for l in lines), to_decimal(0))
    audit(
        tenant_id=tenant_id,
        actor_id=None,
        actor_email=None,
        action="grn.posted",
        entity_type="grn",
        entity_id=str(grn.id),
        meta={"number": grn.number, "po": grn.po_number, "accepted": decimal_str(accepted_total), "rejected": decimal_str(rejected_total)},
    )

    payload = {
        "grnId": str(grn.id),
        "grnNumber": grn.number,
        "poId": str(grn.po_id),
        "poNumber": grn.po_number,
        "vendorId": str(grn.vendor_id) if grn.vendor_id else None,
        "warehouseId": str(grn.warehouse_id),
        "warehouseCode": grn.warehouse_code,
        "receivedDate": grn.received_date.isoformat() if grn.received_date else None,
        "lines": [
            {
                "grnLineId": str(l.id),
                "poLineId": str(l.po_line_id) if l.po_line_id else None,
                "productId": str(l.product_id),
                "sku": l.sku,
                "uom": l.uom,
                "acceptedQty": decimal_str(l.accepted_qty),
                "rejectedQty": decimal_str(l.rejected_qty),
                "batchNo": l.batch_no,
                "expiryDate": l.expiry_date.isoformat() if l.expiry_date else None,
                "unitPrice": decimal_str(l.unit_price),
                "locationId": str(l.location_id) if is_positive(l.accepted_qty) and l.location_id else None,
                "locationCode": l.location_code if is_positive(l.accepted_qty) else None,
                "quarantineLocationId": str(quarantine.id) if is_positive(l.rejected_qty) and quarantine else None,
                "quarantineLocationCode": quarantine.code if is_positive(l.rejected_qty) and quarantine else None,
            }
            for l in lines
        ],
    }

    # The GRN is warehouse's fact; posting it into the stock ledger and onto
    # the PO's received quantities are two separate facts owned by inventory
    # and procurement respectively - direct calls, same transaction.
    inventory_ledger.post_grn_receipt(tenant_id, payload)
    procurement_repo.apply_grn_receipt(tenant_id, payload)
    finance_repo.ensure_period_open(tenant_id, grn.received_date)

    # A Finished Good can be bought in (GRN) instead of manufactured
    # (Production). Order Allocation only ever picks from FinishedGoodItem,
    # so convert the accepted portion of any finished-good line's
    # InventoryItem(s) into real FinishedGoodItem row(s) now that receiving
    # and ledger posting are both settled.
    _convert_finished_good_receipts(tenant_id, lines)


def _convert_inventory_item_to_finished_good(item: InventoryItem) -> FinishedGoodItem:
    """Converts one QC-passed, GRN-received InventoryItem into a
    FinishedGoodItem - the bought-in mirror of production output. Caller
    must flush/commit."""
    fg_id = warehouse_repo.reserve_finished_good_ids(item.tenant_id, 1)[0]
    fg_item = FinishedGoodItem(
        tenant_id=item.tenant_id,
        inventory_id=fg_id,
        source_inventory_item_id=item.id,
        product_id=item.product_id,
        sku=item.sku,
        warehouse_id=item.warehouse_id,
        kind=item.kind,
        quantity=item.accepted_qty,
        uom=item.uom,
        received_date=item.received_date,
        batch_no=item.batch_no,
        location_id=item.location_id,
        location_code=item.location_code,
    )
    session.add(fg_item)
    item.consumed_qty = item.accepted_qty
    return fg_item


def _convert_finished_good_receipts(tenant_id: uuid.UUID, lines: list[GrnLine]) -> None:
    if not lines:
        return
    product_ids = {l.product_id for l in lines}
    fg_product_ids = {
        p.id for p in Product.query.filter(Product.tenant_id == tenant_id, Product.id.in_(product_ids), Product.type == "finished_good").all()
    }
    if not fg_product_ids:
        return
    fg_line_ids = [l.id for l in lines if l.product_id in fg_product_ids]
    if not fg_line_ids:
        return
    items = InventoryItem.query.filter(
        InventoryItem.tenant_id == tenant_id,
        InventoryItem.grn_line_id.in_(fg_line_ids),
        InventoryItem.accepted_qty > 0,
        InventoryItem.deleted_at.is_(None),
    ).all()
    for item in items:
        _convert_inventory_item_to_finished_good(item)
