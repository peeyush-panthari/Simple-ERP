"""Ported from backend_py/tests/test_auth.py - same assertions, `.json()`
instead of Flask test client's `.get_json()` (fastapi.testclient.TestClient
wraps httpx, which uses the standard `.json()` name)."""


def test_login_unknown_user_rejected(client):
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@example.test", "password": "whatever"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_CREDENTIALS"


def test_login_success_then_refresh_rotation_and_reuse_detection(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["accessToken"]
    assert body["user"]["permissions"] == ["*"]

    old_refresh = body["refreshToken"]

    resp = client.post("/api/v1/auth/refresh", json={"refreshToken": old_refresh})
    assert resp.status_code == 200
    new_refresh = resp.json()["refreshToken"]
    assert new_refresh != old_refresh

    # Reusing the rotated-away token is the signature of a stolen token.
    resp = client.post("/api/v1/auth/refresh", json={"refreshToken": old_refresh})
    assert resp.status_code == 401
    assert resp.json()["code"] == "REFRESH_TOKEN_REUSED"

    # ...and it revokes the whole chain, including the token that replaced it.
    resp = client.post("/api/v1/auth/refresh", json={"refreshToken": new_refresh})
    assert resp.status_code == 401


def test_me_requires_bearer_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, fresh_admin):
    login = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    access = login.json()["accessToken"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == fresh_admin["email"]
