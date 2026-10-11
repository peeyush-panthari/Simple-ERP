"""Smoke coverage for every list endpoint whose queries were batched.

Not a perf assertion - it proves the rewritten SQL still builds and runs
against a real database. Several of these endpoints (balances, factories,
transport-requests, working-capital) had no route test at all before.

One test covering every endpoint, not one parametrised case each: the login
route is rate-limited, so a per-case login fixture would eat that budget.
"""

import pytest

ENDPOINTS = [
    "/api/v1/boms",
    "/api/v1/warehouses",
    "/api/v1/product-categories",
    "/api/v1/product-categories/tree",
    "/api/v1/factories",
    "/api/v1/roles",
    "/api/v1/purchase-orders",
    "/api/v1/products",
    "/api/v1/inventory/balances",
    "/api/v1/inventory/balances?includeZero=true",
    "/api/v1/inventory/ledger",
    "/api/v1/transport-requests",
    "/api/v1/payments",
    "/api/v1/ar",
    "/api/v1/ap",
    "/api/v1/working-capital",
    "/api/v1/working-capital/cycle",
    "/api/v1/grns",
    "/api/v1/orders",
    "/api/v1/parties",
    "/api/v1/users",
    "/api/v1/business-entities",
]


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_batched_list_endpoints_all_return_200(client, admin_access):
    headers = {"Authorization": f"Bearer {admin_access}"}
    failures = []
    for path in ENDPOINTS:
        resp = client.get(path, headers=headers)
        if resp.status_code != 200 or resp.get_json() is None:
            failures.append(f"{path} -> {resp.status_code} {resp.get_data(as_text=True)[:200]}")
    assert not failures, "\n".join(failures)
