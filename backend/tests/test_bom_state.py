"""New coverage - the Node bom service had no tests for state.ts."""

import pytest

from app.services.bom_state import can_transition, explain_transition, is_editable


@pytest.mark.parametrize(
    "frm,to,expected",
    [
        ("draft", "pending_approval", True),
        ("draft", "approved", False),
        ("pending_approval", "approved", True),
        ("pending_approval", "rejected", True),
        ("pending_approval", "draft", True),
        ("approved", "retired", True),
        ("approved", "pending_approval", False),
        ("rejected", "draft", False),
        ("retired", "approved", False),
    ],
)
def test_can_transition(frm, to, expected):
    assert can_transition(frm, to) is expected


def test_only_draft_is_editable():
    assert is_editable("draft") is True
    for state in ("pending_approval", "approved", "retired", "rejected"):
        assert is_editable(state) is False


def test_explain_transition_none_when_legal():
    assert explain_transition("draft", "pending_approval") is None


def test_explain_transition_approved_points_to_revise():
    problem = explain_transition("approved", "pending_approval")
    assert problem["code"] == "BOM_VERSION_IMMUTABLE"
    assert "revise" in problem["detail"]


def test_explain_transition_retired():
    problem = explain_transition("retired", "approved")
    assert problem["code"] == "BOM_VERSION_RETIRED"


def test_explain_transition_rejected_points_to_revise():
    problem = explain_transition("rejected", "pending_approval")
    assert problem["code"] == "BOM_VERSION_REJECTED"
    assert "revise" in problem["detail"]
