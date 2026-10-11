"""New coverage - the Node product service had zero tests."""

import pytest

from app.core.errors import ProblemError
from app.services.product_conversion import ProductConversion, assert_conversion_consistent, resolve_conversion


def test_resolve_conversion_same_unit_is_identity():
    assert str(resolve_conversion("5", "KG", "KG", [])) == "5.000000"


def test_resolve_conversion_uses_direct_product_specific_factor():
    conversions = [ProductConversion(from_uom="BOX", to_uom="UNIT", factor="12")]
    assert str(resolve_conversion("2", "BOX", "UNIT", conversions)) == "24.000000"


def test_resolve_conversion_uses_reverse_of_product_specific_factor():
    conversions = [ProductConversion(from_uom="BOX", to_uom="UNIT", factor="12")]
    assert str(resolve_conversion("24", "UNIT", "BOX", conversions)) == "2.000000"


def test_resolve_conversion_falls_back_to_dimensional_table():
    assert str(resolve_conversion("1000", "G", "KG", [])) == "1.000000"


def test_resolve_conversion_undefined_raises_rule_violation():
    with pytest.raises(ProblemError) as exc_info:
        resolve_conversion("1", "BOX", "PAL", [])
    assert exc_info.value.code == "UOM_CONVERSION_UNDEFINED"


def test_assert_conversion_consistent_rejects_unknown_units():
    with pytest.raises(ProblemError) as exc_info:
        assert_conversion_consistent(ProductConversion(from_uom="XX", to_uom="UNIT", factor="1"), [])
    assert exc_info.value.code == "UOM_UNKNOWN"


def test_assert_conversion_consistent_rejects_trivial_pair():
    with pytest.raises(ProblemError) as exc_info:
        assert_conversion_consistent(ProductConversion(from_uom="UNIT", to_uom="UNIT", factor="1"), [])
    assert exc_info.value.code == "UOM_CONVERSION_TRIVIAL"


def test_assert_conversion_consistent_rejects_non_positive_factor():
    with pytest.raises(ProblemError) as exc_info:
        assert_conversion_consistent(ProductConversion(from_uom="BOX", to_uom="UNIT", factor="0"), [])
    assert exc_info.value.code == "UOM_CONVERSION_FACTOR_INVALID"


def test_assert_conversion_consistent_rejects_conflicting_existing_factor():
    existing = [ProductConversion(from_uom="BOX", to_uom="UNIT", factor="12")]
    with pytest.raises(ProblemError) as exc_info:
        assert_conversion_consistent(ProductConversion(from_uom="BOX", to_uom="UNIT", factor="24"), existing)
    assert exc_info.value.code == "UOM_CONVERSION_CONFLICT"


def test_assert_conversion_consistent_allows_matching_reverse_of_existing():
    # Use a factor whose reciprocal round-trips exactly at scale 6 (1/4 = 0.25,
    # unlike 1/12) so this isolates "is the reverse-factor check applied" from
    # the rounding precision of the reciprocal itself.
    existing = [ProductConversion(from_uom="BOX", to_uom="UNIT", factor="4")]
    assert_conversion_consistent(ProductConversion(from_uom="UNIT", to_uom="BOX", factor="0.25"), existing)  # no raise


def test_assert_conversion_consistent_rejects_contradicting_dimensional_table():
    with pytest.raises(ProblemError) as exc_info:
        assert_conversion_consistent(ProductConversion(from_uom="KG", to_uom="G", factor="500"), [])
    assert exc_info.value.code == "UOM_CONVERSION_CONTRADICTS_DIMENSION"


def test_assert_conversion_consistent_allows_correct_dimensional_factor():
    assert_conversion_consistent(ProductConversion(from_uom="KG", to_uom="G", factor="1000"), [])  # no raise
