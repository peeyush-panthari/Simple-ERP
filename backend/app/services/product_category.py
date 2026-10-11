"""Category tree - ported 1:1 from domain/category.ts."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import rule_violation


@dataclass
class CategoryNode:
    id: str
    code: str
    product_category: str
    parent_id: str | None
    product_types: list[str]
    requires_batch: bool
    requires_expiry: bool
    default_tax_code: str | None
    status: str


def resolve_ancestry(category_id: str, by_id: dict[str, CategoryNode], max_depth: int) -> list[CategoryNode]:
    """Walks a category to the root, rejecting cycles and over-deep trees.
    Returns the chain root-first so callers can render a breadcrumb."""
    chain: list[CategoryNode] = []
    seen: set[str] = set()
    cursor: str | None = category_id

    while cursor:
        if cursor in seen:
            path = " → ".join([c.code for c in chain] + [by_id[cursor].code if cursor in by_id else cursor])
            raise rule_violation(f"Category tree contains a cycle: {path}", code="CATEGORY_CYCLE")
        seen.add(cursor)
        node = by_id.get(cursor)
        if not node:
            break
        chain.insert(0, node)
        if len(chain) > max_depth:
            raise rule_violation(
                f"Category nesting exceeds the maximum depth of {max_depth} ({' → '.join(c.code for c in chain)})",
                code="CATEGORY_TOO_DEEP",
            )
        cursor = node.parent_id
    return chain


@dataclass
class EffectiveCategoryRules:
    requires_batch: bool
    requires_expiry: bool
    allowed_product_types: list[str]
    default_tax_code: str | None
    breadcrumb: str


def effective_rules(ancestry: list[CategoryNode]) -> EffectiveCategoryRules:
    """Cascades down the tree: the strictest ancestor wins. A child may narrow
    but never widen what its parent permits."""
    allowed: list[str] = []
    tax_code: str | None = None
    for node in ancestry:
        if node.product_types:
            allowed = [t for t in allowed if t in node.product_types] if allowed else list(node.product_types)
        if node.default_tax_code:
            tax_code = node.default_tax_code
    return EffectiveCategoryRules(
        requires_batch=any(n.requires_batch for n in ancestry),
        requires_expiry=any(n.requires_expiry for n in ancestry),
        allowed_product_types=allowed,
        default_tax_code=tax_code,
        breadcrumb=" → ".join(n.product_category for n in ancestry),
    )


def category_problems(
    *, sku: str, type: str, batch_tracked: bool, expiry_tracked: bool, rules: EffectiveCategoryRules
) -> list[dict]:
    errors: list[dict] = []
    if rules.allowed_product_types and type not in rules.allowed_product_types:
        errors.append({"field": "type", "message": f"Category {rules.breadcrumb} only accepts {', '.join(rules.allowed_product_types)}"})
    if rules.requires_batch and not batch_tracked:
        errors.append({"field": "batchTracked", "message": f"Category {rules.breadcrumb} requires batch tracking"})
    if rules.requires_expiry and not expiry_tracked:
        errors.append({"field": "expiryTracked", "message": f"Category {rules.breadcrumb} requires expiry tracking"})
    return errors


def assert_category_compliance(
    *, sku: str, type: str, batch_tracked: bool, expiry_tracked: bool, rules: EffectiveCategoryRules
) -> None:
    errors = category_problems(
        sku=sku, type=type, batch_tracked=batch_tracked, expiry_tracked=expiry_tracked, rules=rules
    )
    if errors:
        joined = "; ".join(e["message"] for e in errors)
        raise rule_violation(f"{sku} does not satisfy its category rules: {joined}", code="CATEGORY_RULE_VIOLATION", meta={"errors": errors})
