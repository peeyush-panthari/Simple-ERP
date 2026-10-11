"""Standard cost rollup for a BOM version - ported 1:1 from domain/cost.ts.

  grossQty(line)  = quantity x (1 + scrapPercent / 100)
  extended(line)  = grossQty x unitCost
  unitCost(node)  = sum(extended(lines)) / (yieldPercent / 100)

Alternates are excluded (they substitute for a primary line, not add to it).
Pure - the caller materialises the tree from the database and the product module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.money import decimal_str, div, mul, to_decimal


@dataclass
class CostTreeComponent:
    line_no: int
    sku: str
    quantity: str
    scrap_percent: str
    is_alternate: bool
    nested: "CostTreeNode | None" = None


@dataclass
class CostTreeNode:
    sku: str
    yield_percent: str
    components: list[CostTreeComponent] = field(default_factory=list)


@dataclass
class CostRollupLine:
    line_no: int
    sku: str
    gross_quantity: str
    unit_cost: str
    extended_cost: str
    source: str


@dataclass
class CostRollup:
    unit_cost: str
    lines: list[CostRollupLine]
    unpriced_skus: list[str]


def rollup_cost(node: CostTreeNode) -> CostRollup:
    lines: list[CostRollupLine] = []
    unpriced: set[str] = set()
    material_cost = to_decimal(0)

    for component in node.components:
        if component.is_alternate:
            continue

        scrap_factor = to_decimal(1) + div(component.scrap_percent, 100)
        gross_quantity = mul(component.quantity, scrap_factor)

        unit_cost = to_decimal(0)
        source = "unknown"
        if component.nested:
            nested = rollup_cost(component.nested)
            unit_cost = to_decimal(nested.unit_cost)
            source = "bom-rollup"
            for sku in nested.unpriced_skus:
                unpriced.add(sku)
        else:
            unpriced.add(component.sku)

        extended = mul(gross_quantity, unit_cost)
        material_cost = material_cost + extended
        lines.append(
            CostRollupLine(
                line_no=component.line_no,
                sku=component.sku,
                gross_quantity=decimal_str(gross_quantity),
                unit_cost=decimal_str(unit_cost),
                extended_cost=decimal_str(extended),
                source=source,
            )
        )

    yield_fraction = div(node.yield_percent, 100)
    if yield_fraction <= 0:
        # Guarded by a check constraint and validation, so reaching here means
        # corrupt data - fail loudly rather than dividing by zero.
        raise ValueError(f"BOM {node.sku} has a non-positive yield of {node.yield_percent}%")

    return CostRollup(
        unit_cost=decimal_str(div(material_cost, yield_fraction)),
        lines=lines,
        unpriced_skus=list(unpriced),
    )
