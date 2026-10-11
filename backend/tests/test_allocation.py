"""New coverage - the Node inventory service had no tests for allocation.ts."""

from datetime import datetime, timedelta

import pytest

from app.core.errors import ProblemError
from app.services.allocation import BatchCandidate, allocate, free_quantity, sort_candidates


def candidate(batch_no, on_hand, *, reserved="0", expiry_date=None, days_ago=0, location_id=None):
    return BatchCandidate(
        batch_no=batch_no,
        location_id=location_id,
        expiry_date=expiry_date,
        on_hand=on_hand,
        reserved=reserved,
        received_at=datetime(2026, 1, 1) - timedelta(days=days_ago),
    )


def test_fefo_sorts_dated_batches_before_undated_by_expiry():
    candidates = [
        candidate("UNDATED", "10", days_ago=5),
        candidate("LATE", "10", expiry_date="2026-06-01"),
        candidate("EARLY", "10", expiry_date="2026-03-01"),
    ]
    sorted_ = sort_candidates(candidates, "fefo")
    assert [c.batch_no for c in sorted_] == ["EARLY", "LATE", "UNDATED"]


def test_fifo_sorts_by_received_at_regardless_of_expiry():
    candidates = [
        candidate("NEWER", "10", expiry_date="2026-01-01", days_ago=1),
        candidate("OLDER", "10", expiry_date="2026-12-01", days_ago=10),
    ]
    sorted_ = sort_candidates(candidates, "fifo")
    assert [c.batch_no for c in sorted_] == ["OLDER", "NEWER"]


def test_free_quantity_never_negative():
    assert free_quantity(candidate("B", "10", reserved="15")) == 0


def test_allocate_splits_across_batches_in_fefo_order():
    candidates = [
        candidate("EARLY", "6", expiry_date="2026-03-01"),
        candidate("LATE", "10", expiry_date="2026-06-01"),
    ]
    result = allocate(sku="RM-1", requested="8", uom="KG", candidates=candidates, strategy="fefo", as_of="2026-01-01")
    assert [(a.batch_no, a.quantity) for a in result] == [("EARLY", "6.000000"), ("LATE", "2.000000")]


def test_allocate_skips_expired_batches():
    candidates = [
        candidate("EXPIRED", "10", expiry_date="2026-01-01"),
        candidate("GOOD", "10", expiry_date="2026-12-01"),
    ]
    result = allocate(sku="RM-1", requested="5", uom="KG", candidates=candidates, strategy="fefo", as_of="2026-06-01")
    assert len(result) == 1
    assert result[0].batch_no == "GOOD"


def test_allocate_raises_with_exact_shortfall_never_partially_allocates():
    candidates = [candidate("A", "3")]
    with pytest.raises(ProblemError) as exc:
        allocate(sku="RM-1", requested="10", uom="KG", candidates=candidates, strategy="fefo")
    assert exc.value.code == "INSUFFICIENT_STOCK"
    assert exc.value.meta["shortBy"] == "7.000000"


def test_allocate_excludes_reserved_quantity():
    candidates = [candidate("A", "10", reserved="7")]
    result = allocate(sku="RM-1", requested="3", uom="KG", candidates=candidates, strategy="fefo")
    assert result[0].quantity == "3.000000"
    with pytest.raises(ProblemError):
        allocate(sku="RM-1", requested="4", uom="KG", candidates=candidates, strategy="fefo")
