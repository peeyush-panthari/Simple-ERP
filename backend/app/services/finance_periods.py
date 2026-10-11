"""Accounting period guards - ported 1:1 from domain/periods.ts.

Two different defaults for "this period row doesn't exist yet" - preserved
exactly, not reconciled: assert_period_open() treats an unknown period as
open (periods are lazily created on first posting, see finance_repo.
ensure_period_open), but assert_reopenable() treats the same unknown-period
case as NOT reopenable (PERIOD_NOT_CLOSED). `locked` is a genuinely dead
status - the CHECK constraint allows it and assert_reopenable() handles it,
but nothing anywhere ever sets a period to locked, and there is no override
path for it.
"""

from __future__ import annotations

from datetime import date

from app.core.errors import rule_violation


def period_of(on_date: date) -> str:
    return on_date.isoformat()[:7]


def assert_period_open(period: str, status: str | None, action: str) -> None:
    if status is None or status == "open":
        return
    raise rule_violation(f"{period} is {status} - {action} cannot be posted into a closed period", code="PERIOD_CLOSED", meta={"period": period, "status": status})


def assert_reopenable(period: str, status: str | None) -> None:
    if status == "closed":
        return
    if status == "locked":
        raise rule_violation(f"{period} is locked and cannot be reopened", code="PERIOD_LOCKED", meta={"period": period, "status": status})
    raise rule_violation(f"{period} is not closed", code="PERIOD_NOT_CLOSED", meta={"period": period, "status": status})
