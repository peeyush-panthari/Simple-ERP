"""Rules deciding whether a goods receipt may be created and posted - ported
1:1 from domain/receiving.ts. Pure - the route supplies the PO snapshot and
the location facts."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import rule_violation
from app.core.money import decimal_str, div, mul, round_dp, to_decimal


@dataclass
class PoLineSnapshot:
    id: str
    product_id: str
    sku: str
    uom: str
    ordered_qty: str
    received_qty: str
    rejected_qty: str
    open_qty: str
    unit_price: str


@dataclass
class ReceiptLineInput:
    po_line_id: str
    received_qty: str
    accepted_qty: str
    rejected_qty: str
    batch_no: str | None
    expiry_date: str | None
    location_id: str | None
    rejection_code: str | None


@dataclass
class ProductRules:
    product_id: str
    sku: str
    status: str
    batch_tracked: bool
    expiry_tracked: bool
    type: str
    uom: str


@dataclass
class LocationRules:
    id: str
    code: str
    warehouse_id: str
    status: str
    type: str
    allowed_product_types: list[str]


def max_receivable(ordered_qty, tolerance_percent):
    return mul(ordered_qty, to_decimal(1) + div(tolerance_percent, 100))


def receipt_line_problems(
    input_: ReceiptLineInput,
    index: int,
    po_line: PoLineSnapshot | None,
    product: ProductRules | None,
    location: LocationRules | None,
    *,
    tolerance_percent: str,
    warehouse_id: str,
    warehouse_allowed_types: list[str],
) -> list[dict]:
    field = f"lines.{index}"
    errors: list[dict] = []

    if not po_line:
        errors.append({"field": field, "message": f"PO line {input_.po_line_id} is not on this purchase order"})
        return errors
    if not product:
        errors.append({"field": field, "message": f"Product {po_line.sku} could not be resolved from the product master"})
        return errors

    received = to_decimal(input_.received_qty)
    accepted = to_decimal(input_.accepted_qty)
    rejected = to_decimal(input_.rejected_qty)

    if received <= 0:
        errors.append({"field": f"{field}.receivedQty", "message": f"Received quantity for {po_line.sku} must be greater than zero"})
    if accepted + rejected > received:
        errors.append(
            {
                "field": f"{field}.acceptedQty",
                "message": f"{po_line.sku}: accepted ({decimal_str(accepted)}) plus rejected ({decimal_str(rejected)}) exceeds the received quantity ({decimal_str(received)})",
            }
        )
    if rejected > 0 and not input_.rejection_code:
        errors.append({"field": f"{field}.rejectionCode", "message": f"{po_line.sku}: a rejection reason code is required when any quantity is rejected"})

    already = to_decimal(po_line.received_qty) + to_decimal(po_line.rejected_qty)
    ceiling = max_receivable(po_line.ordered_qty, tolerance_percent)
    if already + received > ceiling:
        errors.append(
            {
                "field": f"{field}.receivedQty",
                "message": (
                    f"{po_line.sku}: receiving {decimal_str(received)} would bring the total to {decimal_str(already + received)} "
                    f"against {decimal_str(po_line.ordered_qty)} ordered (limit {decimal_str(round_dp(ceiling, 3))} with "
                    f"{decimal_str(tolerance_percent)}% tolerance). Amend the purchase order first"
                ),
            }
        )

    if input_.batch_no is None and product.batch_tracked:
        errors.append({"field": f"{field}.batchNo", "message": f"{po_line.sku} is batch tracked — a batch number is required"})

    if input_.location_id:
        if not location:
            errors.append({"field": f"{field}.locationId", "message": f"Storage location {input_.location_id} does not exist"})
        else:
            if location.warehouse_id != warehouse_id:
                errors.append({"field": f"{field}.locationId", "message": f"Location {location.code} belongs to a different warehouse"})
            if location.status != "active":
                errors.append({"field": f"{field}.locationId", "message": f"Location {location.code} is {location.status}"})
            if location.allowed_product_types and product.type not in location.allowed_product_types:
                errors.append({"field": f"{field}.locationId", "message": f"Location {location.code} does not accept {product.type.replace('_', ' ')}"})

    if warehouse_allowed_types and product.type not in warehouse_allowed_types:
        errors.append({"field": field, "message": f"This warehouse does not stock {product.type.replace('_', ' ')} ({po_line.sku})"})

    return errors


def assert_receipt_valid(errors: list[dict], grn_label: str) -> None:
    if not errors:
        return
    raise rule_violation(f"{grn_label} cannot be recorded: {'; '.join(e['message'] for e in errors)}", code="GRN_VALIDATION_FAILED", meta={"errors": errors})


def quality_status_for(accepted, rejected, received) -> str:
    a = to_decimal(accepted)
    r = to_decimal(rejected)
    total = to_decimal(received)
    if a + r == 0:
        return "pending"
    if r == 0 and a >= total:
        return "passed"
    if a == 0 and r >= total:
        return "failed"
    return "partial"
