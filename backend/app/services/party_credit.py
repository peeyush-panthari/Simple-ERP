"""Credit exposure maths - ported 1:1 from domain/credit.ts.

A credit limit of zero means "no credit extended", not "unlimited".
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import rule_violation
from app.core.money import decimal_str, is_negative, is_zero, to_decimal


def credit_available(limit, used) -> str:
    remaining = to_decimal(limit) - to_decimal(used)
    return decimal_str(remaining if remaining >= 0 else 0)


@dataclass
class CreditPosition:
    credit_limit: str
    credit_used: str
    credit_available: str
    eligible: bool
    reason: str | None


def credit_position(*, credit_limit, credit_used, status: str) -> CreditPosition:
    limit = to_decimal(credit_limit)
    used = to_decimal(credit_used)
    available = credit_available(limit, used)

    reason: str | None = None
    if status == "blocked":
        reason = "Party is blocked — no new documents may be raised against it"
    elif status != "active":
        reason = f'Party status is "{status}" — only active parties may transact'
    elif is_zero(limit):
        reason = "No credit limit is configured — this party trades on prepayment only"
    elif is_zero(available):
        reason = "Credit limit is fully consumed"

    return CreditPosition(
        credit_limit=decimal_str(limit),
        credit_used=decimal_str(used),
        credit_available=available,
        eligible=reason is None,
        reason=reason,
    )


@dataclass
class CreditUsageResult:
    credit_used: str
    credit_available: str
    over_by: str | None


def apply_credit_usage(*, credit_limit, credit_used, delta, allow_override: bool = False, party_code: str) -> CreditUsageResult:
    limit = to_decimal(credit_limit)
    used = to_decimal(credit_used)
    delta_d = to_decimal(delta)
    next_used = used + delta_d

    if is_negative(next_used):
        raise rule_violation(
            f"Releasing {abs(delta_d)} from {party_code} would drop credit used below zero "
            f"(currently {used}) — this reference was most likely released already",
            code="CREDIT_USAGE_NEGATIVE",
            meta={"creditUsed": decimal_str(used), "delta": decimal_str(delta_d)},
        )

    exceeds = next_used > limit
    if exceeds and not allow_override:
        over_by = next_used - limit
        raise rule_violation(
            f"{party_code} would exceed its credit limit by {over_by} "
            f"(limit {limit}, already used {used}, this request {delta_d}). "
            "Raise the limit, collect payment, or resubmit with allowOverride and an approved reason",
            code="CREDIT_LIMIT_EXCEEDED",
            meta={
                "creditLimit": decimal_str(limit),
                "creditUsed": decimal_str(used),
                "requested": decimal_str(delta_d),
                "overBy": decimal_str(over_by),
            },
        )

    return CreditUsageResult(
        credit_used=decimal_str(next_used),
        credit_available=credit_available(limit, next_used),
        over_by=decimal_str(next_used - limit) if exceeds else None,
    )
