"""Generic helpers for building parameterized BigQuery INSERT/UPDATE
statements from plain dicts, for use inside a bq_transaction.run_in_transaction
script.

This is the Phase 3 replacement for SQLAlchemy ORM's `db.session.add(...)` +
`db.session.commit()` write pattern. That pattern doesn't carry over to
BigQuery: a multi-statement transaction has to be one complete SQL script
sent as a single job (see bq_transaction.py), so a write can't be built by
handing individual model instances to a long-lived ORM session the way the
Postgres path still does - every statement a logical operation needs (e.g.
insert a business entity + unset every other row's is_default flag + insert
an audit-log row) becomes one explicit INSERT/UPDATE, batched into one
script.

Reads are unaffected by any of this - plain SELECTs via the existing
SQLAlchemy ORM query API keep working through the sqlalchemy-bigquery
dialect (see the plan's Phase 3 note); only writes that need transactional
atomicity go through this module instead.

See /Users/Peeyush/.claude/plans/mossy-stirring-gosling.md (Phase 3).
"""

from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from google.cloud import bigquery

from app.services.bq_transaction import run_in_transaction


@dataclass
class InsertOp:
    """One row to insert into one table, as part of a larger script."""

    table: str
    values: dict[str, Any]


class Not:
    """Wraps a WHERE value so it renders as `!=` instead of `=`."""

    def __init__(self, value: Any):
        self.value = value


@dataclass
class UpdateOp:
    """One UPDATE statement, as part of a larger script. `where` maps column
    -> value (rendered as `col = @param`) or column -> Not(value) (rendered
    as `col != @param`); every condition is ANDed together."""

    table: str
    set_values: dict[str, Any]
    where: dict[str, Any]


@dataclass
class DeleteOp:
    """One DELETE statement, as part of a larger script. `where` follows the
    same rules as UpdateOp's: column -> value for `=`, column -> Not(value)
    for `!=`, all ANDed."""

    table: str
    where: dict[str, Any]


WriteOp = InsertOp | UpdateOp | DeleteOp


def _bq_type_and_value(value: Any) -> tuple[str, Any]:
    """Maps a Python value to (BigQuery param type, bindable value)."""
    if value is None:
        return "STRING", None  # type is irrelevant for a NULL scalar param
    if isinstance(value, bool):
        return "BOOL", value
    if isinstance(value, int):
        return "INT64", value
    if isinstance(value, (float, Decimal)):
        return "NUMERIC", value
    if isinstance(value, uuid.UUID):
        return "STRING", str(value)
    if isinstance(value, datetime.datetime):
        return "TIMESTAMP", value
    if isinstance(value, datetime.date):
        return "DATE", value
    if isinstance(value, dict):
        return "JSON", json.dumps(value)
    return "STRING", str(value)


def _param_for(name: str, value: Any) -> bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter:
    if isinstance(value, (list, tuple)):
        if not value:
            return bigquery.ArrayQueryParameter(name, "STRING", [])
        item_type, _ = _bq_type_and_value(value[0])
        bound_items = [_bq_type_and_value(v)[1] for v in value]
        return bigquery.ArrayQueryParameter(name, item_type, bound_items)
    bq_type, bound_value = _bq_type_and_value(value)
    return bigquery.ScalarQueryParameter(name, bq_type, bound_value)


def _render_insert(dataset: str, op: InsertOp, index: int, params: list) -> str:
    columns = list(op.values.keys())
    placeholders = []
    for col in columns:
        param_name = f"p{index}_{col}"
        placeholders.append(f"@{param_name}")
        params.append(_param_for(param_name, op.values[col]))
    columns_sql = ", ".join(columns)
    values_sql = ", ".join(placeholders)
    return f"INSERT INTO `{dataset}.{op.table}` ({columns_sql}) VALUES ({values_sql});"


def _render_where(where: dict[str, Any], index: int, params: list) -> str:
    clauses = []
    for col, value in where.items():
        param_name = f"p{index}_where_{col}"
        if isinstance(value, Not):
            clauses.append(f"{col} != @{param_name}")
            params.append(_param_for(param_name, value.value))
        else:
            clauses.append(f"{col} = @{param_name}")
            params.append(_param_for(param_name, value))
    return " AND ".join(clauses)


def _render_update(dataset: str, op: UpdateOp, index: int, params: list) -> str:
    if not op.where:
        raise ValueError(f"UpdateOp on '{op.table}' has no WHERE condition - refusing to build an unconditional UPDATE")
    if not op.set_values:
        raise ValueError(f"UpdateOp on '{op.table}' has no SET values - refusing to build an empty UPDATE")

    set_clauses = []
    for col, value in op.set_values.items():
        param_name = f"p{index}_set_{col}"
        set_clauses.append(f"{col} = @{param_name}")
        params.append(_param_for(param_name, value))

    set_sql = ", ".join(set_clauses)
    where_sql = _render_where(op.where, index, params)
    return f"UPDATE `{dataset}.{op.table}` SET {set_sql} WHERE {where_sql};"


def _render_delete(dataset: str, op: DeleteOp, index: int, params: list) -> str:
    if not op.where:
        raise ValueError(f"DeleteOp on '{op.table}' has no WHERE condition - refusing to build an unconditional DELETE")
    return f"DELETE FROM `{dataset}.{op.table}` WHERE {_render_where(op.where, index, params)};"


def build_write_script(dataset: str, ops: list[WriteOp]) -> tuple[str, list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter]]:
    """Builds one BEGIN/COMMIT TRANSACTION script executing every op in
    order. Parameter names are prefixed with the op's index so two ops
    touching a same-named column in different tables never collide."""
    if not ops:
        raise ValueError("build_write_script requires at least one op")

    statements = ["BEGIN TRANSACTION;"]
    params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] = []
    for i, op in enumerate(ops):
        if isinstance(op, InsertOp):
            statements.append(_render_insert(dataset, op, i, params))
        elif isinstance(op, UpdateOp):
            statements.append(_render_update(dataset, op, i, params))
        elif isinstance(op, DeleteOp):
            statements.append(_render_delete(dataset, op, i, params))
        else:
            raise TypeError(f"unsupported op type {type(op).__name__}")
    statements.append("COMMIT TRANSACTION;")
    return "\n".join(statements), params


def run_write_transaction(dataset: str, build_ops: Callable[[], list[WriteOp]], *, max_retries: int = 5):
    """Runs build_write_script(dataset, build_ops()) as one retried
    transaction. `build_ops` is called fresh on every attempt - for
    operations with no state that needs re-reading under concurrency (most
    flat master-data creates), it can just be `lambda: ops` over an
    already-built list; for anything that depends on a value read at write
    time (e.g. a document number from app/services/sequences.py, or an
    availability check), `build_ops` should redo that read itself so a
    retry sees the latest committed state, not a stale one from the first
    attempt."""

    def build() -> tuple[str, list]:
        return build_write_script(dataset, build_ops())

    return run_in_transaction(build, max_retries=max_retries)
