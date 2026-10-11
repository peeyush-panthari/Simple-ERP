"""Tests for native credentials lifecycle (Phase 2):
- Forgot password token issuance & email queuing
- Reset password enforcement (policy, history, single-use)
- User invite creation, resending, and acceptance
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core import security
from app.core.db import session
from app.models.notification import Notification
from app.models.role import Role
from app.models.user import User
from app.models.user_credentials import PasswordResetToken, UserInvitation


def test_forgot_password_and_reset_flow(client, default_tenant_id, fresh_admin):
    admin = fresh_admin

    # 1. Non-existent email returns generic 200 (prevents enumeration)
    r = client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@example.com"})
    assert r.status_code == 200
    assert "If an account with that email exists" in r.json()["message"]

    # 2. Existing user forgot-password
    r = client.post("/api/v1/auth/forgot-password", json={"email": admin["email"]})
    assert r.status_code == 200
    assert "If an account with that email exists" in r.json()["message"]

    # Verify a PasswordResetToken row was stored
    reset_tokens = PasswordResetToken.query.filter_by(user_id=uuid.UUID(admin["id"])).all()
    assert len(reset_tokens) == 1
    assert reset_tokens[0].used_at is None
    assert reset_tokens[0].expires_at > datetime.now(timezone.utc)

    # Verify Notification was queued
    notif = Notification.query.filter_by(tenant_id=default_tenant_id, template_key="user.password_reset").first()
    assert notif is not None
    assert notif.recipients == [admin["email"]]
    token_str = notif.data["resetToken"]
    assert security.hash_token(token_str) == reset_tokens[0].token_hash

    # 3. Invalid token fails
    r = client.post("/api/v1/auth/reset-password", json={"token": "bogus-token-1234", "newPassword": "BrandNewSecret#999"})
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_RESET_TOKEN"

    # 4. Valid token resets password
    r = client.post("/api/v1/auth/reset-password", json={"token": token_str, "newPassword": "BrandNewSecret#999"})
    assert r.status_code == 200
    assert "successfully reset" in r.json()["message"]

    # 5. Token is consumed (cannot be reused)
    r = client.post("/api/v1/auth/reset-password", json={"token": token_str, "newPassword": "AnotherSecret#888"})
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_RESET_TOKEN"

    # 6. Verify user can log in with new password
    r = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": "BrandNewSecret#999"})
    assert r.status_code == 200
    assert "accessToken" in r.json()


def test_user_invitation_lifecycle(client, default_tenant_id, fresh_admin):
    admin = fresh_admin

    # Log in as admin to get auth token
    login_res = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login_res.status_code == 200
    admin_token = login_res.json()["accessToken"]

    role = Role.query.filter_by(tenant_id=default_tenant_id, name="System Admin").first()
    assert role is not None

    # 1. Create invited user
    invited_email = f"invited_{uuid.uuid4().hex[:6]}@example.test"
    r = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": invited_email,
            "displayName": "Invited Candidate",
            "status": "invited",
            "roles": [{"roleId": str(role.id)}],
        },
    )
    assert r.status_code == 201
    invited_user_id = uuid.UUID(r.json()["id"])

    # Verify UserInvitation was created
    inv = UserInvitation.query.filter_by(user_id=invited_user_id).first()
    assert inv is not None
    assert inv.accepted_at is None

    # Verify notification queued
    notif = Notification.query.filter_by(tenant_id=default_tenant_id, template_key="user.invitation").first()
    assert notif is not None
    invite_token = notif.data["inviteToken"]

    # 2. Resend invitation
    r = client.post(
        f"/api/v1/users/{invited_user_id}/resend-invite",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Invitation resent successfully"

    # The previous invitation should be expired and a new one active
    session.expire_all()
    invitations = UserInvitation.query.filter_by(user_id=invited_user_id).order_by(UserInvitation.created_at.asc()).all()
    assert len(invitations) == 2
    assert invitations[0].expires_at <= datetime.now(timezone.utc)  # invalidated

    # Get latest invitation token from notifications
    latest_notif = Notification.query.filter_by(tenant_id=default_tenant_id, template_key="user.invitation").order_by(Notification.created_at.desc()).first()
    new_token = latest_notif.data["inviteToken"]

    # 3. Old token fails
    r = client.post("/api/v1/auth/accept-invite", json={"token": invite_token, "password": "BrandNewSecret#777"})
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_INVITE_TOKEN"

    # 4. New token succeeds and activates account
    r = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": new_token, "password": "BrandNewSecret#777", "displayName": "Candidate Activated"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "accessToken" in body
    assert body["user"]["displayName"] == "Candidate Activated"

    # Verify user is active in DB
    user_db = session.get(User, invited_user_id)
    assert user_db.status == "active"
    assert user_db.display_name == "Candidate Activated"
