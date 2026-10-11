"""PO "short close" - force-closes a PO with an outstanding balance instead
of waiting for the remaining quantity to ever be received. See
purchase_orders.py's short_close_po() route."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def draft_po(app, default_tenant_id):
    """A single-line PO left at 'draft' - no receiving flow needed for the
    "can't short-close a draft PO" case."""
    from app.models.party import Party
    from app.models.po_line import PoLine
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        product = Product(tenant_id=default_tenant_id, sku=f"TST-SC-{suffix}", name="Short Close Test RM", type="raw_material", uom="KG", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-SC-{suffix}", legal_name="Short Close Vendor", display_name="Short Close Vendor", type="vendor", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-SC-{suffix}", name="Short Close Test Warehouse", status="active")
        _db.session.add_all([product, vendor, warehouse])
        _db.session.flush()

        po = PurchaseOrder(
            tenant_id=default_tenant_id, number=f"PO-SC-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name,
            warehouse_id=warehouse.id, warehouse_code=warehouse.code, status="draft", expected_date=date.today() + timedelta(days=1),
        )
        _db.session.add(po)
        _db.session.flush()
        line = PoLine(tenant_id=default_tenant_id, po_id=po.id, line_no=1, product_id=product.id, sku=product.sku, quantity=Decimal("10"), uom=product.uom, unit_price=Decimal("50"), tax_code="NA")
        _db.session.add(line)
        _db.session.commit()

        yield {"po_id": po.id}

        PoLine.query.filter_by(po_id=po.id).delete(synchronize_session=False)
        PurchaseOrder.query.filter_by(id=po.id).delete(synchronize_session=False)
        Product.query.filter_by(id=product.id).delete(synchronize_session=False)
        Party.query.filter_by(id=vendor.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def issued_po(app, default_tenant_id):
    """A single-line, issued/receivable PO - ordered qty 10, so a 5-qty
    receipt leaves it partially_received and a 10-qty receipt leaves it
    fully received."""
    from app.models.location import Location
    from app.models.party import Party
    from app.models.po_line import PoLine
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        product = Product(tenant_id=default_tenant_id, sku=f"TST-SC2-{suffix}", name="Short Close Test RM 2", type="raw_material", uom="KG", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-SC2-{suffix}", legal_name="Short Close Vendor 2", display_name="Short Close Vendor 2", type="vendor", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-SC2-{suffix}", name="Short Close Test Warehouse 2", status="active")
        _db.session.add_all([product, vendor, warehouse])
        _db.session.flush()

        quarantine = Location(tenant_id=default_tenant_id, warehouse_id=warehouse.id, code=f"QTN-{suffix}", type="quarantine", status="active")
        _db.session.add(quarantine)
        _db.session.flush()

        po = PurchaseOrder(
            tenant_id=default_tenant_id, number=f"PO-SC2-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name,
            warehouse_id=warehouse.id, warehouse_code=warehouse.code, status="issued", expected_date=date.today() + timedelta(days=1),
        )
        _db.session.add(po)
        _db.session.flush()
        line = PoLine(tenant_id=default_tenant_id, po_id=po.id, line_no=1, product_id=product.id, sku=product.sku, quantity=Decimal("10"), uom=product.uom, unit_price=Decimal("50"), tax_code="NA")
        _db.session.add(line)
        _db.session.commit()

        yield {"po_id": po.id, "warehouse_id": warehouse.id, "line_id": line.id}

        from app.models.grn import Grn
        from app.models.grn_line import GrnLine
        from app.models.inventory_item import InventoryItem
        from app.models.stock_balance import StockBalance
        from app.models.stock_ledger import StockLedger

        grn_ids = [g.id for g in Grn.query.filter_by(po_id=po.id).all()]
        InventoryItem.query.filter(InventoryItem.grn_id.in_(grn_ids)).delete(synchronize_session=False)
        GrnLine.query.filter(GrnLine.grn_id.in_(grn_ids)).delete(synchronize_session=False)
        Grn.query.filter(Grn.id.in_(grn_ids)).delete(synchronize_session=False)
        StockLedger.query.filter_by(product_id=product.id).delete(synchronize_session=False)
        StockBalance.query.filter_by(product_id=product.id).delete(synchronize_session=False)
        PoLine.query.filter_by(po_id=po.id).delete(synchronize_session=False)
        PurchaseOrder.query.filter_by(id=po.id).delete(synchronize_session=False)
        Location.query.filter_by(id=quarantine.id).delete(synchronize_session=False)
        Product.query.filter_by(id=product.id).delete(synchronize_session=False)
        Party.query.filter_by(id=vendor.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _receive_and_post(client, headers, issued_po, qty):
    """Full receive -> QC-accept -> auto-post flow, mirroring
    test_grn_finished_good_conversion.py's pattern."""
    grn_resp = client.post(
        "/api/v1/grns",
        json={
            "poId": str(issued_po["po_id"]),
            "warehouseId": str(issued_po["warehouse_id"]),
            "invoiceNumber": f"INV-{uuid.uuid4().hex[:8].upper()}",
            "lines": [{"poLineId": str(issued_po["line_id"]), "receivedQty": qty}],
        },
        headers=headers,
    )
    assert grn_resp.status_code == 201, grn_resp.get_json()
    grn = grn_resp.get_json()
    grn_line_id = grn["lines"][0]["id"]

    qc_resp = client.post(
        f"/api/v1/grns/{grn['id']}/qc",
        json={"items": [], "lines": [{"lineId": grn_line_id, "acceptedQty": qty, "rejectedQty": "0"}]},
        headers=headers,
    )
    assert qc_resp.status_code == 200, qc_resp.get_json()
    assert qc_resp.get_json()["status"] == "posted"


