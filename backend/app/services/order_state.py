"""Sales order lifecycle - an order is confirmed the instant it's created
(see routes/orders.py::_create_order), so 'confirmed' is the initial state
rather than something reached only by a transition.

  confirmed -> allocated / partially_allocated -> shipped / partially_shipped -> fulfilled / partially_fulfilled
       \\                    /
        \\------------------/--> cancelled (only while confirmed/allocated/partially_allocated)

'allocated'/'partially_allocated' -> 'confirmed' is a legal backward step
("a repack, not a rollback of history") - ported from the pre-redesign state
machine's 'allocated -> confirmed'. `shipped`/`partially_shipped` is the
point of no return for cancellation.

'allocated' vs 'partially_allocated', and 'shipped' vs 'partially_shipped',
are not chosen by the caller - routes/orders.py::allocate_order /
ship_order derive them from whether every non-cancelled line reached full
allocated_qty / shipped_qty. Use can_allocate()/can_ship() (not
can_transition(), whose targets are fixed) to gate those two actions.

'fulfilled'/'partially_fulfilled' are terminal and only ever set manually
(routes/orders.py::mark_fulfilled) - "received by the customer" isn't
something this system observes on its own, only 'shipped'/'partially_shipped'
-> either of those two is a real transition.

'invoiced' is a LEGACY status only - it used to be a real stage every order
passed through (shipped -> invoiced -> fulfilled), stamped by
routes/orders.py::invoice_order. Invoicing is no longer tied to order status
at all: it can happen at any point in an order's life (any status except
cancelled), exactly once, and is tracked independently via Order.invoice_id/
invoice_number (see routes/orders.py::invoice_order and the Finance >
Invoices tab, which shows "Invoiced" as its own tag rather than a status).
'invoiced' stays in ORDER_STATUSES/_TRANSITIONS purely so already-existing
orders that reached it before this change can still be marked fulfilled - no
order will ever be newly set to this status again.
"""

from __future__ import annotations

from app.core.errors import rule_violation

ORDER_STATUSES = (
    "confirmed",
    "allocated",
    "partially_allocated",
    "shipped",
    "partially_shipped",
    "invoiced",
    "fulfilled",
    "partially_fulfilled",
    "cancelled",
)

_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "confirmed": ("allocated", "partially_allocated", "cancelled"),
    "partially_allocated": ("allocated", "partially_allocated", "shipped", "partially_shipped", "confirmed", "cancelled"),
    "allocated": ("shipped", "partially_shipped", "partially_allocated", "confirmed", "cancelled"),
    "shipped": ("fulfilled", "partially_fulfilled"),
    "partially_shipped": ("shipped", "partially_shipped", "fulfilled", "partially_fulfilled"),
    "invoiced": ("fulfilled", "partially_fulfilled"),  # legacy source only - see module docstring
    "fulfilled": (),
    "partially_fulfilled": ("fulfilled",),
    "cancelled": (),
}

STATUS_LABELS = {
    "confirmed": "Confirmed",
    "allocated": "Allocated",
    "partially_allocated": "Partially Allocated",
    "shipped": "Shipped",
    "partially_shipped": "Partially Shipped",
    "invoiced": "Invoiced",
    "fulfilled": "Fulfilled",
    "partially_fulfilled": "Partially Fulfilled",
    "cancelled": "Cancelled",
}


def can_transition(from_: str, to: str) -> bool:
    return to in _TRANSITIONS.get(from_, ())


def is_editable(status: str) -> bool:
    # 'confirmed' is the earliest state an order exists in - editable until
    # it's actually being worked (allocated onward).
    return status == "confirmed"


def is_cancellable(status: str) -> bool:
    return "cancelled" in _TRANSITIONS.get(status, ())


def can_allocate(status: str) -> bool:
    """Whether /allocate is a meaningful action from this status - the
    resulting status ('allocated' vs 'partially_allocated') is computed by
    the route from real per-line data, not looked up here."""
    return status in ("confirmed", "partially_allocated")


def can_ship(status: str) -> bool:
    """Whether /ship is a meaningful action from this status - same
    data-derived-result caveat as can_allocate()."""
    return status in ("allocated", "partially_allocated", "partially_shipped")


def assert_transition(number: str, from_: str, to: str) -> None:
    if can_transition(from_, to):
        return
    from_label = STATUS_LABELS[from_]
    if to == "cancelled":
        raise rule_violation(f"{number} is {from_label} — an order cannot be cancelled once it has shipped. Raise a return or a credit note instead", code="ORDER_NOT_CANCELLABLE")
    raise rule_violation(f"{number} is {from_label} and cannot move to {STATUS_LABELS[to]}", code="ORDER_STATE_INVALID", meta={"from": from_, "to": to, "allowed": list(_TRANSITIONS.get(from_, ()))})


def assert_invoiceable(number: str, status: str) -> None:
    """Invoicing is decoupled from order status entirely (see module
    docstring) - the only real-world nonsensical case is a cancelled order.
    The "already invoiced" guard lives in routes/orders.py::invoice_order,
    keyed off Order.invoice_id, not status."""
    if status == "cancelled":
        raise rule_violation(f"{number} is cancelled and cannot be invoiced", code="ORDER_NOT_INVOICEABLE")


def assert_allocatable(number: str, status: str) -> None:
    if can_allocate(status):
        return
    raise rule_violation(f"{number} is {STATUS_LABELS[status]} and cannot be allocated", code="ORDER_STATE_INVALID", meta={"from": status})


def assert_shippable(number: str, status: str) -> None:
    if can_ship(status):
        return
    raise rule_violation(f"{number} is {STATUS_LABELS[status]} and cannot be shipped", code="ORDER_STATE_INVALID", meta={"from": status})


def assert_editable(number: str, status: str) -> None:
    if is_editable(status):
        return
    raise rule_violation(f"{number} is {STATUS_LABELS[status]} — only just-received orders can be edited. Cancel and re-raise, or amend the shipment", code="ORDER_IMMUTABLE")
