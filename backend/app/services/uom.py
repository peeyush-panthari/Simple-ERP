"""UOM conversions - ported 1:1 from packages/shared/src/util/uom.ts.

Only configured conversions are allowed; converting across incompatible
dimensions (KG -> UNIT) is rejected rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.money import div, mul, round_dp, to_decimal


@dataclass
class UomDefinition:
    code: str
    name: str
    dimension: str
    to_base: str
    decimals: int


UOMS: dict[str, UomDefinition] = {
    "KG": UomDefinition("KG", "Kilogram", "mass", "1", 3),
    "G": UomDefinition("G", "Gram", "mass", "0.001", 3),
    "MT": UomDefinition("MT", "Metric tonne", "mass", "1000", 3),
    "LB": UomDefinition("LB", "Pound", "mass", "0.45359237", 3),
    "L": UomDefinition("L", "Litre", "volume", "1", 3),
    "ML": UomDefinition("ML", "Millilitre", "volume", "0.001", 3),
    "M3": UomDefinition("M3", "Cubic metre", "volume", "1000", 4),
    "M": UomDefinition("M", "Metre", "length", "1", 3),
    "MM": UomDefinition("MM", "Millimetre", "length", "0.001", 1),
    "UNIT": UomDefinition("UNIT", "Unit", "count", "1", 0),
    "BOX": UomDefinition("BOX", "Box", "count", "1", 0),
    "PAL": UomDefinition("PAL", "Pallet", "count", "1", 0),
    "HR": UomDefinition("HR", "Hour", "time", "1", 2),
}

UOM_CODES = list(UOMS.keys())


def is_known_uom(code: str) -> bool:
    return code in UOMS


class UomConversionError(ValueError):
    def __init__(self, from_: str, to: str, message: str):
        super().__init__(message)
        self.from_ = from_
        self.to = to


def can_convert(from_: str, to: str) -> bool:
    a = UOMS.get(from_)
    b = UOMS.get(to)
    if not a or not b:
        return False
    if a.dimension != b.dimension:
        return False
    # Count units are only interchangeable with themselves - a BOX is not a
    # UNIT unless a product-specific pack size says so.
    if a.dimension == "count":
        return a.code == b.code
    return True


def convert(quantity, from_: str, to: str):
    if from_ == to:
        return to_decimal(quantity)
    a = UOMS.get(from_)
    b = UOMS.get(to)
    if not a:
        raise UomConversionError(from_, to, f"Unknown unit of measure: {from_}")
    if not b:
        raise UomConversionError(from_, to, f"Unknown unit of measure: {to}")
    if not can_convert(from_, to):
        if a.dimension == b.dimension:
            msg = f"Conversion from {from_} to {to} requires a product-specific pack size"
        else:
            msg = f"Cannot convert {a.dimension} ({from_}) to {b.dimension} ({to})"
        raise UomConversionError(from_, to, msg)
    return div(mul(quantity, a.to_base), b.to_base)


def round_to_uom(quantity, uom: str):
    definition = UOMS.get(uom)
    decimals = definition.decimals if definition else 3
    return round_dp(quantity, decimals)
