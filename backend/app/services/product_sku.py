"""SKU rules - ported 1:1 from domain/sku.ts.

A SKU is a public identifier (POs, GRNs, invoices, pallets). Once anything
has transacted against it, renaming it would orphan documents already in
customers'/vendors' hands - so it's frozen and an alias is issued instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from app.core.errors import rule_violation

SKU_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,31}$")


def normalise_sku(raw: str) -> str:
    return raw.strip().upper()


def is_valid_sku(raw: str) -> bool:
    return bool(SKU_PATTERN.match(normalise_sku(raw)))


def assert_valid_sku(raw: str) -> str:
    sku = normalise_sku(raw)
    if not SKU_PATTERN.match(sku):
        raise rule_violation(
            f'"{raw}" is not a valid SKU — use 3 to 32 characters: uppercase letters, digits and hyphens, starting with a letter or digit',
            code="SKU_INVALID",
            meta={"errors": [{"field": "sku", "message": "3–32 chars, A–Z, 0–9 and hyphens"}]},
        )
    return sku


@dataclass
class SkuChangeContext:
    current_sku: str
    status: str
    first_transaction_at: datetime | None
    first_transaction_ref: str | None


def assert_sku_change_allowed(ctx: SkuChangeContext, next_sku: str) -> None:
    if normalise_sku(next_sku) == ctx.current_sku:
        return
    if ctx.first_transaction_at:
        ref = f" (first on {ctx.first_transaction_ref})" if ctx.first_transaction_ref else ""
        raise rule_violation(
            f"{ctx.current_sku} has already been transacted against{ref} — its SKU cannot change. "
            f'Register "{normalise_sku(next_sku)}" as an alias instead: POST /products/{{id}}/aliases',
            code="SKU_IMMUTABLE",
        )
    if ctx.status != "draft":
        raise rule_violation(
            f'{ctx.current_sku} is published — its SKU is immutable. Register "{normalise_sku(next_sku)}" as an alias instead',
            code="SKU_IMMUTABLE",
        )


def assert_uom_change_allowed(ctx: SkuChangeContext, current_uom: str, next_uom: str) -> None:
    if current_uom == next_uom:
        return
    if ctx.status != "draft" or ctx.first_transaction_at:
        raise rule_violation(
            f"{ctx.current_sku} is published in {current_uom} — changing the base unit of measure would rescale every "
            f"existing balance and ledger entry. Create a new SKU in {next_uom} and deprecate this one",
            code="UOM_CHANGE_REQUIRES_NEW_SKU",
        )
