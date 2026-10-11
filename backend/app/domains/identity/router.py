"""Identity domain: auth (login/refresh/logout/me/change-password), users, roles.

Ported 1:1 (behavior) from backend_py/app/routes/auth.py + users.py + roles.py.
Route-by-route notes on what changed mechanically (not behaviorally) are in
each section below; anywhere the *behavior* itself is a preserved quirk from
the original, it's called out explicitly (see "PRESERVED QUIRK" comments) -
per the migration plan, quirks get carried over deliberately, not silently.

`notify_user_invited` calls notification_repo.send_notification directly
(in-process, like the original); a failed send is logged and never fails
user creation.
"""

from __future__ import annotations

import logging
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import or_

from app.core import security
from app.core.client_ip import client_ip
from app.core.rate_limit import LOGIN_LIMIT, limiter
from app.core.auth import Actor, CurrentActor, require_permission
from app.core.config import settings
from app.core.db import session
from app.core.errors import ProblemError, conflict, forbidden, not_found, rule_violation, unauthorized
from app.core.idempotency import get_raw_body, run_idempotent
from app.core.pagination import ListQuery, list_response, offset_of
from app.domains.identity import repo
from app.domains.identity.schemas import (
    AssignRolesBody,
    ChangePasswordBody,
    CreateUserBody,
    ForgotPasswordBody,
    LoginBody,
    LogoutBody,
    MfaConfirmBody,
    PatchUserBody,
    RefreshBody,
    ReplacePermissionsBody,
    ResetPasswordBody,
    RoleAssignment,
    RoleBody,
    RolePatchBody,
    AcceptInviteBody,
)
from app.domains.identity.serializers import me_response, session_user
from app.core.audit import audit, read_audit_trail
from app.core.permissions import ALL_PERMISSIONS, PERMISSIONS, can_grant
from app.models.factory import Factory
from app.models.password_history import PasswordHistory
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.tenant import Tenant
from app.models.user import User
from app.models.session import Session as SessionModel
from app.models.user_credentials import MfaRecoveryCode, PasswordResetToken, UserInvitation
from app.models.user_role import UserRole
from app.models.user_role_factory import UserRoleFactory
from app.models.user_role_warehouse import UserRoleWarehouse
from app.models.warehouse import Warehouse

logger = logging.getLogger("app.identity")

_DUMMY_HASH = "$argon2id$v=19$m=19456,t=2,p=1$c29tZXNhbHQ$0000000000000000000000000000000000000000000"

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/v1", tags=["users"])
roles_router = APIRouter(prefix="/api/v1", tags=["roles"])


def _client_ip(request: Request) -> str | None:
    return client_ip(request)


def _resolve_tenant(slug: str | None, fallback):
    if not slug:
        return fallback
    tenant = Tenant.query.filter_by(slug=slug, status="active").first()
    if tenant is None:
        raise unauthorized("Unknown tenant", code="TENANT_UNKNOWN")
    return tenant.id


def _record_attempt(tenant_id, email: str, ip: str | None, successful: bool, reason: str | None = None) -> None:
    from app.models.login_attempt import LoginAttempt

    session.add(LoginAttempt(tenant_id=tenant_id, email=email, ip=ip, successful=successful, reason=reason))
    session.commit()


# ============================================================================
# auth
# ============================================================================


def _complete_login(user: User, tenant_id, email: str, request: Request, now: datetime, *, reason: str | None = None) -> dict:
    """Everything after the credentials were accepted - password login and SSO exchange share it:
    require an active role, open the session, and mint this app's own access/refresh tokens."""
    access = repo.effective_access(user.id)
    if not access["permissions"]:
        raise forbidden(
            "No active role is assigned to this account — ask an administrator to assign one",
            code="NO_ROLE_ASSIGNED",
        )

    ip = _client_ip(request)
    raw_refresh, new_session = security.create_session(
        user_id=user.id, tenant_id=tenant_id, ip=ip, user_agent=request.headers.get("User-Agent")
    )
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    session.commit()
    _record_attempt(tenant_id, email, ip, True, reason)

    access_token = security.sign_access_token(
        user_id=user.id,
        tenant_id=tenant_id,
        email=user.email,
        name=user.display_name,
        roles=[r["name"] for r in access["roles"]],
        permissions=access["permissions"],
        scopes=access["scopes"],
        warehouse_ids=access["warehouseIds"],
        factory_ids=access["factoryIds"],
        session_id=new_session.id,
    )

    return {
        "accessToken": access_token,
        "refreshToken": raw_refresh,
        "tokenType": "Bearer",
        "expiresIn": settings.access_token_ttl,
        "mustChangePassword": user.must_change_password,
        "user": session_user(user, access),
    }


