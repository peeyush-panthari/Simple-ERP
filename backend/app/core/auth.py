"""Resolves the Bearer JWT into the current actor + permission-guard dependencies.

Ported from backend_py/app/auth_guard.py, adapted to FastAPI's dependency
injection instead of Flask's global `before_request` + decorators:

- Flask resolved `g.actor` for every request via a before_request hook, then
  exempted PUBLIC_PATHS/PUBLIC_PATH_PREFIX inside that hook. FastAPI has no
  request-scoped global equivalent, so instead: protected routers/routes take
  `actor: Actor = Depends(get_current_actor)`; public routes (login, refresh,
  logout, health, the public/* intake routes) simply don't. This means "is
  this route public" is declared at the route/router itself, not centrally -
  more idiomatic FastAPI, same effective behavior (verified per-domain as
  each router is ported, e.g. the public logistics intake router matches the
  original PUBLIC_PATH_PREFIX == "/api/v1/public/" carve-out).
- `require_permission(*perms)`/`require_any_permission(*perms)` were route
  decorators wrapping `current_actor()`; they're now dependency *factories*
  passed to `Depends(...)`, following the same "actor already resolved,
  permission checked against the flat string catalogue" logic.
"""

from __future__ import annotations

import uuid
from typing import Annotated, TypedDict

from fastapi import Depends, Header

from app.core.errors import forbidden, unauthorized
from app.core.permissions import permits_all, permits_any
from app.core.security import verify_access_token


class Actor(TypedDict):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str | None
    name: str | None
    roles: list[str]
    permissions: list[str]
    scopes: list[str]
    warehouse_ids: list[str] | None
    factory_ids: list[str] | None
    session_id: uuid.UUID | None


def get_current_actor(authorization: Annotated[str | None, Header()] = None) -> Actor:
    if not authorization or not authorization.startswith("Bearer "):
        raise unauthorized("Missing bearer token")
    token = authorization[len("Bearer ") :].strip()
    claims = verify_access_token(token)
    return {
        "user_id": uuid.UUID(claims["sub"]),
        "tenant_id": uuid.UUID(claims["tid"]),
        "email": claims.get("email"),
        "name": claims.get("name"),
        "roles": claims.get("roles", []),
        "permissions": claims.get("perms", []),
        "scopes": claims.get("scopes", []),
        "warehouse_ids": claims.get("whIds"),
        "factory_ids": claims.get("facIds"),
        "session_id": uuid.UUID(claims["sid"]) if claims.get("sid") else None,
    }


CurrentActor = Annotated[Actor, Depends(get_current_actor)]


def _flatten_perms(perms: tuple) -> list[str]:
    result = []
    for p in perms:
        if isinstance(p, (list, tuple, set)):
            result.extend(p)
        else:
            result.append(p)
    return result


def require_permission(*perms: str | list[str]):
    flat = _flatten_perms(perms)

    def _dependency(actor: CurrentActor) -> Actor:
        if not permits_all(actor["permissions"], flat):
            raise forbidden(f"Missing required permission: {', '.join(flat)}")
        return actor

    return _dependency


def require_any_permission(*perms: str | list[str]):
    flat = _flatten_perms(perms)

    def _dependency(actor: CurrentActor) -> Actor:
        if not permits_any(actor["permissions"], flat):
            raise forbidden(f"Missing one of required permissions: {', '.join(flat)}")
        return actor

    return _dependency
