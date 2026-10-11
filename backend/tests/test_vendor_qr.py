"""GRN "Vendor's QR and ID" checkbox (Receive Goods form) and the
POST /inventory-items/<id>/vendor-qr endpoint it unlocks - see grns.py's
GrnBody.vendorQrEnabled, InventoryItem.vendor_qr_enabled/vendor_inventory_id,
and set_inventory_item_vendor_qr."""

import base64
import io
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import qrcode

from tests.flaskcompat import db as _db


@pytest.fixture
def po_fixture(app, default_tenant_id):
    from app.models.location import Location
    from app.models.party import Party
    from app.models.po_line import PoLine
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        product = Product(tenant_id=default_tenant_id, sku=f"TST-VQR-{suffix}", name="Vendor QR Test RM", type="raw_material", uom="KG", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-VQR-{suffix}", legal_name="Vendor QR Test Vendor", display_name="Vendor QR Test Vendor", type="vendor", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-VQR-{suffix}", name="Vendor QR Test Warehouse", status="active")
        _db.session.add_all([product, vendor, warehouse])
        _db.session.flush()

        quarantine = Location(tenant_id=default_tenant_id, warehouse_id=warehouse.id, code=f"QTN-{suffix}", type="quarantine", status="active")
        _db.session.add(quarantine)
        _db.session.flush()

        po = PurchaseOrder(
            tenant_id=default_tenant_id, number=f"PO-VQR-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name,
            warehouse_id=warehouse.id, warehouse_code=warehouse.code, status="issued", expected_date=date.today() + timedelta(days=1),
        )
        _db.session.add(po)
        _db.session.flush()
        line = PoLine(tenant_id=default_tenant_id, po_id=po.id, line_no=1, product_id=product.id, sku=product.sku, quantity=Decimal("10"), uom=product.uom, unit_price=Decimal("50"), tax_code="NA")
        _db.session.add(line)
        _db.session.commit()

        yield {"po_id": po.id, "line_id": line.id, "warehouse_id": warehouse.id}

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
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _receive(client, headers, fx, *, vendor_qr_enabled: bool):
    body = {
        "poId": str(fx["po_id"]),
        "warehouseId": str(fx["warehouse_id"]),
        "invoiceNumber": f"INV-{uuid.uuid4().hex[:8]}",
        "vendorQrEnabled": vendor_qr_enabled,
        "lines": [{"poLineId": str(fx["line_id"]), "receivedQty": "1"}],
    }
    return client.post("/api/v1/grns", json=body, headers=headers)