def test_short_close_from_draft_is_rejected(client, admin_access, draft_po):
    resp = client.post(
        f"/api/v1/purchase-orders/{draft_po['po_id']}/short-close",
        json={"reason": "Testing short close from draft"},
        headers={"Authorization": f"Bearer {admin_access}"},
    )
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "PO_STATE_INVALID"


def test_short_close_partially_received_po_succeeds_and_blocks_further_grns(client, admin_access, issued_po):
    headers = {"Authorization": f"Bearer {admin_access}"}
    _receive_and_post(client, headers, issued_po, "4")

    resp = client.post(
        f"/api/v1/purchase-orders/{issued_po['po_id']}/short-close",
        json={"reason": "Vendor cannot supply the remaining balance"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "closed"

    # Further receiving against the now-closed PO is blocked.
    blocked = client.post(
        "/api/v1/grns",
        json={
            "poId": str(issued_po["po_id"]),
            "warehouseId": str(issued_po["warehouse_id"]),
            "invoiceNumber": f"INV-{uuid.uuid4().hex[:8].upper()}",
            "lines": [{"poLineId": str(issued_po["line_id"]), "receivedQty": "1"}],
        },
        headers=headers,
    )
    assert blocked.status_code == 422, blocked.get_json()
    assert blocked.get_json()["code"] == "PO_NOT_RECEIVABLE"


def test_short_close_fully_received_po_is_rejected(client, admin_access, issued_po):
    headers = {"Authorization": f"Bearer {admin_access}"}
    _receive_and_post(client, headers, issued_po, "10")

    resp = client.post(
        f"/api/v1/purchase-orders/{issued_po['po_id']}/short-close",
        json={"reason": "Nothing left to close"},
        headers=headers,
    )
    assert resp.status_code == 422, resp.get_json()
    assert resp.get_json()["code"] == "PO_FULLY_RECEIVED"


def test_short_close_requires_permission(app, client, default_tenant_id, issued_po):
    """A role without po:short_close (but with everything else) gets 403."""
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.session import Session
    from app.models.user import User
    from app.models.user_role import UserRole
    from app.core.security import hash_password

    email = f"short-close-test-{uuid.uuid4().hex[:8]}@example.test"
    password = "TestShortClose#Passw0rd1"

    with app.app_context():
        role = Role(tenant_id=default_tenant_id, name=f"No Short Close {uuid.uuid4().hex[:8]}", status="active")
        _db.session.add(role)
        _db.session.flush()
        for perm in ("po:read", "po:write", "po:issue"):
            _db.session.add(RolePermission(role_id=role.id, permission=perm))
        user = User(tenant_id=default_tenant_id, email=email, display_name="Short Close Test", status="active", password_hash=hash_password(password))
        _db.session.add(user)
        _db.session.flush()
        _db.session.add(UserRole(user_id=user.id, role_id=role.id))
        _db.session.commit()
        user_id, role_id = user.id, role.id

    try:
        login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.get_json()
        token = login.get_json()["accessToken"]

        resp = client.post(
            f"/api/v1/purchase-orders/{issued_po['po_id']}/short-close",
            json={"reason": "Should not be allowed"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, resp.get_json()
    finally:
        with app.app_context():
            Session.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            UserRole.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            User.query.filter_by(id=user_id).delete(synchronize_session=False)
            RolePermission.query.filter_by(role_id=role_id).delete(synchronize_session=False)
            Role.query.filter_by(id=role_id).delete(synchronize_session=False)
            _db.session.commit()
