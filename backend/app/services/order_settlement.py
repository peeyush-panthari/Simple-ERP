"""Payment settlement + the logistics-raise decision - ported 1:1 from
domain/settlement.ts."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import rule_violation
from app.core.money import decimal_str, is_negative, is_positive, is_zero, to_decimal


@dataclass
class SettlementPosition:
    total: str
    paid_amount: str
    outstanding: str
    fully_paid: bool
    paid_percent: int


def settlement_position(total, paid_amount) -> SettlementPosition:
    total_d = to_decimal(total)
    paid_d = to_decimal(paid_amount)
    outstanding = total_d - paid_d
    if is_negative(outstanding):
        outstanding = to_decimal(0)
    # A zero-total order is never "fully paid" by this predicate even though
    # outstanding is 0 - faithful edge case, not "fixed" into intuitive.
    fully_paid = paid_d >= total_d and is_positive(total_d)
    # Display-only rounding, never used for a decision.
    paid_percent = 0 if is_zero(total_d) else round(float(paid_d) / float(total_d) * 100)
    paid_percent = max(0, min(100, paid_percent))
    return SettlementPosition(total=decimal_str(total_d), paid_amount=decimal_str(paid_d), outstanding=decimal_str(outstanding), fully_paid=fully_paid, paid_percent=paid_percent)


@dataclass
class LogisticsTriggerDecision:
    allowed: bool
    automatic: bool
    requires_override: bool
    reason: str


def evaluate_logistics_trigger(*, number: str, settlement: SettlementPosition, has_override_permission: bool, override_reason: str | None) -> LogisticsTriggerDecision:
    if settlement.fully_paid:
        return LogisticsTriggerDecision(allowed=True, automatic=True, requires_override=False, reason="Order is fully settled")
    if not has_override_permission:
        return LogisticsTriggerDecision(
            allowed=False,
            automatic=False,
            requires_override=True,
            reason=f"{number} still has {settlement.outstanding} outstanding. Raising logistics before full payment needs the order:override-logistics permission",
        )
    reason = (override_reason or "").strip()
    if not reason:
        return LogisticsTriggerDecision(allowed=False, automatic=False, requires_override=True, reason="An audited reason is required to raise logistics before full payment")
    return LogisticsTriggerDecision(allowed=True, automatic=False, requires_override=True, reason=reason)


def assert_logistics_allowed(decision: LogisticsTriggerDecision) -> None:
    if not decision.allowed:
        raise rule_violation(decision.reason, code="LOGISTICS_BEFORE_PAYMENT_BLOCKED")


def assert_invoice_matches_order(order_number: str, order_total, invoice_total) -> None:
    order_d = to_decimal(order_total)
    invoice_d = to_decimal(invoice_total)
    if order_d != invoice_d:
        raise rule_violation(
            f"Invoice total {decimal_str(invoice_d)} does not match order {order_number} total {decimal_str(order_d)}",
            code="INVOICE_TOTAL_MISMATCH",
            meta={"orderTotal": decimal_str(order_d), "invoiceTotal": decimal_str(invoice_d), "difference": decimal_str(invoice_d - order_d)},
        )
