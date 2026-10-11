"""New coverage - the Node bom service had no tests for components.ts."""

from app.services.bom_components import ComponentInput, find_broken_alternates, find_duplicate_primary_lines, find_numeric_problems, is_valid_yield


def line(line_no, product_id="p1", sku="RM-1", quantity="1", uom="UNIT", scrap="0", is_alternate=False, alt_for=None):
    return ComponentInput(line_no=line_no, component_product_id=product_id, component_sku=sku, quantity=quantity, uom=uom, scrap_percent=scrap, is_alternate=is_alternate, alternate_for_line=alt_for)


def test_no_duplicate_when_lines_differ_by_product():
    lines = [line(1, product_id="p1"), line(2, product_id="p2")]
    assert find_duplicate_primary_lines(lines) == []


def test_duplicate_primary_lines_same_product_and_uom():
    lines = [line(1, product_id="p1", uom="KG"), line(2, product_id="p1", uom="KG")]
    errors = find_duplicate_primary_lines(lines)
    assert len(errors) == 1


def test_duplicate_check_ignores_alternates():
    lines = [line(1, product_id="p1", uom="KG"), line(2, product_id="p1", uom="KG", is_alternate=True, alt_for=1)]
    assert find_duplicate_primary_lines(lines) == []


def test_broken_alternate_missing_target():
    lines = [line(1, is_alternate=True, alt_for=None)]
    errors = find_broken_alternates(lines)
    assert len(errors) == 1


def test_broken_alternate_points_at_nonexistent_line():
    lines = [line(1, is_alternate=True, alt_for=5)]
    errors = find_broken_alternates(lines)
    assert len(errors) == 1


def test_broken_alternate_points_at_another_alternate():
    lines = [line(1, is_alternate=True, alt_for=2), line(2, is_alternate=True, alt_for=1)]
    errors = find_broken_alternates(lines)
    assert len(errors) >= 1


def test_broken_alternate_points_at_itself():
    lines = [line(1, is_alternate=True, alt_for=1)]
    errors = find_broken_alternates(lines)
    assert len(errors) == 1


def test_non_alternate_with_alternate_for_line_set_is_an_error():
    lines = [line(1, is_alternate=False, alt_for=2)]
    errors = find_broken_alternates(lines)
    assert len(errors) == 1


def test_valid_alternate_wiring_has_no_errors():
    lines = [line(1, is_alternate=False), line(2, is_alternate=True, alt_for=1)]
    assert find_broken_alternates(lines) == []


def test_numeric_problems_zero_quantity():
    errors = find_numeric_problems([line(1, quantity="0")])
    assert len(errors) == 1


def test_numeric_problems_scrap_at_100_is_invalid():
    errors = find_numeric_problems([line(1, scrap="100")])
    assert len(errors) == 1


def test_numeric_problems_scrap_just_under_100_is_valid():
    assert find_numeric_problems([line(1, scrap="99.999")]) == []


def test_is_valid_yield():
    assert is_valid_yield("100") is True
    assert is_valid_yield("0.01") is True
    assert is_valid_yield("0") is False
    assert is_valid_yield("100.01") is False
