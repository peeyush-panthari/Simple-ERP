"""Port of backend/services/finance/test/three-way-match.test.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.finance_three_way_match import MatchLine, assert_match_approved, three_way_match


def line(ordered_qty="100", unit_price="1000", received_qty="100", invoiced_qty="100", invoiced_unit_price="1000") -> MatchLine:
    return MatchLine(po_line_id="l1", sku="SKU-1", ordered_qty=ordered_qty, unit_price=unit_price, received_qty=received_qty, invoiced_qty=invoiced_qty, invoiced_unit_price=invoiced_unit_price)


def test_exact_match():
    result = three_way_match([line()], "2")
    assert result.status == "matched"
    assert result.issues == []
    assert result.variance == "0.000000"


def test_empty_lines_is_not_applicable():
    result = three_way_match([], "2")
    assert result.status == "not_applicable"


def test_over_invoiced_quantity_at_zero_tolerance_is_a_variance():
    result = three_way_match([line(received_qty="100", invoiced_qty="120")], "0")
    assert result.status == "variance"
    assert len(result.issues) == 1
    assert "invoiced for more than received" in result.issues[0]
    assert result.lines[0].ok is False


def test_over_priced_at_zero_tolerance_is_a_variance():
    result = three_way_match([line(unit_price="1000", invoiced_unit_price="1200")], "0")
    assert result.status == "variance"
    assert len(result.issues) == 1
    assert "above the ordered price" in result.issues[0]


def test_under_invoiced_quantity_is_matched_with_no_issues():
    # Vendor bills for less than ordered/received - a directional check,
    # under-invoicing is never flagged (it's the vendor's loss).
    result = three_way_match([line(ordered_qty="100", received_qty="100", unit_price="1000", invoiced_qty="60", invoiced_unit_price="1000")], "0")
    assert result.status == "matched"
    assert result.issues == []
    assert result.variance == "-40000.000000"


def test_tolerance_band_absorbs_the_variance_but_issues_survive():
    # ~2.17% over-invoice: received 1,840,000 (received_qty*unit_price),
    # invoiced 1,880,000 -> variance 40,000.
    lines = [line(ordered_qty="1840", received_qty="1840", unit_price="1000", invoiced_qty="1880", invoiced_unit_price="1000")]

    tight = three_way_match(lines, "2")
    assert tight.status == "variance"

    loose = three_way_match(lines, "3")
    assert loose.status == "matched"
    # The single most important quirk: status says "matched" via tolerance,
    # but the per-line issue is still present - not reconciled away.
    assert loose.issues != []
    assert loose.variance == "40000.000000"
    assert float(loose.variance_percent) == pytest.approx(2.1739, abs=1e-4)


def test_assert_match_approved_raises_on_unresolved_variance():
    result = three_way_match([line(received_qty="100", invoiced_qty="120")], "0")
    with pytest.raises(ProblemError) as exc:
        assert_match_approved(result, "VINV-1")
    assert exc.value.code == "THREE_WAY_MATCH_FAILED"


def test_assert_match_approved_rejects_whitespace_only_override_reason():
    result = three_way_match([line(received_qty="100", invoiced_qty="120")], "0")
    with pytest.raises(ProblemError):
        assert_match_approved(result, "VINV-1", "   ")


def test_assert_match_approved_accepts_a_real_override_reason():
    result = three_way_match([line(received_qty="100", invoiced_qty="120")], "0")
    assert_match_approved(result, "VINV-1", "Vendor confirmed the extra units were a goodwill top-up")


def test_assert_match_approved_never_raises_on_a_clean_match():
    result = three_way_match([line()], "2")
    assert_match_approved(result, "VINV-1")