@auth_router.post("/login")
@limiter.limit(LOGIN_LIMIT)
def login(body: LoginBody, request: Request):
    default_tenant_id = uuid_mod.UUID(settings.default_tenant_id)
    tenant_id = _resolve_tenant(body.tenantSlug, default_tenant_id)
    policy = repo.auth_policy(tenant_id)
    session.commit()
    user = repo.find_user_by_email(tenant_id, body.email)
    ip = _client_ip(request)

    if not user or not user.password_hash:
        security.verify_password(body.password, _DUMMY_HASH)
        _record_attempt(tenant_id, body.email, ip, False, "unknown_user")
        raise unauthorized("Email or password is incorrect", code="INVALID_CREDENTIALS")

    now = datetime.now(timezone.utc)

    if user.locked_until and user.locked_until > now:
        _record_attempt(tenant_id, body.email, ip, False, "locked")
        raise ProblemError(
            403,
            "Forbidden",
            detail=f"Account is locked until {user.locked_until.isoformat()} after too many failed attempts",
            code="ACCOUNT_LOCKED",
            meta={"lockedUntil": user.locked_until.isoformat()},
        )

    if user.status != "active":
        _record_attempt(tenant_id, body.email, ip, False, f"status_{user.status}")
        raise forbidden(f"This account is {user.status}", code="ACCOUNT_NOT_ACTIVE")

    if not security.verify_password(body.password, user.password_hash):
        attempts = user.failed_attempts + 1
        lock = attempts >= policy.max_failed_attempts
        user.failed_attempts = attempts
        user.locked_until = now + timedelta(minutes=policy.lockout_minutes) if lock else None
        session.commit()
        _record_attempt(tenant_id, body.email, ip, False, "bad_password")
        if lock:
            raise forbidden(
                f"Too many failed attempts — the account is locked for {policy.lockout_minutes} minutes",
                code="ACCOUNT_LOCKED",
            )
        raise unauthorized("Email or password is incorrect", code="INVALID_CREDENTIALS")

    mfa_required = user.mfa_enabled or policy.mfa_required
    if mfa_required:
        if not user.mfa_secret:
            raise rule_violation(
                "Multi-factor authentication is required but not yet enrolled for this account",
                code="MFA_ENROLLMENT_REQUIRED",
            )
        if body.mfaRecoveryCode:
            cleaned_code = body.mfaRecoveryCode.strip().upper().replace("-", "").replace(" ", "")
            code_hash = security.hash_token(cleaned_code)
            rec_code = MfaRecoveryCode.query.filter_by(
                user_id=user.id,
                code_hash=code_hash,
                used_at=None,
            ).first()
            if not rec_code:
                _record_attempt(tenant_id, body.email, ip, False, "mfa_recovery_invalid")
                raise unauthorized("The recovery code is invalid or has already been used", code="MFA_RECOVERY_CODE_INVALID")
            rec_code.used_at = now
            audit(
                tenant_id=tenant_id,
                actor_id=user.id,
                actor_email=user.email,
                action="user.mfa.recovery_code_used",
                entity_type="user",
                entity_id=str(user.id),
                meta={"ip": ip},
            )
            session.commit()
        elif body.mfaCode:
            if not security.verify_totp(user.mfa_secret, body.mfaCode):
                _record_attempt(tenant_id, body.email, ip, False, "mfa_invalid")
                raise unauthorized("The authentication code is incorrect or expired", code="MFA_CODE_INVALID")
        else:
            _record_attempt(tenant_id, body.email, ip, False, "mfa_required")
            # PRESERVED QUIRK (auth.py:127-138 original): returned as a raw
            # inline 401 body rather than through ProblemError/rule_violation
            # - same shape either way, kept literal for fidelity.
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=401,
                media_type="application/problem+json",
                content={
                    "type": "https://errors.axon-erp.dev/mfa-required",
                    "title": "MFA required",
                    "status": 401,
                    "detail": "Provide the 6-digit code from your authenticator app or an emergency recovery code",
                    "code": "MFA_REQUIRED",
                },
            )

    return _complete_login(user, tenant_id, body.email, request, now)





@auth_router.post("/refresh")
def refresh(body: RefreshBody, request: Request):
    new_raw, new_session = security.rotate_session(
        body.refreshToken, ip=_client_ip(request), user_agent=request.headers.get("User-Agent")
    )

    user = session.get(User, new_session.user_id)
    if not user or user.status != "active":
        # Matches the original: the rotation itself is still persisted even
        # though the caller gets rejected - an inactive account still burns
        # its old refresh token.
        session.commit()
        raise forbidden("Account is no longer active", code="ACCOUNT_NOT_ACTIVE")

    access = repo.effective_access(user.id)
    session.commit()

    access_token = security.sign_access_token(
        user_id=user.id,
        tenant_id=new_session.tenant_id,
        email=user.email,
        name=user.display_name,
        roles=[r["name"] for r in access["roles"]],
        permissions=access["permissions"],
        scopes=access["scopes"],
        warehouse_ids=access["warehouseIds"],
        factory_ids=access["factoryIds"],
        session_id=new_session.id,
    )

    return {
        "accessToken": access_token,
        "refreshToken": new_raw,
        "tokenType": "Bearer",
        "expiresIn": settings.access_token_ttl,
    }


@auth_router.post("/logout", status_code=204)
def logout(body: LogoutBody):
    # PRESERVED QUIRK: /auth/logout is a public path in the original app
    # (auth_guard.PUBLIC_PATHS), so the actor is never resolved here even if
    # a bearer token is sent - the "revoke every session for the current
    # actor" branch only ever fires via an explicit refreshToken, matching
    # that. A bearer-token-only logout (no body) is a real, pre-existing gap
    # in the original app, carried over rather than quietly fixed.
    if body.refreshToken:
        security.revoke_session_by_refresh_token(body.refreshToken)
    session.commit()
    return Response(status_code=204)


@auth_router.get("/me")
def me(actor: CurrentActor):
    user = session.get(User, actor["user_id"])
    if not user:
        raise unauthorized()
    access = repo.effective_access(user.id)
    return me_response(user, access)


@auth_router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordBody, actor: CurrentActor):
    user = session.get(User, actor["user_id"])
    if not user or not user.password_hash:
        raise unauthorized()

    if not security.verify_password(body.currentPassword, user.password_hash):
        raise unauthorized("Current password is incorrect", code="INVALID_CREDENTIALS")

    policy = repo.auth_policy(actor["tenant_id"])
    security.assert_password_meets_policy(body.newPassword, policy, user.email)

    history = (
        PasswordHistory.query.filter_by(user_id=user.id)
        .order_by(PasswordHistory.changed_at.desc())
        .limit(policy.password_history)
        .all()
    )
    for h in history:
        if security.verify_password(body.newPassword, h.password_hash):
            raise conflict(f"You cannot reuse any of your last {policy.password_history} passwords", code="PASSWORD_REUSED")

    session.add(PasswordHistory(user_id=user.id, password_hash=user.password_hash))
    user.password_hash = security.hash_password(body.newPassword)
    user.password_changed_at = datetime.now(timezone.utc)
    user.must_change_password = False
    security.revoke_all_sessions_for_user(user.id)
    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="password.changed",
        entity_type="user",
        entity_id=str(user.id),
    )
    session.commit()
    return Response(status_code=204)


