"""Exact fixed-point decimal helper for money/quantity fields.

Ported verbatim from backend_py/app/services/money.py - framework-agnostic,
no changes. Scale 6, values stored as numeric(20,6), never floats. Canonical
string form always carries exactly 6 decimal places (e.g. "2454400.000000")
so ported test fixtures compare byte-for-byte with the Flask app's.
"""

from __future__ import annotations

import re
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal as PyDecimal

SCALE = 6
QUANT = PyDecimal(1).scaleb(-SCALE)  # 0.000001

_NUMERIC_RE = re.compile(r"^[+-]?(\d+)(\.\d+)?$")


class DecimalError(ValueError):
    pass


def to_decimal(value) -> PyDecimal:
    """Parses a string/int/float/Decimal into the canonical scale-6 form,
    truncating (not rounding) extra fractional digits.

    NOT for re-quantizing the *result* of a multiply/divide - use mul()/div()
    for that (they round-half-up immediately after the operation). Using this
    (truncating) helper on an arithmetic result instead will silently drift
    from the canonical numbers.
    """
    if isinstance(value, PyDecimal):
        raw = format(value, "f")
    elif isinstance(value, (int,)):
        raw = str(value)
    elif isinstance(value, float):
        raw = repr(value)
    else:
        raw = str(value).strip()

    if not _NUMERIC_RE.match(raw):
        raise DecimalError(f"Not a decimal value: {value!r}")

    return PyDecimal(raw).quantize(QUANT, rounding=ROUND_DOWN)


def decimal_str(value) -> str:
    """Canonical string form, always 6 decimal places."""
    return format(to_decimal(value), "f")


def mul(a, b) -> PyDecimal:
    """a * b, rescaled to scale-6 with round-half-up."""
    return (to_decimal(a) * to_decimal(b)).quantize(QUANT, rounding=ROUND_HALF_UP)


def div(a, b) -> PyDecimal:
    """a / b, rescaled to scale-6 with round-half-up."""
    divisor = to_decimal(b)
    if divisor == 0:
        raise DecimalError("Division by zero")
    return (to_decimal(a) / divisor).quantize(QUANT, rounding=ROUND_HALF_UP)


def round_dp(value, dp: int = 2) -> PyDecimal:
    """Half-up rounding to `dp` decimal places."""
    quant = PyDecimal(1).scaleb(-dp)
    return to_decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def is_negative(value) -> bool:
    return to_decimal(value) < 0


def is_positive(value) -> bool:
    return to_decimal(value) > 0


def is_zero(value) -> bool:
    return to_decimal(value) == 0
