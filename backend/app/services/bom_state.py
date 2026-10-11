"""BOM version lifecycle - ported 1:1 from domain/state.ts.

  draft --submit--> pending_approval --approve--> approved --> retired
    ^                     |
    +-------reject--------+  (reject lands in `rejected`, not back in draft:
                              the rejected document stays as evidence and the
                              author clones it with POST .../revise)

`approved` is terminal for editing. The only transition out of it is
automatic retirement when a successor takes effect.
"""

from __future__ import annotations

BOM_VERSION_STATES = ["draft", "pending_approval", "approved", "retired", "rejected"]

_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending_approval"],
    "pending_approval": ["approved", "rejected", "draft"],
    "approved": ["retired"],
    "rejected": [],
    "retired": [],
}

_EDITABLE = ["draft"]


def can_transition(from_: str, to: str) -> bool:
    return to in _TRANSITIONS.get(from_, [])


def is_editable(state: str) -> bool:
    return state in _EDITABLE


def explain_transition(from_: str, to: str) -> dict | None:
    """Why an edit or transition was refused, phrased for the end user. Returns
    None when the move is legal."""
    if can_transition(from_, to):
        return None
    if from_ == "approved":
        return {
            "code": "BOM_VERSION_IMMUTABLE",
            "detail": "This version is approved and cannot be changed. Use POST /boms/{id}/versions/{versionId}/revise to start a new draft from it.",
        }
    if from_ == "retired":
        return {
            "code": "BOM_VERSION_RETIRED",
            "detail": "This version has been retired by a newer effective version and can no longer be changed.",
        }
    if from_ == "rejected":
        return {
            "code": "BOM_VERSION_REJECTED",
            "detail": "This version was rejected. Use POST /boms/{id}/versions/{versionId}/revise to clone it into a new draft.",
        }
    return {
        "code": "BOM_VERSION_STATE_INVALID",
        "detail": f"A {from_.replace('_', ' ')} BOM version cannot move to {to.replace('_', ' ')}.",
    }