@auth_router.post("/forgot-password")
@limiter.limit(LOGIN_LIMIT)
def forgot_password(body: ForgotPasswordBody, request: Request):
    """Requests a password reset token for the given email. Always returns 200 to prevent email enumeration."""
    default_tenant_id = uuid_mod.UUID(settings.default_tenant_id)
    tenant_id = _resolve_tenant(body.tenantSlug, default_tenant_id)
    user = repo.find_user_by_email(tenant_id, body.email)
    ip = _client_ip(request)

    if user and user.status == "active":
        raw_token = security.random_token(24)
        token_hash = security.hash_token(raw_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=1)

        # Invalidate any existing unused reset tokens for this user
        PasswordResetToken.query.filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None)
        ).update({"used_at": now}, synchronize_session=False)

        reset_record = PasswordResetToken(
            tenant_id=tenant_id,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip=ip,
        )
        session.add(reset_record)
        session.commit()

        from app.services import notification_repo
        try:
            notification_repo.send_notification(
                tenant_id,
                template="user.password_reset",
                to=[user.email],
                data={"displayName": user.display_name, "resetToken": raw_token},
            )
        except Exception:
            logger.exception("Failed to send password reset email to %s", user.email)

        audit(
            tenant_id=tenant_id,
            actor_id=user.id,
            actor_email=user.email,
            action="password.reset_requested",
            entity_type="user",
            entity_id=str(user.id),
            meta={"ip": ip},
        )
        session.commit()

    return {"message": "If an account with that email exists, a password reset email has been sent."}


@auth_router.post("/reset-password")
@limiter.limit(LOGIN_LIMIT)
def reset_password(body: ResetPasswordBody, request: Request):
    """Resets user password using a valid, unexpired reset token."""
    token_hash = security.hash_token(body.token)
    reset_record = PasswordResetToken.query.filter_by(token_hash=token_hash).first()

    now = datetime.now(timezone.utc)
    if not reset_record or reset_record.used_at is not None or reset_record.expires_at < now:
        raise rule_violation("The password reset token is invalid or has expired", code="INVALID_RESET_TOKEN")

    user = User.query.filter_by(tenant_id=reset_record.tenant_id, id=reset_record.user_id).first()
    if not user or user.status != "active":
        raise rule_violation("Account is not active or no longer exists", code="ACCOUNT_NOT_ACTIVE")

    policy = repo.auth_policy(reset_record.tenant_id)
    security.assert_password_meets_policy(body.newPassword, policy, user.email)

    # Check password history
    history = (
        PasswordHistory.query.filter_by(user_id=user.id)
        .order_by(PasswordHistory.changed_at.desc())
        .limit(policy.password_history)
        .all()
    )
    for h in history:
        if security.verify_password(body.newPassword, h.password_hash):
            raise conflict(f"You cannot reuse any of your last {policy.password_history} passwords", code="PASSWORD_REUSED")

    if user.password_hash:
        session.add(PasswordHistory(user_id=user.id, password_hash=user.password_hash))

    user.password_hash = security.hash_password(body.newPassword)
    user.password_changed_at = now
    user.must_change_password = False
    user.failed_attempts = 0
    user.locked_until = None

    reset_record.used_at = now
    security.revoke_all_sessions_for_user(user.id)

    audit(
        tenant_id=reset_record.tenant_id,
        actor_id=user.id,
        actor_email=user.email,
        action="password.reset_completed",
        entity_type="user",
        entity_id=str(user.id),
        meta={"ip": _client_ip(request)},
    )
    session.commit()
    return {"message": "Password has been successfully reset. You may now sign in."}


@auth_router.post("/accept-invite")
@limiter.limit(LOGIN_LIMIT)
def accept_invite(body: AcceptInviteBody, request: Request):
    """Sets initial password, optional display name, and activates an invited user account."""
    token_hash = security.hash_token(body.token)
    invitation = UserInvitation.query.filter_by(token_hash=token_hash).first()

    now = datetime.now(timezone.utc)
    if not invitation or invitation.accepted_at is not None or invitation.expires_at < now:
        raise rule_violation("The invitation token is invalid or has expired", code="INVALID_INVITE_TOKEN")

    user = User.query.filter_by(tenant_id=invitation.tenant_id, id=invitation.user_id).first()
    if not user:
        raise not_found("User")
    if user.status not in ("invited", "active"):
        raise rule_violation(f"Account is {user.status} and cannot accept an invitation", code="ACCOUNT_NOT_INVITED")

    policy = repo.auth_policy(invitation.tenant_id)
    security.assert_password_meets_policy(body.password, policy, user.email)

    user.password_hash = security.hash_password(body.password)
    user.password_changed_at = now
    user.status = "active"
    user.must_change_password = False
    if body.displayName:
        user.display_name = body.displayName

    invitation.accepted_at = now

    audit(
        tenant_id=invitation.tenant_id,
        actor_id=user.id,
        actor_email=user.email,
        action="user.invite_accepted",
        entity_type="user",
        entity_id=str(user.id),
        meta={"ip": _client_ip(request)},
    )
    session.commit()

    return _complete_login(user, invitation.tenant_id, user.email, request, now, reason="invite_accepted")


def _device_info(ua_string: str | None) -> str:
    if not ua_string:
        return "Unknown device"
    ua = ua_string.lower()
    os = "Unknown OS"
    if "macintosh" in ua or "mac os" in ua:
        os = "macOS"
    elif "windows" in ua:
        os = "Windows"
    elif "linux" in ua:
        os = "Linux"
    elif "android" in ua:
        os = "Android"
    elif "iphone" in ua or "ipad" in ua:
        os = "iOS"

    browser = "Browser"
    if "edg" in ua:
        browser = "Edge"
    elif "chrome" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "postman" in ua:
        browser = "Postman"
    elif "curl" in ua:
        browser = "cURL"

    return f"{browser} on {os}"


@auth_router.get("/sessions")
def list_my_sessions(actor: CurrentActor):
    """Lists all active sessions for the current authenticated user."""
    now = datetime.now(timezone.utc)
    sessions = (
        SessionModel.query.filter(
            SessionModel.user_id == actor["user_id"],
            SessionModel.revoked_at.is_(None),
            SessionModel.expires_at > now,
        )
        .order_by(SessionModel.issued_at.desc())
        .all()
    )
    current_sid = actor["session_id"]
    return {
        "sessions": [
            {
                "id": str(s.id),
                "ip": s.ip,
                "userAgent": s.user_agent,
                "device": _device_info(s.user_agent),
                "issuedAt": s.issued_at.isoformat() if s.issued_at else None,
                "expiresAt": s.expires_at.isoformat() if s.expires_at else None,
                "isCurrent": bool(current_sid and s.id == current_sid),
            }
            for s in sessions
        ]
    }


