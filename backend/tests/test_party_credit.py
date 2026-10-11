"""Ported 1:1 from backend/services/party/test/credit.test.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.party_credit import apply_credit_usage, credit_available, credit_position


class TestCreditHeadroom:
    def test_is_limit_minus_used(self):
        assert credit_available("10000000", "2454400") == "7545600.000000"

    def test_zero_rather_than_negative_when_over_exposed(self):
        assert credit_available("100", "150") == "0.000000"


class TestCreditEligibility:
    def test_eligible_for_active_party_inside_limit(self):
        position = credit_position(credit_limit="10000000", credit_used="0", status="active")
        assert position.eligible is True
        assert position.reason is None

    def test_explains_a_block_rather_than_just_refusing(self):
        assert "blocked" in credit_position(credit_limit="1", credit_used="0", status="blocked").reason
        assert '"draft"' in credit_position(credit_limit="1", credit_used="0", status="draft").reason
        assert "prepayment only" in credit_position(credit_limit="0", credit_used="0", status="active").reason
        assert credit_position(credit_limit="100", credit_used="100", status="active").reason == "Credit limit is fully consumed"

    def test_block_reason_takes_priority_over_limit_reason(self):
        position = credit_position(credit_limit="0", credit_used="0", status="blocked")
        assert "blocked" in position.reason


class TestApplyingExposure:
    def test_consumes_credit_on_confirmation(self):
        result = apply_credit_usage(credit_limit="10000000", credit_used="0", delta="2454400", party_code="CUS-0001")
        assert result.credit_used == "2454400.000000"
        assert result.credit_available == "7545600.000000"
        assert result.over_by is None

    def test_releases_credit_on_settlement(self):
        result = apply_credit_usage(credit_limit="10000000", credit_used="2454400", delta="-2454400", party_code="CUS-0001")
        assert result.credit_used == "0.000000"

    def test_blocks_confirmation_that_would_exceed_limit(self):
        with pytest.raises(ProblemError) as exc_info:
            apply_credit_usage(credit_limit="1000", credit_used="900", delta="200", party_code="CUS-0001")
        err = exc_info.value
        assert err.code == "CREDIT_LIMIT_EXCEEDED"
        assert "exceed its credit limit by 100" in err.detail
        assert err.meta["overBy"] == "100.000000"

    def test_allows_breach_with_override(self):
        result = apply_credit_usage(credit_limit="1000", credit_used="900", delta="200", allow_override=True, party_code="CUS-0001")
        assert result.credit_used == "1100.000000"
        assert result.over_by == "100.000000"
        assert result.credit_available == "0.000000"

    def test_accepts_confirmation_landing_exactly_on_limit(self):
        result = apply_credit_usage(credit_limit="1000", credit_used="900", delta="100", party_code="C")
        assert result.over_by is None

    def test_refuses_double_release(self):
        with pytest.raises(ProblemError) as exc_info:
            apply_credit_usage(credit_limit="1000", credit_used="100", delta="-200", party_code="C")
        assert exc_info.value.code == "CREDIT_USAGE_NEGATIVE"