def _qr_photo_base64(text: str) -> str:
    img = qrcode.make(text, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _first_item(client, headers, grn_id):
    resp = client.get("/api/v1/inventory-items", query_string={"grnId": grn_id}, headers=headers)
    return resp.get_json()["data"][0]


def test_grn_stamps_vendor_qr_enabled_onto_its_items(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_fixture, vendor_qr_enabled=True)
    assert resp.status_code == 201, resp.get_json()
    grn = resp.get_json()
    assert grn["hasVendorQr"] is True

    item = _first_item(client, headers, grn["id"])
    assert item["vendorQrEnabled"] is True
    assert item["vendorInventoryId"] is None


def test_grn_without_the_checkbox_leaves_items_unenabled(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_fixture, vendor_qr_enabled=False)
    grn = resp.get_json()
    assert grn["hasVendorQr"] is False

    item = _first_item(client, headers, grn["id"])
    assert item["vendorQrEnabled"] is False


def test_setting_vendor_id_manually_when_not_enabled_is_rejected(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_fixture, vendor_qr_enabled=False)
    grn = resp.get_json()
    item = _first_item(client, headers, grn["id"])

    set_resp = client.post(f"/api/v1/inventory-items/{item['id']}/vendor-qr", json={"vendorInventoryId": "VENDOR-SN-001"}, headers=headers)
    assert set_resp.status_code == 422
    assert set_resp.get_json()["code"] == "VENDOR_QR_NOT_ENABLED"


def test_setting_vendor_id_manually_when_enabled_succeeds(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_fixture, vendor_qr_enabled=True)
    grn = resp.get_json()
    item = _first_item(client, headers, grn["id"])

    set_resp = client.post(f"/api/v1/inventory-items/{item['id']}/vendor-qr", json={"vendorInventoryId": "  VENDOR-SN-001  "}, headers=headers)
    assert set_resp.status_code == 200, set_resp.get_json()
    assert set_resp.get_json()["vendorInventoryId"] == "VENDOR-SN-001"  # trimmed


def test_neither_photo_nor_manual_id_is_rejected(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_fixture, vendor_qr_enabled=True)
    grn = resp.get_json()
    item = _first_item(client, headers, grn["id"])

    set_resp = client.post(f"/api/v1/inventory-items/{item['id']}/vendor-qr", json={}, headers=headers)
    assert set_resp.status_code == 422
    assert set_resp.get_json()["code"] == "VENDOR_QR_INPUT_REQUIRED"


def test_uploading_a_photo_of_a_real_qr_decodes_it_as_the_vendor_id(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_fixture, vendor_qr_enabled=True)
    grn = resp.get_json()
    item = _first_item(client, headers, grn["id"])

    # This vendor's QR encodes their own arbitrary serial scheme, not one
    # of our /inventory-item/{uuid} URLs - decoding it must not try to
    # resolve it against our own inventory at all, just return the text.
    photo = _qr_photo_base64("VENDOR-LOT-77712-BATCH-A")
    set_resp = client.post(f"/api/v1/inventory-items/{item['id']}/vendor-qr", json={"imageBase64": photo}, headers=headers)
    assert set_resp.status_code == 200, set_resp.get_json()
    assert set_resp.get_json()["vendorInventoryId"] == "VENDOR-LOT-77712-BATCH-A"

    # And it's actually persisted, not just echoed back.
    get_resp = client.get(f"/api/v1/inventory-items/{item['id']}", headers=headers)
    assert get_resp.get_json()["vendorInventoryId"] == "VENDOR-LOT-77712-BATCH-A"


def test_uploading_a_photo_of_our_own_inventory_item_qr_still_just_stores_its_url_text(client, admin_access, po_fixture):
    """Confirms set_inventory_item_vendor_qr never tries to resolve the
    decoded text against our own inventory (unlike decode_inventory_item_qr)
    - even a photo of one of our own QR codes is stored verbatim as
    whatever text it decodes to."""
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_fixture, vendor_qr_enabled=True)
    grn = resp.get_json()
    item = _first_item(client, headers, grn["id"])

    photo = _qr_photo_base64(f"https://simple.example/inventory-item/{item['id']}")
    set_resp = client.post(f"/api/v1/inventory-items/{item['id']}/vendor-qr", json={"imageBase64": photo}, headers=headers)
    assert set_resp.status_code == 200, set_resp.get_json()
    assert set_resp.get_json()["vendorInventoryId"] == f"https://simple.example/inventory-item/{item['id']}"


def test_photo_with_no_qr_code_is_rejected(client, admin_access, po_fixture):
    from PIL import Image

    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_fixture, vendor_qr_enabled=True)
    grn = resp.get_json()
    item = _first_item(client, headers, grn["id"])

    blank = Image.new("RGB", (200, 200), "white")
    buf = io.BytesIO()
    blank.save(buf, format="PNG")
    photo = base64.b64encode(buf.getvalue()).decode("ascii")

    set_resp = client.post(f"/api/v1/inventory-items/{item['id']}/vendor-qr", json={"imageBase64": photo}, headers=headers)
    assert set_resp.status_code == 422
    assert set_resp.get_json()["code"] == "QR_NOT_FOUND"


def test_garbage_image_data_is_rejected(client, admin_access, po_fixture):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_fixture, vendor_qr_enabled=True)
    grn = resp.get_json()
    item = _first_item(client, headers, grn["id"])

    set_resp = client.post(f"/api/v1/inventory-items/{item['id']}/vendor-qr", json={"imageBase64": base64.b64encode(b"not an image").decode("ascii")}, headers=headers)
    assert set_resp.status_code == 400
    assert set_resp.get_json()["code"] == "QR_IMAGE_INVALID"
