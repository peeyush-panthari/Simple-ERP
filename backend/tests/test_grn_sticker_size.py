"""GRN "Sticker Size" field (Receive Goods form) and the QR/label endpoints
sizing themselves against it - see grns.py's GrnBody.stickerSizeId,
_resolve_sticker_size_for_grn, _render_qr_label_png and
get_grn_qr_codes_pdf."""

import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.flaskcompat import db as _db


@pytest.fixture
def po_and_sticker_size(app, default_tenant_id):
    from app.models.location import Location
    from app.models.party import Party
    from app.models.po_line import PoLine
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.sticker_size import StickerSize
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        product = Product(tenant_id=default_tenant_id, sku=f"TST-STK-{suffix}", name="Sticker Size Test RM", type="raw_material", uom="KG", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-STK-{suffix}", legal_name="Sticker Size Test Vendor", display_name="Sticker Size Test Vendor", type="vendor", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-STK-{suffix}", name="Sticker Size Test Warehouse", status="active")
        sticker = StickerSize(
            tenant_id=default_tenant_id, name=f"Test Label {suffix}", page_size="A4",
            page_width_mm=Decimal("210"), page_height_mm=Decimal("297"),
            sticker_width_mm=Decimal("50"), sticker_height_mm=Decimal("30"),
            columns=3, rows=8,
            margin_left_mm=Decimal("5"), margin_right_mm=Decimal("5"), margin_top_mm=Decimal("10"), margin_bottom_mm=Decimal("10"),
            gap_horizontal_mm=Decimal("2"), gap_vertical_mm=Decimal("2"),
        )
        _db.session.add_all([product, vendor, warehouse, sticker])
        _db.session.flush()

        quarantine = Location(tenant_id=default_tenant_id, warehouse_id=warehouse.id, code=f"QTN-{suffix}", type="quarantine", status="active")
        _db.session.add(quarantine)
        _db.session.flush()

        po = PurchaseOrder(
            tenant_id=default_tenant_id, number=f"PO-STK-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name,
            warehouse_id=warehouse.id, warehouse_code=warehouse.code, status="issued", expected_date=date.today() + timedelta(days=1),
        )
        _db.session.add(po)
        _db.session.flush()
        line = PoLine(tenant_id=default_tenant_id, po_id=po.id, line_no=1, product_id=product.id, sku=product.sku, quantity=Decimal("10"), uom=product.uom, unit_price=Decimal("50"), tax_code="NA")
        _db.session.add(line)
        _db.session.commit()

        yield {
            "po_id": po.id, "line_id": line.id, "warehouse_id": warehouse.id, "sticker_id": sticker.id,
            "sticker_width_mm": Decimal("50"), "sticker_height_mm": Decimal("30"),
            "po_number": po.number, "sticker_name": sticker.name, "sku": product.sku,
        }

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
        StickerSize.query.filter_by(id=sticker.id).delete(synchronize_session=False)
        Product.query.filter_by(id=product.id).delete(synchronize_session=False)
        Party.query.filter_by(id=vendor.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


@pytest.fixture
def admin_access(client, fresh_admin):
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    return resp.get_json()["accessToken"]


def _receive(client, headers, fx, *, with_sticker_size: bool, invoice_number: str):
    body = {
        "poId": str(fx["po_id"]),
        "warehouseId": str(fx["warehouse_id"]),
        "invoiceNumber": invoice_number,
        "lines": [{"poLineId": str(fx["line_id"]), "receivedQty": "1"}],
    }
    if with_sticker_size:
        body["stickerSizeId"] = str(fx["sticker_id"])
    return client.post("/api/v1/grns", json=body, headers=headers)


def test_grn_stores_and_serializes_the_chosen_sticker_size(client, admin_access, po_and_sticker_size):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_and_sticker_size, with_sticker_size=True, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert data["stickerSizeId"] == str(po_and_sticker_size["sticker_id"])
    assert data["stickerSizeName"] is not None

    get_resp = client.get(f"/api/v1/grns/{data['id']}", headers=headers)
    assert get_resp.get_json()["stickerSizeId"] == str(po_and_sticker_size["sticker_id"])


def test_grn_without_sticker_size_leaves_it_null(client, admin_access, po_and_sticker_size):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_and_sticker_size, with_sticker_size=False, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert data["stickerSizeId"] is None
    assert data["stickerSizeName"] is None


def test_unknown_sticker_size_is_rejected(client, admin_access, po_and_sticker_size):
    headers = {"Authorization": f"Bearer {admin_access}"}
    body = {
        "poId": str(po_and_sticker_size["po_id"]),
        "warehouseId": str(po_and_sticker_size["warehouse_id"]),
        "invoiceNumber": f"INV-{uuid.uuid4().hex[:8]}",
        "stickerSizeId": str(uuid.uuid4()),
        "lines": [{"poLineId": str(po_and_sticker_size["line_id"]), "receivedQty": "1"}],
    }
    resp = client.post("/api/v1/grns", json=body, headers=headers)
    assert resp.status_code == 404


def test_labelled_qr_png_is_sized_to_the_chosen_sticker(client, admin_access, po_and_sticker_size):
    from PIL import Image

    from app.domains.grn.qr_router import PX_PER_MM

    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_and_sticker_size, with_sticker_size=True, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    grn = resp.get_json()

    items_resp = client.get("/api/v1/inventory-items", query_string={"grnId": grn["id"]}, headers=headers)
    item = items_resp.get_json()["data"][0]

    qr_resp = client.get(f"/api/v1/inventory-items/{item['id']}/qr", query_string={"label": "1"}, headers=headers)
    assert qr_resp.status_code == 200
    assert qr_resp.content_type == "image/png"

    import io

    img = Image.open(io.BytesIO(qr_resp.data))
    expected_w = round(float(po_and_sticker_size["sticker_width_mm"]) * PX_PER_MM)
    expected_h = round(float(po_and_sticker_size["sticker_height_mm"]) * PX_PER_MM)
    assert img.size == (expected_w, expected_h)


def test_grn_qr_codes_zip_still_works_with_a_sticker_size_chosen(client, admin_access, po_and_sticker_size):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_and_sticker_size, with_sticker_size=True, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    grn = resp.get_json()

    zip_resp = client.get(f"/api/v1/grns/{grn['id']}/qr-codes", headers=headers)
    assert zip_resp.status_code == 200
    assert zip_resp.content_type == "application/zip"
    assert len(zip_resp.data) > 0


def test_grn_qr_codes_pdf_uses_the_stickers_own_page_layout(client, admin_access, po_and_sticker_size):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_and_sticker_size, with_sticker_size=True, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    grn = resp.get_json()

    pdf_resp = client.get(f"/api/v1/grns/{grn['id']}/qr-codes/pdf", headers=headers)
    assert pdf_resp.status_code == 200
    # In the test environment (no Gotenberg/WeasyPrint), document_pdf falls
    # back to a raw HTML passthrough - inspect that HTML directly to
    # confirm the sticker's own page size actually drove the layout,
    # rather than the legacy fixed-A4/5mm fallback.
    if pdf_resp.content_type.startswith("text/html"):
        body = pdf_resp.data.decode("utf-8")
        assert re.search(r"210(\.00)?mm 297(\.00)?mm", body)
        assert re.search(r"grid-template-columns: repeat\(3, 50(\.00)?mm\)", body)


def test_grn_qr_codes_pdf_without_sticker_size_keeps_legacy_layout(client, admin_access, po_and_sticker_size):
    headers = {"Authorization": f"Bearer {admin_access}"}
    resp = _receive(client, headers, po_and_sticker_size, with_sticker_size=False, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")
    grn = resp.get_json()

    pdf_resp = client.get(f"/api/v1/grns/{grn['id']}/qr-codes/pdf", headers=headers)
    assert pdf_resp.status_code == 200
    if pdf_resp.content_type.startswith("text/html"):
        body = pdf_resp.data.decode("utf-8")
        assert "size: A4; margin: 10mm" in body


@pytest.fixture
def po_and_small_grid_sticker(app, default_tenant_id):
    """A serialised (UNIT) product + a sticker sized for a 2x2 = 4-per-page
    grid, so receiving more than 4 pieces exercises real pagination - see
    test_pdf_paginates_exactly_at_the_stickers_own_rows_per_page below."""
    from app.models.location import Location
    from app.models.party import Party
    from app.models.po_line import PoLine
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.sticker_size import StickerSize
    from app.models.warehouse import Warehouse

    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        product = Product(tenant_id=default_tenant_id, sku=f"TST-PG-{suffix}", name="Pagination Test RM", type="raw_material", uom="UNIT", status="active")
        vendor = Party(tenant_id=default_tenant_id, code=f"VEN-PG-{suffix}", legal_name="Pagination Test Vendor", display_name="Pagination Test Vendor", type="vendor", status="active")
        warehouse = Warehouse(tenant_id=default_tenant_id, code=f"WH-PG-{suffix}", name="Pagination Test Warehouse", status="active")
        # 2 columns x 2 rows fits comfortably on an A4 page even with
        # generous margins/gaps - _assert_layout_fits (sticker_sizes.py)
        # would reject this fixture outright if it didn't.
        sticker = StickerSize(
            tenant_id=default_tenant_id, name=f"Pagination Label {suffix}", page_size="A4",
            page_width_mm=Decimal("210"), page_height_mm=Decimal("297"),
            sticker_width_mm=Decimal("40"), sticker_height_mm=Decimal("40"),
            columns=2, rows=2,
            margin_left_mm=Decimal("5"), margin_right_mm=Decimal("5"), margin_top_mm=Decimal("5"), margin_bottom_mm=Decimal("5"),
            gap_horizontal_mm=Decimal("2"), gap_vertical_mm=Decimal("2"),
        )
        _db.session.add_all([product, vendor, warehouse, sticker])
        _db.session.flush()

        quarantine = Location(tenant_id=default_tenant_id, warehouse_id=warehouse.id, code=f"QTN-{suffix}", type="quarantine", status="active")
        _db.session.add(quarantine)
        _db.session.flush()

        po = PurchaseOrder(
            tenant_id=default_tenant_id, number=f"PO-PG-{suffix}", vendor_id=vendor.id, vendor_name=vendor.display_name,
            warehouse_id=warehouse.id, warehouse_code=warehouse.code, status="issued", expected_date=date.today() + timedelta(days=1),
        )
        _db.session.add(po)
        _db.session.flush()
        line = PoLine(tenant_id=default_tenant_id, po_id=po.id, line_no=1, product_id=product.id, sku=product.sku, quantity=Decimal("10"), uom=product.uom, unit_price=Decimal("50"), tax_code="NA")
        _db.session.add(line)
        _db.session.commit()

        yield {"po_id": po.id, "line_id": line.id, "warehouse_id": warehouse.id, "sticker_id": sticker.id}

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
        StickerSize.query.filter_by(id=sticker.id).delete(synchronize_session=False)
        Product.query.filter_by(id=product.id).delete(synchronize_session=False)
        Party.query.filter_by(id=vendor.id).delete(synchronize_session=False)
        Warehouse.query.filter_by(id=warehouse.id).delete(synchronize_session=False)
        _db.session.commit()


def test_paginate_tiles_chunks_exactly_at_columns_times_rows():
    """Regression test for a real bug: printing a GRN whose sticker
    template says 2 columns x 2 rows (4 tiles/page) for 5 received pieces
    used to let the browser/PDF engine's own overflow-based pagination
    decide row boundaries (unaware of the template's declared row count),
    which could fit an extra row on page one and then split a row's tiles
    across two pages. Tiles must instead land in hard-chunked pages of
    exactly columns*rows each - unit-tested directly against the pure
    chunking function so it doesn't depend on which PDF engine (if any)
    this environment happens to have available."""
    from app.domains.grn.qr_router import _paginate_tiles

    tiles = [f"tile-{i}" for i in range(5)]
    pages = _paginate_tiles(tiles, per_page=4)  # 2 columns x 2 rows
    assert [len(p) for p in pages] == [4, 1]
    assert pages[0] == tiles[:4]
    assert pages[1] == tiles[4:]


def test_paginate_tiles_exact_multiple_has_no_trailing_empty_page():
    from app.domains.grn.qr_router import _paginate_tiles

    tiles = [f"tile-{i}" for i in range(8)]
    pages = _paginate_tiles(tiles, per_page=4)
    assert [len(p) for p in pages] == [4, 4]


def test_pdf_paginates_exactly_at_the_stickers_own_rows_per_page(client, admin_access, po_and_small_grid_sticker):
    """End-to-end smoke test alongside the unit test above - when this
    environment's PDF engine falls back to the raw HTML passthrough (no
    Gotenberg/WeasyPrint), the generated markup itself is inspectable."""
    fx = po_and_small_grid_sticker
    headers = {"Authorization": f"Bearer {admin_access}"}
    body = {
        "poId": str(fx["po_id"]),
        "warehouseId": str(fx["warehouse_id"]),
        "invoiceNumber": f"INV-{uuid.uuid4().hex[:8]}",
        "stickerSizeId": str(fx["sticker_id"]),
        "lines": [{"poLineId": str(fx["line_id"]), "receivedQty": "5"}],
    }
    resp = client.post("/api/v1/grns", json=body, headers=headers)
    assert resp.status_code == 201, resp.get_json()
    grn = resp.get_json()

    pdf_resp = client.get(f"/api/v1/grns/{grn['id']}/qr-codes/pdf", headers=headers)
    assert pdf_resp.status_code == 200
    if not pdf_resp.content_type.startswith("text/html"):
        pytest.skip("A real PDF engine (Gotenberg/WeasyPrint) is available in this environment - see the unit tests above for the engine-independent assertion")

    html = pdf_resp.data.decode("utf-8")
    assert html.count('<div class="sheet">') == 2  # 5 tiles at 4/page -> 2 pages
    sheets = html.split('<div class="sheet">')[1:]
    tiles_per_sheet = [sheet.count('<div class="tile">') for sheet in sheets]
    assert tiles_per_sheet == [4, 1]
    assert "break-after: page" in html


def _bulk_upload_csv(fx, *, sticker_name: str, vendor_qr_enabled: str, grn_ref: str, invoice_number: str) -> str:
    header = (
        "grnRef,poNumber,receivedDate,vehicleNumber,deliveryNote,gateEntryNo,invoiceNumber,notes,"
        "stickerSizeName,vendorQrEnabled,lineSku,receivedQty,batchNo,expiryDate,manufactureDate,locationCode"
    )
    row = f"{grn_ref},{fx['po_number']},,,,,{invoice_number},,{sticker_name},{vendor_qr_enabled},{fx['sku']},10,,,,"
    return f"{header}\n{row}\n"


def test_bulk_upload_resolves_sticker_size_name_and_vendor_qr_flag(client, admin_access, po_and_sticker_size):
    """bulk_upload_grns() resolves stickerSizeName/vendorQrEnabled into the
    same GrnBody.stickerSizeId/vendorQrEnabled the interactive Receive Goods
    form sends - see grns.py's BULK_UPLOAD_ALL_COLUMNS."""
    fx = po_and_sticker_size
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn_ref = f"BULK-{uuid.uuid4().hex[:8]}"
    csv_content = _bulk_upload_csv(fx, sticker_name=fx["sticker_name"], vendor_qr_enabled="true", grn_ref=grn_ref, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")

    resp = client.post("/api/v1/grns/bulk-upload", json={"csvContent": csv_content}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    result = resp.get_json()
    assert result["summary"]["successCount"] == 1, result
    grn_number = result["results"][0]["grnNumber"]

    list_resp = client.get("/api/v1/grns", query_string={"poId": str(fx["po_id"])}, headers=headers)
    grn = next(g for g in list_resp.get_json()["data"] if g["number"] == grn_number)
    assert grn["stickerSizeId"] == str(fx["sticker_id"])
    assert grn["hasVendorQr"] is True


def test_bulk_upload_without_sticker_size_or_vendor_qr_leaves_them_at_defaults(client, admin_access, po_and_sticker_size):
    fx = po_and_sticker_size
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn_ref = f"BULK-{uuid.uuid4().hex[:8]}"
    csv_content = _bulk_upload_csv(fx, sticker_name="", vendor_qr_enabled="", grn_ref=grn_ref, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")

    resp = client.post("/api/v1/grns/bulk-upload", json={"csvContent": csv_content}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    result = resp.get_json()
    assert result["summary"]["successCount"] == 1, result
    grn_number = result["results"][0]["grnNumber"]

    list_resp = client.get("/api/v1/grns", query_string={"poId": str(fx["po_id"])}, headers=headers)
    grn = next(g for g in list_resp.get_json()["data"] if g["number"] == grn_number)
    assert grn["stickerSizeId"] is None
    assert grn["hasVendorQr"] is False


def test_bulk_upload_unknown_sticker_size_name_is_reported_as_a_row_error(client, admin_access, po_and_sticker_size):
    fx = po_and_sticker_size
    headers = {"Authorization": f"Bearer {admin_access}"}
    grn_ref = f"BULK-{uuid.uuid4().hex[:8]}"
    csv_content = _bulk_upload_csv(fx, sticker_name="No Such Sticker Template", vendor_qr_enabled="false", grn_ref=grn_ref, invoice_number=f"INV-{uuid.uuid4().hex[:8]}")

    resp = client.post("/api/v1/grns/bulk-upload", json={"csvContent": csv_content}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    result = resp.get_json()
    assert result["summary"]["errorCount"] == 1, result
    assert "No Such Sticker Template" in result["results"][0]["error"]
