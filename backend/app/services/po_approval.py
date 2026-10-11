"""Approval tiering by document value - ported 1:1 from domain/approval.ts.

Tier 0 means "no approval required" - a stationery order should not need a
director. Tiers are inclusive-upper: a PO worth exactly L1 still sits in
tier 0, because thresholds are written as "approval required above X".
"""

from __future__ import annotations

from app.core.errors import rule_violation
from app.core.money import to_decimal


def resolve_tier(total, thresholds: dict) -> int:
    value = to_decimal(total)
    if value <= to_decimal(thresholds["l1"]):
        return 0
    if value <= to_decimal(thresholds["l2"]):
        return 1
    if value <= to_decimal(thresholds["l3"]):
        return 2
    return 3


def describe_tier(tier: int, thresholds: dict) -> str:
    if tier == 0:
        return f"No approval required (at or below {thresholds['l1']})"
    if tier == 1:
        return f"Tier 1 approval (above {thresholds['l1']})"
    if tier == 2:
        return f"Tier 2 approval (above {thresholds['l2']})"
    return f"Tier 3 approval (above {thresholds['l3']})"


def assert_not_self_approval(created_by: str | None, approver_id: str, document_number: str) -> None:
    """The approver may never be the person who raised the document - the
    cheapest possible fraud control and the one auditors always look for."""
    if created_by and created_by == approver_id:
        raise rule_violation(f"{document_number} was raised by you — it must be approved by someone else", code="SELF_APPROVAL_BLOCKED")
