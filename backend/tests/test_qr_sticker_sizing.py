"""_qr_and_text_dimensions_mm - the QR code plus its caption, stacked
directly under it, must cover between 70% and 80% of a chosen Sticker
Size's own area, as large within that band as the sticker physically
allows (see grns.py's own docstring). The QR is always square, so it can
never exceed the sticker's shorter dimension, and the caption always sits
below it - on a sticker much wider than it is tall that caps achievable
coverage well under 70% even with a zero-height caption; the physical fit
(never exceeding the sticker's own edges) wins over the percentage target
when the two conflict."""

from decimal import Decimal

from app.domains.grn.qr_router import _QR_MAX_COVERAGE, _QR_MIN_COVERAGE, _qr_and_text_dimensions_mm


def _coverage(width_mm, height_mm):
    qr_side, text_height = _qr_and_text_dimensions_mm(width_mm, height_mm)
    block_area = qr_side**2 + qr_side * text_height
    sticker_area = float(width_mm) * float(height_mm)
    return qr_side, text_height, block_area / sticker_area


def _assert_fits(width_mm, height_mm, qr_side, text_height):
    w, h = float(width_mm), float(height_mm)
    assert qr_side <= w + 1e-6
    assert qr_side + text_height <= h + 1e-6


def test_square_label_lands_within_70_to_80_percent():
    qr_side, text_height, coverage = _coverage("40", "40")
    assert _QR_MIN_COVERAGE - 1e-6 <= coverage <= _QR_MAX_COVERAGE + 1e-6
    _assert_fits("40", "40", qr_side, text_height)


def test_tall_label_lands_within_70_to_80_percent():
    qr_side, text_height, coverage = _coverage("30", "40")
    assert _QR_MIN_COVERAGE - 1e-6 <= coverage <= _QR_MAX_COVERAGE + 1e-6
    _assert_fits("30", "40", qr_side, text_height)


def test_large_a4_sticker_still_respects_the_80_percent_ceiling():
    qr_side, text_height, coverage = _coverage("100", "150")
    assert coverage <= _QR_MAX_COVERAGE + 1e-6
    _assert_fits("100", "150", qr_side, text_height)


def test_wide_label_falls_back_to_the_largest_physically_fitting_qr():
    """A sticker noticeably wider than it is tall (e.g. the app's own
    "RM Label 50x30" example) can never reach 70% coverage with the
    caption stacked under the QR - the QR is capped by the shorter
    (height) dimension regardless, so most of the width goes unused. The
    physical fit must win over the percentage target here, not the other
    way round."""
    qr_side, text_height, coverage = _coverage("50", "30")
    assert coverage < _QR_MIN_COVERAGE
    assert qr_side == min(50.0, 30.0 - text_height)
    _assert_fits("50", "30", qr_side, text_height)


def test_extremely_elongated_label_falls_back_to_the_largest_physically_fitting_qr():
    qr_side, text_height, coverage = _coverage("20", "60")
    assert coverage < _QR_MIN_COVERAGE
    _assert_fits("20", "60", qr_side, text_height)


def test_result_never_exceeds_the_stickers_own_edges_across_many_sizes():
    for w, h in [("10", "10"), ("20", "15"), ("60", "40"), ("35", "100"), ("120", "80"), ("90", "20")]:
        qr_side, text_height = _qr_and_text_dimensions_mm(w, h)
        _assert_fits(w, h, qr_side, text_height)


def test_accepts_decimal_input_matching_stickersize_columns():
    qr_side, text_height = _qr_and_text_dimensions_mm(Decimal("50.00"), Decimal("30.00"))
    assert qr_side > 0
    assert text_height > 0
