"""Per-warehouse/per-factory scoped role assignments - covers the new
user_role_warehouses/user_role_factories tables, effective_access()'s scope
aggregation, and enforcement in the warehouses/factories/GRN routes."""

import uuid

import pytest


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cleanup(app):
    ids: dict[str, list[str]] = {"users": [], "roles": [], "warehouses": [], "factories": []}
    yield ids
    from tests.flaskcompat import db as _db
    from app.models.factory import Factory
    from app.models.location import Location
    from app.models.password_history import PasswordHistory
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.session import Session
    from app.models.user import User
    from app.models.user_role import UserRole
    from app.models.user_role_factory import UserRoleFactory
    from app.models.user_role_warehouse import UserRoleWarehouse
    from app.models.warehouse import Warehouse

    with app.app_context():
        user_ids = [uuid.UUID(i) for i in ids["users"]]
        role_ids = [uuid.UUID(i) for i in ids["roles"]]
        warehouse_ids = [uuid.UUID(i) for i in ids["warehouses"]]
        factory_ids = [uuid.UUID(i) for i in ids["factories"]]
        if user_ids or role_ids:
            UserRoleWarehouse.query.filter(
                UserRoleWarehouse.user_id.in_(user_ids) | UserRoleWarehouse.role_id.in_(role_ids)
            ).delete(synchronize_session=False)
            UserRoleFactory.query.filter(
                UserRoleFactory.user_id.in_(user_ids) | UserRoleFactory.role_id.in_(role_ids)
            ).delete(synchronize_session=False)
            UserRole.query.filter(UserRole.user_id.in_(user_ids) | UserRole.role_id.in_(role_ids)).delete(synchronize_session=False)
        if user_ids:
            Session.query.filter(Session.user_id.in_(user_ids)).delete(synchronize_session=False)
            PasswordHistory.query.filter(PasswordHistory.user_id.in_(user_ids)).delete(synchronize_session=False)
            User.query.filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        if role_ids:
            RolePermission.query.filter(RolePermission.role_id.in_(role_ids)).delete(synchronize_session=False)
            Role.query.filter(Role.id.in_(role_ids)).delete(synchronize_session=False)
        if warehouse_ids:
            Location.query.filter(Location.warehouse_id.in_(warehouse_ids)).delete(synchronize_session=False)
            Warehouse.query.filter(Warehouse.id.in_(warehouse_ids)).delete(synchronize_session=False)
        if factory_ids:
            Factory.query.filter(Factory.id.in_(factory_ids)).delete(synchronize_session=False)
        _db.session.commit()


def _create_warehouse(client, admin_access, cleanup, name=None):
    # Explicit code: the auto-numbered next_warehouse_code() sequence can
    # collide with WH-AA09, the fixed anchor warehouse reset_demo_data.py
    # protects in this shared dev database.
    resp = client.post(
        "/api/v1/warehouses",
        json={"name": name or f"WH Scope Test {uuid.uuid4().hex[:6]}", "code": f"WHT-{uuid.uuid4().hex[:8].upper()}"},
        headers=_headers(admin_access),
    )
    assert resp.status_code == 201, resp.get_json()
    warehouse = resp.get_json()
    cleanup["warehouses"].append(warehouse["id"])
    return warehouse


def _create_factory(client, admin_access, cleanup, name=None):
    resp = client.post(
        "/api/v1/factories", json={"name": name or f"Factory Scope Test {uuid.uuid4().hex[:6]}"}, headers=_headers(admin_access)
    )
    assert resp.status_code == 201, resp.get_json()
    factory = resp.get_json()
    cleanup["factories"].append(factory["id"])
    return factory


def _create_role(client, admin_access, cleanup, permissions):
    resp = client.post(
        "/api/v1/roles",
        json={"name": f"Scope Test Role {uuid.uuid4().hex[:8]}", "permissions": permissions},
        headers=_headers(admin_access),
    )
    assert resp.status_code == 201, resp.get_json()
    role = resp.get_json()
    cleanup["roles"].append(role["id"])
    return role