@auth_router.delete("/sessions/other")
def revoke_other_sessions(actor: CurrentActor):
    """Terminates all active sessions for the current user except the current session."""
    now = datetime.now(timezone.utc)
    current_sid = actor["session_id"]
    q = SessionModel.query.filter(
        SessionModel.user_id == actor["user_id"],
        SessionModel.revoked_at.is_(None),
    )
    if current_sid:
        q = q.filter(SessionModel.id != current_sid)

    revoked_count = q.update({"revoked_at": now}, synchronize_session=False)
    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="sessions.other_revoked",
        entity_type="user",
        entity_id=str(actor["user_id"]),
        meta={"revokedCount": revoked_count},
    )
    session.commit()
    return {"revokedCount": revoked_count, "message": f"Logged out of {revoked_count} other device(s)"}


@auth_router.delete("/sessions/{session_id}", status_code=204)
def revoke_my_session(session_id: uuid_mod.UUID, actor: CurrentActor):
    """Terminates a specific session belonging to the caller."""
    sess = SessionModel.query.filter_by(user_id=actor["user_id"], id=session_id).first()
    if sess and sess.revoked_at is None:
        sess.revoked_at = datetime.now(timezone.utc)
        audit(
            tenant_id=actor["tenant_id"],
            actor_id=actor["user_id"],
            actor_email=actor["email"],
            action="session.revoked",
            entity_type="session",
            entity_id=str(session_id),
        )
        session.commit()
    return Response(status_code=204)


# ============================================================================
# users
# ============================================================================


def _assert_scope_grantable(tenant_id, actor: Actor, assignment: RoleAssignment, role_name: str) -> None:
    if assignment.warehouseIds:
        found = {
            w.id
            for w in Warehouse.query.filter(Warehouse.tenant_id == tenant_id, Warehouse.id.in_(assignment.warehouseIds)).all()
        }
        if any(wid not in found for wid in assignment.warehouseIds):
            raise not_found("Warehouse", code="NOT_FOUND")
        granter_warehouse_ids = actor["warehouse_ids"]
        if granter_warehouse_ids is not None:
            out_of_scope = [str(wid) for wid in assignment.warehouseIds if str(wid) not in granter_warehouse_ids]
            if out_of_scope:
                raise rule_violation(
                    f'You cannot grant "{role_name}" for warehouses outside your own scope: {", ".join(out_of_scope)}',
                    code="LEAST_PRIVILEGE_VIOLATION",
                )

    if assignment.factoryIds:
        found = {
            f.id for f in Factory.query.filter(Factory.tenant_id == tenant_id, Factory.id.in_(assignment.factoryIds)).all()
        }
        if any(fid not in found for fid in assignment.factoryIds):
            raise not_found("Factory", code="NOT_FOUND")
        granter_factory_ids = actor["factory_ids"]
        if granter_factory_ids is not None:
            out_of_scope = [str(fid) for fid in assignment.factoryIds if str(fid) not in granter_factory_ids]
            if out_of_scope:
                raise rule_violation(
                    f'You cannot grant "{role_name}" for factories outside your own scope: {", ".join(out_of_scope)}',
                    code="LEAST_PRIVILEGE_VIOLATION",
                )


def _assert_roles_grantable(tenant_id, actor: Actor, assignments: list[RoleAssignment]) -> None:
    granter_permissions = actor["permissions"]
    for assignment in assignments:
        role = Role.query.filter_by(tenant_id=tenant_id, id=assignment.roleId).first()
        if role is None:
            raise not_found("Role", code="NOT_FOUND")
        if role.status != "active":
            raise rule_violation(f'Role "{role.name}" is suspended and cannot be assigned', code="ROLE_SUSPENDED")
        perms = repo.permissions_for_role(role.id)
        missing = [p for p in perms if "*" not in granter_permissions and p not in granter_permissions]
        if missing:
            raise rule_violation(
                f'You cannot assign "{role.name}" because it grants permissions you do not hold: {", ".join(missing)}',
                code="LEAST_PRIVILEGE_VIOLATION",
            )
        _assert_scope_grantable(tenant_id, actor, assignment, role.name)


def _add_scope_rows(user_id: uuid_mod.UUID, assignment: RoleAssignment) -> None:
    for warehouse_id in assignment.warehouseIds:
        session.add(UserRoleWarehouse(user_id=user_id, role_id=assignment.roleId, warehouse_id=warehouse_id))
    for factory_id in assignment.factoryIds:
        session.add(UserRoleFactory(user_id=user_id, role_id=assignment.roleId, factory_id=factory_id))


def _role_names_for_user(user_id: uuid_mod.UUID) -> list[str]:
    rows = (
        session.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .distinct()
        .all()
    )
    return sorted(r[0] for r in rows)


def _notify_user_invited(*, tenant_id, email: str, display_name: str, invite_token: str | None) -> None:
    from app.services import notification_repo

    try:
        notification_repo.send_notification(
            tenant_id,
            template="user.invitation",
            to=[email],
            data={"displayName": display_name, "inviteToken": invite_token},
        )
        session.commit()
    except Exception:
        logger.exception("Failed to send invite email to %s", email)


def _validated_manager_id(tenant_id, user_id, manager_id):
    """The manager must be another active user of this tenant, and never someone who (directly or further up) reports to
    the person being edited - a loop would leave nobody to approve anything."""
    if manager_id is None:
        return None
    if user_id is not None and manager_id == user_id:
        raise rule_violation("A person cannot be their own manager", code="MANAGER_SELF")
    manager = User.query.filter_by(tenant_id=tenant_id, id=manager_id).first()
    if not manager:
        raise rule_violation(f"Manager {manager_id} does not exist", code="MANAGER_NOT_FOUND")
    if manager.status != "active":
        raise rule_violation(f"{manager.display_name} is {manager.status} - choose an active user as manager", code="MANAGER_NOT_ACTIVE")
    seen, current = set(), manager
    levels = 0
    while current is not None and current.id not in seen:
        if levels >= 20:
            raise rule_violation("Manager hierarchy is too deep (exceeds 20 levels)", code="MANAGER_HIERARCHY_TOO_DEEP")
        if user_id is not None and current.manager_id == user_id:
            raise rule_violation(f"{manager.display_name} already reports to this person, so they cannot be their manager", code="MANAGER_LOOP")
        seen.add(current.id)
        current = User.query.filter_by(tenant_id=tenant_id, id=current.manager_id).first() if current.manager_id else None
        levels += 1
    return manager_id


