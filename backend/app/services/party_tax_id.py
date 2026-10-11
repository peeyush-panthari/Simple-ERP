"""Tax identifier validation - ported 1:1 from domain/tax-id.ts.

Indian GSTINs are checked strictly (format, state code, modulo-36 check
digit). Other jurisdictions get a conservative shape check only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.errors import rule_violation

GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{1}Z[A-Z0-9]{1}$")
GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GST_STATE_CODES = {f"{i:02d}" for i in range(1, 39)} | {"97", "99"}

_TAX_ID_SHAPE = re.compile(r"^[A-Z0-9-]{5,32}$")


def gstin_check_digit(first14: str) -> str:
    if len(first14) < 14:
        raise ValueError(f"A GSTIN check digit needs 14 preceding characters, got {len(first14)}")
    base = len(GSTIN_ALPHABET)
    factor = 2
    total = 0
    for i in range(13, -1, -1):
        value = GSTIN_ALPHABET.find(first14[i])
        if value < 0:
            raise ValueError(f"Character {first14[i]!r} is not valid inside a GSTIN")
        product = factor * value
        factor = 1 if factor == 2 else 2
        total += product // base + product % base
    return GSTIN_ALPHABET[(base - (total % base)) % base]


def is_valid_gstin(value: str) -> bool:
    candidate = value.strip().upper()
    if not GSTIN_PATTERN.match(candidate):
        return False
    if candidate[:2] not in GST_STATE_CODES:
        return False
    return gstin_check_digit(candidate[:14]) == candidate[14]


@dataclass
class NormalisedTaxId:
    tax_id: str
    country: str
    state_code: str | None


def tax_id_problems(tax_id: str, country: str) -> list[dict]:
    value = tax_id.strip().upper()
    iso = country.strip().upper()
    errors: list[dict] = []

    if len(value) == 0:
        errors.append({"field": "taxId", "message": "Tax ID cannot be blank — omit the field instead"})
        return errors
    if not _TAX_ID_SHAPE.match(value):
        errors.append(
            {
                "field": "taxId",
                "message": "Tax ID may only contain letters, digits and hyphens, and must be 5–32 characters",
            }
        )
        return errors

    if iso == "IN":
        if not GSTIN_PATTERN.match(value):
            errors.append(
                {
                    "field": "taxId",
                    "message": (
                        f'"{value}" is not a valid GSTIN. Expected 15 characters: 2-digit state code, '
                        "10-character PAN, entity number, 'Z', then the check digit (e.g. 27AAPFU0939F1ZV)"
                    ),
                }
            )
            return errors
        if value[:2] not in GST_STATE_CODES:
            errors.append(
                {
                    "field": "taxId",
                    "message": f'"{value[:2]}" is not a GST state code — the first two digits must be 01–38, 97 or 99',
                }
            )
        expected = gstin_check_digit(value[:14])
        if expected != value[14]:
            errors.append(
                {
                    "field": "taxId",
                    "message": f'GSTIN "{value}" fails its check digit — the last character should be "{expected}". Re-read the certificate',
                }
            )

    return errors


def normalise_tax_id(tax_id: str, country: str) -> NormalisedTaxId:
    value = tax_id.strip().upper()
    iso = country.strip().upper()
    state_code = value[:2] if iso == "IN" and GSTIN_PATTERN.match(value) else None
    return NormalisedTaxId(tax_id=value, country=iso, state_code=state_code)


def assert_valid_tax_id(tax_id: str, country: str, *, validate: bool = True) -> NormalisedTaxId:
    if validate:
        errors = tax_id_problems(tax_id, country)
        if errors:
            raise rule_violation(
                f'Tax ID "{tax_id.strip().upper()}" is not valid for country {country.strip().upper()}',
                code="TAX_ID_INVALID",
                meta={"errors": errors},
            )
    return normalise_tax_id(tax_id, country)
