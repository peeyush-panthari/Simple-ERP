"""Gapless per-tenant document numbering using PostgreSQL.

Must be called inside the same transaction that inserts the document so a
rolled-back document does not burn a number.
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import session
from app.models.doc_sequence import DocSequence


def format_doc_number(prefix: str, seq: int, pad: int = 4) -> str:
    return f"{prefix}-{str(seq).zfill(pad)}"


def next_sequence_value(tenant_id: uuid.UUID, prefix: str, *, start: int = 0) -> int:
    stmt = (
        pg_insert(DocSequence)
        .values(tenant_id=tenant_id, prefix=prefix, current_value=start + 1)
        .on_conflict_do_update(
            index_elements=["tenant_id", "prefix"],
            set_={"current_value": DocSequence.current_value + 1},
        )
        .returning(DocSequence.current_value)
    )
    return session.execute(stmt).scalar_one()


def next_document_number(tenant_id: uuid.UUID, prefix: str, *, pad: int = 4, start: int = 1000) -> str:
    value = next_sequence_value(tenant_id, prefix, start=start)
    return format_doc_number(prefix, value, pad)


_SKU_TYPE_PREFIXES = {
    "raw_material": "RM",
    "finished_good": "FG",
    "consumable": "CN",
    "service": "SR",
}


def _sku_alnum_suffix(n: int) -> str:
    """Maps a 1-based counter to AA01, AA02, ..., AA99, AB01, ..., AZ99, BA01, ...
    - 2 letters cycling A-Z x A-Z, 2 digits cycling 01-99 within each letter pair."""
    idx = n - 1
    number_part = (idx % 99) + 1
    letter_index = idx // 99
    letter1 = chr(ord("A") + letter_index // 26)
    letter2 = chr(ord("A") + letter_index % 26)
    return f"{letter1}{letter2}{number_part:02d}"


def next_sku(tenant_id: uuid.UUID, product_type: str) -> str:
    """<TYPE prefix>-<AA01-style counter>, e.g. RM-AA01, RM-AA02, ... RM-AB01."""
    prefix = _SKU_TYPE_PREFIXES.get(product_type)
    if prefix is None:
        raise ValueError(f"no SKU prefix configured for product type {product_type!r}")
    value = next_sequence_value(tenant_id, f"SKU-{prefix}", start=0)
    return f"{prefix}-{_sku_alnum_suffix(value)}"


def next_prefixed_code(tenant_id: uuid.UUID, prefix: str, sequence_key: str) -> str:
    """<PREFIX>-<AA01-style counter>, one counter per tenant + sequence_key."""
    value = next_sequence_value(tenant_id, sequence_key, start=0)
    return f"{prefix}-{_sku_alnum_suffix(value)}"


def next_category_code(tenant_id: uuid.UUID) -> str:
    return next_prefixed_code(tenant_id, "PROD", "CATEGORY-CODE")


def next_factory_code(tenant_id: uuid.UUID) -> str:
    return next_prefixed_code(tenant_id, "FAC", "FACTORY-CODE")


def next_business_entity_code(tenant_id: uuid.UUID) -> str:
    return next_prefixed_code(tenant_id, "ENT", "ENTITY-CODE")


def next_warehouse_code(tenant_id: uuid.UUID) -> str:
    return next_prefixed_code(tenant_id, "WH", "WAREHOUSE-CODE")