def _manager_names(users) -> dict:
    ids = {u.manager_id for u in users if u.manager_id}
    if not ids:
        return {}
    return {u.id: u.display_name for u in User.query.filter(User.id.in_(ids)).all()}


@users_router.get("/users")
def list_users(
    actor: Actor = Depends(require_permission("user:read")),
    query: ListQuery = Depends(),
    status: str | None = None,
    roleId: uuid_mod.UUID | None = None,
    businessUnit: str | None = None,
):
    q = User.query.filter(User.tenant_id == actor["tenant_id"])
    if status:
        q = q.filter(User.status == status)
    if businessUnit:
        q = q.filter(User.business_unit == businessUnit)
    if roleId:
        q = q.filter(User.id.in_(session.query(UserRole.user_id).filter(UserRole.role_id == roleId)))
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(User.display_name.ilike(like), User.email.ilike(like)))

    total = q.count()
    sort_col = {
        "display_name": User.display_name,
        "email": User.email,
        "created_at": User.created_at,
        "last_login_at": User.last_login_at,
        "status": User.status,
    }.get((query.sort or "").lstrip("-"), User.display_name)
    order = sort_col.desc() if (query.sort or "").startswith("-") else sort_col.asc()

    users = q.order_by(order).limit(query.limit).offset(offset_of(query)).all()
    manager_names = _manager_names(users)

    data = [
        {
            "id": str(u.id),
            "email": u.email,
            "displayName": u.display_name,
            "businessUnit": u.business_unit,
            "managerId": str(u.manager_id) if u.manager_id else None,
            "managerName": manager_names.get(u.manager_id),
            "status": u.status,
            "mfaEnabled": u.mfa_enabled,
            "roles": _role_names_for_user(u.id),
            "lastLoginAt": u.last_login_at.isoformat() if u.last_login_at else None,
            "createdAt": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]
    return list_response(data, query, total)


@users_router.get("/users/{id}")
def get_user(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("user:read"))):
    user = User.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not user:
        raise not_found("User")
    access = repo.effective_access(id)
    assignments = (
        session.query(UserRole, Role.name)
        .join(Role, Role.id == UserRole.role_id)
        .filter(UserRole.user_id == id)
        .all()
    )
    warehouse_ids_by_role: dict[uuid_mod.UUID, list[str]] = {}
    for role_id, warehouse_id in (
        session.query(UserRoleWarehouse.role_id, UserRoleWarehouse.warehouse_id).filter(UserRoleWarehouse.user_id == id).all()
    ):
        warehouse_ids_by_role.setdefault(role_id, []).append(str(warehouse_id))
    factory_ids_by_role: dict[uuid_mod.UUID, list[str]] = {}
    for role_id, factory_id in (
        session.query(UserRoleFactory.role_id, UserRoleFactory.factory_id).filter(UserRoleFactory.user_id == id).all()
    ):
        factory_ids_by_role.setdefault(role_id, []).append(str(factory_id))

    return {
        "id": str(user.id),
        "email": user.email,
        "displayName": user.display_name,
        "businessUnit": user.business_unit,
        "managerId": str(user.manager_id) if user.manager_id else None,
        "managerName": _manager_names([user]).get(user.manager_id),
        "phone": user.phone,
        "status": user.status,
        "mfaEnabled": user.mfa_enabled,
        "mustChangePassword": user.must_change_password,
        "lastLoginAt": user.last_login_at.isoformat() if user.last_login_at else None,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
        "roleAssignments": [
            {
                "roleId": str(ur.role_id),
                "roleName": name,
                "effectiveFrom": ur.effective_from.isoformat() if ur.effective_from else None,
                "effectiveTo": ur.effective_to.isoformat() if ur.effective_to else None,
                "scopes": ur.scopes,
                "warehouseIds": warehouse_ids_by_role.get(ur.role_id, []),
                "factoryIds": factory_ids_by_role.get(ur.role_id, []),
            }
            for ur, name in assignments
        ],
        "permissions": access["permissions"],
    }


@users_router.post("/users", status_code=201)
def create_user(
    body: CreateUserBody,
    request: Request,
    raw_body: bytes = Depends(get_raw_body),
    actor: Actor = Depends(require_permission("user:write")),
    idempotency_key: str | None = None,
):
    def _do():
        tenant_id = actor["tenant_id"]
        policy = repo.auth_policy(tenant_id)
        if body.password:
            security.assert_password_meets_policy(body.password, policy, body.email)
        _assert_roles_grantable(tenant_id, actor, body.roles)

        if User.query.filter_by(tenant_id=tenant_id, email=body.email).first():
            raise conflict(f"A user with email {body.email} already exists", code="EMAIL_TAKEN")

        password_hash = security.hash_password(body.password) if body.password else None
        invite_token = security.random_token(18) if not body.password else None

        user = User(
            tenant_id=tenant_id,
            email=body.email,
            display_name=body.displayName,
            business_unit=body.businessUnit,
            manager_id=_validated_manager_id(tenant_id, None, body.managerId),
            phone=body.phone,
            password_hash=password_hash,
            status=body.status,
            must_change_password=bool(body.password),
        )
        session.add(user)
        session.flush()

        today = date.today()
        for r in body.roles:
            session.add(
                UserRole(
                    user_id=user.id,
                    role_id=r.roleId,
                    effective_from=r.effectiveFrom or today,
                    effective_to=r.effectiveTo,
                    scopes=r.scopes,
                    assigned_by=actor["user_id"],
                )
            )
            _add_scope_rows(user.id, r)

        if invite_token:
            token_hash = security.hash_token(invite_token)
            expires_at = datetime.now(timezone.utc) + timedelta(days=2)
            session.add(
                UserInvitation(
                    tenant_id=tenant_id,
                    user_id=user.id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                )
            )

        audit(
            tenant_id=tenant_id,
            actor_id=actor["user_id"],
            actor_email=actor["email"],
            action="user.created",
            entity_type="user",
            entity_id=str(user.id),
            meta={"after": {"email": body.email, "displayName": body.displayName, "status": body.status}},
        )
        session.commit()

        if invite_token:
            _notify_user_invited(tenant_id=tenant_id, email=body.email, display_name=body.displayName, invite_token=invite_token)

        return 201, {"id": str(user.id), "email": body.email, "displayName": body.displayName, "status": body.status}

    from fastapi.responses import JSONResponse

    status_code, response_body = run_idempotent(
        request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do
    )
    return JSONResponse(status_code=status_code, content=response_body)


