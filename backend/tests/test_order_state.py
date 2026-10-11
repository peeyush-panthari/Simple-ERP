"""Order lifecycle state machine, including the 'partial' vocabulary that
allocate_order/ship_order derive from real per-line data (see
routes/orders.py and order_state.py's module docstring)."""

import pytest

from app.core.errors import ProblemError
from app.services.order_state import (
    ORDER_STATUSES,
    STATUS_LABELS,
    assert_editable,
    assert_invoiceable,
    assert_transition,
    can_allocate,
    can_ship,
    can_transition,
    is_cancellable,
    is_editable,
)


def test_walks_the_happy_path_end_to_end():
    # No 'draft' - an order is confirmed the moment it's created. Fulfillment
    # now follows shipment directly - 'invoiced' is a legacy status only
    # (invoicing is decoupled from order status entirely, see
    # order_state.py's module docstring and test_assert_invoiceable below).
    path = ["confirmed", "allocated", "shipped", "fulfilled"]
    for i in range(len(path) - 1):
        assert can_transition(path[i], path[i + 1]) is True


def test_walks_the_partial_path_end_to_end():
    path = ["confirmed", "partially_allocated", "partially_shipped"]
    for i in range(len(path) - 1):
        assert can_transition(path[i], path[i + 1]) is True
    assert can_transition("partially_allocated", "shipped") is True
    assert can_transition("partially_shipped", "partially_fulfilled") is True
    assert can_transition("partially_fulfilled", "fulfilled") is True


def test_invoiced_stays_as_a_legacy_source_for_already_existing_orders():
    """No new order is ever set to 'invoiced' any more, but an order that
    reached it before this behavior changed must still be fulfillable."""
    assert can_transition("invoiced", "fulfilled") is True
    assert can_transition("invoiced", "partially_fulfilled") is True
    assert can_transition("shipped", "invoiced") is False  # no longer a real transition


class TestAssertInvoiceable:
    """Invoicing is decoupled from order status entirely - the only
    real-world nonsensical case is a cancelled order. 'already invoiced' is
    guarded separately in routes/orders.py via Order.invoice_id, not here."""

    @pytest.mark.parametrize("status", [s for s in ORDER_STATUSES if s != "cancelled"])
    def test_allows_every_non_cancelled_status(self, status):
        assert_invoiceable("SO-7701", status) is None

    def test_refuses_a_cancelled_order(self):
        with pytest.raises(ProblemError) as exc:
            assert_invoiceable("SO-7701", "cancelled")
        assert exc.value.code == "ORDER_NOT_INVOICEABLE"


def test_allows_cancellation_right_up_to_dispatch_and_never_after():
    assert is_cancellable("confirmed") is True
    assert is_cancellable("allocated") is True
    assert is_cancellable("partially_allocated") is True
    assert is_cancellable("shipped") is False
    assert is_cancellable("partially_shipped") is False
    assert is_cancellable("invoiced") is False
    with pytest.raises(ProblemError) as exc:
        assert_transition("SO-7701", "shipped", "cancelled")
    assert exc.value.code == "ORDER_NOT_CANCELLABLE"


def test_points_at_the_right_remedy_when_cancellation_is_too_late():
    with pytest.raises(ProblemError) as exc:
        assert_transition("SO-7701", "shipped", "cancelled")
    assert "credit note" in exc.value.detail


def test_allows_stepping_back_from_allocated_to_confirmed_a_repack_not_a_rollback():
    assert can_transition("partially_allocated", "confirmed") is True
    assert can_transition("allocated", "confirmed") is True


def test_treats_fulfilled_partially_fulfilled_and_cancelled_as_terminal():
    for to in ORDER_STATUSES:
        assert can_transition("fulfilled", to) is False
        assert can_transition("cancelled", to) is False
    # partially_fulfilled has exactly one way out: an upgrade to fulfilled.
    assert [to for to in ORDER_STATUSES if can_transition("partially_fulfilled", to)] == ["fulfilled"]


def test_only_lets_a_just_confirmed_order_be_edited():
    # 'confirmed' is the initial state now (no 'draft'), so it's the one
    # that's still editable - same rule as before, new name for the state.
    assert is_editable("confirmed") is True
    with pytest.raises(ProblemError) as exc:
        assert_editable("SO-7701", "allocated")
    assert exc.value.code == "ORDER_IMMUTABLE"


def test_gives_every_status_the_operational_label_the_prd_uses():
    assert STATUS_LABELS["confirmed"] == "Confirmed"
    assert STATUS_LABELS["allocated"] == "Allocated"
    assert STATUS_LABELS["partially_allocated"] == "Partially Allocated"
    assert STATUS_LABELS["shipped"] == "Shipped"
    assert STATUS_LABELS["partially_shipped"] == "Partially Shipped"
    assert STATUS_LABELS["fulfilled"] == "Fulfilled"
    assert STATUS_LABELS["partially_fulfilled"] == "Partially Fulfilled"
    for s in ORDER_STATUSES:
        assert STATUS_LABELS[s]


def test_can_allocate_only_from_confirmed_or_partially_allocated():
    assert can_allocate("confirmed") is True
    assert can_allocate("partially_allocated") is True
    for s in ORDER_STATUSES:
        if s not in ("confirmed", "partially_allocated"):
            assert can_allocate(s) is False


def test_can_ship_only_once_something_is_allocated():
    assert can_ship("allocated") is True
    assert can_ship("partially_allocated") is True
    assert can_ship("partially_shipped") is True
    for s in ORDER_STATUSES:
        if s not in ("allocated", "partially_allocated", "partially_shipped"):
            assert can_ship(s) is False
