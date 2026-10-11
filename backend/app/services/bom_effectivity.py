"""Effective-date arithmetic for BOM versions - ported 1:1 from domain/effectivity.ts.

Only one 'approved' version per product may be effective at a time. Ranges
are inclusive on both ends; `to = None` means open-ended ("effective until
superseded").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class EffectivityRange:
    id: str
    version: int
    from_: date
    to: date | None


def ranges_overlap(a_from: date, a_to: date | None, b_from: date, b_to: date | None) -> bool:
    a_ends_before_b = a_to is not None and a_to < b_from
    b_ends_before_a = b_to is not None and b_to < a_from
    return not a_ends_before_b and not b_ends_before_a


def find_overlaps(candidate_from: date, candidate_to: date | None, existing: list[EffectivityRange], *, ignore_id: str | None = None) -> list[EffectivityRange]:
    """Every existing range the candidate collides with, oldest version first."""
    matches = [r for r in existing if r.id != ignore_id and ranges_overlap(candidate_from, candidate_to, r.from_, r.to)]
    return sorted(matches, key=lambda r: r.version)


def describe_range(from_: date, to: date | None) -> str:
    return f"{from_.isoformat()} → {to.isoformat() if to else 'open-ended'}"


def is_well_ordered(from_: date, to: date | None) -> bool:
    return to is None or to >= from_


def covers_date(from_: date, to: date | None, as_of: date) -> bool:
    return from_ <= as_of and (to is None or to >= as_of)


@dataclass
class RetirementPlan:
    retire: list[EffectivityRange]
    truncate: list[tuple[EffectivityRange, date]]  # (range, new_to)


def plan_retirement(incoming_from: date, incoming_to: date | None, approved: list[EffectivityRange]) -> RetirementPlan:
    """Given the incoming range and the currently approved ones, decide what to
    do with each predecessor - retire outright, or truncate the day before the
    newcomer takes effect."""
    plan = RetirementPlan(retire=[], truncate=[])
    day_before = incoming_from - timedelta(days=1)

    for r in approved:
        if not ranges_overlap(incoming_from, incoming_to, r.from_, r.to):
            continue
        if r.from_ >= incoming_from:
            # The predecessor does not start any earlier, so there is no window
            # in which it was ever the sole authority - retire it whole.
            plan.retire.append(r)
        elif r.to is None or r.to > day_before:
            plan.truncate.append((r, day_before))
    return plan
