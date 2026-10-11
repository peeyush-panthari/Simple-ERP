"""Regression coverage for a real bug: not_found() only accepts one
positional argument (detail) plus keyword-only `code`, but several call
sites across finance_repo.py, inventory_ledger.py and routes/finance.py used
to pass a second positional argument (the id) - e.g. `not_found("Payable",
id)`. That raised a TypeError at the not_found() call itself, so every real
"not found" case on these paths crashed into an unhandled 500 instead of
returning a clean 404. Fixed by interpolating the id into a single string
argument; these tests prove the fix (a 404, not a 500, on a real miss)."""

import uuid

import pytest

from app.core.errors import ProblemError


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def test_get_ap_invoice_missing_returns_404_not_500(client, admin_access):
    resp = client.get(f"/api/v1/ap/{uuid.uuid4()}", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 404
    assert resp.get_json()["title"] == "Not Found"


def test_get_ar_invoice_missing_returns_404_not_500(client, admin_access):
    resp = client.get(f"/api/v1/ar/{uuid.uuid4()}", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 404
    assert resp.get_json()["title"] == "Not Found"


def test_reverse_payment_missing_returns_404_not_500(client, admin_access):
    resp = client.post(f"/api/v1/payments/{uuid.uuid4()}/reverse", json={"reason": "test reversal reason"}, headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 404


def test_approve_payment_missing_returns_404_not_500(client, admin_access):
    resp = client.post(f"/api/v1/payments/{uuid.uuid4()}/approve", headers={"Authorization": f"Bearer {admin_access}"})
    assert resp.status_code == 404


def test_issue_reservation_missing_raises_problem_error_not_type_error(app, default_tenant_id):
    """issue_reservation() is only ever called internally (from order
    shipment) with real reservation ids - no direct route exists to hit this
    with an arbitrary bad id, so it's exercised at the function level."""
    from app.services.inventory_ledger import issue_reservation

    with app.app_context():
        with pytest.raises(ProblemError) as exc:
            issue_reservation(default_tenant_id, uuid.uuid4(), "test-ref", "shipment")
        assert exc.value.status == 404
