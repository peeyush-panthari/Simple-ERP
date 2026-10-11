"""PO/GRN/Invoice three-way match - ported 1:1 from domain/three-way-match.ts.

Directional, not magnitude-based, for issue generation: only POSITIVE
variance (invoiced more than received, or invoiced above the ordered price)
raises an issue - under-invoicing is the vendor's loss and is never flagged,
even though the variance/percent figures themselves are signed.

The single most important quirk here: status is "matched" whenever
`not issues OR the net variance percent is within tolerance` - a match with
real per-line issues can still be reported (and persisted) as "matched" if
the aggregate variance nets out small. issues[]/match_note still carry the
raw per-line problems even when match_status says "matched" - do not treat
a non-empty issues list as implying status=="variance".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.errors import rule_violation
from app.core.money import decimal_str, mul, round_dp, to_decimal


@dataclass
class MatchLine:
    po_line_id: str | None
    sku: str | None
    ordered_qty: str
    unit_price: str
    received_qty: str
    invoiced_qty: str
    invoiced_unit_price: str


@dataclass
class MatchLineResult:
    po_line_id: str | None
    sku: str | None
    quantity_variance: str
    price_variance: str
    ok: bool


@dataclass
class MatchResult:
    status: str  # "matched" | "variance" | "unmatched" | "not_applicable"
    variance: str
    variance_percent: str
    issues: list[str] = field(default_factory=list)
    lines: list[MatchLineResult] = field(default_factory=list)


def three_way_match(lines: list[MatchLine], tolerance_percent) -> MatchResult:
    if not lines:
        return MatchResult(status="not_applicable", variance="0", variance_percent="0")

    issues: list[str] = []
    line_results: list[MatchLineResult] = []
    received_value = to_decimal(0)
    invoiced_value = to_decimal(0)

    for line in lines:
        quantity_variance = to_decimal(line.invoiced_qty) - to_decimal(line.received_qty)
        price_variance = to_decimal(line.invoiced_unit_price) - to_decimal(line.unit_price)

        received_value += mul(line.received_qty, line.unit_price)
        invoiced_value += mul(line.invoiced_qty, line.invoiced_unit_price)

        ok = True
        if quantity_variance > 0:
            issues.append(f"{line.sku or line.po_line_id}: invoiced for more than received ({decimal_str(line.invoiced_qty)} vs {decimal_str(line.received_qty)})")
            ok = False
        if price_variance > 0:
            issues.append(f"{line.sku or line.po_line_id}: invoiced price {decimal_str(line.invoiced_unit_price)} is above the ordered price {decimal_str(line.unit_price)}")
            ok = False

        line_results.append(MatchLineResult(po_line_id=line.po_line_id, sku=line.sku, quantity_variance=decimal_str(quantity_variance), price_variance=decimal_str(price_variance), ok=ok))

    variance = invoiced_value - received_value
    if received_value == 0:
        variance_percent = to_decimal(0)
    else:
        variance_percent = round_dp((variance / received_value) * to_decimal(100), 4)

    within_tolerance = abs(variance_percent) <= to_decimal(tolerance_percent)
    status = "matched" if (not issues or within_tolerance) else "variance"

    return MatchResult(status=status, variance=decimal_str(round_dp(variance, 2)), variance_percent=decimal_str(variance_percent), issues=issues, lines=line_results)


def assert_match_approved(result: MatchResult, invoice_number: str, override_reason: str | None = None) -> None:
    if result.status in ("matched", "not_applicable"):
        return
    if override_reason and override_reason.strip():
        return
    raise rule_violation(
        f"{invoice_number} failed three-way match: {'; '.join(result.issues)}",
        code="THREE_WAY_MATCH_FAILED",
        meta={"variance": result.variance, "variancePercent": result.variance_percent, "issues": result.issues},
    )
