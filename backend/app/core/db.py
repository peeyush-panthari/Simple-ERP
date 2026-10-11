"""SQLAlchemy session plumbing.

This is the load-bearing decision of the whole port: we keep synchronous
SQLAlchemy (same `psycopg` driver, same query patterns, same explicit
`.with_for_update()` locking) instead of rewriting to async SQLAlchemy, and
we replicate Flask-SQLAlchemy's `Model.query` / `db.session` ergonomics with
a plain `scoped_session` + `query_property()` so every ported model/service
file needs only a two-line import change (`from app.extensions import db` +
`db.Model` -> `from app.core.db import Base` + `Base`), not a rewrite of
every query. See the migration plan for the full rationale.

Route handlers stay plain `def` (not `async def`), so FastAPI runs them via
`anyio.to_thread.run_sync` in a shared worker threadpool - NOT one thread
per request. Threads are reused across unrelated requests, which rules out
the "default scopefunc = thread ident" scoping Flask-SQLAlchemy gets away
with under a sync WSGI server (there, gunicorn really does give each
in-flight request its own OS thread/process). Scoping by thread ident here
would let two different requests that happen to land on the same pooled
thread share one one session/identity-map/transaction - and worse, a
middleware's own `SessionLocal.remove()` runs on the *event-loop* thread,
never the worker thread that actually touched the session, so nothing would
ever really get cleaned up.

Instead, `_request_scope` is a contextvar set once per request in
`SessionCleanupMiddleware`, before `call_next` dispatches into the
threadpool. anyio's `to_thread.run_sync` copies the current context
(`contextvars.copy_context()`) into the worker thread it runs the sync
handler in, so the same token is visible whichever thread ends up serving
that request - `scopefunc` keys the session on that token, and the
middleware's own `.remove()` (running back on the event loop, in the same
context it set the token in) reliably tears down that exact session.
Code that uses `SessionLocal`/`Base.query` outside of a request (scripts,
the bootstrap CLI, tests hitting the DB directly) falls back to thread
ident, which is correct for that single-threaded use.
"""

from __future__ import annotations

import contextvars
import threading
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_timeout=settings.db_pool_timeout_seconds,
)

_request_scope: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_scope", default=None)


def _scopefunc():
    token = _request_scope.get()
    return token if token is not None else threading.get_ident()


SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=True, autocommit=False), scopefunc=_scopefunc)


class Base(DeclarativeBase):
    query = SessionLocal.query_property()


# Ported code written against Flask-SQLAlchemy's `db.session`/`db.session.add`
# etc. keeps working unchanged against this proxy.
session = SessionLocal


def get_db():
    """FastAPI dependency for routes that want the session injected
    explicitly rather than through the `Base.query` / `session` globals -
    prefer this in new code; ported code may keep using `session` directly."""
    try:
        yield SessionLocal
    finally:
        pass  # cleanup is centralized in SessionCleanupMiddleware, not per-dependency


_request_end_hooks: list = []


def on_request_end(fn) -> None:
    """Register `fn(scope_token)`, called when a request finishes - for state kept per request (the
    equivalent of Flask's `g`). Keyed by the same token that scopes the DB session."""
    _request_end_hooks.append(fn)


def current_request_scope() -> str | None:
    """The token of the request being served, or None outside one (scripts, tests calling services directly)."""
    return _request_scope.get()


class SessionCleanupMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        token_value = uuid.uuid4().hex
        token = _request_scope.set(token_value)
        try:
            response = await call_next(request)
        finally:
            SessionLocal.remove()
            for hook in _request_end_hooks:
                hook(token_value)
            _request_scope.reset(token)
        return response