@users_router.post("/users/{id}/resend-invite")
def resend_invite(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("user:write"))):
    user = User.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not user:
        raise not_found("User")
    if user.status != "invited":
        raise rule_violation("Only users with status 'invited' can be resent an invitation", code="USER_NOT_INVITED")

    now = datetime.now(timezone.utc)
    UserInvitation.query.filter(
        UserInvitation.user_id == user.id,
        UserInvitation.accepted_at.is_(None)
    ).update({"expires_at": now}, synchronize_session=False)

    invite_token = security.random_token(18)
    token_hash = security.hash_token(invite_token)
    expires_at = now + timedelta(days=2)

    session.add(
        UserInvitation(
            tenant_id=actor["tenant_id"],
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )

    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="user.invite_resent",
        entity_type="user",
        entity_id=str(user.id),
    )
    session.commit()

    _notify_user_invited(tenant_id=actor["tenant_id"], email=user.email, display_name=user.display_name, invite_token=invite_token)

    return {"message": "Invitation resent successfully"}


@users_router.patch("/users/{id}")
def patch_user(id: uuid_mod.UUID, body: PatchUserBody, actor: Actor = Depends(require_permission("user:write"))):
    user = User.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not user:
        raise not_found("User")

    if body.status and body.status != "active" and user.status == "active":
        remaining = repo.count_users_with_permission(actor["tenant_id"], "system:admin", exclude_user_id=id)
        is_admin = "*" in repo.effective_access(id)["permissions"]
        if is_admin and remaining == 0:
            raise rule_violation(
                "This is the last active administrator — assign another admin before deactivating",
                code="LAST_ADMIN_USER",
            )

    before = {"status": user.status, "displayName": user.display_name}

    if body.displayName is not None:
        user.display_name = body.displayName
    if "businessUnit" in body.model_fields_set:
        user.business_unit = body.businessUnit
    if "managerId" in body.model_fields_set:
        before["managerId"] = str(user.manager_id) if user.manager_id else None
        user.manager_id = _validated_manager_id(actor["tenant_id"], id, body.managerId)
    if "phone" in body.model_fields_set:
        user.phone = body.phone
    if body.status is not None:
        user.status = body.status
    if body.mfaEnabled is not None:
        user.mfa_enabled = body.mfaEnabled

    if body.status and body.status != "active":
        security.revoke_all_sessions_for_user(id)

    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="user.updated",
        entity_type="user",
        entity_id=str(id),
        reason=body.reason,
        meta={"before": before, "after": body.model_dump(exclude_none=True, mode="json")},
    )

    session.commit()
    return {"id": str(user.id), "email": user.email, "displayName": user.display_name, "status": user.status}


@users_router.patch("/users/{id}/roles")
def assign_roles(id: uuid_mod.UUID, body: AssignRolesBody, actor: Actor = Depends(require_permission("role:assign"))):
    user = User.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not user:
        raise not_found("User")
    if user.status == "deactivated":
        raise rule_violation("Deactivated users cannot be assigned roles or operational records", code="USER_DEACTIVATED")

    _assert_roles_grantable(actor["tenant_id"], actor, body.roles)

    if body.mode == "replace":
        UserRoleWarehouse.query.filter_by(user_id=id).delete()
        UserRoleFactory.query.filter_by(user_id=id).delete()
        UserRole.query.filter_by(user_id=id).delete()
        session.flush()

    today = date.today()
    for r in body.roles:
        existing = UserRole.query.filter_by(user_id=id, role_id=r.roleId).first()
        if existing:
            existing.effective_from = r.effectiveFrom or today
            existing.effective_to = r.effectiveTo
            existing.scopes = r.scopes
            existing.assigned_by = actor["user_id"]
            existing.assigned_at = datetime.now(timezone.utc)
            UserRoleWarehouse.query.filter_by(user_id=id, role_id=r.roleId).delete()
            UserRoleFactory.query.filter_by(user_id=id, role_id=r.roleId).delete()
        else:
            session.add(
                UserRole(
                    user_id=id,
                    role_id=r.roleId,
                    effective_from=r.effectiveFrom or today,
                    effective_to=r.effectiveTo,
                    scopes=r.scopes,
                    assigned_by=actor["user_id"],
                )
            )
        _add_scope_rows(id, r)

    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="user.roles.assigned",
        entity_type="user",
        entity_id=str(id),
    )
    security.revoke_all_sessions_for_user(id)
    session.commit()

    access = repo.effective_access(id)
    return {"id": str(id), "roles": access["roles"], "permissions": access["permissions"]}


@users_router.post("/users/{id}/mfa/enrol")
def mfa_enrol(id: uuid_mod.UUID, actor: CurrentActor):
    if actor["user_id"] != id and "*" not in actor["permissions"]:
        raise rule_violation("You may only enrol MFA for your own account", code="MFA_SELF_ONLY")
    user = User.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not user:
        raise not_found("User")
    secret = security.generate_totp_secret()
    user.mfa_secret = secret
    session.commit()
    return {"secret": secret, "otpauthUrl": security.build_otpauth_url(secret, user.email)}