def _create_scoped_user(client, admin_access, cleanup, role_id, warehouse_ids=None, factory_ids=None):
    email = f"scope-test-{uuid.uuid4().hex[:8]}@example.test"
    password = "TestScoped#Passw0rd1"
    resp = client.post(
        "/api/v1/users",
        json={
            "email": email,
            "displayName": "Scope Test User",
            "password": password,
            "status": "active",
            "roles": [{"roleId": role_id, "warehouseIds": warehouse_ids or [], "factoryIds": factory_ids or []}],
        },
        headers=_headers(admin_access),
    )
    assert resp.status_code == 201, resp.get_json()
    user = resp.get_json()
    cleanup["users"].append(user["id"])

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.get_json()
    return user, login.get_json()["accessToken"]


def test_unscoped_assignment_sees_every_warehouse(client, admin_access, cleanup):
    wh1 = _create_warehouse(client, admin_access, cleanup)
    wh2 = _create_warehouse(client, admin_access, cleanup)
    role = _create_role(client, admin_access, cleanup, ["warehouse:read"])
    _user, token = _create_scoped_user(client, admin_access, cleanup, role["id"])

    listed = client.get("/api/v1/warehouses", query_string={"limit": 200}, headers=_headers(token))
    ids = {w["id"] for w in listed.get_json()["data"]}
    assert {wh1["id"], wh2["id"]} <= ids

    detail = client.get(f"/api/v1/warehouses/{wh2['id']}", headers=_headers(token))
    assert detail.status_code == 200


def test_warehouse_scoped_assignment_only_sees_its_warehouse(client, admin_access, cleanup):
    wh1 = _create_warehouse(client, admin_access, cleanup)
    wh2 = _create_warehouse(client, admin_access, cleanup)
    role = _create_role(client, admin_access, cleanup, ["warehouse:read"])
    _user, token = _create_scoped_user(client, admin_access, cleanup, role["id"], warehouse_ids=[wh1["id"]])

    listed = client.get("/api/v1/warehouses", query_string={"limit": 200}, headers=_headers(token))
    ids = {w["id"] for w in listed.get_json()["data"]}
    assert wh1["id"] in ids
    assert wh2["id"] not in ids

    ok = client.get(f"/api/v1/warehouses/{wh1['id']}", headers=_headers(token))
    assert ok.status_code == 200

    denied = client.get(f"/api/v1/warehouses/{wh2['id']}", headers=_headers(token))
    assert denied.status_code == 403
    assert denied.get_json()["code"] == "WAREHOUSE_OUT_OF_SCOPE"


def test_factory_scope_implies_its_warehouses(client, admin_access, cleanup):
    factory = _create_factory(client, admin_access, cleanup)
    wh_in_factory = _create_warehouse(client, admin_access, cleanup)
    patch = client.patch(f"/api/v1/warehouses/{wh_in_factory['id']}", json={"factoryId": factory["id"]}, headers=_headers(admin_access))
    assert patch.status_code == 200
    wh_outside = _create_warehouse(client, admin_access, cleanup)

    role = _create_role(client, admin_access, cleanup, ["warehouse:read"])
    _user, token = _create_scoped_user(client, admin_access, cleanup, role["id"], factory_ids=[factory["id"]])

    in_scope = client.get(f"/api/v1/warehouses/{wh_in_factory['id']}", headers=_headers(token))
    assert in_scope.status_code == 200

    out_of_scope = client.get(f"/api/v1/warehouses/{wh_outside['id']}", headers=_headers(token))
    assert out_of_scope.status_code == 403


def test_scoped_admin_cannot_grant_access_outside_their_own_scope(client, admin_access, cleanup):
    wh1 = _create_warehouse(client, admin_access, cleanup)
    wh2 = _create_warehouse(client, admin_access, cleanup)
    granter_role = _create_role(client, admin_access, cleanup, ["warehouse:read", "user:write", "role:assign", "role:read"])
    _granter_user, granter_token = _create_scoped_user(client, admin_access, cleanup, granter_role["id"], warehouse_ids=[wh1["id"]])

    grantee_role = _create_role(client, admin_access, cleanup, ["warehouse:read"])
    resp = client.post(
        "/api/v1/users",
        json={
            "email": f"scope-grantee-{uuid.uuid4().hex[:8]}@example.test",
            "displayName": "Grantee",
            "password": "TestGrantee#Passw0rd1",
            "status": "active",
            "roles": [{"roleId": grantee_role["id"], "warehouseIds": [wh2["id"]], "factoryIds": []}],
        },
        headers=_headers(granter_token),
    )
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "LEAST_PRIVILEGE_VIOLATION"
    if resp.status_code == 201:
        cleanup["users"].append(resp.get_json()["id"])
