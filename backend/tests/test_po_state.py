"""New coverage - the Node procurement service had no tests for domain/state.ts (PO)."""

import pytest

from app.core.errors import ProblemError
from app.services.po_state import assert_editable, assert_transition, is_editable, is_receivable


def test_draft_and_pending_approval_are_editable():
    assert is_editable("draft")
    assert is_editable("pending_approval")
    assert not is_editable("approved")
    assert not is_editable("issued")


def test_issued_and_partially_received_are_receivable():
    assert is_receivable("issued")
    assert is_receivable("partially_received")
    assert not is_receivable("draft")
    assert not is_receivable("received")


def test_valid_lifecycle_transitions_pass():
    assert_transition("PO-1", "draft", "pending_approval") is None
    assert_transition("PO-1", "pending_approval", "approved") is None
    assert_transition("PO-1", "approved", "issued") is None
    assert_transition("PO-1", "issued", "partially_received") is None
    assert_transition("PO-1", "partially_received", "received") is None
    assert_transition("PO-1", "received", "closed") is None


def test_closed_and_cancelled_are_terminal():
    with pytest.raises(ProblemError) as exc:
        assert_transition("PO-1", "closed", "issued")
    assert exc.value.code == "PO_STATE_INVALID"
    with pytest.raises(ProblemError):
        assert_transition("PO-1", "cancelled", "draft")


def test_assert_editable_issued_po_names_the_amend_endpoint():
    with pytest.raises(ProblemError) as exc:
        assert_editable("PO-1", "issued")
    assert exc.value.code == "PO_IMMUTABLE"
    assert "amend" in exc.value.detail.lower()


def test_assert_editable_cancelled_po_generic_message():
    with pytest.raises(ProblemError) as exc:
        assert_editable("PO-1", "cancelled")
    assert exc.value.code == "PO_IMMUTABLE"
    assert "amend" not in exc.value.detail.lower()
