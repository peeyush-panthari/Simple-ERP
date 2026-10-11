"""Input normalisation for party sub-resources - ported 1:1 from domain/normalise.ts.

Pure: validates and cleans, routes persist. Problems are collected per record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.errors import rule_violation
from app.services.party_contactable import assert_no_header_injection, email_problems, normalise_email, phone_problems


@dataclass
class NormalisedContact:
    name: str
    role: str | None
    email: str | None
    phone: str | None
    is_primary: bool


def contact_problems(*, name: str, email: str | None, phone: str | None, path: str = "contact") -> list[dict]:
    errors: list[dict] = []
    if re.search(r"[\r\n]", name):
        errors.append({"field": f"{path}.name", "message": "Remove carriage returns and line feeds from the contact name"})
    if email:
        errors.extend(email_problems(f"{path}.email", email))
    if phone:
        errors.extend(phone_problems(f"{path}.phone", phone))
    return errors


def normalise_contact(
    *, name: str, role: str | None = None, email: str | None = None, phone: str | None = None, is_primary: bool = False, path: str = "contact"
) -> NormalisedContact:
    errors = contact_problems(name=name, email=email, phone=phone, path=path)
    if errors:
        joined = "; ".join(e["message"] for e in errors)
        raise rule_violation(f'Contact "{name.strip()}" is not valid: {joined}', code="CONTACT_INVALID", meta={"errors": errors})
    return NormalisedContact(
        name=name.strip(),
        role=(role.strip() or None) if role else None,
        email=normalise_email(email) if email else None,
        phone=(phone.strip() or None) if phone else None,
        is_primary=is_primary,
    )


@dataclass
class NormalisedAddress:
    type: str
    label: str | None
    line1: str
    line2: str | None
    city: str
    state_code: str | None
    postal_code: str | None
    country: str
    is_default: bool


def normalise_address(
    *,
    type: str,
    label: str | None = None,
    line1: str,
    line2: str | None = None,
    city: str,
    state_code: str | None = None,
    postal_code: str | None = None,
    country: str,
    is_default: bool = False,
    path: str = "address",
) -> NormalisedAddress:
    for field, value in (("line1", line1), ("line2", line2), ("city", city), ("label", label)):
        if isinstance(value, str):
            assert_no_header_injection(f"{path}.{field}", value)
    return NormalisedAddress(
        type=type,
        label=(label.strip() or None) if label else None,
        line1=line1.strip(),
        line2=(line2.strip() or None) if line2 else None,
        city=city.strip(),
        state_code=(state_code.strip().upper() or None) if state_code else None,
        postal_code=(postal_code.strip().upper() or None) if postal_code else None,
        country=country.strip().upper(),
        is_default=is_default,
    )


def normalise_account_number(raw: str) -> str:
    return re.sub(r"[\s-]", "", raw).upper()
