"""Ported 1:1 from backend/services/bom/test/cycle.test.ts."""

from app.services.bom_cycle import BomNode, find_cycle, find_cycle_for_proposed_components, format_path


def n(sku: str) -> BomNode:
    return BomNode(product_id=sku.lower(), sku=sku)


def graph(edges: dict[str, list[str]]):
    """Builds a resolver from a plain adjacency map keyed by SKU."""

    def resolve(node: BomNode) -> list[BomNode]:
        return [n(s) for s in edges.get(node.sku, [])]

    return resolve


MAX_DEPTH = 20


def test_passes_simple_two_level_bom():
    finding = find_cycle(n("FG"), graph({"FG": ["SUB", "RM1"], "SUB": ["RM2"]}), max_depth=MAX_DEPTH)
    assert finding is None


def test_catches_direct_self_reference():
    finding = find_cycle(n("FG"), graph({"FG": ["FG"]}), max_depth=MAX_DEPTH)
    assert finding.kind == "cycle"
    assert format_path(finding.path) == "FG → FG"


def test_catches_indirect_cycle_and_renders_the_loop_not_the_whole_walk():
    finding = find_cycle(n("A"), graph({"A": ["B"], "B": ["C"], "C": ["A"]}), max_depth=MAX_DEPTH)
    assert format_path(finding.path) == "A → B → C → A"


def test_reports_loop_from_where_it_closes_not_from_root():
    # Root R reaches B, and B -> C -> B is the actual cycle.
    finding = find_cycle(n("R"), graph({"R": ["B"], "B": ["C"], "C": ["B"]}), max_depth=MAX_DEPTH)
    assert format_path(finding.path) == "B → C → B"


def test_does_not_mistake_diamond_for_cycle():
    # Both sub-assemblies consume the same raw material. Legal, and common.
    finding = find_cycle(n("FG"), graph({"FG": ["L", "R"], "L": ["RM"], "R": ["RM"]}), max_depth=MAX_DEPTH)
    assert finding is None


def test_visits_shared_subtree_once_rather_than_exponentially():
    # A chain of diamonds would blow up without memoisation.
    edges: dict[str, list[str]] = {}
    for i in range(12):
        edges[f"N{i}"] = [f"L{i}", f"R{i}"]
    for i in range(12):
        edges[f"L{i}"] = [f"N{i + 1}"]
        edges[f"R{i}"] = [f"N{i + 1}"]
    edges["N12"] = []

    call_count = 0
    base_resolve = graph(edges)

    def counting_resolve(node: BomNode) -> list[BomNode]:
        nonlocal call_count
        call_count += 1
        return base_resolve(node)

    finding = find_cycle(n("N0"), counting_resolve, max_depth=100)
    assert finding is None
    # 13 N-nodes + 24 side nodes = 37 distinct products, each expanded once.
    assert call_count <= 37


def test_gives_up_with_depth_exceeded_rather_than_recursing_forever():
    deep: dict[str, list[str]] = {}
    for i in range(30):
        deep[f"L{i}"] = [f"L{i + 1}"]
    finding = find_cycle(n("L0"), graph(deep), max_depth=5)
    assert finding.kind == "depth-exceeded"
    assert finding.max_depth == 5


def test_rejects_edit_before_it_lands_using_proposed_component_list():
    # SUB already consumes nothing. Proposing that FG consumes SUB is fine...
    stored = graph({"SUB": []})
    assert find_cycle_for_proposed_components(n("FG"), [n("SUB")], stored, max_depth=MAX_DEPTH) is None

    # ...but if SUB consumes FG, the proposed edge closes a loop.
    circular = graph({"SUB": [n("FG").sku]})
    finding = find_cycle_for_proposed_components(n("FG"), [n("SUB")], circular, max_depth=MAX_DEPTH)
    assert finding.kind == "cycle"
    assert format_path(finding.path) == "FG → SUB → FG"


def test_rejects_proposal_listing_product_as_its_own_component():
    finding = find_cycle_for_proposed_components(n("FG"), [n("FG")], graph({}), max_depth=MAX_DEPTH)
    assert finding.kind == "cycle"
