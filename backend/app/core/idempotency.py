"""Idempotency-Key support for mutating endpoints.

Ported from backend_py/app/idempotency.py. The original wrapped a Flask view
function and read `request.get_data()` synchronously; FastAPI's `Request.body()`
is a coroutine, so the raw bytes are captured up front by the async
`get_raw_body` dependency and threaded into the (sync) route handler, which
calls `run_idempotent(...)` explicitly - same explicit opt-in shape as the
original's `with_idempotency(_do)()` call sites (this was never a global
middleware in the original either).
"""

from __future__ import annotations

import hashlib

from fastapi import Request

from app.core.db import session
from app.core.errors import conflict
from app.models.idempotency_key import IdempotencyKey


async def get_raw_body(request: Request) -> bytes:
    return await request.body()


def _request_hash(method: str, path: str, body: bytes) -> str:
    return hashlib.sha256(f"{method}:{path}:".encode("utf-8") + body).hexdigest()


def run_idempotent(key: str | None, method: str, path: str, raw_body: bytes, actor: dict | None, fn):
    """`fn()` returns `(status_code, body_dict)`. Returns the same tuple,
    either freshly computed or replayed from a prior identical request."""
    if not key or not actor:
        return fn()

    tenant_id = actor["tenant_id"]
    req_hash = _request_hash(method, path, raw_body)
    existing = session.get(IdempotencyKey, (tenant_id, key))
    if existing is not None:
        if existing.request_hash != req_hash:
            raise conflict("Idempotency-Key was reused with a different request body", code="IDEMPOTENCY_KEY_CONFLICT")
        return existing.response_status, existing.response_body

    status_code, body = fn()
    if body is not None:
        session.add(
            IdempotencyKey(
                tenant_id=tenant_id,
                key=key,
                method=method,
                route=path,
                request_hash=req_hash,
                response_status=status_code,
                response_body=body,
            )
        )
        session.commit()
    return status_code, body
