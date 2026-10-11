"""New coverage - the Node product service had zero tests."""

import pytest

from app.core.errors import ProblemError
from app.services.product_publish import PublishCandidate, assert_publishable, publish_blockers


def candidate(**over):
    base = dict(
        sku="RM-1", name="Steel Rod", type="raw_material", category_id="cat-1", uom="KG",
        status="draft", image_count=0, spec_count=1, sellable=False, has_approved_bom=None,
    )
    base.update(over)
    return PublishCandidate(**base)


def test_all_blockers_reported_at_once():
    errors = publish_blockers(candidate(name="", category_id=None, uom="XX", spec_count=0))
    fields = {e["field"] for e in errors}
    assert fields == {"name", "categoryId", "uom", "specs"}


def test_finished_good_needs_image():
    errors = publish_blockers(candidate(type="finished_good", spec_count=0, image_count=0))
    assert any(e["field"] == "images" for e in errors)
    assert not any(e["field"] == "specs" for e in errors)


def test_raw_material_needs_spec():
    errors = publish_blockers(candidate(type="raw_material", spec_count=0))
    assert any(e["field"] == "specs" for e in errors)


def test_sellable_finished_good_needs_approved_bom():
    errors = publish_blockers(candidate(type="finished_good", image_count=1, spec_count=1, sellable=True, has_approved_bom=False))
    assert any(e["field"] == "sellable" for e in errors)


def test_sellable_finished_good_passes_with_approved_bom():
    errors = publish_blockers(candidate(type="finished_good", image_count=1, spec_count=1, sellable=True, has_approved_bom=True))
    assert errors == []


def test_unknown_bom_status_does_not_block():
    """has_approved_bom=None (unreachable/unknown) is treated as passing here -
    contrast with deprecate's stricter unknown-handling."""
    errors = publish_blockers(candidate(type="finished_good", image_count=1, spec_count=1, sellable=True, has_approved_bom=None))
    assert errors == []


def test_assert_publishable_rejects_deprecated_outright():
    with pytest.raises(ProblemError) as exc_info:
        assert_publishable(candidate(status="deprecated"))
    assert exc_info.value.code == "PRODUCT_DEPRECATED"


def test_assert_publishable_passes_when_fully_compliant():
    assert_publishable(candidate())  # no raise