@users_router.post("/users/{id}/mfa/confirm")
def mfa_confirm(id: uuid_mod.UUID, body: MfaConfirmBody, actor: CurrentActor):
    user = User.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not user or not user.mfa_secret:
        raise rule_violation("Start MFA enrolment before confirming", code="MFA_NOT_STARTED")
    if not security.verify_totp(user.mfa_secret, body.code):
        raise rule_violation("That code did not match — check your authenticator app clock", code="MFA_CODE_INVALID")

    user.mfa_enabled = True
    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="user.mfa.enabled",
        entity_type="user",
        entity_id=str(id),
    )
    session.commit()
    return {"id": str(id), "mfaEnabled": True}


@users_router.post("/users/{id}/mfa/generate-recovery-codes")
def generate_recovery_codes(id: uuid_mod.UUID, actor: CurrentActor):
    if actor["user_id"] != id and "*" not in actor["permissions"]:
        raise rule_violation("You may only generate recovery codes for your own account", code="MFA_SELF_ONLY")
    user = User.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not user:
        raise not_found("User")
    if not user.mfa_enabled:
        raise rule_violation("Enable multi-factor authentication before generating recovery codes", code="MFA_NOT_ENABLED")

    now = datetime.now(timezone.utc)
    MfaRecoveryCode.query.filter(
        MfaRecoveryCode.user_id == id,
        MfaRecoveryCode.used_at.is_(None)
    ).delete(synchronize_session=False)

    plain_codes: list[str] = []
    for _ in range(8):
        token = security.random_token(6).upper()[:8]
        code_str = f"{token[:4]}-{token[4:8]}"
        plain_codes.append(code_str)
        session.add(
            MfaRecoveryCode(
                tenant_id=actor["tenant_id"],
                user_id=id,
                code_hash=security.hash_token(f"{token[:4]}{token[4:8]}"),
                created_at=now,
            )
        )

    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="user.mfa.recovery_codes_generated",
        entity_type="user",
        entity_id=str(id),
    )
    session.commit()
    return {"recoveryCodes": plain_codes}


@users_router.get("/users/{id}/sessions")
def list_user_sessions(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("user:read"))):
    user = User.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not user:
        raise not_found("User")
    now = datetime.now(timezone.utc)
    sessions = (
        SessionModel.query.filter(
            SessionModel.user_id == id,
            SessionModel.revoked_at.is_(None),
            SessionModel.expires_at > now,
        )
        .order_by(SessionModel.issued_at.desc())
        .all()
    )
    return {
        "userId": str(id),
        "sessions": [
            {
                "id": str(s.id),
                "ip": s.ip,
                "userAgent": s.user_agent,
                "device": _device_info(s.user_agent),
                "issuedAt": s.issued_at.isoformat() if s.issued_at else None,
                "expiresAt": s.expires_at.isoformat() if s.expires_at else None,
            }
            for s in sessions
        ]
    }


@users_router.delete("/users/{id}/sessions")
def revoke_user_sessions(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("user:write"))):
    user = User.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not user:
        raise not_found("User")
    security.revoke_all_sessions_for_user(id)
    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="user.sessions.revoked_all",
        entity_type="user",
        entity_id=str(id),
    )
    session.commit()
    return {"message": "All active sessions for this user have been terminated"}


@users_router.delete("/users/{id}/sessions/{session_id}", status_code=204)
def revoke_specific_user_session(id: uuid_mod.UUID, session_id: uuid_mod.UUID, actor: Actor = Depends(require_permission("user:write"))):
    user = User.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not user:
        raise not_found("User")
    sess = SessionModel.query.filter_by(user_id=id, id=session_id).first()
    if sess and sess.revoked_at is None:
        sess.revoked_at = datetime.now(timezone.utc)
        audit(
            tenant_id=actor["tenant_id"],
            actor_id=actor["user_id"],
            actor_email=actor["email"],
            action="user.session.revoked",
            entity_type="session",
            entity_id=str(session_id),
            meta={"targetUserId": str(id)},
        )
        session.commit()
    return Response(status_code=204)


@users_router.get("/users/{id}/audit")
def user_audit(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("audit:read"))):
    rows = read_audit_trail(tenant_id=actor["tenant_id"], entity_type="user", entity_id=str(id))
    return {"data": [_audit_entry(r) for r in rows]}


@users_router.get("/audit")
def audit_trail(
    actor: Actor = Depends(require_permission("audit:read")),
    entityType: str | None = None,
    entityId: str | None = None,
    limit: int = 100,
):
    limit = min(limit, 500)
    rows = read_audit_trail(tenant_id=actor["tenant_id"], entity_type=entityType, entity_id=entityId, limit=limit)
    return {"data": [_audit_entry(r) for r in rows]}


def _audit_entry(row) -> dict:
    return {
        "id": str(row.id),
        "actor_id": str(row.actor_id) if row.actor_id else None,
        "actor_email": row.actor_email,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "reason": row.reason,
        "correlation_id": row.correlation_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ============================================================================
# roles
# ============================================================================


def _assert_grantable(granter_permissions: list[str], requested: list[str]) -> None:
    missing = can_grant(granter_permissions, requested)
    if missing:
        raise rule_violation(
            f"You cannot grant permissions you do not hold: {', '.join(missing)}",
            code="LEAST_PRIVILEGE_VIOLATION",
        )


def _role_to_api(role: Role) -> dict:
    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "businessUnit": role.business_unit,
        "isSystem": role.is_system,
        "status": role.status,
        "createdAt": role.created_at.isoformat() if role.created_at else None,
        "updatedAt": role.updated_at.isoformat() if role.updated_at else None,
    }


@roles_router.get("/permissions")
def list_permissions(actor: Actor = Depends(require_permission("role:read"))):
    return {
        "data": [
            {"permission": key, "resource": key.split(":")[0], "action": key.split(":")[1], "description": desc}
            for key, desc in PERMISSIONS.items()
        ]
    }


