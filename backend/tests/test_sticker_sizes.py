"""Configuration > Sticker Size - GET/POST /sticker-sizes, PATCH/DELETE
/sticker-sizes/:id."""

import uuid

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


@pytest.fixture
def headers(admin_access):
    return {"Authorization": f"Bearer {admin_access}"}


@pytest.fixture
def unique_name(app):
    """A fresh name per test - this test suite runs against a shared,
    non-rolled-back dev database (see fresh_admin's own docstring), and
    sticker_sizes_tenant_name_uniq would otherwise collide across test
    functions and even across runs."""
    from app.models.sticker_size import StickerSize

    name = f"Test Label {uuid.uuid4().hex[:8]}"
    yield name

    with app.app_context():
        StickerSize.query.filter_by(name=name).delete(synchronize_session=False)
        _db.session.commit()


def _body(name, **overrides):
    body = {
        "name": name,
        "pageSize": "A4",
        "stickerWidthMm": "50",
        "stickerHeightMm": "30",
        "columns": "3",
        "rows": "8",
        "marginLeftMm": "5",
        "marginRightMm": "5",
        "marginTopMm": "10",
        "marginBottomMm": "10",
        "gapHorizontalMm": "2",
        "gapVerticalMm": "2",
    }
    body.update(overrides)
    return body


def test_create_sticker_size_with_a4_fills_in_standard_page_dims(client, headers, unique_name):
    resp = client.post("/api/v1/sticker-sizes", json=_body(unique_name), headers=headers)
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert data["pageSize"] == "A4"
    assert data["pageWidthMm"] == "210.00"
    assert data["pageHeightMm"] == "297.00"
    assert data["totalStickersPerPage"] == 24
    assert data["status"] == "active"


def test_create_sticker_size_with_custom_page_uses_supplied_dims(client, headers, unique_name):
    resp = client.post(
        "/api/v1/sticker-sizes",
        json=_body(unique_name, pageSize="Custom", pageWidthMm="300", pageHeightMm="400", columns="4", rows="10"),
        headers=headers,
    )
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert data["pageWidthMm"] == "300.00"
    assert data["pageHeightMm"] == "400.00"


def test_custom_page_without_dims_is_rejected(client, headers, unique_name):
    resp = client.post("/api/v1/sticker-sizes", json=_body(unique_name, pageSize="Custom"), headers=headers)
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "STICKER_SIZE_INVALID"


def test_layout_that_does_not_fit_the_page_is_rejected(client, headers, unique_name):
    # 10 columns of 50mm stickers (+ gaps/margins) is far wider than an A4
    # sheet (210mm) can hold.
    resp = client.post("/api/v1/sticker-sizes", json=_body(unique_name, columns="10"), headers=headers)
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "STICKER_LAYOUT_INVALID"


def test_duplicate_name_is_rejected(client, headers, unique_name):
    first = client.post("/api/v1/sticker-sizes", json=_body(unique_name), headers=headers)
    assert first.status_code == 201
    second = client.post("/api/v1/sticker-sizes", json=_body(unique_name), headers=headers)
    assert second.status_code == 409
    assert second.get_json()["code"] == "STICKER_SIZE_NAME_TAKEN"


def test_list_and_filter_by_status(client, headers, unique_name):
    created = client.post("/api/v1/sticker-sizes", json=_body(unique_name), headers=headers).get_json()
    client.patch(f"/api/v1/sticker-sizes/{created['id']}", json={"status": "inactive"}, headers=headers)

    active_resp = client.get("/api/v1/sticker-sizes", query_string={"status": "active"}, headers=headers)
    assert created["id"] not in {r["id"] for r in active_resp.get_json()["data"]}

    inactive_resp = client.get("/api/v1/sticker-sizes", query_string={"status": "inactive"}, headers=headers)
    assert created["id"] in {r["id"] for r in inactive_resp.get_json()["data"]}


def test_patch_partial_edit_revalidates_effective_layout(client, headers, unique_name):
    created = client.post("/api/v1/sticker-sizes", json=_body(unique_name), headers=headers).get_json()
    # Bumping columns to 10 alone (without touching anything else) should
    # still be checked against the *effective* merged layout and rejected.
    resp = client.patch(f"/api/v1/sticker-sizes/{created['id']}", json={"columns": 10}, headers=headers)
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "STICKER_LAYOUT_INVALID"


def test_patch_updates_fields_and_recomputes_total(client, headers, unique_name):
    created = client.post("/api/v1/sticker-sizes", json=_body(unique_name), headers=headers).get_json()
    resp = client.patch(f"/api/v1/sticker-sizes/{created['id']}", json={"columns": 2, "rows": 4}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["columns"] == 2
    assert data["rows"] == 4
    assert data["totalStickersPerPage"] == 8


def test_delete_removes_the_template(client, headers, unique_name):
    created = client.post("/api/v1/sticker-sizes", json=_body(unique_name), headers=headers).get_json()
    resp = client.delete(f"/api/v1/sticker-sizes/{created['id']}", headers=headers)
    assert resp.status_code == 204

    list_resp = client.get("/api/v1/sticker-sizes", headers=headers)
    assert created["id"] not in {r["id"] for r in list_resp.get_json()["data"]}
