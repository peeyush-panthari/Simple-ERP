"""Purchase order lifecycle - ported 1:1 from domain/state.ts.

  draft --submit--> pending_approval --approve--> approved --issue--> issued
    |                     |                                              |
    |                     \\--reject--> draft                            +-> partially_received -> received -> closed
    \\--cancel--> cancelled <-----------------------------------------------/

`issued` is the point of no return for edits: the vendor has the document.
Changes after that go through `amend`, which supersedes the PO with a new
revision rather than mutating the one the vendor is holding.
"""

from __future__ import annotations

from app.core.errors import rule_violation

PO_STATUSES = ("draft", "pending_approval", "approved", "issued", "partially_received", "received", "closed", "cancelled")

_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("pending_approval", "approved", "cancelled"),
    "pending_approval": ("approved", "draft", "cancelled"),
    "approved": ("issued", "draft", "cancelled"),
    "issued": ("partially_received", "received", "cancelled", "closed"),
    "partially_received": ("received", "closed", "cancelled"),
    "received": ("closed",),
    "closed": (),
    "cancelled": (),
}

_EDITABLE = ("draft", "pending_approval")


def can_transition(from_: str, to: str) -> bool:
    return to in _TRANSITIONS.get(from_, ())


def is_editable(status: str) -> bool:
    return status in _EDITABLE


def is_receivable(status: str) -> bool:
    return status in ("issued", "partially_received")


def assert_editable(number: str, status: str) -> None:
    if is_editable(status):
        return
    if status in ("issued", "partially_received", "received"):
        raise rule_violation(f"{number} has been issued to the vendor and cannot be edited. Use POST /purchase-orders/{{id}}/amend to raise a revision", code="PO_IMMUTABLE")
    raise rule_violation(f"A {status.replace('_', ' ')} purchase order cannot be edited", code="PO_IMMUTABLE")


def assert_transition(number: str, from_: str, to: str) -> None:
    if can_transition(from_, to):
        return
    raise rule_violation(f"{number} is {from_.replace('_', ' ')} and cannot move to {to.replace('_', ' ')}", code="PO_STATE_INVALID", meta={"from": from_, "to": to, "allowed": list(_TRANSITIONS.get(from_, ()))})
