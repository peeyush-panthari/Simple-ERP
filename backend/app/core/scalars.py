"""Shared Pydantic scalar types, ported from backend_py/app/routes/product_schemas.py.
Named `scalars` rather than `product_schemas` here since orders/procurement/
BOM all need these, not just products."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator

from app.core.money import DecimalError, decimal_str, is_negative
from app.services.uom import UOM_CODES


def _decimal_string(value) -> str:
    try:
        s = decimal_str(value)
    except DecimalError as exc:
        raise ValueError(f'"{value}" is not a decimal amount') from exc
    if is_negative(s):
        raise ValueError("Must be a non-negative decimal")
    return s


DecimalString = Annotated[str | int | float, AfterValidator(_decimal_string)]


def _uom_code(value: str) -> str:
    v = value.strip().upper()
    if v not in UOM_CODES:
        raise ValueError(f'"{v}" is not a configured unit of measure')
    return v


UomCode = Annotated[str, AfterValidator(_uom_code)]

PRODUCT_TYPES = ("raw_material", "finished_good", "consumable", "service")
