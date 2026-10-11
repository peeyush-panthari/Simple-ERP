"""Materialises the recursive structures the pure cost/explode modules
operate on. Ported from backend_py/app/services/bom_tree.py."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.services import bom_repo
from app.services.bom_cost import CostTreeComponent, CostTreeNode
from app.services.bom_explode import ExplodeComponent, ExplodeNode
from app.core.money import decimal_str


@dataclass
class TreeContext:
    tenant_id: uuid.UUID
    as_of: date
    max_depth: int


def _nested_nodes(ctx: TreeContext, components: list) -> dict[uuid.UUID, dict]:
    """The active approved BOM of each of a level's sibling components,
    batched across the whole sibling group."""
    product_ids = [c.component_product_id for c in components]
    active_by_product = bom_repo.find_active_versions_for_products(ctx.tenant_id, product_ids, ctx.as_of)
    components_by_version = bom_repo.components_of_many([version.id for _, version in active_by_product.values()])
    return {
        product_id: {"sku": bom.product_sku, "yield_percent": decimal_str(version.yield_percent), "components": components_by_version.get(version.id, [])}
        for product_id, (bom, version) in active_by_product.items()
    }


def build_cost_tree(ctx: TreeContext, sku: str, yield_percent: str, components: list, depth: int = 0) -> CostTreeNode:
    lines: list[CostTreeComponent] = []
    nested_by_product = _nested_nodes(ctx, components) if depth < ctx.max_depth and components else {}

    for component in components:
        nested = nested_by_product.get(component.component_product_id)

        lines.append(
            CostTreeComponent(
                line_no=component.line_no,
                sku=component.component_sku,
                quantity=decimal_str(component.quantity),
                scrap_percent=decimal_str(component.scrap_percent),
                is_alternate=component.is_alternate,
                nested=build_cost_tree(ctx, nested["sku"], nested["yield_percent"], nested["components"], depth + 1) if nested else None,
            )
        )

    return CostTreeNode(sku=sku, yield_percent=yield_percent, components=lines)


def build_explode_tree(ctx: TreeContext, root: dict, components: list, depth: int = 0) -> ExplodeNode:
    lines: list[ExplodeComponent] = []
    nested_by_product = _nested_nodes(ctx, components) if depth < ctx.max_depth and components else {}

    for component in components:
        nested = nested_by_product.get(component.component_product_id)
        lines.append(
            ExplodeComponent(
                line_no=component.line_no,
                product_id=str(component.component_product_id),
                sku=component.component_sku,
                quantity=decimal_str(component.quantity),
                uom=component.uom,
                scrap_percent=decimal_str(component.scrap_percent),
                is_alternate=component.is_alternate,
                alternate_for_line=component.alternate_for_line,
                nested=build_explode_tree(
                    ctx,
                    {"product_id": str(component.component_product_id), "sku": nested["sku"], "uom": component.uom, "yield_percent": nested["yield_percent"]},
                    nested["components"],
                    depth + 1,
                )
                if nested
                else None,
            )
        )

    return ExplodeNode(product_id=root["product_id"], sku=root["sku"], uom=root["uom"], yield_percent=root["yield_percent"], components=lines)
