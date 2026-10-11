"""New coverage - the Node procurement service had no tests for approval.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.po_approval import assert_not_self_approval, describe_tier, resolve_tier

THRESHOLDS = {"l1": "100000", "l2": "1000000", "l3": "5000000"}


def test_tier_boundaries_are_inclusive_upper():
    assert resolve_tier("100000", THRESHOLDS) == 0
    assert resolve_tier("100000.000001", THRESHOLDS) == 1
    assert resolve_tier("1000000", THRESHOLDS) == 1
    assert resolve_tier("1000000.000001", THRESHOLDS) == 2
    assert resolve_tier("5000000", THRESHOLDS) == 2
    assert resolve_tier("5000000.000001", THRESHOLDS) == 3


def test_tier_zero_needs_no_approval():
    assert resolve_tier("1", THRESHOLDS) == 0
    assert "No approval required" in describe_tier(0, THRESHOLDS)


def test_describe_tier_messages_reference_the_right_threshold():
    assert THRESHOLDS["l2"] in describe_tier(2, THRESHOLDS)
    assert THRESHOLDS["l3"] in describe_tier(3, THRESHOLDS)


def test_self_approval_blocked():
    with pytest.raises(ProblemError) as exc:
        assert_not_self_approval("user-1", "user-1", "PO-1001")
    assert exc.value.code == "SELF_APPROVAL_BLOCKED"


def test_different_approver_allowed():
    assert_not_self_approval("user-1", "user-2", "PO-1001")


def test_no_creator_recorded_allows_approval():
    """A PO with no recorded creator (e.g. a system-generated one) cannot be
    blocked on self-approval since there is no "self" to compare against."""
    assert_not_self_approval(None, "user-2", "PO-1001")
