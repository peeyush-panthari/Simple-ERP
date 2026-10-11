"""Pagination helpers, ported from backend_py/app/pagination.py.

`ListQuery` is now populated via FastAPI's native query-param dependency
injection (`Depends(ListQuery)`) instead of `ListQuery.model_validate(request.args)`
- same fields, same defaults/bounds, FastAPI just parses it earlier and
produces the same `problem+json` VALIDATION_FAILED shape through the
RequestValidationError handler in app/core/errors.py.
"""

from __future__ import annotations

import math

from fastapi import Query
from pydantic import BaseModel


class ListQuery(BaseModel):
    page: int = 1
    limit: int = 25
    sort: str | None = None
    q: str | None = None

    def __init__(
        self,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=25, ge=1, le=200),
        sort: str | None = Query(default=None),
        q: str | None = Query(default=None, min_length=1, max_length=200),
    ) -> None:
        super().__init__(page=page, limit=limit, sort=sort, q=q)


def list_response(data: list, query: ListQuery, total: int) -> dict:
    return {
        "data": data,
        "meta": {
            "page": query.page,
            "limit": query.limit,
            "total": total,
            "pages": max(1, math.ceil(total / query.limit)) if query.limit else 1,
        },
    }


def offset_of(query: ListQuery) -> int:
    return (query.page - 1) * query.limit


def parse_sort(sort: str | None, allowed: list[str], fallback: tuple[str, str]) -> list[tuple[str, str]]:
    """Whitelist-based sort parsing. Returns [(column, 'asc'|'desc'), ...]."""
    if not sort:
        return [fallback]
    parts: list[tuple[str, str]] = []
    for raw in sort.split(","):
        raw = raw.strip()
        if not raw:
            continue
        desc = raw.startswith("-")
        column = raw[1:] if desc else raw
        if column in allowed:
            parts.append((column, "desc" if desc else "asc"))
    return parts or [fallback]
