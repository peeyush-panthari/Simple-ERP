"""New coverage - the Node warehouse service had no tests for receiving.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.grn_receiving import LocationRules, PoLineSnapshot, ProductRules, ReceiptLineInput, assert_receipt_valid, max_receivable, quality_status_for, receipt_line_problems


def po_line(**overrides):
    base = dict(id="line-1", product_id="p1", sku="RM-1", uom="KG", ordered_qty="100", received_qty="0", rejected_qty="0", open_qty="100", unit_price="10")
    base.update(overrides)
    return PoLineSnapshot(**base)


def product(**overrides):
    base = dict(product_id="p1", sku="RM-1", status="active", batch_tracked=False, expiry_tracked=False, type="raw_material", uom="KG")
    base.update(overrides)
    return ProductRules(**base)


def receipt(**overrides):
    base = dict(po_line_id="line-1", received_qty="10", accepted_qty="0", rejected_qty="0", batch_no=None, expiry_date=None, location_id=None, rejection_code=None)
    base.update(overrides)
    return ReceiptLineInput(**base)


def test_max_receivable_matches_tolerance_formula():
    assert str(max_receivable("100", "2")) == "102.000000"


def test_missing_po_line_reports_single_error_and_stops():
    errors = receipt_line_problems(receipt(), 0, None, product(), None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert len(errors) == 1
    assert "not on this purchase order" in errors[0]["message"]


def test_missing_product_reports_single_error_and_stops():
    errors = receipt_line_problems(receipt(), 0, po_line(), None, None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert len(errors) == 1
    assert "could not be resolved" in errors[0]["message"]


def test_zero_received_qty_is_rejected():
    errors = receipt_line_problems(receipt(received_qty="0"), 0, po_line(), product(), None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert any("receivedQty" in e["field"] for e in errors)


def test_receiving_beyond_tolerance_ceiling_is_rejected():
    errors = receipt_line_problems(receipt(received_qty="103"), 0, po_line(), product(), None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert any("bring the total to" in e["message"] for e in errors)


def test_tolerance_check_uses_po_lines_running_total_not_just_this_receipt():
    line = po_line(received_qty="95", rejected_qty="5")  # already at 100 against ordered 100
    errors = receipt_line_problems(receipt(received_qty="3"), 0, line, product(), None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert any("bring the total to" in e["message"] for e in errors)


def test_batch_required_when_product_is_batch_tracked():
    errors = receipt_line_problems(receipt(batch_no=None), 0, po_line(), product(batch_tracked=True), None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert any("batchNo" in e["field"] for e in errors)


def test_expiry_date_is_not_required_even_when_product_is_expiry_tracked():
    """Raw materials don't need expiry-date tracking at receipt - expiry_tracked
    is intentionally not enforced here (unlike batch_tracked above)."""
    errors = receipt_line_problems(receipt(expiry_date=None), 0, po_line(), product(expiry_tracked=True), None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert not any("expiryDate" in e["field"] for e in errors)


def test_rejected_qty_requires_rejection_code():
    errors = receipt_line_problems(receipt(accepted_qty="5", rejected_qty="5"), 0, po_line(), product(), None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert any("rejectionCode" in e["field"] for e in errors)


def test_accepted_plus_rejected_cannot_exceed_received():
    errors = receipt_line_problems(receipt(received_qty="10", accepted_qty="8", rejected_qty="8"), 0, po_line(), product(), None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert any("exceeds the" in e["message"] for e in errors)


def test_location_in_different_warehouse_rejected():
    loc = LocationRules(id="l1", code="BIN-1", warehouse_id="other-warehouse", status="active", type="bin", allowed_product_types=[])
    errors = receipt_line_problems(receipt(location_id="l1"), 0, po_line(), product(), loc, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert any("different warehouse" in e["message"] for e in errors)


def test_location_product_type_restriction_enforced():
    loc = LocationRules(id="l1", code="BIN-1", warehouse_id="w1", status="active", type="bin", allowed_product_types=["finished_good"])
    errors = receipt_line_problems(receipt(location_id="l1"), 0, po_line(), product(type="raw_material"), loc, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert any("does not accept" in e["message"] for e in errors)


def test_warehouse_level_product_type_restriction_enforced():
    errors = receipt_line_problems(receipt(), 0, po_line(), product(type="raw_material"), None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=["finished_good"])
    assert any("does not stock" in e["message"] for e in errors)


def test_valid_receipt_has_no_errors():
    errors = receipt_line_problems(receipt(received_qty="50"), 0, po_line(), product(), None, tolerance_percent="2", warehouse_id="w1", warehouse_allowed_types=[])
    assert errors == []


def test_assert_receipt_valid_aggregates_all_errors_into_one_exception():
    errors = [{"field": "lines.0", "message": "problem one"}, {"field": "lines.1", "message": "problem two"}]
    with pytest.raises(ProblemError) as exc:
        assert_receipt_valid(errors, "Goods receipt against PO-1")
    assert exc.value.code == "GRN_VALIDATION_FAILED"
    assert "problem one" in exc.value.detail
    assert "problem two" in exc.value.detail
    assert len(exc.value.meta["errors"]) == 2


def test_assert_receipt_valid_passes_with_no_errors():
    assert_receipt_valid([], "Goods receipt against PO-1") is None


def test_quality_status_for_transitions():
    assert quality_status_for("0", "0", "10") == "pending"
    assert quality_status_for("10", "0", "10") == "passed"
    assert quality_status_for("0", "10", "10") == "failed"
    assert quality_status_for("6", "4", "10") == "partial"
