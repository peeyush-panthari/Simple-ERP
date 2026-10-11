"""New coverage - the monolith-appropriate replacement for Node's
architecture.tsx service map (see routes/system_status.py's module
docstring for why the literal port isn't possible)."""

import pytest


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_requires_analytics_read_permission(client):
    resp = client.get("/api/v1/system-status")
    assert resp.status_code == 401  # no token at all


def test_returns_checks_and_module_map(client, admin_access):
    resp = client.get("/api/v1/system-status", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["checks"]["database"]["healthy"] is True
    assert "documentStorage" in body["checks"]
    assert "pdfEngine" in body["checks"]
    assert "mailTransport" in body["checks"]

    keys = [m["key"] for m in body["modules"]]
    assert "identity" in keys
    assert "gateway" in keys
    assert all(m["status"] in ("done", "not_started", "not_applicable") for m in body["modules"])

    assert body["modulesTotal"] == len([m for m in body["modules"] if m["status"] != "not_applicable"])
    assert body["modulesDone"] == len([m for m in body["modules"] if m["status"] == "done"])
