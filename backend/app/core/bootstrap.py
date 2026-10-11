"""First-boot bootstrap: default tenant, seeded system roles, first administrator.

Ported verbatim from backend_py/app/bootstrap.py (imports adjusted to
app.core.db / app.core.security / app.core.permissions). Idempotent - safe
to run on every startup. Invoked explicitly via `python -m app.core.bootstrap`
or the bootstrap CLI (see scripts/cli.py) - never automatically on
import, matching the original (bootstrap under gunicorn only runs via the
Flask CLI's `flask bootstrap`, never on worker boot).
"""

from __future__ import annotations

import logging
import secrets
import uuid

from app.core.config import settings
from app.core.db import session
from app.core.permissions import SYSTEM_ROLES
from app.core.security import hash_password
from app.models.auth_policy import AuthPolicy
from app.models.party_type import PartyType
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_role import UserRole

logger = logging.getLogger("axon.bootstrap")

DEFAULT_PARTY_TYPES = [
    ("raw_material_vendor", "Vendor - Raw Material", "vendor"),
    ("production_vendor", "Vendor - Production", "vendor"),
    ("customer", "Customer", "customer"),
]


def bootstrap_tenant() -> None:
    tenant_id = uuid.UUID(settings.default_tenant_id)

    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(
            id=tenant_id,
            name=settings.default_tenant_name,
            slug=settings.default_tenant_slug,
            country="IN",
            base_currency="INR",
        )
        session.add(tenant)
        session.flush()

    if session.get(AuthPolicy, tenant_id) is None:
        session.add(AuthPolicy(tenant_id=tenant_id))
        session.flush()

    for name, definition in SYSTEM_ROLES.items():
        role = Role.query.filter_by(tenant_id=tenant_id, name=name).first()
        if role is None:
            role = Role(
                tenant_id=tenant_id,
                name=name,
                description=definition["description"],
                is_system=True,
                status="active",
            )
            session.add(role)
            session.flush()
        else:
            role.description = definition["description"]

        RolePermission.query.filter_by(role_id=role.id).delete()
        for permission in definition["permissions"]:
            session.add(RolePermission(role_id=role.id, permission=permission))

    for code, label, base_type in DEFAULT_PARTY_TYPES:
        if PartyType.query.filter_by(tenant_id=tenant_id, code=code).first() is None:
            session.add(PartyType(tenant_id=tenant_id, code=code, label=label, base_type=base_type))

    session.flush()
    _ensure_first_administrator(tenant_id)
    session.commit()

    # The original seeds the built-in notification templates on every app
    # boot; here it rides along with bootstrap (same idempotent hash-based
    # upsert), so a fresh DB gets them from `python -m app.core.bootstrap`.
    from app.services.notification_templates import seed_templates

    seed_templates()
    logger.info("bootstrap complete: tenant=%s roles=%d party_types=%d", tenant_id, len(SYSTEM_ROLES), len(DEFAULT_PARTY_TYPES))


def _ensure_first_administrator(tenant_id: uuid.UUID) -> None:
    """Creates the first administrator only when the tenant has zero users."""
    existing_count = User.query.filter_by(tenant_id=tenant_id).count()
    if existing_count > 0:
        return

    email = settings.bootstrap_admin_email.strip().lower()
    generated = not settings.bootstrap_admin_password
    password = settings.bootstrap_admin_password or f"Axon!{secrets.token_urlsafe(9)}"

    admin_role = Role.query.filter_by(tenant_id=tenant_id, name="System Admin").first()
    if admin_role is None:
        logger.error("System Admin role missing - cannot create the first administrator")
        return

    user = User(
        tenant_id=tenant_id,
        email=email,
        display_name="Administrator",
        status="active",
        password_hash=hash_password(password),
        must_change_password=generated,
    )
    session.add(user)
    session.flush()

    session.add(UserRole(user_id=user.id, role_id=admin_role.id))

    if generated:
        logger.warning(
            "\n\n  First administrator created.\n    %s\n    %s\n\n"
            "  Change it at first sign-in. Set BOOTSTRAP_ADMIN_PASSWORD to choose your own.\n",
            email,
            password,
        )
    else:
        logger.info("first administrator created from BOOTSTRAP_ADMIN_PASSWORD: %s", email)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    bootstrap_tenant()
