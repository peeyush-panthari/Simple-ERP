"""Several list/detail endpoints are called directly by modules other than
the one that "owns" them, just to resolve names for display or to populate
a picker - not only by their own dedicated module. A role holding an
operational permission from one of those other modules can therefore call
these lookup endpoints even without the owning module's own :read
permission, which still gates that module's own nav/page and all of its
write actions. See each route file's own _..._LOOKUP_PERMISSIONS constant:
products.py, warehouses.py, factories.py, boms.py, parties.py,
business_entities.py, sticker_sizes.py, purchase_orders.py, orders.py, and
grns.py (whose OWN nav permission is warehouse:read, not grn:read - the one
case here where the mismatch was inside a single module rather than across
two)."""

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
    ids: dict[str, list[str]] = {"users": [], "roles": []}
    yield ids
    from tests.flaskcompat import db as _db
    from app.models.password_history import PasswordHistory
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.session import Session
    from app.models.user import User
    from app.models.user_role import UserRole

    with app.app_context():
        user_ids = [uuid.UUID(i) for i in ids["users"]]
        role_ids = [uuid.UUID(i) for i in ids["roles"]]
        if user_ids or role_ids:
            UserRole.query.filter(UserRole.user_id.in_(user_ids) | UserRole.role_id.in_(role_ids)).delete(synchronize_session=False)
        if user_ids:
            Session.query.filter(Session.user_id.in_(user_ids)).delete(synchronize_session=False)
            PasswordHistory.query.filter(PasswordHistory.user_id.in_(user_ids)).delete(synchronize_session=False)
            User.query.filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        if role_ids:
            RolePermission.query.filter(RolePermission.role_id.in_(role_ids)).delete(synchronize_session=False)
            Role.query.filter(Role.id.in_(role_ids)).delete(synchronize_session=False)
        _db.session.commit()


def _create_role(client, admin_access, cleanup, permissions):
    resp = client.post(
        "/api/v1/roles",
        json={"name": f"Lookup Permission Test Role {uuid.uuid4().hex[:8]}", "permissions": permissions},
        headers=_headers(admin_access),
    )
    assert resp.status_code == 201, resp.get_json()
    role = resp.get_json()
    cleanup["roles"].append(role["id"])
    return role


def _create_user_with_role(client, admin_access, cleanup, role_id):
    email = f"lookup-perm-test-{uuid.uuid4().hex[:8]}@example.test"
    password = "TestLookup#Passw0rd1"
    resp = client.post(
        "/api/v1/users",
        json={
            "email": email,
            "displayName": "Lookup Permission Test User",
            "password": password,
            "status": "active",
            "roles": [{"roleId": role_id, "warehouseIds": [], "factoryIds": []}],
        },
        headers=_headers(admin_access),
    )
    assert resp.status_code == 201, resp.get_json()
    user = resp.get_json()
    cleanup["users"].append(user["id"])

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.get_json()
    return user, login.get_json()["accessToken"]


def test_inventory_read_can_call_product_and_warehouse_and_bom_lookups(client, admin_access, cleanup):
    """The exact scenario that motivated this: a warehouse-scoped operational
    role (inventory:read, no product:read/warehouse:read/bom:read) must be
    able to resolve product/warehouse/BOM data for the pages it does have
    access to (Inventory, Production)."""
    role = _create_role(client, admin_access, cleanup, ["inventory:read"])
    _user, token = _create_user_with_role(client, admin_access, cleanup, role["id"])

    assert client.get("/api/v1/products", headers=_headers(token)).status_code == 200
    assert client.get("/api/v1/warehouses", headers=_headers(token)).status_code == 200
    assert client.get("/api/v1/boms", headers=_headers(token)).status_code == 200


def test_order_read_and_po_read_can_also_call_product_and_warehouse_lookups(client, admin_access, cleanup):
    role = _create_role(client, admin_access, cleanup, ["order:read", "po:read"])
    _user, token = _create_user_with_role(client, admin_access, cleanup, role["id"])

    assert client.get("/api/v1/products", headers=_headers(token)).status_code == 200
    assert client.get("/api/v1/warehouses", headers=_headers(token)).status_code == 200


def test_warehouse_read_alone_can_reach_every_grn_and_qc_page_dependency(client, admin_access, cleanup):
    """The GRN & QC page's own nav permission is warehouse:read (see
    frontend auth_state.py's NAV_ITEMS), not grn:read - so a role that can
    reach the page at all must also be able to use everything on it: the
    GRN list itself, plus the vendor (parties), PO and sticker-size pickers
    its Receive Goods form depends on."""
    role = _create_role(client, admin_access, cleanup, ["warehouse:read"])
    _user, token = _create_user_with_role(client, admin_access, cleanup, role["id"])

    assert client.get("/api/v1/grns", headers=_headers(token)).status_code == 200
    assert client.get("/api/v1/parties", headers=_headers(token)).status_code == 200
    assert client.get("/api/v1/purchase-orders", headers=_headers(token)).status_code == 200
    assert client.get("/api/v1/sticker-sizes", headers=_headers(token)).status_code == 200


