"""Product-specific UOM conversions - ported 1:1 from domain/conversion.ts.

Order of preference: (1) explicit product-specific pack size, (2) reverse of
one, (3) the shared dimensional table. Anything else is refused rather than
guessed - a wrong conversion silently corrupts stock.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import rule_violation
from app.core.money import div, mul, to_decimal
from app.services.uom import UomConversionError, can_convert, convert, is_known_uom


@dataclass
class ProductConversion:
    from_uom: str
    to_uom: str
    factor: str


def resolve_conversion(quantity, from_: str, to: str, conversions: list[ProductConversion]):
    if from_ == to:
        return to_decimal(quantity)

    direct = next((c for c in conversions if c.from_uom == from_ and c.to_uom == to), None)
    if direct:
        return mul(quantity, direct.factor)

    reverse = next((c for c in conversions if c.from_uom == to and c.to_uom == from_), None)
    if reverse:
        return div(quantity, reverse.factor)

    try:
        return convert(quantity, from_, to)
    except UomConversionError as exc:
        raise rule_violation(
            f"{exc}. Define a product-specific conversion ({from_} → {to}) if this product is packed that way",
            code="UOM_CONVERSION_UNDEFINED",
            meta={"from": from_, "to": to},
        ) from exc


def assert_conversion_consistent(candidate: ProductConversion, existing: list[ProductConversion]) -> None:
    if not is_known_uom(candidate.from_uom):
        raise rule_violation(f'"{candidate.from_uom}" is not a configured unit of measure', code="UOM_UNKNOWN")
    if not is_known_uom(candidate.to_uom):
        raise rule_violation(f'"{candidate.to_uom}" is not a configured unit of measure', code="UOM_UNKNOWN")
    if candidate.from_uom == candidate.to_uom:
        raise rule_violation("A conversion must be between two different units", code="UOM_CONVERSION_TRIVIAL")
    if to_decimal(candidate.factor) <= 0:
        raise rule_violation("A conversion factor must be greater than zero", code="UOM_CONVERSION_FACTOR_INVALID")

    clash = next(
        (
            c
            for c in existing
            if (c.from_uom == candidate.from_uom and c.to_uom == candidate.to_uom)
            or (c.from_uom == candidate.to_uom and c.to_uom == candidate.from_uom)
        ),
        None,
    )
    if clash:
        candidate_factor = to_decimal(candidate.factor)
        expected = candidate_factor if clash.from_uom == candidate.from_uom else div(1, candidate_factor)
        if to_decimal(clash.factor) != to_decimal(expected):
            raise rule_violation(
                f"A conversion between {candidate.from_uom} and {candidate.to_uom} already exists with a different factor "
                f"({clash.from_uom} → {clash.to_uom} = {clash.factor}). Update that one instead of adding a second",
                code="UOM_CONVERSION_CONFLICT",
            )

    # Overriding a dimensional conversion (KG -> G) with a different number would
    # make the same question answerable two ways depending on the code path.
    if can_convert(candidate.from_uom, candidate.to_uom):
        shared = convert(1, candidate.from_uom, candidate.to_uom)
        if to_decimal(shared) != to_decimal(candidate.factor):
            raise rule_violation(
                f"{candidate.from_uom} → {candidate.to_uom} is already fixed by physics at {shared}; "
                f"a product cannot redefine it as {candidate.factor}",
                code="UOM_CONVERSION_CONTRADICTS_DIMENSION",
            )
