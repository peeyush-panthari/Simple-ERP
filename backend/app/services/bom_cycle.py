"""Circular-reference detection for nested BOMs - ported 1:1 from domain/cycle.ts.

DFS over the *product* graph (not the version graph): can starting from
finished good A ever reach A again, regardless of which version supplies the
edge. Edges come from the caller's `resolve` function, which lets the caller
feed in the proposed (not-yet-saved) component list for the root.

Ported as plain synchronous functions rather than Node's async ones - Flask +
SQLAlchemy here are synchronous (no concurrent-I/O benefit to async, unlike
Node's HTTP calls to a separate Product service); the algorithm and results
are identical, only the sync/async mechanics differ.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class BomNode:
    product_id: str
    sku: str


ComponentResolver = Callable[[BomNode], list[BomNode]]


@dataclass
class CycleFinding:
    kind: str  # "cycle"
    path: list[BomNode]


@dataclass
class DepthFinding:
    kind: str  # "depth-exceeded"
    path: list[BomNode]
    max_depth: int


def format_path(path: list[BomNode]) -> str:
    return " → ".join(n.sku for n in path)


def find_cycle(root: BomNode, resolve: ComponentResolver, *, max_depth: int) -> CycleFinding | DepthFinding | None:
    """DFS for a repeated product on the current branch. Nodes proven clean are
    memoised in `settled` so a diamond-shaped BOM costs O(V+E) rather than
    exponential time."""
    settled: set[str] = set()
    on_stack: dict[str, int] = {}
    branch: list[BomNode] = []

    def visit(node: BomNode, depth: int) -> CycleFinding | DepthFinding | None:
        seen_at = on_stack.get(node.product_id)
        if seen_at is not None:
            return CycleFinding(kind="cycle", path=[*branch[seen_at:], node])
        if node.product_id in settled:
            return None
        if depth > max_depth:
            return DepthFinding(kind="depth-exceeded", path=[*branch, node], max_depth=max_depth)

        on_stack[node.product_id] = len(branch)
        branch.append(node)
        try:
            for child in resolve(node):
                finding = visit(child, depth + 1)
                if finding:
                    return finding
        finally:
            branch.pop()
            del on_stack[node.product_id]
        settled.add(node.product_id)
        return None

    return visit(root, 0)


def find_cycle_for_proposed_components(
    root: BomNode, proposed: list[BomNode], resolve: ComponentResolver, *, max_depth: int
) -> CycleFinding | DepthFinding | None:
    """The root's edges are overridden with the proposed (unsaved) list so an
    in-flight edit is checked before it's persisted."""

    def resolve_with_root_override(node: BomNode) -> list[BomNode]:
        if node.product_id == root.product_id:
            return list(proposed)
        return resolve(node)

    return find_cycle(root, resolve_with_root_override, max_depth=max_depth)
