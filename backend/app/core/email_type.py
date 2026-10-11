"""Lenient email validation matching zod's z.string().email() behavior.

Ported verbatim from backend_py/app/email_type.py. Pydantic's EmailStr (via
email-validator) rejects reserved/special-use TLDs like .local, which the
dev bootstrap admin address (admin@axon-erp.local) relies on.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _validate(value: str) -> str:
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("value is not a valid email address")
    return value


Email = Annotated[str, AfterValidator(_validate)]