@roles_router.get("/roles")
def list_roles(actor: Actor = Depends(require_permission("role:read")), query: ListQuery = Depends(), status: str | None = None):
    q = Role.query.filter(Role.tenant_id == actor["tenant_id"])
    if status:
        q = q.filter(Role.status == status)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(Role.name.ilike(like), Role.description.ilike(like)))

    total = q.count()
    sort_col = {"name": Role.name, "created_at": Role.created_at, "status": Role.status}.get(
        (query.sort or "").lstrip("-"), Role.name
    )
    order = sort_col.desc() if (query.sort or "").startswith("-") else sort_col.asc()
    roles = q.order_by(order).limit(query.limit).offset(offset_of(query)).all()

    role_ids = [r.id for r in roles]
    user_counts: dict = {}
    perms_by_role: dict = {}
    if role_ids:
        from sqlalchemy import func

        user_counts = dict(
            session.query(UserRole.role_id, func.count())
            .filter(UserRole.role_id.in_(role_ids))
            .group_by(UserRole.role_id)
            .all()
        )
        for role_id, permission in (
            session.query(RolePermission.role_id, RolePermission.permission)
            .filter(RolePermission.role_id.in_(role_ids))
            .all()
        ):
            perms_by_role.setdefault(role_id, []).append(permission)

    data = [
        {**_role_to_api(r), "userCount": user_counts.get(r.id, 0), "permissions": perms_by_role.get(r.id, [])}
        for r in roles
    ]
    return list_response(data, query, total)


@roles_router.get("/roles/{id}")
def get_role(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("role:read"))):
    role = Role.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not role:
        raise not_found("Role")
    return {**_role_to_api(role), "permissions": repo.permissions_for_role(role.id)}


@roles_router.post("/roles", status_code=201)
def create_role(
    body: RoleBody,
    request: Request,
    raw_body: bytes = Depends(get_raw_body),
    actor: Actor = Depends(require_permission("role:write")),
):
    def _do():
        tenant_id = actor["tenant_id"]
        _assert_grantable(actor["permissions"], body.permissions)

        if Role.query.filter_by(tenant_id=tenant_id, name=body.name).first():
            raise conflict(f'A role named "{body.name}" already exists in this tenant', code="ROLE_NAME_TAKEN")

        role = Role(
            tenant_id=tenant_id,
            name=body.name,
            description=body.description,
            business_unit=body.businessUnit,
            status=body.status,
        )
        session.add(role)
        session.flush()

        for permission in body.permissions:
            session.add(RolePermission(role_id=role.id, permission=permission, granted_by=actor["user_id"]))

        audit(
            tenant_id=tenant_id,
            actor_id=actor["user_id"],
            actor_email=actor["email"],
            action="role.created",
            entity_type="role",
            entity_id=str(role.id),
        )
        session.commit()

        return 201, {**_role_to_api(role), "permissions": repo.permissions_for_role(role.id)}

    from fastapi.responses import JSONResponse

    status_code, response_body = run_idempotent(
        request.headers.get("Idempotency-Key"), "POST", request.url.path, raw_body, actor, _do
    )
    return JSONResponse(status_code=status_code, content=response_body)


@roles_router.patch("/roles/{id}")
def patch_role(id: uuid_mod.UUID, body: RolePatchBody, actor: Actor = Depends(require_permission("role:write"))):
    role = Role.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not role:
        raise not_found("Role")

    if role.is_system and (body.name or body.permissions is not None or body.status):
        raise rule_violation(
            f'"{role.name}" is a system role — its name, permissions and status are immutable',
            code="SYSTEM_ROLE_IMMUTABLE",
        )

    before_permissions = repo.permissions_for_role(role.id)

    if body.permissions is not None:
        _assert_grantable(actor["permissions"], body.permissions)
        if "*" in before_permissions and "*" not in body.permissions:
            if repo.count_active_admin_roles(actor["tenant_id"], exclude_role_id=role.id) == 0:
                raise rule_violation("At least one active administrator role must remain in the tenant", code="LAST_ADMIN_ROLE")

    if body.status == "suspended" and "*" in before_permissions:
        if repo.count_active_admin_roles(actor["tenant_id"], exclude_role_id=role.id) == 0:
            raise rule_violation("At least one active administrator role must remain in the tenant", code="LAST_ADMIN_ROLE")

    if body.name is not None:
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    if "businessUnit" in body.model_fields_set:
        role.business_unit = body.businessUnit
    if body.status is not None:
        role.status = body.status

    if body.permissions is not None:
        RolePermission.query.filter_by(role_id=id).delete()
        for permission in body.permissions:
            session.add(RolePermission(role_id=id, permission=permission, granted_by=actor["user_id"]))

    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="role.updated",
        entity_type="role",
        entity_id=str(id),
    )
    session.commit()

    return {**_role_to_api(role), "permissions": repo.permissions_for_role(id)}


@roles_router.patch("/roles/{id}/permissions")
def replace_permissions(id: uuid_mod.UUID, body: ReplacePermissionsBody, actor: Actor = Depends(require_permission("role:write"))):
    role = Role.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not role:
        raise not_found("Role")
    if role.is_system:
        raise rule_violation(f'"{role.name}" is a system role', code="SYSTEM_ROLE_IMMUTABLE")

    _assert_grantable(actor["permissions"], body.permissions)

    before = repo.permissions_for_role(id)
    if "*" in before and "*" not in body.permissions:
        if repo.count_active_admin_roles(actor["tenant_id"], exclude_role_id=id) == 0:
            raise rule_violation("At least one active administrator role must remain in the tenant", code="LAST_ADMIN_ROLE")

    RolePermission.query.filter_by(role_id=id).delete()
    for permission in body.permissions:
        session.add(RolePermission(role_id=id, permission=permission, granted_by=actor["user_id"]))

    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="role.permissions.replaced",
        entity_type="role",
        entity_id=str(id),
    )
    session.commit()

    return {"id": str(id), "permissions": body.permissions}


@roles_router.delete("/roles/{id}", status_code=204)
def delete_role(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("role:write"))):
    role = Role.query.filter_by(tenant_id=actor["tenant_id"], id=id).first()
    if not role:
        raise not_found("Role")
    if role.is_system:
        raise rule_violation(f'"{role.name}" is a system role and cannot be deleted', code="SYSTEM_ROLE_IMMUTABLE")

    UserRole.query.filter_by(role_id=id).delete()

    audit(
        tenant_id=actor["tenant_id"],
        actor_id=actor["user_id"],
        actor_email=actor["email"],
        action="role.deleted",
        entity_type="role",
        entity_id=str(id),
    )
    session.delete(role)
    session.commit()
    return Response(status_code=204)


router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(roles_router)
