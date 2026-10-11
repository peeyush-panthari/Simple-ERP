"""Wire-shape helpers, ported verbatim from backend_py/app/serializers.py."""

from __future__ import annotations

from app.models.user import User


def session_user(user: User, access: dict) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "displayName": user.display_name,
        "businessUnit": user.business_unit,
        "mfaEnabled": user.mfa_enabled,
        "roles": access["roles"],
        "permissions": access["permissions"],
        "scopes": access["scopes"],
        "warehouseIds": access["warehouseIds"],
        "factoryIds": access["factoryIds"],
    }


def me_response(user: User, access: dict) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "displayName": user.display_name,
        "businessUnit": user.business_unit,
        "status": user.status,
        "mfaEnabled": user.mfa_enabled,
        "mustChangePassword": user.must_change_password,
        "lastLoginAt": user.last_login_at.isoformat() if user.last_login_at else None,
        "roles": access["roles"],
        "permissions": access["permissions"],
        "scopes": access["scopes"],
        "warehouseIds": access["warehouseIds"],
        "factoryIds": access["factoryIds"],
    }


def user_summary(user: User, access: dict) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "displayName": user.display_name,
        "businessUnit": user.business_unit,
        "status": user.status,
        "mfaEnabled": user.mfa_enabled,
        "lastLoginAt": user.last_login_at.isoformat() if user.last_login_at else None,
        "roles": access["roles"],
    }


def user_detail(user: User, access: dict, role_assignments: list[dict]) -> dict:
    return {
        **user_summary(user, access),
        "phone": user.phone,
        "roleAssignments": role_assignments,
        "permissions": access["permissions"],
    }
