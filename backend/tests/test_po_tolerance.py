"""New coverage - the Node procurement service had no tests for tolerance.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.po_tolerance import LineReceipt, ReceiptDelta, assert_within_tolerance, document_receipt_status, line_receipt_status, max_receivable, open_quantity


def test_max_receivable_applies_percent_on_top_of_ordered():
    assert str(max_receivable("100", "2")) == "102.000000"


def test_open_quantity_never_negative():
    line = LineReceipt(line_id="1", sku="RM-1", ordered_qty="10", received_qty="12", rejected_qty="0")
    assert str(open_quantity(line)) == "0.000000"


def test_assert_within_tolerance_passes_exactly_at_ceiling():
    line = LineReceipt(line_id="1", sku="RM-1", ordered_qty="100", received_qty="0", rejected_qty="0")
    assert_within_tolerance(line, ReceiptDelta(line_id="1", accepted_qty="102", rejected_qty="0"), "2")


def test_assert_within_tolerance_rejects_one_unit_over_ceiling():
    line = LineReceipt(line_id="1", sku="RM-1", ordered_qty="100", received_qty="0", rejected_qty="0")
    with pytest.raises(ProblemError) as exc:
        assert_within_tolerance(line, ReceiptDelta(line_id="1", accepted_qty="102.000001", rejected_qty="0"), "2")
    assert exc.value.code == "RECEIPT_EXCEEDS_TOLERANCE"


def test_tolerance_applies_to_accepted_plus_rejected_together():
    """Rejecting material still means it physically arrived and counts
    against the ceiling."""
    line = LineReceipt(line_id="1", sku="RM-1", ordered_qty="100", received_qty="50", rejected_qty="50")
    with pytest.raises(ProblemError):
        assert_within_tolerance(line, ReceiptDelta(line_id="1", accepted_qty="2", rejected_qty="1"), "2")


def test_assert_within_tolerance_rejects_negative_delta():
    line = LineReceipt(line_id="1", sku="RM-1", ordered_qty="100", received_qty="0", rejected_qty="0")
    with pytest.raises(ProblemError) as exc:
        assert_within_tolerance(line, ReceiptDelta(line_id="1", accepted_qty="-1", rejected_qty="0"), "2")
    assert exc.value.code == "RECEIPT_QUANTITY_INVALID"


def test_line_receipt_status_none_when_untouched():
    line = LineReceipt(line_id="1", sku="RM-1", ordered_qty="10", received_qty="0", rejected_qty="0")
    assert line_receipt_status(line, "2") == "none"


def test_line_receipt_status_partial_below_ordered_and_below_ceiling():
    line = LineReceipt(line_id="1", sku="RM-1", ordered_qty="10", received_qty="9", rejected_qty="0")
    assert line_receipt_status(line, "2") == "partial"


def test_line_receipt_status_full_when_received_meets_ordered():
    line = LineReceipt(line_id="1", sku="RM-1", ordered_qty="10", received_qty="10", rejected_qty="0")
    assert line_receipt_status(line, "2") == "full"


def test_line_receipt_status_full_once_tolerance_ceiling_is_exhausted_by_rejects():
    """Nothing more is coming - the shortfall becomes a vendor claim, not an
    open receipt."""
    line = LineReceipt(line_id="1", sku="RM-1", ordered_qty="10", received_qty="8", rejected_qty="2.2")
    assert line_receipt_status(line, "2") == "full"


def test_document_receipt_status_mixed_lines_is_partial():
    lines = [
        LineReceipt(line_id="1", sku="A", ordered_qty="10", received_qty="10", rejected_qty="0"),
        LineReceipt(line_id="2", sku="B", ordered_qty="10", received_qty="5", rejected_qty="0"),
    ]
    assert document_receipt_status(lines, "2") == "partial"


def test_document_receipt_status_all_full_is_full():
    lines = [LineReceipt(line_id="1", sku="A", ordered_qty="10", received_qty="10", rejected_qty="0")]
    assert document_receipt_status(lines, "2") == "full"


def test_document_receipt_status_empty_is_none():
    assert document_receipt_status([], "2") == "none"
