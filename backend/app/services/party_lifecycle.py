"""Party status machine - ported 1:1 from domain/lifecycle.ts.

draft -> active -> (blocked <-> active) -> inactive. A party may not become
active until it carries everything AP/AR needs. Every activation blocker is
reported at once.
"""

from __future__ import annotations

from app.core.errors import rule_violation

TRANSITIONS: dict[str, list[str]] = {
    "draft": ["active", "inactive"],
    "active": ["blocked", "inactive"],
    "blocked": ["active", "inactive"],
    "inactive": ["active"],
}


def activation_blockers(*, code: str, payment_terms: str | None, currency: str | None, addresses: list[dict], contacts: list[dict]) -> list[dict]:
    errors: list[dict] = []
    if not (payment_terms or "").strip():
        errors.append({"field": "paymentTerms", "message": "Payment terms are required before a party can transact"})
    if not (currency or "").strip():
        errors.append({"field": "currency", "message": "A trading currency is required before a party can transact"})
    if not any(a["type"] == "billing" for a in addresses):
        errors.append(
            {"field": "addresses", "message": "At least one billing address is required — invoices have nowhere to go without it"}
        )
    if not any((c.get("email") or "").strip() for c in contacts):
        errors.append({"field": "contacts", "message": "At least one contact with an email address is required"})
    return errors


def assert_activatable(*, code: str, payment_terms: str | None, currency: str | None, addresses: list[dict], contacts: list[dict]) -> None:
    errors = activation_blockers(code=code, payment_terms=payment_terms, currency=currency, addresses=addresses, contacts=contacts)
    if errors:
        joined = "; ".join(e["message"] for e in errors)
        raise rule_violation(f"{code} cannot be activated yet: {joined}", code="PARTY_NOT_READY_FOR_ACTIVATION", meta={"errors": errors})


def can_transition(from_status: str, to_status: str) -> bool:
    return from_status == to_status or to_status in TRANSITIONS.get(from_status, [])


def assert_transition(code: str, from_status: str, to_status: str) -> None:
    if can_transition(from_status, to_status):
        return
    allowed = TRANSITIONS.get(from_status, [])
    raise rule_violation(
        f'{code} cannot move from "{from_status}" to "{to_status}". Allowed next states: {", ".join(allowed) or "none"}',
        code="PARTY_STATUS_TRANSITION_INVALID",
        meta={"from": from_status, "to": to_status, "allowed": allowed},
    )


def is_blocked(status: str) -> bool:
    return status == "blocked"


def assert_transactable(code: str, status: str) -> None:
    """Guard for future order/invoice modules before raising documents against a party."""
    if status == "active":
        return
    if status == "blocked":
        raise rule_violation(
            f"{code} is blocked — existing documents are unaffected, but no new ones may be raised against it",
            code="PARTY_BLOCKED",
        )
    raise rule_violation(f'{code} is "{status}" and cannot be used on new documents — activate it first', code="PARTY_NOT_ACTIVE")
