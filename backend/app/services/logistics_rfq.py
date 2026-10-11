"""Carrier RFQ/quotation rules - ported 1:1 from domain/rfq.ts.

Two output fields here (`premiumPercent` in requires_award_justification,
`variance` in assert_invoice_within_quotation) use the raw, unrounded
scale-6 decimal_str() form pinned by Node's own tests (e.g. "4.000000",
"1000.000000") - not the 2dp-trimmed form used almost everywhere else in
this codebase. Do not "normalize" these to match the rest by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import rule_violation
from app.core.money import decimal_str, is_zero, round_dp, to_decimal


def assert_enough_invitations(invited: int, minimum: int, rfq_number: str) -> None:
    if invited < minimum:
        plural = "" if invited == 1 else "s"
        raise rule_violation(
            f"{rfq_number} has only {invited} carrier invitation{plural} — at least {minimum} are required before a quotation can be awarded",
            code="RFQ_INSUFFICIENT_INVITATIONS",
            meta={"invited": invited, "minimum": minimum},
        )


@dataclass
class QuoteCandidate:
    id: str
    carrier_id: str
    carrier_name: str
    amount: str
    status: str
    valid_until: str | None = None


def assert_quote_awardable(quote: QuoteCandidate | None, rfq_number: str, as_of: str) -> QuoteCandidate:
    if not quote:
        raise rule_violation(f"No such quotation on {rfq_number}", code="QUOTATION_NOT_FOUND")
    if quote.status == "approved":
        raise rule_violation("This quotation is already awarded", code="QUOTATION_ALREADY_AWARDED")
    if quote.status == "rejected":
        raise rule_violation("This quotation was rejected and cannot be awarded", code="QUOTATION_REJECTED")
    # String comparison on ISO dates - a quotation valid *through* today
    # (validUntil == asOf) is still live, boundary is inclusive.
    if quote.valid_until and quote.valid_until < as_of:
        raise rule_violation(f"{quote.carrier_name}'s quotation expired on {quote.valid_until} — ask them to re-quote", code="QUOTATION_EXPIRED")
    return quote


@dataclass
class AwardJustification:
    required: bool
    cheapest: QuoteCandidate | None
    premium_percent: str


def requires_award_justification(chosen: QuoteCandidate, all_quotes: list[QuoteCandidate], tolerance_percent="5") -> AwardJustification:
    eligible = [q for q in all_quotes if q.status == "received" or q.id == chosen.id]
    cheapest = None
    for q in eligible:
        if cheapest is None or to_decimal(q.amount) < to_decimal(cheapest.amount):
            cheapest = q

    if cheapest is None or cheapest.id == chosen.id:
        return AwardJustification(required=False, cheapest=cheapest, premium_percent="0")
    if is_zero(cheapest.amount):
        return AwardJustification(required=False, cheapest=cheapest, premium_percent="0")

    premium = (to_decimal(chosen.amount) - to_decimal(cheapest.amount)) / to_decimal(cheapest.amount) * to_decimal(100)
    required = premium > to_decimal(tolerance_percent)
    return AwardJustification(required=required, cheapest=cheapest, premium_percent=decimal_str(round_dp(premium, 2)))


def assert_invoice_within_quotation(*, invoice_number: str, amount, quoted_amount: str | None, variance_approved: bool, variance_reason: str | None = None) -> dict:
    if quoted_amount is None:
        return {"variance": None}
    invoice_d = to_decimal(amount)
    quoted_d = to_decimal(quoted_amount)
    if invoice_d <= quoted_d:
        return {"variance": None}

    variance = invoice_d - quoted_d
    if not (variance_approved and (variance_reason or "").strip()):
        raise rule_violation(
            f"{invoice_number} is {decimal_str(variance)} above the approved quotation of {decimal_str(quoted_d)}. Record an approved variance with a reason, or ask the carrier to correct the invoice",
            code="LOGISTICS_INVOICE_EXCEEDS_QUOTATION",
            meta={"invoiceAmount": decimal_str(invoice_d), "quotedAmount": decimal_str(quoted_d), "variance": decimal_str(variance)},
        )
    return {"variance": decimal_str(variance)}
