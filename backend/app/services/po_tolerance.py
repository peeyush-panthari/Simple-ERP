"""Over-receipt tolerance - ported 1:1 from domain/tolerance.ts.

Suppliers routinely ship a little over or under on bulk commodities, so a
hard equality check would block legitimate receipts. The allowance is a
percentage of the ordered quantity, applied to received *plus* rejected -
rejecting material still means it arrived and was counted.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import rule_violation
from app.core.money import decimal_str, div, is_negative, mul, round_dp, to_decimal


@dataclass
class LineReceipt:
    line_id: str
    sku: str
    ordered_qty: str
    received_qty: str
    rejected_qty: str


@dataclass
class ReceiptDelta:
    line_id: str
    accepted_qty: str
    rejected_qty: str


def max_receivable(ordered_qty, tolerance_percent):
    return mul(ordered_qty, to_decimal(1) + div(tolerance_percent, 100))


def open_quantity(line: LineReceipt):
    consumed = to_decimal(line.received_qty) + to_decimal(line.rejected_qty)
    open_ = to_decimal(line.ordered_qty) - consumed
    return open_ if not is_negative(open_) else to_decimal(0)


def assert_within_tolerance(line: LineReceipt, delta: ReceiptDelta, tolerance_percent) -> None:
    incoming = to_decimal(delta.accepted_qty) + to_decimal(delta.rejected_qty)
    if is_negative(incoming):
        raise rule_violation(f"Receipt quantities for {line.sku} cannot be negative", code="RECEIPT_QUANTITY_INVALID")
    already = to_decimal(line.received_qty) + to_decimal(line.rejected_qty)
    ceiling = max_receivable(line.ordered_qty, tolerance_percent)
    total = already + incoming

    if total > ceiling:
        raise rule_violation(
            f"Receiving {decimal_str(incoming)} of {line.sku} would bring the total to {decimal_str(total)} against "
            f"{decimal_str(line.ordered_qty)} ordered — the limit with {decimal_str(tolerance_percent)}% "
            f"tolerance is {decimal_str(round_dp(ceiling, 3))}. Amend the purchase order if the extra quantity is genuinely expected",
            code="RECEIPT_EXCEEDS_TOLERANCE",
            meta={"sku": line.sku, "ordered": line.ordered_qty, "alreadyReceived": decimal_str(already), "incoming": decimal_str(incoming), "ceiling": decimal_str(ceiling)},
        )


def line_receipt_status(line: LineReceipt, tolerance_percent) -> str:
    """A line counts as closed once the *accepted* quantity meets the order, or
    once accepted + rejected has consumed the tolerance ceiling (nothing more
    is coming, and the shortfall is a claim against the vendor rather than an
    open receipt)."""
    received = to_decimal(line.received_qty)
    ordered = to_decimal(line.ordered_qty)
    if received == 0 and to_decimal(line.rejected_qty) == 0:
        return "none"
    if received >= ordered:
        return "full"
    if received + to_decimal(line.rejected_qty) >= max_receivable(ordered, tolerance_percent):
        return "full"
    return "partial"


def document_receipt_status(lines: list[LineReceipt], tolerance_percent) -> str:
    if not lines:
        return "none"
    statuses = [line_receipt_status(l, tolerance_percent) for l in lines]
    if all(s == "full" for s in statuses):
        return "full"
    if all(s == "none" for s in statuses):
        return "none"
    return "partial"
