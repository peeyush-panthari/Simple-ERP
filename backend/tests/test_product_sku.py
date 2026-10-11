"""New coverage - the Node product service had zero tests."""

import pytest

from app.core.errors import ProblemError
from app.services.product_sku import SkuChangeContext, assert_sku_change_allowed, assert_uom_change_allowed, assert_valid_sku, is_valid_sku, normalise_sku


def test_normalise_sku():
    assert normalise_sku("  rm-steel-01  ") == "RM-STEEL-01"


def test_is_valid_sku():
    assert is_valid_sku("RM-1") is True
    assert is_valid_sku("AB") is False  # too short
    assert is_valid_sku("has spaces") is False


def test_assert_valid_sku_raises_on_bad_shape():
    with pytest.raises(ProblemError) as exc_info:
        assert_valid_sku("!!")
    assert exc_info.value.code == "SKU_INVALID"


def test_sku_change_allowed_when_still_draft_and_untransacted():
    ctx = SkuChangeContext(current_sku="RM-1", status="draft", first_transaction_at=None, first_transaction_ref=None)
    assert_sku_change_allowed(ctx, "RM-2")  # no raise


def test_sku_change_blocked_once_transacted():
    ctx = SkuChangeContext(current_sku="RM-1", status="active", first_transaction_at="2026-01-01", first_transaction_ref="PO-1")
    with pytest.raises(ProblemError) as exc_info:
        assert_sku_change_allowed(ctx, "RM-2")
    assert exc_info.value.code == "SKU_IMMUTABLE"


def test_sku_change_blocked_once_published_even_without_transaction():
    ctx = SkuChangeContext(current_sku="RM-1", status="active", first_transaction_at=None, first_transaction_ref=None)
    with pytest.raises(ProblemError) as exc_info:
        assert_sku_change_allowed(ctx, "RM-2")
    assert exc_info.value.code == "SKU_IMMUTABLE"


def test_sku_change_to_same_value_is_a_noop():
    ctx = SkuChangeContext(current_sku="RM-1", status="active", first_transaction_at="2026-01-01", first_transaction_ref="PO-1")
    assert_sku_change_allowed(ctx, "rm-1")  # normalises equal - no raise


def test_uom_change_allowed_while_draft_and_untransacted():
    ctx = SkuChangeContext(current_sku="RM-1", status="draft", first_transaction_at=None, first_transaction_ref=None)
    assert_uom_change_allowed(ctx, "KG", "G")  # no raise


def test_uom_change_blocked_once_published():
    ctx = SkuChangeContext(current_sku="RM-1", status="active", first_transaction_at=None, first_transaction_ref=None)
    with pytest.raises(ProblemError) as exc_info:
        assert_uom_change_allowed(ctx, "KG", "G")
    assert exc_info.value.code == "UOM_CHANGE_REQUIRES_NEW_SKU"
