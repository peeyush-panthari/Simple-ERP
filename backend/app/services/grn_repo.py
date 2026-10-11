"""GRN queries + API projections. Ported from
backend_py/app/services/grn_repo.py."""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import session
from app.core.errors import not_found
from app.core.money import decimal_str, div, mul, round_dp, to_decimal
from app.models.doc_sequence import DocSequence
from app.models.grn import Grn
from app.models.grn_line import GrnLine
from app.models.inventory_item import InventoryItem
from app.models.po_line import PoLine
from app.models.product import Product
from app.models.warehouse import Warehouse


def find_grn(tenant_id: uuid.UUID, grn_id: uuid.UUID) -> Grn | None:
    return Grn.query.filter_by(tenant_id=tenant_id, id=grn_id).first()


def require_grn(tenant_id: uuid.UUID, grn_id: uuid.UUID) -> Grn:
    grn = find_grn(tenant_id, grn_id)
    if not grn:
        raise not_found("Goods receipt")
    return grn


def grn_lines(grn_id: uuid.UUID) -> list[GrnLine]:
    return GrnLine.query.filter_by(grn_id=grn_id, deleted_at=None).order_by(GrnLine.line_no).all()


def grn_items(grn_id: uuid.UUID) -> list[InventoryItem]:
    return InventoryItem.query.filter_by(grn_id=grn_id, deleted_at=None).order_by(InventoryItem.inventory_id).all()


def received_goods_values(grn_ids: list[uuid.UUID]) -> dict[str, str]:
    """Sum of receivedQty x the PO's unit price, GST-inclusive, per GRN."""
    if not grn_ids:
        return {}
    rows = (
        session.query(GrnLine.grn_id, GrnLine.received_qty, GrnLine.unit_price, PoLine.tax_rate)
        .outerjoin(PoLine, PoLine.id == GrnLine.po_line_id)
        .filter(GrnLine.grn_id.in_(grn_ids))
        .all()
    )
    totals: dict[uuid.UUID, object] = {}
    for grn_id, received_qty, unit_price, tax_rate in rows:
        net = round_dp(mul(received_qty or 0, unit_price or 0), 2)
        tax = round_dp(div(mul(net, tax_rate or 0), 100), 2)
        totals[grn_id] = totals.get(grn_id, to_decimal(0)) + net + tax
    return {str(gid): decimal_str(round_dp(total, 2)) for gid, total in totals.items()}


def warehouse_names(warehouse_ids: list[uuid.UUID]) -> dict[str, str]:
    if not warehouse_ids:
        return {}
    rows = session.query(Warehouse.id, Warehouse.name).filter(Warehouse.id.in_(warehouse_ids)).all()
    return {str(wid): name for wid, name in rows}


def reserve_inventory_ids(tenant_id: uuid.UUID, count: int) -> list[str]:
    """Reserves `count` consecutive Inventory IDs from the tenant's INV
    counter in a single atomic bump. Must be called inside the caller's
    transaction."""
    if count <= 0:
        return []
    stmt = (
        pg_insert(DocSequence)
        .values(tenant_id=tenant_id, prefix="INV", current_value=100000 + count)
        .on_conflict_do_update(index_elements=["tenant_id", "prefix"], set_={"current_value": DocSequence.current_value + count})
        .returning(DocSequence.current_value)
    )
    end = session.execute(stmt).scalar_one()
    start = end - count + 1
    return [f"INV-{str(v).zfill(6)}" for v in range(start, end + 1)]


# ---- API projections --------------------------------------------------------


