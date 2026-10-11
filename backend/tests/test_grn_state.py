"""New coverage - the Node warehouse service had no tests for domain/state.ts (GRN)."""

import pytest

from app.core.errors import ProblemError
from app.services.grn_state import assert_editable, assert_transition, is_editable


def test_under_qc_is_editable():
    assert is_editable("under_qc")
    assert not is_editable("posted")
    assert not is_editable("rejected")
    assert not is_editable("cancelled")


def test_valid_transitions_pass():
    assert_transition("GRN-1", "under_qc", "posted") is None
    assert_transition("GRN-1", "under_qc", "rejected") is None
    assert_transition("GRN-1", "under_qc", "cancelled") is None
    assert_transition("GRN-1", "posted", "cancelled") is None


def test_posted_can_only_move_to_cancelled_with_a_specific_message():
    with pytest.raises(ProblemError) as exc:
        assert_transition("GRN-1", "posted", "rejected")
    assert exc.value.code == "GRN_POSTED"
    assert "cancel" in exc.value.detail.lower()


def test_invalid_transition_reports_allowed_list():
    with pytest.raises(ProblemError) as exc:
        assert_transition("GRN-1", "rejected", "posted")
    assert exc.value.code == "GRN_STATE_INVALID"
    assert exc.value.meta["allowed"] == []


def test_assert_editable_delegates_to_transition_check():
    assert_editable("GRN-1", "under_qc") is None
    with pytest.raises(ProblemError):
        assert_editable("GRN-1", "posted")
