"""New coverage - the Node party service had no tests for lifecycle.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.party_lifecycle import assert_activatable, assert_transactable, assert_transition, can_transition


class TestTransitions:
    @pytest.mark.parametrize(
        "frm,to,expected",
        [
            ("draft", "active", True),
            ("draft", "inactive", True),
            ("draft", "blocked", False),
            ("active", "blocked", True),
            ("active", "inactive", True),
            ("active", "draft", False),
            ("blocked", "active", True),
            ("blocked", "inactive", True),
            ("inactive", "active", True),
            ("inactive", "blocked", False),
        ],
    )
    def test_can_transition(self, frm, to, expected):
        assert can_transition(frm, to) is expected

    def test_same_status_is_always_allowed(self):
        assert can_transition("active", "active") is True

    def test_assert_transition_raises_with_allowed_list(self):
        with pytest.raises(ProblemError) as exc_info:
            assert_transition("PTY-0001", "draft", "blocked")
        err = exc_info.value
        assert err.code == "PARTY_STATUS_TRANSITION_INVALID"
        assert err.meta["allowed"] == ["active", "inactive"]


class TestActivationBlockers:
    def test_all_blockers_reported_at_once(self):
        with pytest.raises(ProblemError) as exc_info:
            assert_activatable(code="PTY-0001", payment_terms=None, currency=None, addresses=[], contacts=[])
        errors = exc_info.value.meta["errors"]
        assert {e["field"] for e in errors} == {"paymentTerms", "currency", "addresses", "contacts"}

    def test_passes_once_all_requirements_met(self):
        assert_activatable(
            code="PTY-0001",
            payment_terms="NET30",
            currency="INR",
            addresses=[{"type": "billing"}],
            contacts=[{"email": "a@b.com"}],
        )

    def test_shipping_address_does_not_satisfy_billing_requirement(self):
        with pytest.raises(ProblemError) as exc_info:
            assert_activatable(
                code="PTY-0001", payment_terms="NET30", currency="INR", addresses=[{"type": "shipping"}], contacts=[{"email": "a@b.com"}]
            )
        fields = {e["field"] for e in exc_info.value.meta["errors"]}
        assert "addresses" in fields


class TestTransactable:
    def test_active_party_is_transactable(self):
        assert_transactable("PTY-0001", "active")

    def test_blocked_party_raises_party_blocked(self):
        with pytest.raises(ProblemError) as exc_info:
            assert_transactable("PTY-0001", "blocked")
        assert exc_info.value.code == "PARTY_BLOCKED"

    def test_draft_party_raises_party_not_active(self):
        with pytest.raises(ProblemError) as exc_info:
            assert_transactable("PTY-0001", "draft")
        assert exc_info.value.code == "PARTY_NOT_ACTIVE"
