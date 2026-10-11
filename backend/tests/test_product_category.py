"""New coverage - the Node product service had zero tests."""

import pytest

from app.core.errors import ProblemError
from app.services.product_category import CategoryNode, assert_category_compliance, effective_rules, resolve_ancestry


def node(id, code, *, parent_id=None, allowed=None, batch=False, expiry=False, tax_code=None):
    return CategoryNode(id=id, code=code, product_category=code, parent_id=parent_id, product_types=allowed or [], requires_batch=batch, requires_expiry=expiry, default_tax_code=tax_code, status="active")


def test_resolve_ancestry_root_first():
    by_id = {"a": node("a", "A"), "b": node("b", "B", parent_id="a"), "c": node("c", "C", parent_id="b")}
    ancestry = resolve_ancestry("c", by_id, max_depth=10)
    assert [n.code for n in ancestry] == ["A", "B", "C"]


def test_resolve_ancestry_detects_cycle():
    by_id = {"a": node("a", "A", parent_id="b"), "b": node("b", "B", parent_id="a")}
    with pytest.raises(ProblemError) as exc_info:
        resolve_ancestry("a", by_id, max_depth=10)
    assert exc_info.value.code == "CATEGORY_CYCLE"


def test_resolve_ancestry_over_depth():
    by_id = {"a": node("a", "A"), "b": node("b", "B", parent_id="a"), "c": node("c", "C", parent_id="b")}
    with pytest.raises(ProblemError) as exc_info:
        resolve_ancestry("c", by_id, max_depth=2)
    assert exc_info.value.code == "CATEGORY_TOO_DEEP"


def test_effective_rules_batch_expiry_cascade_via_any_ancestor():
    ancestry = [node("a", "A", batch=True), node("b", "B", parent_id="a")]
    rules = effective_rules(ancestry)
    assert rules.requires_batch is True
    assert rules.requires_expiry is False


def test_effective_rules_allowed_types_narrows_only():
    ancestry = [node("a", "A", allowed=["raw_material", "consumable"]), node("b", "B", parent_id="a", allowed=["raw_material"])]
    rules = effective_rules(ancestry)
    assert rules.allowed_product_types == ["raw_material"]


def test_effective_rules_nearest_ancestor_tax_code_wins():
    ancestry = [node("a", "A", tax_code="GST18"), node("b", "B", parent_id="a", tax_code="GST5")]
    rules = effective_rules(ancestry)
    assert rules.default_tax_code == "GST5"


def test_assert_category_compliance_reports_all_violations_at_once():
    ancestry = [node("a", "A", allowed=["finished_good"], batch=True, expiry=True)]
    rules = effective_rules(ancestry)
    with pytest.raises(ProblemError) as exc_info:
        assert_category_compliance(sku="RM-1", type="raw_material", batch_tracked=False, expiry_tracked=False, rules=rules)
    fields = {e["field"] for e in exc_info.value.meta["errors"]}
    assert fields == {"type", "batchTracked", "expiryTracked"}


def test_assert_category_compliance_passes_when_satisfied():
    ancestry = [node("a", "A", allowed=["raw_material"], batch=True, expiry=True)]
    rules = effective_rules(ancestry)
    assert_category_compliance(sku="RM-1", type="raw_material", batch_tracked=True, expiry_tracked=True, rules=rules)
