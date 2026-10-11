"""New coverage - Node's finance service had no tests for domain/settlement.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.finance_settlement import assert_allocations_valid, position, requires_payment_approval


def test_position_partial_payment():
    pos = position("1000", "400")
    assert pos.outstanding == "600.000000"
    assert pos.settled is False


def test_position_fully_paid_via_paid_amount_alone():
    pos = position("1000", "1000")
    assert pos.outstanding == "0.000000"
    assert pos.settled is True


def test_position_credit_amount_counts_toward_settlement():
    pos = position("1000", "400", "600")
    assert pos.outstanding == "0.000000"
    assert pos.settled is True


def test_position_outstanding_clamps_to_zero_on_overpayment():
    pos = position("1000", "1200")
    assert pos.outstanding == "0.000000"
    assert pos.settled is True


def test_allocations_valid_happy_path():
    summary = assert_allocations_valid(
        payment_amount="1000",
        allocations=[{"invoiceNumber": "AP-1", "requested": "1000", "outstanding": "1000"}],
        overpayment_policy="block",
        direction="outbound",
    )
    assert summary.total_allocated == "1000.000000"
    assert summary.unallocated == "0.000000"
    assert summary.overpayments == []


def test_zero_or_negative_payment_amount_rejected():
    with pytest.raises(ProblemError) as exc:
        assert_allocations_valid(payment_amount="0", allocations=[{"invoiceNumber": "AP-1", "requested": "10", "outstanding": "10"}], overpayment_policy="block", direction="outbound")
    assert exc.value.code == "PAYMENT_AMOUNT_INVALID"


def test_zero_or_negative_allocation_amount_rejected_immediately():
    with pytest.raises(ProblemError) as exc:
        assert_allocations_valid(
            payment_amount="100",
            allocations=[{"invoiceNumber": "AP-1", "requested": "0", "outstanding": "50"}, {"invoiceNumber": "AP-2", "requested": "50", "outstanding": "50"}],
            overpayment_policy="block",
            direction="outbound",
        )
    assert exc.value.code == "ALLOCATION_AMOUNT_INVALID"


def test_overpayment_blocked_under_block_policy():
    with pytest.raises(ProblemError) as exc:
        assert_allocations_valid(payment_amount="200", allocations=[{"invoiceNumber": "AP-1", "requested": "150", "outstanding": "100"}], overpayment_policy="block", direction="outbound")
    assert exc.value.code == "AP_OVERPAYMENT"


def test_ar_overpayment_uses_the_ar_specific_code():
    with pytest.raises(ProblemError) as exc:
        assert_allocations_valid(payment_amount="200", allocations=[{"invoiceNumber": "AR-1", "requested": "150", "outstanding": "100"}], overpayment_policy="block", direction="inbound")
    assert exc.value.code == "AR_OVERPAYMENT"


def test_credit_policy_absorbs_the_overpayment_as_a_phantom_credit():
    # The excess is NOT capped at outstanding, and no ledger balance is
    # created anywhere - just reported transiently in overpayments[].
    summary = assert_allocations_valid(payment_amount="150", allocations=[{"invoiceNumber": "AP-1", "requested": "150", "outstanding": "100"}], overpayment_policy="credit", direction="outbound")
    assert summary.total_allocated == "150.000000"
    assert len(summary.overpayments) == 1
    assert summary.overpayments[0].excess == "50.000000"


def test_allocations_exceeding_payment_rejected_after_the_per_line_checks():
    # Under "credit" policy this check only fires once the SUM across every
    # allocation exceeds the payment - a single line can still individually
    # overpay its own invoice as long as the total stays within the payment.
    with pytest.raises(ProblemError) as exc:
        assert_allocations_valid(
            payment_amount="100",
            allocations=[{"invoiceNumber": "AP-1", "requested": "60", "outstanding": "60"}, {"invoiceNumber": "AP-2", "requested": "60", "outstanding": "60"}],
            overpayment_policy="block",
            direction="outbound",
        )
    assert exc.value.code == "ALLOCATION_EXCEEDS_PAYMENT"


def test_credit_policy_single_line_overpay_still_bounded_by_total_payment():
    summary = assert_allocations_valid(
        payment_amount="120",
        allocations=[{"invoiceNumber": "AP-1", "requested": "100", "outstanding": "60"}, {"invoiceNumber": "AP-2", "requested": "20", "outstanding": "60"}],
        overpayment_policy="credit",
        direction="outbound",
    )
    assert summary.total_allocated == "120.000000"
    assert summary.unallocated == "0.000000"
    assert len(summary.overpayments) == 1


def test_requires_payment_approval_strictly_greater_than():
    assert requires_payment_approval("500000", "500000") is False
    assert requires_payment_approval("500000.000001", "500000") is True
    assert requires_payment_approval("1", "500000") is False
