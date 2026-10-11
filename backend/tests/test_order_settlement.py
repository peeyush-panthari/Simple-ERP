"""New coverage - Node's order service had no tests for domain/settlement.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.order_settlement import (
    assert_invoice_matches_order,
    assert_logistics_allowed,
    evaluate_logistics_trigger,
    settlement_position,
)


def test_fully_paid_when_paid_covers_total():
    pos = settlement_position("1000", "1000")
    assert pos.fully_paid is True
    assert pos.outstanding == "0.000000"
    assert pos.paid_percent == 100


def test_partial_payment_is_not_fully_paid():
    pos = settlement_position("1000", "400")
    assert pos.fully_paid is False
    assert pos.outstanding == "600.000000"
    assert pos.paid_percent == 40


def test_overpayment_clamps_outstanding_to_zero_and_percent_to_100():
    pos = settlement_position("1000", "1200")
    assert pos.outstanding == "0.000000"
    assert pos.fully_paid is True
    assert pos.paid_percent == 100


def test_zero_total_order_is_never_fully_paid_even_though_outstanding_is_zero():
    pos = settlement_position("0", "0")
    assert pos.outstanding == "0.000000"
    assert pos.fully_paid is False
    assert pos.paid_percent == 0


def test_evaluate_logistics_trigger_automatic_when_fully_settled():
    pos = settlement_position("1000", "1000")
    decision = evaluate_logistics_trigger(number="SO-1", settlement=pos, has_override_permission=False, override_reason=None)
    assert decision.allowed is True
    assert decision.automatic is True
    assert decision.requires_override is False


def test_evaluate_logistics_trigger_blocked_without_override_permission():
    pos = settlement_position("1000", "400")
    decision = evaluate_logistics_trigger(number="SO-1", settlement=pos, has_override_permission=False, override_reason=None)
    assert decision.allowed is False
    assert decision.requires_override is True
    assert "override-logistics" in decision.reason


def test_evaluate_logistics_trigger_blocked_with_permission_but_no_reason():
    pos = settlement_position("1000", "400")
    decision = evaluate_logistics_trigger(number="SO-1", settlement=pos, has_override_permission=True, override_reason="   ")
    assert decision.allowed is False
    assert decision.requires_override is True
    assert "audited reason" in decision.reason


def test_evaluate_logistics_trigger_allowed_with_permission_and_reason():
    pos = settlement_position("1000", "400")
    decision = evaluate_logistics_trigger(number="SO-1", settlement=pos, has_override_permission=True, override_reason="Customer requested early dispatch")
    assert decision.allowed is True
    assert decision.automatic is False
    assert decision.requires_override is True
    assert decision.reason == "Customer requested early dispatch"


def test_assert_logistics_allowed_raises_with_the_decision_reason():
    pos = settlement_position("1000", "400")
    decision = evaluate_logistics_trigger(number="SO-1", settlement=pos, has_override_permission=False, override_reason=None)
    with pytest.raises(ProblemError) as exc:
        assert_logistics_allowed(decision)
    assert exc.value.code == "LOGISTICS_BEFORE_PAYMENT_BLOCKED"
    assert exc.value.detail == decision.reason


def test_assert_logistics_allowed_passes_when_allowed():
    pos = settlement_position("1000", "1000")
    decision = evaluate_logistics_trigger(number="SO-1", settlement=pos, has_override_permission=False, override_reason=None)
    assert_logistics_allowed(decision)


def test_assert_invoice_matches_order_passes_when_equal():
    assert_invoice_matches_order("SO-1", "1000", "1000")


def test_assert_invoice_matches_order_raises_on_mismatch():
    with pytest.raises(ProblemError) as exc:
        assert_invoice_matches_order("SO-1", "1000", "1000.01")
    assert exc.value.code == "INVOICE_TOTAL_MISMATCH"
