"""Ported from backend_py/tests/test_users.py (import paths only)."""
import uuid

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


@pytest.fixture(autouse=True)
def _clean_up_created_users(app):
    """These tests create users through the real API, against the shared dev
    database with no transaction rollback - so each run used to leave three
    more rows in `users` behind. Emails are prefixed and uniquely suffixed, so
    they can be reclaimed by prefix without touching anything real."""
    yield
    from app.models.password_history import PasswordHistory
    from app.models.session import Session
    from app.models.user import User
    from app.models.user_role import UserRole

    with app.app_context():
        prefixes = ("newuser-%", "dupe-%", "weak-%", "limited-%")
        stale = User.query.filter(_db.or_(*[User.email.like(p) for p in prefixes])).all()
        if not stale:
            return
        ids = [u.id for u in stale]
        for model in (Session, PasswordHistory, UserRole):
            model.query.filter(model.user_id.in_(ids)).delete(synchronize_session=False)
        User.query.filter(User.id.in_(ids)).delete(synchronize_session=False)
        _db.session.commit()


def test_list_users_requires_permission(client):
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401  # no token at all


def test_create_and_fetch_user(client, admin_access):
    email = f"newuser-{uuid.uuid4().hex[:8]}@example.test"
    resp = client.post(
        "/api/v1/users",
        json={"email": email, "displayName": "New User", "password": "NewUser#Passw0rd", "status": "active"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 201
    user_id = resp.get_json()["id"]

    resp = client.get(f"/api/v1/users/{user_id}", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 200
    assert resp.get_json()["email"] == email


def test_duplicate_email_is_conflict(client, admin_access):
    email = f"dupe-{uuid.uuid4().hex[:8]}@example.test"
    body = {"email": email, "displayName": "Dupe", "password": "Dupe#Passw0rd1", "status": "active"}
    first = client.post("/api/v1/users", json=body, headers={"Authorization": f"Bearer {admin_access}"})
    assert first.status_code == 201
    second = client.post("/api/v1/users", json=body, headers={"Authorization": f"Bearer {admin_access}"})
    assert second.status_code == 409
    assert second.get_json()["code"] == "EMAIL_TAKEN"


def test_weak_password_rejected_by_policy(client, admin_access):
    resp = client.post(
        "/api/v1/users",
        json={"email": f"weak-{uuid.uuid4().hex[:8]}@example.test", "displayName": "Weak", "password": "password", "status": "active"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "PASSWORD_POLICY_VIOLATION"


def test_non_admin_cannot_grant_permission_they_lack(client, admin_access):
    # Create a low-privilege user (no roles) and a role granting a permission
    # the admin holds (fine) - then verify that user, once given only
    # role:assign, cannot grant a role carrying permissions it doesn't hold.
    limited_email = f"limited-{uuid.uuid4().hex[:8]}@example.test"
    created = client.post(
        "/api/v1/users",
        json={"email": limited_email, "displayName": "Limited", "password": "Limited#Passw0rd", "status": "active"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    limited_user_id = created.get_json()["id"]

    role_resp = client.post(
        "/api/v1/roles",
        json={"name": f"Assigner Role {uuid.uuid4().hex[:6]}", "permissions": ["role:assign"]},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assigner_role_id = role_resp.get_json()["id"]

    client.patch(
        f"/api/v1/users/{limited_user_id}/roles",
        json={"roles": [{"roleId": assigner_role_id, "scopes": []}], "mode": "replace"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )

    login = client.post("/api/v1/auth/login", json={"email": limited_email, "password": "Limited#Passw0rd"})
    limited_access = login.get_json()["accessToken"]

    # A role granting user:write - the limited user does not hold user:write.
    target_role_resp = client.post(
        "/api/v1/roles",
        json={"name": f"User Writer Role {uuid.uuid4().hex[:6]}", "permissions": ["user:write"]},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    target_role_id = target_role_resp.get_json()["id"]

    resp = client.patch(
        f"/api/v1/users/{limited_user_id}/roles",
        json={"roles": [{"roleId": target_role_id, "scopes": []}], "mode": "replace"},
        headers={"Authorization": f"Bearer {limited_access}"},
    )
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "LEAST_PRIVILEGE_VIOLATION"
