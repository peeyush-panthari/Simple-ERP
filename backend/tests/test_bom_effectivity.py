"""New coverage - the Node bom service had no tests for effectivity.ts."""

from datetime import date

from app.services.bom_effectivity import EffectivityRange, covers_date, find_overlaps, plan_retirement, ranges_overlap


def d(s: str) -> date:
    return date.fromisoformat(s)


def test_open_ended_ranges_overlap_with_anything_after_their_start():
    assert ranges_overlap(d("2026-01-01"), None, d("2026-06-01"), d("2026-06-30")) is True


def test_non_overlapping_ranges():
    assert ranges_overlap(d("2026-01-01"), d("2026-01-31"), d("2026-02-01"), None) is False


def test_adjacent_ranges_touching_at_boundary_do_overlap_inclusive():
    assert ranges_overlap(d("2026-01-01"), d("2026-01-31"), d("2026-01-31"), d("2026-02-28")) is True


def test_covers_date():
    assert covers_date(d("2026-01-01"), d("2026-06-30"), d("2026-03-15")) is True
    assert covers_date(d("2026-01-01"), None, d("2030-01-01")) is True
    assert covers_date(d("2026-01-01"), d("2026-06-30"), d("2026-07-01")) is False


def test_find_overlaps_sorted_oldest_first_and_excludes_ignored():
    existing = [
        EffectivityRange(id="v3", version=3, from_=d("2026-03-01"), to=None),
        EffectivityRange(id="v1", version=1, from_=d("2026-01-01"), to=d("2026-01-31")),
    ]
    overlaps = find_overlaps(d("2026-01-15"), d("2026-03-15"), existing)
    assert [r.id for r in overlaps] == ["v1", "v3"]


def test_plan_retirement_retires_predecessor_starting_same_day_or_later():
    incoming = (d("2026-02-01"), None)
    approved = [EffectivityRange(id="v1", version=1, from_=d("2026-02-01"), to=None)]
    plan = plan_retirement(*incoming, approved)
    assert [r.id for r in plan.retire] == ["v1"]
    assert plan.truncate == []


def test_plan_retirement_truncates_predecessor_that_started_earlier():
    incoming = (d("2026-06-01"), None)
    approved = [EffectivityRange(id="v1", version=1, from_=d("2026-01-01"), to=None)]
    plan = plan_retirement(*incoming, approved)
    assert plan.retire == []
    assert len(plan.truncate) == 1
    r, new_to = plan.truncate[0]
    assert r.id == "v1"
    assert new_to == d("2026-05-31")


def test_plan_retirement_ignores_non_overlapping_predecessors():
    incoming = (d("2026-06-01"), None)
    approved = [EffectivityRange(id="v1", version=1, from_=d("2025-01-01"), to=d("2025-12-31"))]
    plan = plan_retirement(*incoming, approved)
    assert plan.retire == []
    assert plan.truncate == []
