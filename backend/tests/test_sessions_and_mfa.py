"""Tests for Phase 3: Active Session Explorer & Revocation, and MFA Recovery Codes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pyotp
import pytest
from app.core import security
from app.core.db import session
from app.models.session import Session as SessionModel
from app.models.user import User
from app.models.user_credentials import MfaRecoveryCode


def test_mfa_recovery_codes_flow(client, default_tenant_id, fresh_admin):
    admin = fresh_admin

    # 1. Log in as admin
    login_res = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert login_res.status_code == 200
    token = login_res.json()["accessToken"]
    user_id = admin["id"]

    # 2. Cannot generate recovery codes before MFA is enabled
    r = client.post(f"/api/v1/users/{user_id}/mfa/generate-recovery-codes", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422
    assert r.json()["code"] == "MFA_NOT_ENABLED"

    # 3. Enrol and confirm MFA
    enrol_res = client.post(f"/api/v1/users/{user_id}/mfa/enrol", headers={"Authorization": f"Bearer {token}"})
    assert enrol_res.status_code == 200
    totp_secret = enrol_res.json()["secret"]

    totp_code = pyotp.TOTP(totp_secret).now()
    confirm_res = client.post(
        f"/api/v1/users/{user_id}/mfa/confirm",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": totp_code},
    )
    assert confirm_res.status_code == 200
    assert confirm_res.json()["mfaEnabled"] is True

    # 4. Generate recovery codes
    codes_res = client.post(f"/api/v1/users/{user_id}/mfa/generate-recovery-codes", headers={"Authorization": f"Bearer {token}"})
    assert codes_res.status_code == 200
    recovery_codes = codes_res.json()["recoveryCodes"]
    assert len(recovery_codes) == 8

    # Verify rows in DB
    db_codes = MfaRecoveryCode.query.filter_by(user_id=uuid.UUID(user_id)).all()
    assert len(db_codes) == 8
    assert all(c.used_at is None for c in db_codes)

    # 5. Log in with MFA requirement triggered
    r = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert r.status_code == 401
    assert r.json()["code"] == "MFA_REQUIRED"

    # 6. Log in using the first recovery code
    chosen_code = recovery_codes[0]
    r = client.post(
        "/api/v1/auth/login",
        json={"email": admin["email"], "password": admin["password"], "mfaRecoveryCode": chosen_code},
    )
    assert r.status_code == 200
    assert "accessToken" in r.json()

    # Verify that code is now used in DB
    session.expire_all()
    clean_code = chosen_code.replace("-", "")
    code_hash = security.hash_token(clean_code)
    used_db_code = MfaRecoveryCode.query.filter_by(user_id=uuid.UUID(user_id), code_hash=code_hash).first()
    assert used_db_code is not None
    assert used_db_code.used_at is not None

    # 7. Reusing the same recovery code fails
    r = client.post(
        "/api/v1/auth/login",
        json={"email": admin["email"], "password": admin["password"], "mfaRecoveryCode": chosen_code},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "MFA_RECOVERY_CODE_INVALID"

    # 8. Remaining recovery codes still work
    second_code = recovery_codes[1]
    r = client.post(
        "/api/v1/auth/login",
        json={"email": admin["email"], "password": admin["password"], "mfaRecoveryCode": second_code},
    )
    assert r.status_code == 200


def test_session_explorer_and_revocation(client, default_tenant_id, fresh_admin):
    admin = fresh_admin

    # 1. Establish Session 1
    s1_res = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert s1_res.status_code == 200
    token1 = s1_res.json()["accessToken"]

    # 2. Establish Session 2
    s2_res = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert s2_res.status_code == 200
    token2 = s2_res.json()["accessToken"]

    # 3. List sessions as Session 2
    list_res = client.get("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {token2}"})
    assert list_res.status_code == 200
    sessions_list = list_res.json()["sessions"]
    assert len(sessions_list) >= 2

    # Check isCurrent flag
    current_sessions = [s for s in sessions_list if s["isCurrent"]]
    assert len(current_sessions) == 1
    other_sessions = [s for s in sessions_list if not s["isCurrent"]]
    assert len(other_sessions) >= 1

    # 4. Revoke a specific other session
    target_id = other_sessions[0]["id"]
    del_res = client.delete(f"/api/v1/auth/sessions/{target_id}", headers={"Authorization": f"Bearer {token2}"})
    assert del_res.status_code == 204

    # Verify session is revoked in DB
    session.expire_all()
    target_row = session.get(SessionModel, uuid.UUID(target_id))
    assert target_row.revoked_at is not None

    # 5. Revoke all other sessions
    del_other_res = client.delete("/api/v1/auth/sessions/other", headers={"Authorization": f"Bearer {token2}"})
    assert del_other_res.status_code == 200

    # Listing sessions again should only show current session
    list_res2 = client.get("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {token2}"})
    assert list_res2.status_code == 200
    active_now = list_res2.json()["sessions"]
    assert len(active_now) == 1
    assert active_now[0]["isCurrent"] is True

    # 6. Admin lists sessions for the user
    user_id = admin["id"]
    admin_list_res = client.get(f"/api/v1/users/{user_id}/sessions", headers={"Authorization": f"Bearer {token2}"})
    assert admin_list_res.status_code == 200
    assert len(admin_list_res.json()["sessions"]) == 1

    # 7. Admin revokes all sessions for the user
    admin_del_res = client.delete(f"/api/v1/users/{user_id}/sessions", headers={"Authorization": f"Bearer {token2}"})
    assert admin_del_res.status_code == 200

    # Now all sessions are revoked
    session.expire_all()
    remaining = (
        SessionModel.query.filter(
            SessionModel.user_id == uuid.UUID(user_id),
            SessionModel.revoked_at.is_(None),
        ).count()
    )
    assert remaining == 0
