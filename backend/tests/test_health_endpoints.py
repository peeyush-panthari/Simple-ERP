"""Liveness and readiness must answer without a bearer token.

start.sh polls /readyz to decide the backend came up, and an orchestrator probe
carries no token either. /readyz was missing from auth_guard.PUBLIC_PATHS, so it
answered 401 to every caller and its database check never ran for anyone -
start.sh's 60-second wait could not succeed.
"""


def test_healthz_needs_no_token(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_readyz_needs_no_token(client):
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ready"


def test_readyz_output_is_what_start_sh_greps_for(client):
    """start.sh does: curl -fsS .../readyz | grep -q '"ready"'."""
    resp = client.get("/readyz")
    assert resp.status_code < 400, "curl -fsS treats a 4xx/5xx as failure"
    assert '"ready"' in resp.get_data(as_text=True)


def test_protected_routes_are_still_protected(client):
    """Opening the probes must not have opened anything else."""
    for path in ("/api/v1/products", "/api/v1/users", "/api/v1/roles"):
        assert client.get(path).status_code == 401, path
