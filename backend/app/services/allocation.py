"""Batch picking - ported 1:1 from domain/allocation.ts.

FEFO (first expiry, first out) is the default because shipping the
longest-dated stock first is how warehouses end up writing off the rest.
Batches with no expiry sort last under FEFO and by age under FIFO.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.core.errors import rule_violation
from app.core.money import decimal_str, is_negative, to_decimal


@dataclass
class BatchCandidate:
    batch_no: str
    location_id: str | None
    expiry_date: str | None
    on_hand: str
    reserved: str
    received_at: datetime


@dataclass
class Allocation:
    batch_no: str
    location_id: str | None
    expiry_date: str | None
    quantity: str


def sort_candidates(candidates: list[BatchCandidate], strategy: str) -> list[BatchCandidate]:
    sorted_ = list(candidates)
    if strategy == "fefo":
        # A dated batch always sorts before an undated one - the undated
        # stock is not at risk, the dated stock is.
        sorted_.sort(key=lambda c: (0, c.expiry_date, datetime.min) if c.expiry_date else (1, "", c.received_at))
    else:
        sorted_.sort(key=lambda c: c.received_at)
    return sorted_


def free_quantity(candidate: BatchCandidate):
    free = to_decimal(candidate.on_hand) - to_decimal(candidate.reserved)
    return free if not is_negative(free) else to_decimal(0)


def allocate(*, sku: str, requested, uom: str, candidates: list[BatchCandidate], strategy: str, as_of: str | None = None) -> list[Allocation]:
    as_of = as_of or date.today().isoformat()
    # Expired stock is unsellable even though it is still on the shelf.
    usable = [c for c in sort_candidates(candidates, strategy) if not c.expiry_date or c.expiry_date >= as_of]

    remaining = to_decimal(requested)
    allocations: list[Allocation] = []

    for candidate in usable:
        if remaining <= 0:
            break
        free = free_quantity(candidate)
        if free <= 0:
            continue
        take = remaining if free >= remaining else free
        allocations.append(Allocation(batch_no=candidate.batch_no, location_id=candidate.location_id, expiry_date=candidate.expiry_date, quantity=decimal_str(take)))
        remaining -= take

    if remaining > 0:
        total = sum((free_quantity(c) for c in usable), to_decimal(0))
        expired_count = len(candidates) - len(usable)
        raise rule_violation(
            f"Cannot allocate {decimal_str(requested)} {uom} of {sku}: "
            f"only {decimal_str(total)} {uom} is free across {len(usable)} batch(es)"
            + (f", and {expired_count} batch(es) are past expiry" if expired_count > 0 else "")
            + f". Short by {decimal_str(remaining)} {uom}",
            code="INSUFFICIENT_STOCK",
            meta={"sku": sku, "shortBy": decimal_str(remaining), "free": decimal_str(total), "expiredBatches": expired_count},
        )

    return allocations
