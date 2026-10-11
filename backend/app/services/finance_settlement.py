"""Payment allocation/settlement arithmetic - ported 1:1 from domain/
settlement.ts. Shared by both AP and AR.

`position()` is display-only (used by to_ap_api/to_ar_api's outstanding/
settled fields) - it is NOT used to gate actual payment posting, which
recomputes outstanding itself under a row lock in finance_repo.record_payment.

`assert_allocations_valid()`'s "credit" overpayment policy creates a phantom
credit: the excess is absorbed straight into paid_amount (which can then
exceed amount - there is deliberately no paid_amount<=amount DB constraint)
and reported transiently in the response's overpayments[], never persisted
as an actual ledger balance anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.errors import rule_violation
from app.core.money import decimal_str, to_decimal


@dataclass
class SettlementPosition:
    amount: str
    paid_amount: str
    credit_amount: str
    outstanding: str
    settled: bool


def position(amount, paid_amount, credit_amount="0") -> SettlementPosition:
    amount_d = to_decimal(amount)
    paid_d = to_decimal(paid_amount)
    credit_d = to_decimal(credit_amount)
    outstanding = amount_d - paid_d - credit_d
    if outstanding < 0:
        outstanding = to_decimal(0)
    settled = (paid_d + credit_d) >= amount_d
    return SettlementPosition(amount=decimal_str(amount_d), paid_amount=decimal_str(paid_d), credit_amount=decimal_str(credit_d), outstanding=decimal_str(outstanding), settled=settled)


@dataclass
class Overpayment:
    invoice_number: str
    excess: str


@dataclass
class AllocationSummary:
    total_allocated: str
    unallocated: str
    overpayments: list[Overpayment] = field(default_factory=list)


def assert_allocations_valid(*, payment_amount, allocations: list[dict], overpayment_policy: str, direction: str) -> AllocationSummary:
    """allocations: [{"invoiceNumber": str, "requested": str, "outstanding": str}, ...]"""
    payment_d = to_decimal(payment_amount)
    if payment_d <= 0:
        raise rule_violation("Payment amount must be greater than zero", code="PAYMENT_AMOUNT_INVALID")

    overpayments: list[Overpayment] = []
    total = to_decimal(0)
    for alloc in allocations:
        requested = to_decimal(alloc["requested"])
        outstanding = to_decimal(alloc["outstanding"])
        if requested <= 0:
            raise rule_violation("Each allocation amount must be greater than zero", code="ALLOCATION_AMOUNT_INVALID")
        if requested > outstanding:
            excess = requested - outstanding
            if overpayment_policy == "block":
                code = "AP_OVERPAYMENT" if direction == "outbound" else "AR_OVERPAYMENT"
                raise rule_violation(f"{alloc['invoiceNumber']} would be overpaid by {decimal_str(excess)} - only {decimal_str(outstanding)} is outstanding", code=code)
            overpayments.append(Overpayment(invoice_number=alloc["invoiceNumber"], excess=decimal_str(excess)))
        total += requested

    if total > payment_d:
        raise rule_violation(f"Allocations total {decimal_str(total)} exceed the payment amount {decimal_str(payment_d)}", code="ALLOCATION_EXCEEDS_PAYMENT")

    return AllocationSummary(total_allocated=decimal_str(total), unallocated=decimal_str(payment_d - total), overpayments=overpayments)


def requires_payment_approval(amount, threshold) -> bool:
    return to_decimal(amount) > to_decimal(threshold)
