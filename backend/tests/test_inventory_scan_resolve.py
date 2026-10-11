"""POST /inventory-items/resolve-scan - the text-only counterpart to
decode-qr, for a hardware (HID keyboard-emulation) QR/barcode scanner: it
types the QR's raw text directly, so there's no photo to decode. Backs
"Scan to Jump" boxes and the passive scan-to-add listener on Production
forms. See grns.py's _resolve_inventory_item_from_text /
resolve_inventory_item_scan."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def po_fixture(app, default_tenant_id):
    from app.models.location import Location
    from app.models.party import Party
    from app.models.product import Product
    from app.models.po_line import PoLine
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        product = Product(tenant_id=default_tenant_id, sku=f"TST-SCN-{suffix}", name="Scan Resolve Test RM", type="raw_material", uom="KG", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-SCN-{suffix}", legal_name="Scan Resolve Test Vendor", display_name="Scan Resolve Test Vendor", type="vendor", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-SCN-{suffix}", name="Scan Resolve Test Warehouse", status="active")
        other_warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH2-SCN-{suffix}", name="Scan Resolve Test Warehouse 2", status="active")
        _db.session.add_all([product, vendor, warehouse, other_warehouse])
        _db.session.flush()

        quarantine = Location(tenant_id=default_tenant_id, warehouse_id=warehouse.id, code=f"QTN-{suffix}", type="quarantine", status="active")
        _db.session.add(quarantine)
        _db.session.flush()

        po = PurchaseOrder(
            tenant_id=default_tenant_id, number=f"PO-SCN-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name,
            warehouse_id=warehouse.id, warehouse_code=warehouse.code, status="issued", expected_date=date.today() + timedelta(days=1),
        )
        _db.session.add(po)
        _db.session.flush()
        line = PoLine(tenant_id=default_tenant_id, po_id=po.id, line_no=1, product_id=product.id, sku=product.sku, quantity=Decimal("10"), uom=product.uom, unit_price=Decimal("50"), tax_code="NA")
        _db.session.add(line)
        _db.session.commit()

        yield {"po_id": po.id, "line_id": line.id, "warehouse_id": warehouse.id, "other_warehouse_id": other_warehouse.id}

        from app.models.grn import Grn
        from app.models.grn_line import GrnLine
        from app.models.inventory_item import InventoryItem

        grn_ids = [g.id for g in Grn.query.filter_by(po_id=po.id).all()]
        InventoryItem.query.filter(InventoryItem.grn_id.in_(grn_ids)).delete(synchronize_session=False)
        GrnLine.query.filter(GrnLine.grn_id.in_(grn_ids)).delete(synchronize_session=False)
        Grn.query.filter(Grn.id.in_(grn_ids)).delete(synchronize_session=False)
        PoLine.query.filter_by(po_id=po.id).delete(synchronize_session=False)
        PurchaseOrder.query.filter_by(id=po.id).delete(synchronize_session=False)
        Location.query.filter_by(id=quarantine.id).delete(synchronize_session=False)
        Product.query.filter_by(id=product.id).delete(synchronize_session=False)
        Party.query.filter_by(id=vendor.id).delete(synchronize_session=False)
        Warehouse.query.filter(Warehouse.id.in_([warehouse.id, other_warehouse.id])).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _receive(client, headers, fx):
    body = {
        "poId": str(fx["po_id"]),
        "warehouseId": str(fx["warehouse_id"]),
        "invoiceNumber": f"INV-{uuid.uuid4().hex[:8]}",
        "lines": [{"poLineId": str(fx["line_id"]), "receivedQty": "1"}],
    }
    return client.post("/api/v1/grns", json=body, headers=headers)


def _first_item(client, headers, grn_id):
    resp = client.get("/api/v1/inventory-items", query_string={"grnId": grn_id}, headers=headers)
    return resp.get_json()["data"][0]


def test_resolving_our_own_qr_url_text_returns_the_item(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn = _receive(client, headers, po_fixture).get_json()
    item = _first_item(client, headers, grn["id"])

    resp = client.post("/api/v1/inventory-items/resolve-scan", json={"text": f"http://localhost:3001/inventory-item/{item['id']}"}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["id"] == item["id"]
    assert resp.get_json()["inventoryId"] == item["inventoryId"]


def test_resolving_a_plain_inventory_id_returns_the_item(client, admin_access, po_fixture):
    """"Scan to Jump" also accepts the bare Inventory ID text (not just one
    of our QR URLs) - someone may just type the id printed under the QR
    rather than scan it."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn = _receive(client, headers, po_fixture).get_json()
    item = _first_item(client, headers, grn["id"])

    resp = client.post("/api/v1/inventory-items/resolve-scan", json={"text": item["inventoryId"]}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["id"] == item["id"]


def test_resolving_a_plain_inventory_id_is_case_insensitive_and_trims_whitespace(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn = _receive(client, headers, po_fixture).get_json()
    item = _first_item(client, headers, grn["id"])

    resp = client.post("/api/v1/inventory-items/resolve-scan", json={"text": f"  {item['inventoryId'].lower()}  "}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["id"] == item["id"]


def test_resolving_unrecognized_text_is_rejected(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    _receive(client, headers, po_fixture)

    resp = client.post("/api/v1/inventory-items/resolve-scan", json={"text": "not a simple_erp url at all"}, headers=headers)
    assert resp.status_code == 422
    assert resp.get_json()["code"] == "QR_NOT_RECOGNIZED"


def test_resolving_a_wellformed_but_nonexistent_item_id_404s(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    _receive(client, headers, po_fixture)

    resp = client.post("/api/v1/inventory-items/resolve-scan", json={"text": f"http://localhost:3001/inventory-item/{uuid.uuid4()}"}, headers=headers)
    assert resp.status_code == 404


def test_resolving_an_item_outside_warehouse_scope_is_rejected(client, admin_access, po_fixture):
    """A site-scoped user shouldn't be able to jump to an item outside
    their assigned warehouse(s) just by scanning its QR."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn = _receive(client, headers, po_fixture).get_json()
    item = _first_item(client, headers, grn["id"])

    role_resp = client.post(
        "/api/v1/roles", json={"name": f"Scan Scope Test Role {uuid.uuid4().hex[:8]}", "permissions": ["inventory:read"]}, headers=headers,
    )
    assert role_resp.status_code == 201, role_resp.get_json()
    role = role_resp.get_json()

    email = f"scan-scope-{uuid.uuid4().hex[:8]}@example.test"
    password = "TestScoped#Passw0rd1"
    user_resp = client.post(
        "/api/v1/users",
        json={
            "email": email, "displayName": "Scan Scope Test", "password": password, "status": "active",
            "roles": [{"roleId": role["id"], "warehouseIds": [str(po_fixture["other_warehouse_id"])], "factoryIds": []}],
        },
        headers=headers,
    )
    assert user_resp.status_code == 201, user_resp.get_json()
    user = user_resp.get_json()

    scoped_login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    scoped_headers = {"Authorization": f"Bearer {scoped_login.get_json()['accessToken']}"}

    resp = client.post("/api/v1/inventory-items/resolve-scan", json={"text": f"http://localhost:3001/inventory-item/{item['id']}"}, headers=scoped_headers)
    assert resp.status_code == 403

    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.session import Session
    from app.models.user import User
    from app.models.user_role import UserRole
    from app.models.user_role_warehouse import UserRoleWarehouse

    with client.application.app_context():
        user_id = uuid.UUID(user["id"])
        role_id = uuid.UUID(role["id"])
        UserRoleWarehouse.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        UserRole.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        Session.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        User.query.filter_by(id=user_id).delete(synchronize_session=False)
        RolePermission.query.filter_by(role_id=role_id).delete(synchronize_session=False)
        Role.query.filter_by(id=role_id).delete(synchronize_session=False)
        _db.session.commit()
