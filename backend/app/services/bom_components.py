"""Structural validation of a component list - ported 1:1 from domain/components.ts.

The rules that need nothing but the lines themselves (duplicates, alternate
wiring, numeric ranges). Eligibility rules that need the Product master live
in the route.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.money import to_decimal


@dataclass
class ComponentInput:
    line_no: int
    component_product_id: str
    component_sku: str
    quantity: str
    uom: str
    scrap_percent: str
    is_alternate: bool
    alternate_for_line: int | None


def find_duplicate_primary_lines(components: list[ComponentInput]) -> list[dict]:
    """Two primary lines for the same part+UOM are almost always a data-entry
    slip that silently doubles consumption; an alternate legitimately repeats
    the pair because it names the substitute relationship."""
    seen: dict[str, ComponentInput] = {}
    errors: list[dict] = []
    for line in components:
        if line.is_alternate:
            continue
        key = f"{line.component_product_id}|{line.uom}"
        first = seen.get(key)
        if first:
            errors.append(
                {
                    "field": f"components.{line.line_no}.componentProductId",
                    "message": f'{line.component_sku} in {line.uom} is already on line {first.line_no}. Merge the quantities, or tick "alternate" if this line is a substitute.',
                }
            )
            continue
        seen[key] = line
    return errors


def find_broken_alternates(components: list[ComponentInput]) -> list[dict]:
    """An alternate must point at a primary line that exists and is not itself an alternate."""
    by_line = {c.line_no: c for c in components}
    errors: list[dict] = []
    for line in components:
        if not line.is_alternate:
            if line.alternate_for_line is not None:
                errors.append(
                    {
                        "field": f"components.{line.line_no}.alternateForLine",
                        "message": f"Line {line.line_no} ({line.component_sku}) sets alternateForLine but is not flagged as an alternate.",
                    }
                )
            continue
        if line.alternate_for_line is None:
            errors.append(
                {
                    "field": f"components.{line.line_no}.alternateForLine",
                    "message": f"Alternate line {line.line_no} ({line.component_sku}) must name the primary line it substitutes for.",
                }
            )
            continue
        target = by_line.get(line.alternate_for_line)
        if not target:
            errors.append(
                {
                    "field": f"components.{line.line_no}.alternateForLine",
                    "message": f"Alternate line {line.line_no} ({line.component_sku}) points at line {line.alternate_for_line}, which is not on this version.",
                }
            )
        elif target.is_alternate:
            errors.append(
                {
                    "field": f"components.{line.line_no}.alternateForLine",
                    "message": f"Alternate line {line.line_no} ({line.component_sku}) points at line {line.alternate_for_line}, which is itself an alternate. Point it at the primary component.",
                }
            )
        elif target.line_no == line.line_no:
            errors.append(
                {
                    "field": f"components.{line.line_no}.alternateForLine",
                    "message": f"Line {line.line_no} ({line.component_sku}) cannot be an alternate for itself.",
                }
            )
    return errors


def find_numeric_problems(components: list[ComponentInput]) -> list[dict]:
    errors: list[dict] = []
    for line in components:
        if to_decimal(line.quantity) <= 0:
            errors.append(
                {
                    "field": f"components.{line.line_no}.quantity",
                    "message": f"Quantity for {line.component_sku} on line {line.line_no} must be greater than zero.",
                }
            )
        scrap = to_decimal(line.scrap_percent)
        if scrap < 0 or scrap >= 100:
            errors.append(
                {
                    "field": f"components.{line.line_no}.scrapPercent",
                    "message": f"Scrap for {line.component_sku} on line {line.line_no} must be at least 0% and below 100% (got {line.scrap_percent}%).",
                }
            )
    return errors


def validate_component_structure(components: list[ComponentInput]) -> list[dict]:
    """All structural problems in one pass."""
    return find_numeric_problems(components) + find_duplicate_primary_lines(components) + find_broken_alternates(components)


def is_valid_yield(yield_percent: str) -> bool:
    y = to_decimal(yield_percent)
    return y > 0 and y <= 100
