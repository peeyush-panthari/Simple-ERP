"""New coverage - the Node bom service had no tests for explode.ts."""

from app.services.bom_explode import ExplodeComponent, ExplodeNode, explode_bom


def leaf(product_id, sku, *, quantity="1", uom="UNIT", scrap="0", is_alternate=False, alternate_for_line=None, nested=None, line_no=1):
    return ExplodeComponent(
        line_no=line_no, product_id=product_id, sku=sku, quantity=quantity, uom=uom, scrap_percent=scrap, is_alternate=is_alternate, alternate_for_line=alternate_for_line, nested=nested
    )


def test_simple_single_level_explosion():
    root = ExplodeNode(product_id="fg", sku="FG", uom="UNIT", yield_percent="100", components=[leaf("rm", "RM", quantity="2")])
    result = explode_bom(root, "10", max_depth=10)
    assert len(result.requirements) == 1
    assert result.requirements[0].quantity == "20.000000"
    # depth tracks how deep the walk() recursion goes (root call is level 0),
    # not the requirement's level - a flat, non-nested BOM never recurses.
    assert result.depth == 0


def test_yield_inflates_required_input():
    root = ExplodeNode(product_id="fg", sku="FG", uom="UNIT", yield_percent="50", components=[leaf("rm", "RM", quantity="1")])
    result = explode_bom(root, "10", max_depth=10)
    # input = 10 / 0.5 = 20
    assert result.requirements[0].quantity == "20.000000"


def test_scrap_inflates_required_quantity():
    root = ExplodeNode(product_id="fg", sku="FG", uom="UNIT", yield_percent="100", components=[leaf("rm", "RM", quantity="1", scrap="10")])
    result = explode_bom(root, "10", max_depth=10)
    assert result.requirements[0].quantity == "11.000000"


def test_shared_leaf_across_two_lines_accumulates_and_takes_max_level():
    root = ExplodeNode(
        product_id="fg", sku="FG", uom="UNIT", yield_percent="100",
        components=[leaf("rm", "RM", quantity="1", line_no=1), leaf("rm", "RM", quantity="2", line_no=2)],
    )
    result = explode_bom(root, "1", max_depth=10)
    assert len(result.requirements) == 1
    assert result.requirements[0].quantity == "3.000000"


def test_alternates_quantified_but_not_added_to_requirements():
    root = ExplodeNode(product_id="fg", sku="FG", uom="UNIT", yield_percent="100", components=[leaf("rm-alt", "RM-ALT", quantity="5", is_alternate=True, alternate_for_line=1)])
    result = explode_bom(root, "2", max_depth=10)
    assert result.requirements == []
    assert len(result.alternates) == 1
    assert result.alternates[0].quantity == "10.000000"


def test_nested_subassembly_appears_in_subassemblies_and_its_leaves_in_requirements():
    nested = ExplodeNode(product_id="sub", sku="SUB", uom="UNIT", yield_percent="100", components=[leaf("rm", "RM", quantity="3")])
    root = ExplodeNode(product_id="fg", sku="FG", uom="UNIT", yield_percent="100", components=[leaf("sub", "SUB", quantity="1", nested=nested)])
    result = explode_bom(root, "2", max_depth=10)
    assert len(result.sub_assemblies) == 1
    assert result.sub_assemblies[0].quantity == "2.000000"
    assert len(result.requirements) == 1
    assert result.requirements[0].sku == "RM"
    assert result.requirements[0].quantity == "6.000000"
    # One level of sub-assembly nesting: walk() recurses once, root=0 -> nested=1.
    assert result.depth == 1


def test_depth_exceeded_raises():
    root = ExplodeNode(product_id="fg", sku="FG", uom="UNIT", yield_percent="100", components=[])
    try:
        explode_bom(root, "1", max_depth=-1)
        assert False, "should have raised"
    except ValueError:
        pass
