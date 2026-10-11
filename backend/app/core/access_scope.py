"""Per-warehouse/per-factory scope enforcement. Ported verbatim.

An actor's `warehouse_ids`/`factory_ids` are `None` when unrestricted or a
set of allowed ids when at least one of the actor's active role assignments
carries a warehouse/factory restriction.
"""

from __future__ import annotations

from app.core.errors import forbidden


def assert_warehouse_in_scope(actor: dict, warehouse_id) -> None:
    allowed = actor.get("warehouse_ids")
    if allowed is not None and str(warehouse_id) not in allowed:
        raise forbidden("You do not have access to this warehouse", code="WAREHOUSE_OUT_OF_SCOPE")


def assert_factory_in_scope(actor: dict, factory_id) -> None:
    allowed = actor.get("factory_ids")
    if allowed is not None and str(factory_id) not in allowed:
        raise forbidden("You do not have access to this factory", code="FACTORY_OUT_OF_SCOPE")


def scope_query_by_warehouse(query, column, actor: dict):
    allowed = actor.get("warehouse_ids")
    if allowed is None:
        return query
    return query.filter(column.in_(allowed))


def scope_query_by_factory(query, column, actor: dict):
    allowed = actor.get("factory_ids")
    if allowed is None:
        return query
    return query.filter(column.in_(allowed))
