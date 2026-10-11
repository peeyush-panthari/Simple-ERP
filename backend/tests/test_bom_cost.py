"""Ported 1:1 from backend/services/bom/test/cost.test.ts.

standard_cost was removed from Product (no longer a per-product field), which
was the only base-case pricing source for a BOM leaf component (one with no
nested sub-BOM of its own). Since a nested sub-BOM's own components bottom
out at the same unpriced leaves, every rollup now reports unit_cost 0 -
these tests were updated to reflect that; they still cover the structural
behavior (alternates excluded, unpriced SKUs propagate up through nesting,
non-positive yield errors, empty BOM = 0).
"""

from app.services.bom_cost import CostTreeComponent, CostTreeNode, rollup_cost


def comp(sku, *, line_no=1, quantity="1", scrap_percent="0", is_alternate=False, nested=None):
    return CostTreeComponent(
        line_no=line_no, sku=sku, quantity=quantity, scrap_percent=scrap_percent, is_alternate=is_alternate, nested=nested
    )


def node(sku, *, yield_percent="100", components=None):
    return CostTreeNode(sku=sku, yield_percent=yield_percent, components=components or [])


def test_leaf_component_with_no_nested_bom_is_unpriced():
    result = rollup_cost(node("FG-BRACKET", yield_percent="98.5", components=[comp("RM-AL-6061", quantity="12.5", scrap_percent="2")]))
    assert result.unit_cost == "0.000000"
    assert result.unpriced_skus == ["RM-AL-6061"]
    assert result.lines[0].source == "unknown"
    assert result.lines[0].gross_quantity == "12.750000"


def test_excludes_alternates_so_material_content_is_not_double_counted():
    result = rollup_cost(node("X", components=[comp("PRIMARY", line_no=1), comp("ALTERNATE", line_no=2, is_alternate=True)]))
    assert result.unit_cost == "0.000000"
    assert len(result.lines) == 1


def test_prefers_subassembly_rollup_over_unpriced_leaf():
    """A component with its own nested sub-BOM is priced via that rollup (source
    "bom-rollup"), not treated as an unpriced leaf - even though the sub-BOM's own
    leaf ("RM") is itself unpriced and so the rollup still comes out to 0."""
    result = rollup_cost(node("TOP", components=[comp("SUB", nested=node("SUB", components=[comp("RM", quantity="2")]))]))
    assert result.lines[0].source == "bom-rollup"
    assert result.unit_cost == "0.000000"


def test_names_unpriced_components():
    """unpriced_skus is built from a set, so order isn't guaranteed."""
    result = rollup_cost(node("X", components=[comp("PRICED"), comp("NO-COST", line_no=2)]))
    assert set(result.unpriced_skus) == {"PRICED", "NO-COST"}
    assert result.lines[1].source == "unknown"
    assert result.unit_cost == "0.000000"


def test_propagates_unpriced_components_up_from_nested_assembly():
    result = rollup_cost(node("TOP", components=[comp("SUB", nested=node("SUB", components=[comp("MYSTERY")]))]))
    assert result.unpriced_skus == ["MYSTERY"]


def test_refuses_to_divide_by_non_positive_yield():
    for bad_yield in ("0", "-5"):
        try:
            rollup_cost(node("X", yield_percent=bad_yield))
            assert False, "should have raised"
        except ValueError:
            pass


def test_costs_empty_bom_at_zero():
    assert rollup_cost(node("X")).unit_cost == "0.000000"
