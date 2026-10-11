"""Query helpers, ported verbatim from backend_py/app/services/repo.py
(imports adjusted to app.core.db's session/Base.query)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import distinct, func, or_

from app.core.db import session
from app.models.auth_policy import AuthPolicy
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_role import UserRole
from app.models.user_role_factory import UserRoleFactory
from app.models.user_role_warehouse import UserRoleWarehouse
from app.models.warehouse import Warehouse


def find_user_by_email(tenant_id: uuid.UUID, email: str) -> User | None:
    return User.query.filter(User.tenant_id == tenant_id, User.email == email.lower()).first()


def find_role_by_name(tenant_id: uuid.UUID, name: str) -> Role | None:
    return Role.query.filter(Role.tenant_id == tenant_id, Role.name == name).first()


def permissions_for_role(role_id: uuid.UUID) -> list[str]:
    rows = RolePermission.query.filter(RolePermission.role_id == role_id).all()
    return [r.permission for r in rows]


def effective_access(user_id: uuid.UUID) -> dict:
    """Joins user_roles -> roles -> role_permissions, filtered by active status and
    the effective-date window, deduping permissions/scopes across all held roles."""
    today = date.today()
    rows = (
        session.query(UserRole, Role)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            UserRole.user_id == user_id,
            Role.status == "active",
            UserRole.effective_from <= today,
            or_(UserRole.effective_to.is_(None), UserRole.effective_to >= today),
        )
        .all()
    )

    roles: dict[uuid.UUID, str] = {}
    permissions: set[str] = set()
    scopes: set[str] = set()

    for user_role, role in rows:
        roles[role.id] = role.name
        for scope in user_role.scopes or []:
            scopes.add(scope)

    if roles:
        permissions.update(
            p
            for (p,) in session.query(RolePermission.permission)
            .filter(RolePermission.role_id.in_(list(roles)))
            .distinct()
            .all()
        )

    warehouse_ids, factory_ids = _effective_warehouse_factory_scope(user_id, list(roles))

    return {
        "roles": [{"id": str(rid), "name": name} for rid, name in roles.items()],
        "permissions": sorted(permissions),
        "scopes": sorted(scopes),
        "warehouseIds": warehouse_ids,
        "factoryIds": factory_ids,
    }


def _effective_warehouse_factory_scope(
    user_id: uuid.UUID, role_ids: list[uuid.UUID]
) -> tuple[list[str] | None, list[str] | None]:
    if not role_ids:
        return [], []

    assignment_factory_ids: dict[uuid.UUID, set[uuid.UUID]] = {rid: set() for rid in role_ids}
    for role_id, factory_id in (
        session.query(UserRoleFactory.role_id, UserRoleFactory.factory_id)
        .filter(UserRoleFactory.user_id == user_id, UserRoleFactory.role_id.in_(role_ids))
        .all()
    ):
        assignment_factory_ids[role_id].add(factory_id)

    assignment_warehouse_ids: dict[uuid.UUID, set[uuid.UUID]] = {rid: set() for rid in role_ids}
    for role_id, warehouse_id in (
        session.query(UserRoleWarehouse.role_id, UserRoleWarehouse.warehouse_id)
        .filter(UserRoleWarehouse.user_id == user_id, UserRoleWarehouse.role_id.in_(role_ids))
        .all()
    ):
        assignment_warehouse_ids[role_id].add(warehouse_id)

    if any(not assignment_factory_ids[rid] and not assignment_warehouse_ids[rid] for rid in role_ids):
        return None, None

    all_factory_ids: set[uuid.UUID] = set()
    all_warehouse_ids: set[uuid.UUID] = set()
    for rid in role_ids:
        all_factory_ids |= assignment_factory_ids[rid]
        all_warehouse_ids |= assignment_warehouse_ids[rid]

    if all_factory_ids:
        all_warehouse_ids |= {
            w.id for w in Warehouse.query.filter(Warehouse.factory_id.in_(all_factory_ids)).all()
        }

    return sorted(str(w) for w in all_warehouse_ids), sorted(str(f) for f in all_factory_ids)


def auth_policy(tenant_id: uuid.UUID) -> AuthPolicy:
    """Upserts a default policy row if one doesn't exist yet."""
    policy = session.get(AuthPolicy, tenant_id)
    if policy is None:
        policy = AuthPolicy(tenant_id=tenant_id)
        session.add(policy)
        session.flush()
    return policy


def count_users_with_permission(tenant_id: uuid.UUID, permission: str, exclude_user_id: uuid.UUID | None = None) -> int:
    """Exact match on `permission` or '*' only (not resource:* wildcards)."""
    today = date.today()
    query = (
        session.query(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .filter(
            User.tenant_id == tenant_id,
            User.status == "active",
            Role.status == "active",
            RolePermission.permission.in_([permission, "*"]),
            or_(UserRole.effective_to.is_(None), UserRole.effective_to >= today),
        )
        .distinct()
    )
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.count()


def count_active_admin_roles(tenant_id: uuid.UUID, exclude_role_id: uuid.UUID | None = None) -> int:
    """Roles holding '*' that are active - used for the 'last admin role' safety check."""
    query = (
        session.query(func.count(distinct(Role.id)))
        .join(RolePermission, RolePermission.role_id == Role.id)
        .filter(Role.tenant_id == tenant_id, Role.status == "active", RolePermission.permission == "*")
    )
    if exclude_role_id is not None:
        query = query.filter(Role.id != exclude_role_id)
    return query.scalar() or 0
