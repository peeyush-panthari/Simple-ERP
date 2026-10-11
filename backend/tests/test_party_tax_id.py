"""Ported 1:1 from backend/services/party/test/tax-id.test.ts."""

import pytest

from app.core.errors import ProblemError
from app.services.party_tax_id import assert_valid_tax_id, gstin_check_digit, is_valid_gstin, normalise_tax_id, tax_id_problems

# The GSTINs seeded into the demo tenant - each carries a real check digit.
SEEDED = ["27AAECV1234K1ZA", "07AABCN4571L1Z7", "29AAFCA9982M1ZR", "33AAGCP7766P1ZM", "24AACCC1188N1ZI"]


class TestGstinCheckDigit:
    def test_reproduces_published_example(self):
        assert gstin_check_digit("27AAPFU0939F1Z"[:14]) == "V"

    def test_validates_every_seeded_gstin(self):
        for gstin in SEEDED:
            assert is_valid_gstin(gstin) is True

    def test_refuses_without_14_preceding_characters(self):
        with pytest.raises(ValueError):
            gstin_check_digit("27AAECV1234")

    def test_rejects_character_outside_base36(self):
        with pytest.raises(ValueError):
            gstin_check_digit("27AAECV1234K1-")

    def test_catches_single_character_transcription_error(self):
        assert is_valid_gstin("27AAECV1235K1ZA") is False


class TestTaxIdValidation:
    def test_accepts_valid_gstin_no_problems(self):
        assert tax_id_problems("27AAECV1234K1ZA", "IN") == []

    def test_case_and_whitespace_insensitive(self):
        assert tax_id_problems("  27aaecv1234k1za  ", "in") == []

    def test_explains_expected_shape(self):
        problems = tax_id_problems("ABC123", "IN")
        assert problems[0]["field"] == "taxId"
        assert "2-digit state code" in problems[0]["message"]

    def test_rejects_impossible_state_code(self):
        problems = tax_id_problems("88AAECV1234K1ZA", "IN")
        assert any("not a GST state code" in p["message"] for p in problems)

    def test_names_expected_check_digit(self):
        problems = tax_id_problems("27AAECV1234K1ZB", "IN")
        assert any('should be "A"' in p["message"] for p in problems)

    def test_blank_tax_id_is_a_mistake(self):
        assert "omit the field instead" in tax_id_problems("   ", "IN")[0]["message"]

    def test_conservative_shape_check_outside_india(self):
        assert tax_id_problems("DE123456789", "DE") == []
        assert "letters, digits and hyphens" in tax_id_problems("!!bad!!", "DE")[0]["message"]


class TestNormalisation:
    def test_stores_uppercased_and_extracts_state_code(self):
        result = normalise_tax_id(" 27aaecv1234k1za ", "in")
        assert result.tax_id == "27AAECV1234K1ZA"
        assert result.country == "IN"
        assert result.state_code == "27"

    def test_no_state_code_outside_india(self):
        assert normalise_tax_id("DE123456789", "DE").state_code is None

    def test_throws_rule_violation_with_field_errors(self):
        with pytest.raises(ProblemError) as exc_info:
            assert_valid_tax_id("27AAECV1234K1ZB", "IN")
        err = exc_info.value
        assert err.code == "TAX_ID_INVALID"
        assert err.status == 422
        assert len(err.meta["errors"]) == 1
