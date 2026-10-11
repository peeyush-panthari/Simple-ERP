"""Multi-level BOM explosion - ported 1:1 from domain/explode.ts.

What Inventory calls before posting production: given "make 250 UNIT of FG-1",
return the flattened list of raw materials to consume.

  input(node)      = requiredOutput / (yieldPercent / 100)
  required(line)   = input * quantity * (1 + scrapPercent / 100)

Sub-assemblies with their own active BOM are exploded recursively and appear
in subAssemblies (informational), while their leaves roll into requirements.
Pure - the caller materialises the tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.money import decimal_str, div, mul, to_decimal


@dataclass
class ExplodeComponent:
    line_no: int
    product_id: str
    sku: str
    quantity: str
    uom: str
    scrap_percent: str
    is_alternate: bool
    alternate_for_line: int | None
    nested: "ExplodeNode | None" = None


@dataclass
class ExplodeNode:
    product_id: str
    sku: str
    uom: str
    yield_percent: str
    components: list[ExplodeComponent] = field(default_factory=list)


@dataclass
class Requirement:
    product_id: str
    sku: str
    uom: str
    quantity: str
    level: int


@dataclass
class Alternate:
    product_id: str
    sku: str
    uom: str
    quantity: str
    alternate_for_line: int
    level: int


@dataclass
class Explosion:
    product_id: str
    sku: str
    quantity: str
    uom: str
    requirements: list[Requirement]
    sub_assemblies: list[Requirement]
    alternates: list[Alternate]
    depth: int


def explode_bom(root: ExplodeNode, quantity, *, max_depth: int) -> Explosion:
    requirements: dict[str, Requirement] = {}
    sub_assemblies: dict[str, Requirement] = {}
    alternates: list[Alternate] = []
    depth = 0

    def accumulate(into: dict[str, Requirement], key: str, next_req: Requirement) -> None:
        existing = into.get(key)
        if not existing:
            into[key] = next_req
            return
        existing.quantity = decimal_str(to_decimal(existing.quantity) + to_decimal(next_req.quantity))
        existing.level = max(existing.level, next_req.level)

    def walk(node: ExplodeNode, required_output, level: int) -> None:
        nonlocal depth
        if level > max_depth:
            raise ValueError(f"BOM explosion for {root.sku} exceeded {max_depth} levels at {node.sku} — the structure is probably circular")
        depth = max(depth, level)

        yield_fraction = div(node.yield_percent, 100)
        if yield_fraction <= 0:
            raise ValueError(f"BOM {node.sku} has a non-positive yield of {node.yield_percent}%")
        input_qty = div(required_output, yield_fraction)

        for component in node.components:
            scrap_factor = to_decimal(1) + div(component.scrap_percent, 100)
            required = mul(mul(input_qty, component.quantity), scrap_factor)
            key = f"{component.product_id}|{component.uom}"

            if component.is_alternate:
                alternates.append(
                    Alternate(
                        product_id=component.product_id,
                        sku=component.sku,
                        uom=component.uom,
                        quantity=decimal_str(required),
                        alternate_for_line=component.alternate_for_line or component.line_no,
                        level=level + 1,
                    )
                )
                continue

            if component.nested:
                accumulate(
                    sub_assemblies,
                    key,
                    Requirement(product_id=component.product_id, sku=component.sku, uom=component.uom, quantity=decimal_str(required), level=level + 1),
                )
                walk(component.nested, required, level + 1)
                continue

            accumulate(
                requirements,
                key,
                Requirement(product_id=component.product_id, sku=component.sku, uom=component.uom, quantity=decimal_str(required), level=level + 1),
            )

    walk(root, to_decimal(quantity), 0)

    return Explosion(
        product_id=root.product_id,
        sku=root.sku,
        quantity=decimal_str(quantity),
        uom=root.uom,
        requirements=sorted(requirements.values(), key=lambda r: r.sku),
        sub_assemblies=sorted(sub_assemblies.values(), key=lambda r: r.sku),
        alternates=alternates,
        depth=depth,
    )
