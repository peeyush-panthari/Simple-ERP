"""New coverage - Node's logistics service had no tests for domain/state.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.logistics_state import REQUEST_STATUSES, STATUS_LABELS, assert_transition, can_transition


def test_walks_the_happy_path_end_to_end():
    path = ["pending", "rfq_sent", "quotation_received", "approved", "dispatched", "delivered"]
    for i in range(len(path) - 1):
        assert can_transition(path[i], path[i + 1]) is True


def test_allows_the_requote_loop_back_to_rfq_sent():
    assert can_transition("quotation_received", "rfq_sent") is True


def test_dispatch_without_an_approved_quotation_is_a_named_error():
    with pytest.raises(ProblemError) as exc:
        assert_transition("LR-1", "quotation_received", "dispatched")
    assert exc.value.code == "DISPATCH_WITHOUT_APPROVED_QUOTATION"

    with pytest.raises(ProblemError) as exc:
        assert_transition("LR-1", "pending", "dispatched")
    assert exc.value.code == "DISPATCH_WITHOUT_APPROVED_QUOTATION"


def test_dispatch_from_approved_succeeds():
    assert_transition("LR-1", "approved", "dispatched")


def test_delivered_and_cancelled_are_terminal():
    for to in REQUEST_STATUSES:
        assert can_transition("delivered", to) is False
        assert can_transition("cancelled", to) is False


def test_generic_invalid_transition_uses_the_fallback_code():
    with pytest.raises(ProblemError) as exc:
        assert_transition("LR-1", "delivered", "pending")
    assert exc.value.code == "LOGISTICS_STATE_INVALID"
    assert exc.value.meta["from"] == "delivered"
    assert exc.value.meta["to"] == "pending"


def test_every_status_has_a_label():
    for s in REQUEST_STATUSES:
        assert STATUS_LABELS[s]