def test_order_read_can_call_party_lookup(client, admin_access, cleanup):
    """Orders' customer search depends on the parties list."""
    role = _create_role(client, admin_access, cleanup, ["order:read"])
    _user, token = _create_user_with_role(client, admin_access, cleanup, role["id"])

    assert client.get("/api/v1/parties", headers=_headers(token)).status_code == 200


def test_po_read_can_call_party_and_business_entity_lookups(client, admin_access, cleanup):
    """Procurement's vendor list and its own-legal-entity picker depend on
    parties and business-entities respectively."""
    role = _create_role(client, admin_access, cleanup, ["po:read"])
    _user, token = _create_user_with_role(client, admin_access, cleanup, role["id"])

    assert client.get("/api/v1/parties", headers=_headers(token)).status_code == 200
    assert client.get("/api/v1/business-entities", headers=_headers(token)).status_code == 200


def test_user_read_can_call_factory_lookup(client, admin_access, cleanup):
    """Users & Roles' role-assignment site-scope picker depends on the
    factories list (the warehouses list was already covered above)."""
    role = _create_role(client, admin_access, cleanup, ["user:read"])
    _user, token = _create_user_with_role(client, admin_access, cleanup, role["id"])

    assert client.get("/api/v1/factories", headers=_headers(token)).status_code == 200
    assert client.get("/api/v1/warehouses", headers=_headers(token)).status_code == 200


def test_inventory_read_and_finance_read_can_call_order_lookup(client, admin_access, cleanup):
    """Production's Order Shipping tab and Finance's Invoices tab both
    depend on the orders list/detail endpoints."""
    inventory_role = _create_role(client, admin_access, cleanup, ["inventory:read"])
    _user, inventory_token = _create_user_with_role(client, admin_access, cleanup, inventory_role["id"])
    assert client.get("/api/v1/orders", headers=_headers(inventory_token)).status_code == 200

    finance_role = _create_role(client, admin_access, cleanup, ["finance:read"])
    _user, finance_token = _create_user_with_role(client, admin_access, cleanup, finance_role["id"])
    assert client.get("/api/v1/orders", headers=_headers(finance_token)).status_code == 200
    # A missing order correctly 404s rather than 403ing - proves the
    # permission check itself passed, not just that the route exists.
    assert client.get(f"/api/v1/orders/{uuid.uuid4()}", headers=_headers(finance_token)).status_code == 404
    assert client.get(f"/api/v1/orders/{uuid.uuid4()}/invoice/download", headers=_headers(finance_token)).status_code == 404


def test_unrelated_permission_still_cannot_call_these_lookups(client, admin_access, cleanup):
    """The broadening is scoped to specific operational permissions, not a
    blanket bypass for every authenticated user - a role with no relevant
    permission at all is still rejected, across every endpoint touched by
    this change."""
    role = _create_role(client, admin_access, cleanup, ["document:read"])
    _user, token = _create_user_with_role(client, admin_access, cleanup, role["id"])

    assert client.get("/api/v1/products", headers=_headers(token)).status_code == 403
    assert client.get("/api/v1/warehouses", headers=_headers(token)).status_code == 403
    assert client.get("/api/v1/boms", headers=_headers(token)).status_code == 403
    assert client.get("/api/v1/parties", headers=_headers(token)).status_code == 403
    assert client.get("/api/v1/business-entities", headers=_headers(token)).status_code == 403
    assert client.get("/api/v1/sticker-sizes", headers=_headers(token)).status_code == 403
    assert client.get("/api/v1/factories", headers=_headers(token)).status_code == 403
    assert client.get("/api/v1/purchase-orders", headers=_headers(token)).status_code == 403
    assert client.get("/api/v1/orders", headers=_headers(token)).status_code == 403
    assert client.get("/api/v1/grns", headers=_headers(token)).status_code == 403


def test_broadened_read_access_does_not_grant_write_access(client, admin_access, cleanup):
    """Only the read/lookup endpoints are broadened - creating/editing a
    product or warehouse still requires the module's own write permission."""
    role = _create_role(client, admin_access, cleanup, ["inventory:read"])
    _user, token = _create_user_with_role(client, admin_access, cleanup, role["id"])

    resp = client.post(
        "/api/v1/products",
        json={"name": "Should Be Rejected", "make": "Acme", "type": "raw_material", "uom": "KG"},
        headers=_headers(token),
    )
    assert resp.status_code == 403

    resp = client.post(
        "/api/v1/warehouses",
        json={"name": "Should Be Rejected", "code": f"REJ-{uuid.uuid4().hex[:8].upper()}"},
        headers=_headers(token),
    )
    assert resp.status_code == 403