def to_grn_api(
    row: Grn,
    lines: list[GrnLine] | None = None,
    *,
    received_goods_value: str | None = None,
    warehouse_name: str | None = None,
) -> dict:
    result = {
        "id": str(row.id),
        "number": row.number,
        "poId": str(row.po_id),
        "poNumber": row.po_number,
        "vendorId": str(row.vendor_id) if row.vendor_id else None,
        "vendorName": row.vendor_name,
        "warehouseId": str(row.warehouse_id),
        "warehouseCode": row.warehouse_code,
        "warehouseName": warehouse_name if warehouse_name is not None else warehouse_names([row.warehouse_id]).get(str(row.warehouse_id), row.warehouse_code),
        "receivedGoodsValue": received_goods_value if received_goods_value is not None else received_goods_values([row.id]).get(str(row.id), "0.00"),
        "status": row.status,
        "receivedDate": row.received_date.isoformat() if row.received_date else None,
        "vehicleNumber": row.vehicle_number,
        "deliveryNote": row.delivery_note,
        "gateEntryNo": row.gate_entry_no,
        "stickerSizeId": str(row.sticker_size_id) if row.sticker_size_id else None,
        "stickerSizeName": row.sticker_size_name,
        "hasVendorQr": row.has_vendor_qr,
        "inspectedBy": row.inspected_by,
        "inspectedAt": row.inspected_at.isoformat() if row.inspected_at else None,
        "postedBy": row.posted_by,
        "postedAt": row.posted_at.isoformat() if row.posted_at else None,
        "rejectionReason": row.rejection_reason,
        "cancellationReason": row.cancellation_reason,
        "notes": row.notes,
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }
    if lines is not None:
        names = _product_names(row.tenant_id, lines)
        result["lines"] = [to_grn_line_api(l, product_name=names.get(l.product_id)) for l in lines]
    return result


def _product_names(tenant_id: uuid.UUID, lines: list[GrnLine]) -> dict[uuid.UUID, str]:
    product_ids = {l.product_id for l in lines}
    if not product_ids:
        return {}
    rows = Product.query.filter(Product.tenant_id == tenant_id, Product.id.in_(product_ids)).with_entities(Product.id, Product.name).all()
    return {r[0]: r[1] for r in rows}


def to_grn_line_api(row: GrnLine, product_name: str | None = None) -> dict:
    return {
        "id": str(row.id),
        "lineNo": row.line_no,
        "poLineId": str(row.po_line_id) if row.po_line_id else None,
        "productId": str(row.product_id),
        "sku": row.sku,
        "productName": product_name,
        "orderedQty": decimal_str(row.ordered_qty) if row.ordered_qty is not None else None,
        "receivedQty": decimal_str(row.received_qty),
        "acceptedQty": decimal_str(row.accepted_qty),
        "rejectedQty": decimal_str(row.rejected_qty),
        "uom": row.uom,
        "batchNo": row.batch_no,
        "expiryDate": row.expiry_date.isoformat() if row.expiry_date else None,
        "manufactureDate": row.manufacture_date.isoformat() if row.manufacture_date else None,
        "locationId": str(row.location_id) if row.location_id else None,
        "locationCode": row.location_code,
        "qualityStatus": row.quality_status,
        "rejectionCode": row.rejection_code,
        "rejectionNote": row.rejection_note,
        "unitPrice": decimal_str(row.unit_price),
    }


def to_inventory_item_api(row: InventoryItem) -> dict:
    return {
        "id": str(row.id),
        "inventoryId": row.inventory_id,
        "grnId": str(row.grn_id),
        "grnLineId": str(row.grn_line_id),
        "poId": str(row.po_id) if row.po_id else None,
        "poNumber": row.po_number,
        "productId": str(row.product_id),
        "sku": row.sku,
        "warehouseId": str(row.warehouse_id),
        "status": row.status,
        "kind": row.kind,
        "quantity": decimal_str(row.quantity),
        "uom": row.uom,
        "receivedDate": row.received_date.isoformat() if row.received_date else None,
        "acceptedQty": decimal_str(row.accepted_qty),
        "rejectedQty": decimal_str(row.rejected_qty),
        "consumedQty": decimal_str(row.consumed_qty),
        "writtenOffQty": decimal_str(row.written_off_qty),
        "availableQty": decimal_str(to_decimal(row.accepted_qty) - to_decimal(row.consumed_qty) - to_decimal(row.written_off_qty)),
        "batchNo": row.batch_no,
        "qcBy": row.qc_by,
        "qcAt": row.qc_at.isoformat() if row.qc_at else None,
        "rejectionCode": row.rejection_code,
        "rejectionNote": row.rejection_note,
        "locationId": str(row.location_id) if row.location_id else None,
        "locationCode": row.location_code,
        "transferId": str(row.transfer_id) if row.transfer_id else None,
        "bucket": row.bucket,
        "vendorQrEnabled": row.vendor_qr_enabled,
        "vendorInventoryId": row.vendor_inventory_id,
        "consumedRunId": str(row.consumed_run_id) if row.consumed_run_id else None,
        "consumedRunNumber": row.consumed_run_number,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }
