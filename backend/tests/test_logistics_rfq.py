"""Port of backend/services/logistics/test/rfq.test.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.logistics_rfq import (
    QuoteCandidate,
    assert_enough_invitations,
    assert_invoice_within_quotation,
    assert_quote_awardable,
    requires_award_justification,
)


def quote(id: str, amount: str, *, status: str = "received", valid_until: str | None = None) -> QuoteCandidate:
    return QuoteCandidate(
        id=id,
        carrier_id=f"c-{id}",
        carrier_name=f"Carrier {id}",
        amount=amount,
        status=status,
        valid_until=valid_until,
    )


class TestCompetitiveTension:
    def test_requires_the_configured_minimum_number_of_invitations(self):
        assert_enough_invitations(2, 2, "RFQ-501")
        with pytest.raises(ProblemError) as exc:
            assert_enough_invitations(1, 2, "RFQ-501")
        assert exc.value.code == "RFQ_INSUFFICIENT_INVITATIONS"

    def test_gets_the_singular_right_in_the_message(self):
        with pytest.raises(ProblemError) as exc:
            assert_enough_invitations(1, 2, "RFQ-501")
        assert "1 carrier invitation —" in exc.value.detail


class TestAwardEligibility:
    as_of = "2026-08-19"

    def test_awards_a_live_quotation(self):
        assert assert_quote_awardable(quote("q1", "10000"), "RFQ-501", self.as_of).id == "q1"

    def test_refuses_a_missing_already_awarded_or_rejected_quotation(self):
        with pytest.raises(ProblemError) as exc:
            assert_quote_awardable(None, "RFQ-501", self.as_of)
        assert exc.value.code == "QUOTATION_NOT_FOUND"

        with pytest.raises(ProblemError) as exc:
            assert_quote_awardable(quote("q1", "1", status="approved"), "RFQ-501", self.as_of)
        assert exc.value.code == "QUOTATION_ALREADY_AWARDED"

        with pytest.raises(ProblemError) as exc:
            assert_quote_awardable(quote("q1", "1", status="rejected"), "RFQ-501", self.as_of)
        assert exc.value.code == "QUOTATION_REJECTED"

    def test_refuses_an_expired_quotation_and_says_when_it_lapsed(self):
        with pytest.raises(ProblemError) as exc:
            assert_quote_awardable(quote("q1", "1", valid_until="2026-08-18"), "RFQ-501", self.as_of)
        assert exc.value.code == "QUOTATION_EXPIRED"
        assert "2026-08-18" in exc.value.detail

    def test_treats_a_quotation_valid_through_today_as_live(self):
        assert_quote_awardable(quote("q1", "1", valid_until=self.as_of), "RFQ-501", self.as_of)


class TestAwardJustification:
    cheap = quote("cheap", "10000")
    mid = quote("mid", "10400")
    dear = quote("dear", "12000")

    def test_needs_no_justification_for_the_cheapest_quote(self):
        result = requires_award_justification(self.cheap, [self.cheap, self.mid, self.dear])
        assert result.required is False
        assert result.cheapest.id == "cheap"

    def test_allows_a_small_premium_without_ceremony(self):
        # 4% over the cheapest, inside the 5% band.
        result = requires_award_justification(self.mid, [self.cheap, self.mid, self.dear])
        assert result.required is False
        assert result.premium_percent == "4.000000"

    def test_demands_a_justification_above_the_band(self):
        result = requires_award_justification(self.dear, [self.cheap, self.mid, self.dear])
        assert result.required is True
        assert result.premium_percent == "20.000000"

    def test_ignores_rejected_quotes_when_finding_the_cheapest(self):
        withdrawn = quote("withdrawn", "5000", status="rejected")
        result = requires_award_justification(self.mid, [withdrawn, self.cheap, self.mid])
        assert result.cheapest.id == "cheap"
        assert result.required is False

    def test_needs_no_justification_when_there_is_only_one_quote(self):
        assert requires_award_justification(self.cheap, [self.cheap]).required is False


class TestCarrierInvoiceAgainstTheAward:
    def test_passes_an_invoice_at_or_below_the_quotation(self):
        result = assert_invoice_within_quotation(invoice_number="CIN-1", amount="10000", quoted_amount="10000", variance_approved=False)
        assert result == {"variance": None}

    def test_blocks_an_over_invoice_without_an_approved_reason(self):
        with pytest.raises(ProblemError) as exc:
            assert_invoice_within_quotation(invoice_number="CIN-1", amount="11000", quoted_amount="10000", variance_approved=False)
        assert exc.value.code == "LOGISTICS_INVOICE_EXCEEDS_QUOTATION"

    def test_will_not_accept_an_approval_flag_with_a_blank_reason(self):
        with pytest.raises(ProblemError):
            assert_invoice_within_quotation(
                invoice_number="CIN-1",
                amount="11000",
                quoted_amount="10000",
                variance_approved=True,
                variance_reason="   ",
            )

    def test_records_the_variance_when_it_is_properly_approved(self):
        result = assert_invoice_within_quotation(
            invoice_number="CIN-1",
            amount="11000",
            quoted_amount="10000",
            variance_approved=True,
            variance_reason="Detention charges agreed on 14 Aug",
        )
        assert result == {"variance": "1000.000000"}

    def test_has_nothing_to_check_when_the_shipment_was_never_quoted(self):
        result = assert_invoice_within_quotation(invoice_number="CIN-1", amount="9999", quoted_amount=None, variance_approved=False)
        assert result == {"variance": None}
