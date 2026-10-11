"""GRN lifecycle - ported 1:1 from domain/state.ts, since amended locally:
the unused 'draft' status was dropped and 'inspection' renamed to 'under_qc'
to match the vocabulary inventory_items.status already used for the same
real-world state.

  under_qc -> posted
    \\----------> rejected / cancelled

Cancelling a `posted` GRN is a reversal (see grns.py's cancel_grn /
procurement_repo.reverse_grn_receipt), not a plain edit - it undoes the stock
ledger receipt and the PO's received quantities. It is blocked once any of
the GRN's stock has been consumed or put away.
"""

from __future__ import annotations

from app.core.errors import rule_violation

GRN_STATUSES = ("under_qc", "posted", "rejected", "cancelled")

_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "under_qc": ("posted", "rejected", "cancelled"),
    "posted": ("cancelled",),
    "rejected": (),
    "cancelled": (),
}


def is_editable(status: str) -> bool:
    return status == "under_qc"


def assert_transition(number: str, from_: str, to: str) -> None:
    if to in _TRANSITIONS.get(from_, ()):
        return
    if from_ == "posted":
        raise rule_violation(f"{number} has been posted to inventory and cannot be changed. Cancel it (a reversal) instead", code="GRN_POSTED")
    raise rule_violation(f"{number} is {from_} and cannot move to {to}", code="GRN_STATE_INVALID", meta={"from": from_, "to": to, "allowed": list(_TRANSITIONS.get(from_, ()))})


def assert_editable(number: str, status: str) -> None:
    if is_editable(status):
        return
    if status == "posted":
        raise rule_violation(f"{number} has been posted to inventory and cannot be changed. Cancel it (a reversal) instead", code="GRN_POSTED")
    raise rule_violation(f"{number} is {status} and cannot be edited", code="GRN_STATE_INVALID", meta={"status": status})
