"""Transport-request lifecycle - ported 1:1 from domain/state.ts.

  pending -> rfq_sent -> quotation_received -> approved -> dispatched -> delivered
                              \\-----------------/  (re-quote loop)
  every non-terminal status -> cancelled (no route currently reaches this - see plan)

No route in Node ever calls assertTransition(..., "cancelled") for either a
transport request or an RFQ, despite the transition existing - a genuine gap
in the current app, ported faithfully (no cancel route built here either).
"""

from __future__ import annotations

from app.core.errors import rule_violation

REQUEST_STATUSES = ("pending", "rfq_sent", "quotation_received", "approved", "dispatched", "delivered", "cancelled")

_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pending": ("rfq_sent", "cancelled"),
    "rfq_sent": ("quotation_received", "cancelled"),
    "quotation_received": ("approved", "rfq_sent", "cancelled"),
    "approved": ("dispatched", "cancelled"),
    "dispatched": ("delivered", "cancelled"),
    "delivered": (),
    "cancelled": (),
}

STATUS_LABELS = {
    "pending": "Pending review",
    "rfq_sent": "RFQ sent",
    "quotation_received": "Quotation received",
    "approved": "Quotation approved",
    "dispatched": "Dispatched",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
}


def can_transition(from_: str, to: str) -> bool:
    return to in _TRANSITIONS.get(from_, ())


def assert_transition(number: str, from_: str, to: str) -> None:
    if can_transition(from_, to):
        return
    if to == "dispatched" and from_ != "approved":
        raise rule_violation(f"{number} cannot be dispatched — a quotation must be approved first (currently {STATUS_LABELS[from_].lower()})", code="DISPATCH_WITHOUT_APPROVED_QUOTATION")
    raise rule_violation(f"{number} is {STATUS_LABELS[from_]} and cannot move to {STATUS_LABELS[to]}", code="LOGISTICS_STATE_INVALID", meta={"from": from_, "to": to, "allowed": list(_TRANSITIONS.get(from_, ()))})
