"""New coverage - Node's finance service had no tests for domain/periods.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.finance_periods import assert_period_open, assert_reopenable, period_of


def test_period_of_formats_year_month():
    from datetime import date

    assert period_of(date(2026, 3, 5)) == "2026-03"


def test_assert_period_open_allows_open_status():
    assert_period_open("2026-03", "open", "a vendor invoice")


def test_assert_period_open_allows_an_unknown_never_created_period():
    # Periods are lazily created on first posting - a row that doesn't exist
    # yet is treated as open, not closed.
    assert_period_open("2026-03", None, "a vendor invoice")


def test_assert_period_open_blocks_closed():
    with pytest.raises(ProblemError) as exc:
        assert_period_open("2026-03", "closed", "a vendor invoice")
    assert exc.value.code == "PERIOD_CLOSED"


def test_assert_period_open_blocks_locked():
    with pytest.raises(ProblemError) as exc:
        assert_period_open("2026-03", "locked", "a vendor invoice")
    assert exc.value.code == "PERIOD_CLOSED"


def test_assert_reopenable_allows_closed():
    assert_reopenable("2026-03", "closed")


def test_assert_reopenable_blocks_locked_permanently():
    # No override path exists anywhere for a locked period.
    with pytest.raises(ProblemError) as exc:
        assert_reopenable("2026-03", "locked")
    assert exc.value.code == "PERIOD_LOCKED"


def test_assert_reopenable_rejects_an_unknown_never_created_period():
    # The opposite default from assert_period_open: an unknown period is
    # open for POSTING purposes but NOT reopenable - the two guards
    # deliberately disagree about what "no row" means.
    with pytest.raises(ProblemError) as exc:
        assert_reopenable("2026-03", None)
    assert exc.value.code == "PERIOD_NOT_CLOSED"


def test_assert_reopenable_rejects_an_already_open_period():
    with pytest.raises(ProblemError) as exc:
        assert_reopenable("2026-03", "open")
    assert exc.value.code == "PERIOD_NOT_CLOSED"
