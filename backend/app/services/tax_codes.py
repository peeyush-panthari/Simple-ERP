"""Server-side tax recalculation - ported 1:1 from packages/shared/src/util/tax.ts.

Client-supplied totals are never trusted - lines are recomputed here before
persistence. Indian GST rate table keyed by HSN-style tax code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.money import decimal_str, div, mul, round_dp, to_decimal


@dataclass
class TaxCode:
    code: str
    description: str
    rate_percent: str
    splittable: bool


GST_TAX_CODES: dict[str, TaxCode] = {
    "GST0": TaxCode("GST0", "Exempt / nil rated", "0", True),
    "GST5": TaxCode("GST5", "GST 5%", "5", True),
    "GST12": TaxCode("GST12", "GST 12%", "12", True),
    "GST18": TaxCode("GST18", "GST 18%", "18", True),
    "GST28": TaxCode("GST28", "GST 28%", "28", True),
    "EXEMPT": TaxCode("EXEMPT", "Out of scope", "0", False),
}


def tax_rate_for(tax_code: str):
    entry = GST_TAX_CODES.get(tax_code)
    if not entry:
        raise ValueError(f"Unknown tax code: {tax_code}")
    return to_decimal(entry.rate_percent)


def is_known_tax_code(tax_code: str) -> bool:
    return tax_code in GST_TAX_CODES


@dataclass
class TaxableLine:
    quantity: object
    unit_price: object
    tax_code: str
    discount: object = 0


@dataclass
class ComputedLine:
    net_amount: str
    tax_rate: str
    tax_amount: str
    gross_amount: str


@dataclass
class ComputedTotals:
    lines: list[ComputedLine]
    subtotal: str
    tax_total: str
    total: str
    by_tax_code: list[dict] = field(default_factory=list)


def compute_totals(lines: list[TaxableLine], extra_charges=0) -> ComputedTotals:
    computed: list[ComputedLine] = []
    buckets: dict[str, dict] = {}
    subtotal = to_decimal(0)
    tax_total = to_decimal(0)

    for line in lines:
        gross = mul(line.quantity, line.unit_price)
        net = round_dp(gross - to_decimal(line.discount or 0), 2)
        rate = tax_rate_for(line.tax_code)
        tax = round_dp(div(mul(net, rate), 100), 2)

        computed.append(
            ComputedLine(
                net_amount=decimal_str(net),
                tax_rate=decimal_str(rate),
                tax_amount=decimal_str(tax),
                gross_amount=decimal_str(net + tax),
            )
        )

        subtotal = subtotal + net
        tax_total = tax_total + tax
        bucket = buckets.setdefault(line.tax_code, {"taxable": to_decimal(0), "tax": to_decimal(0)})
        bucket["taxable"] = bucket["taxable"] + net
        bucket["tax"] = bucket["tax"] + tax

    charges = to_decimal(extra_charges)
    subtotal_r = round_dp(subtotal, 2)
    tax_total_r = round_dp(tax_total, 2)
    return ComputedTotals(
        lines=computed,
        subtotal=decimal_str(subtotal_r),
        tax_total=decimal_str(tax_total_r),
        total=decimal_str(round_dp(subtotal_r + tax_total_r + charges, 2)),
        by_tax_code=[
            {"taxCode": code, "taxableAmount": decimal_str(round_dp(b["taxable"], 2)), "taxAmount": decimal_str(round_dp(b["tax"], 2))}
            for code, b in buckets.items()
        ],
    )


def split_gst(tax_amount, intra_state: bool) -> dict:
    total = to_decimal(tax_amount)
    if not intra_state:
        return {"cgst": "0", "sgst": "0", "igst": decimal_str(round_dp(total, 2))}
    half = round_dp(div(total, 2), 2)
    return {"cgst": decimal_str(half), "sgst": decimal_str(round_dp(total - half, 2)), "igst": "0"}
