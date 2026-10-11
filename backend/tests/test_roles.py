"""Ported from backend_py/tests/test_roles.py (import paths only)."""
import uuid

import pytest


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_role_can_hold_any_combination_of_permissions(client, admin_access):
    """No segregation-of-duties restriction on which permissions a role can
    combine - a role holding both sides of a maker/checker pair (e.g.
    po:write + po:approve) is a tenant policy choice, not something this
    app blocks."""
    resp = client.post(
        "/api/v1/roles",
        json={"name": f"Conflicted Role Test {uuid.uuid4().hex[:8]}", "permissions": ["po:write", "po:approve"]},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 201, resp.get_json()
    assert set(resp.get_json()["permissions"]) == {"po:write", "po:approve"}


def test_duplicate_role_name_is_conflict(client, admin_access):
    body = {"name": f"Duplicate Role Test {uuid.uuid4().hex[:8]}", "permissions": []}
    first = client.post("/api/v1/roles", json=body, headers={"Authorization": f"Bearer {admin_access}"})
    assert first.status_code == 201
    second = client.post("/api/v1/roles", json=body, headers={"Authorization": f"Bearer {admin_access}"})
    assert second.status_code == 409
    assert second.get_json()["code"] == "ROLE_NAME_TAKEN"


def test_system_role_is_immutable(client, admin_access):
    roles = client.get(
        "/api/v1/roles", query_string={"q": "System Admin"}, headers={"Authorization": f"Bearer {admin_access}"}
    )
    system_admin_id = roles.get_json()["data"][0]["id"]
    resp = client.patch(
        f"/api/v1/roles/{system_admin_id}",
        json={"description": "trying to rename a system role"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    # description-only changes are allowed; permissions/name/status are not.
    resp2 = client.patch(
        f"/api/v1/roles/{system_admin_id}",
        json={"permissions": ["user:read"]},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp2.status_code == 422
    assert resp2.get_json()["code"] == "SYSTEM_ROLE_IMMUTABLE"
