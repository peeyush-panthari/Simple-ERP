"""Route-level coverage for GET /dashboard - permission gating and response
shape. Logic itself is covered in test_analytics_repo.py."""

import pytest


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_requires_analytics_read_permission(client):
    resp = client.get("/api/v1/dashboard")
    assert resp.status_code == 401  # no token at all


def test_returns_all_panels(client, admin_access):
    resp = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["workingCapital"]["available"] is True
    assert body["workingCapital"]["source"] == "finance"
    assert "trend" in body["workingCapital"]["data"]

    assert "available" in body["inventory"]

    assert len(body["orderFunnel"]) == 5
    assert {"unit", "sampleSize", "orderToShip", "shipToInvoice", "invoiceToCash", "orderToCash"} <= body["cycleTimes"].keys()
    assert isinstance(body["recentActivity"], list)
