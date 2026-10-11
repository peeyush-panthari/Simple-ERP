"""Email/phone hygiene - ported 1:1 from domain/contactable.ts.

The header-injection guard applies to display fields too - a legal name flows
into the To: display part of PO/invoice mails, so CR/LF there is as dangerous
as one in the address itself.
"""

from __future__ import annotations

import re

from app.core.errors import rule_violation

HEADER_INJECTION = re.compile(r"[\r\n]|%0[ad]|\\r|\\n", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 ()-]{6,19}$")


def contains_header_injection(value: str) -> bool:
    return bool(HEADER_INJECTION.search(value))


def assert_no_header_injection(field: str, value: str) -> str:
    if contains_header_injection(value):
        raise rule_violation(
            f'"{field}" contains a line break, which cannot be used in an email header',
            code="EMAIL_HEADER_INJECTION",
            meta={"errors": [{"field": field, "message": "Remove carriage returns and line feeds from this value"}]},
        )
    return value.strip()


def normalise_email(raw: str) -> str:
    return raw.strip().lower()


def email_problems(field: str, raw: str) -> list[dict]:
    if contains_header_injection(raw):
        return [{"field": field, "message": "Remove carriage returns and line feeds from this email address"}]
    email = normalise_email(raw)
    if not EMAIL_PATTERN.match(email):
        return [{"field": field, "message": f'"{raw}" is not a valid email address — expected name@example.com'}]
    if len(email) > 254:
        return [{"field": field, "message": "Email addresses are limited to 254 characters"}]
    return []


def assert_email(field: str, raw: str) -> str:
    errors = email_problems(field, raw)
    if errors:
        raise rule_violation(errors[0]["message"], code="EMAIL_INVALID", meta={"errors": errors})
    return normalise_email(raw)


def phone_problems(field: str, raw: str) -> list[dict]:
    phone = raw.strip()
    if not PHONE_PATTERN.match(phone):
        return [
            {
                "field": field,
                "message": f'"{raw}" is not a valid phone number — use 7–20 digits, optionally prefixed with the country code',
            }
        ]
    if len(re.sub(r"\D", "", phone)) < 7:
        return [{"field": field, "message": f'"{raw}" has too few digits to be a phone number'}]
    return []


def assert_phone(field: str, raw: str) -> str:
    errors = phone_problems(field, raw)
    if errors:
        raise rule_violation(errors[0]["message"], code="PHONE_INVALID", meta={"errors": errors})
    return raw.strip()
