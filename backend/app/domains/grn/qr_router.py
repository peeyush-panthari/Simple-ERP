"""Inventory-item QR codes and sticker sheets: GET /inventory-items/{id}/qr,
POST /inventory-items/decode-qr, POST /inventory-items/{id}/vendor-qr,
GET /grns/{id}/qr-codes (zip of PNGs), GET /grns/{id}/qr-codes/pdf (sticker
sheet). Ported 1:1 (behavior) from the QR section of
backend_py/app/routes/grns.py (the hardware-scanner text path,
`/inventory-items/resolve-scan`, lives in grn/router.py).

Needs qrcode + Pillow (rendering) and zxing-cpp (photo decode); the sticker
sheet goes through document_pdf.html_to_pdf like every other PDF.
"""

from __future__ import annotations

import base64
import io
import math
import uuid as uuid_mod
import zipfile

import qrcode
import zxingcpp
from fastapi import APIRouter, Depends, Request, Response
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.access_scope import assert_warehouse_in_scope
from app.core.audit import audit
from app.core.auth import Actor, require_any_permission, require_permission
from app.core.config import settings
from app.core.db import session
from app.core.errors import bad_request, rule_violation
from app.domains.grn.router import _GRN_LOOKUP_PERMISSIONS, _require_inventory_item, _resolve_inventory_item_from_text
from app.models.grn import Grn
from app.models.sticker_size import StickerSize
from app.services import document_pdf, document_repo, grn_repo

router = APIRouter(prefix="/api/v1", tags=["grn"])


def _qr_with_label(qr_img, text: str):
    """Stamps the Inventory ID under the QR pattern, for a saved/printed
    copy that's no longer sitting next to the page's own on-screen label."""
    qr_img = qr_img.convert("RGB")
    font = ImageFont.load_default(size=28)
    measurer = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    left, top, right, bottom = measurer.textbbox((0, 0), text, font=font)
    text_w, text_h = right - left, bottom - top
    padding = 16
    canvas = Image.new("RGB", (qr_img.width, qr_img.height + text_h + padding * 2), "white")
    canvas.paste(qr_img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.text(((canvas.width - text_w) // 2 - left, qr_img.height + padding - top), text, fill="black", font=font)
    return canvas


# ---- sticker-size-aware QR/label sizing -------------------------------------
#
# A chosen Sticker Size template (Configuration > Sticker Size, picked on the
# Receive Goods form and stamped onto the GRN) drives how big the QR code and
# its caption are printed, so they read cleanly off a small sticker - between
# 70% and 80% of the sticker's own area, as large within that band as the
# sticker allows (bigger scans more reliably), never bigger than the sticker.

PX_PER_MM = 12  # ~300 DPI print resolution (304.8 dpi), rounded for simple math
_QR_MIN_COVERAGE = 0.70
_QR_MAX_COVERAGE = 0.80


def _qr_and_text_dimensions_mm(sticker_width_mm, sticker_height_mm) -> tuple[float, float]:
    """Returns (qr_side_mm, text_height_mm) for a sticker of the given size,
    sized so the QR code plus a one-line caption stacked directly under it
    together cover between _QR_MIN_COVERAGE and _QR_MAX_COVERAGE of the
    sticker's own area - as close to the top of that band as the sticker's
    own edges allow, never exceeding them.

    The QR is always square, so its side can never exceed the sticker's
    shorter dimension; on a sticker much wider than it is tall, that caps the
    achievable coverage well under 70% - accepted rather than relocating the
    caption: the physical fit always wins over the percentage target."""
    w, h = float(sticker_width_mm), float(sticker_height_mm)
    if w <= 0 or h <= 0:
        return (0.0, 0.0)
    sticker_area = w * h

    # Caption: legible but modest - an 18% slice of the sticker's height,
    # clamped so a tiny sticker still gets a readable minimum and a huge one
    # doesn't grow an oversized caption.
    text_height = max(1.5, min(h * 0.18, 6.0))

    max_qr_side = max(0.0, min(w, h - text_height))
    area_at_max = max_qr_side**2 + max_qr_side * text_height
    target_max_area = _QR_MAX_COVERAGE * sticker_area

    if area_at_max <= target_max_area:
        qr_side = max_qr_side
    else:
        # Solve qr^2 + qr*text_height - target_max_area = 0 for the positive
        # root, so the block lands exactly on the 80% ceiling.
        qr_side = (-text_height + math.sqrt(text_height**2 + 4 * target_max_area)) / 2
        qr_side = min(qr_side, max_qr_side)

    return (qr_side, text_height)


def _paginate_tiles(tiles: list, per_page: int) -> list[list]:
    """Splits `tiles` into pages of exactly `per_page` each (the last page
    holding whatever's left over) - a hard, explicit chunk rather than
    leaving it to the PDF engine's own overflow-based pagination."""
    per_page = max(1, per_page)
    return [tiles[i : i + per_page] for i in range(0, len(tiles), per_page)]


def _resolve_sticker_size_for_grn(tenant_id, grn: Grn | None) -> StickerSize | None:
    if not grn or not grn.sticker_size_id:
        return None
    return StickerSize.query.filter_by(tenant_id=tenant_id, id=grn.sticker_size_id).first()


def _fit_font(draw, text: str, *, max_width_px: int, max_height_px: int, initial_size: int):
    """Picks the largest font (down to a 6px floor) that renders `text` on
    one line within max_width_px x max_height_px - shrinks to the string's
    own measured box rather than trusting the initial guess, so a long
    Inventory ID on a narrow sticker is scaled down to actually fit."""
    size = max(6, initial_size)
    font = ImageFont.load_default(size=size)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = right - left, bottom - top
    scale = min(1.0, max_width_px / text_w if text_w > 0 else 1.0, max_height_px / text_h if text_h > 0 else 1.0)
    if scale < 1.0:
        size = max(6, int(size * scale))
        font = ImageFont.load_default(size=size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = right - left, bottom - top
    return font, left, top, text_w, text_h


def _render_qr_label_png(url: str, inventory_id: str, sticker: StickerSize | None):
    """Renders one QR with the Inventory ID captioned underneath, sized to
    `sticker` when given (the canvas is the sticker's own area at PX_PER_MM,
    QR+caption centered and covering 70-80% of it) or falling back to the
    original fixed pixel sizing when no Sticker Size was chosen for this
    item's GRN, so existing GRNs/behavior are unaffected."""
    if sticker is None:
        return _qr_with_label(qrcode.make(url, box_size=8, border=2), inventory_id)

    qr_side_mm, text_height_mm = _qr_and_text_dimensions_mm(sticker.sticker_width_mm, sticker.sticker_height_mm)
    canvas_w = max(1, round(float(sticker.sticker_width_mm) * PX_PER_MM))
    canvas_h = max(1, round(float(sticker.sticker_height_mm) * PX_PER_MM))
    qr_side_px = max(1, round(qr_side_mm * PX_PER_MM))
    text_height_px = max(1, round(text_height_mm * PX_PER_MM))

    qr_img = qrcode.make(url, box_size=10, border=1).convert("RGB").resize((qr_side_px, qr_side_px), Image.NEAREST)
    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(canvas)

    block_h = qr_side_px + text_height_px
    qr_x = (canvas_w - qr_side_px) // 2
    qr_y = max(0, (canvas_h - block_h) // 2)
    canvas.paste(qr_img, (qr_x, qr_y))

    font, left, top, text_w, text_h = _fit_font(draw, inventory_id, max_width_px=canvas_w, max_height_px=text_height_px, initial_size=round(text_height_px * 0.75))
    tx = (canvas_w - text_w) // 2 - left
    ty = qr_y + qr_side_px + max(0, (text_height_px - text_h) // 2) - top

    draw.text((tx, ty), inventory_id, fill="black", font=font)
    return canvas


@router.get("/inventory-items/{id}/qr")
def get_inventory_item_qr(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("inventory:read")), label: str | None = None):
    """Renders on demand rather than being stored at creation time: the QR
    payload is just this item's own id, so regenerating it is always
    byte-identical to whatever would have been persisted. ?label=1 stamps the
    Inventory ID underneath - used for the downloadable copy, not the inline
    on-page preview which already sits next to that label."""
    tenant_id = actor["tenant_id"]
    item = _require_inventory_item(tenant_id, id)
    assert_warehouse_in_scope(actor, item.warehouse_id)
    url = f"{settings.frontend_base_url}/inventory-item/{item.id}"
    if label:
        sticker = _resolve_sticker_size_for_grn(tenant_id, grn_repo.find_grn(tenant_id, item.grn_id))
        img = _render_qr_label_png(url, item.inventory_id, sticker)
    else:
        img = qrcode.make(url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=31536000, immutable"})


class DecodeInventoryQrBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    imageBase64: str = Field(min_length=1)


def _decode_qr_photo_text(image_base64: str) -> str:
    """Shared first half of every "photo of a QR code" upload flow: base64
    -> image -> whatever raw text zxingcpp reads out of it. What the *text*
    is expected to mean is entirely up to the caller (an internal
    /inventory-item/{uuid} URL for decode-qr, or arbitrary vendor-defined
    text for vendor-qr)."""
    try:
        raw = base64.b64decode(image_base64, validate=True)
    except Exception:
        raise bad_request("Could not read the uploaded photo", code="QR_IMAGE_INVALID")

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.load()
    except Exception:
        raise bad_request("Could not read the uploaded photo", code="QR_IMAGE_INVALID")

    results = zxingcpp.read_barcodes(image)
    text = results[0].text if results else ""
    if not text:
        raise rule_violation("No QR code found in that photo — center it, hold steady, and make sure it's in focus", code="QR_NOT_FOUND")
    return text


@router.post("/inventory-items/decode-qr")
def decode_inventory_item_qr(body: DecodeInventoryQrBody, actor: Actor = Depends(require_permission("inventory:read"))):
    """Server-side counterpart to get_inventory_item_qr(): given a photo of
    one of those QR codes (a picture taken with the device's own camera, not
    a live in-page scanner), decode it and resolve it back to the Inventory
    ID it encodes. Kept server-side rather than a client-side JS decoder so
    the scan flow is just another upload."""
    text = _decode_qr_photo_text(body.imageBase64)
    item = _resolve_inventory_item_from_text(actor["tenant_id"], actor, text)
    return grn_repo.to_inventory_item_api(item)


_VENDOR_QR_IMAGE_CONTENT_TYPE = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class VendorQrBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Exactly one of these two - a photo of the vendor's own QR sticker
    # (decoded server-side), or the Vendor Inventory ID typed in directly for
    # when the photo won't decode (a damaged label, bad lighting, ...).
    imageBase64: str | None = None
    vendorInventoryId: str | None = Field(default=None, max_length=120)

    @field_validator("vendorInventoryId")
    @classmethod
    def _trim(cls, v):
        v = v.strip() if v else v
        return v or None


@router.post("/inventory-items/{id}/vendor-qr")
def set_inventory_item_vendor_qr(id: uuid_mod.UUID, body: VendorQrBody, actor: Actor = Depends(require_permission("inventory:adjust"))):
    """Attaches the vendor's own identifier to one piece/lot - only offered
    for an item whose GRN had "Vendor's QR and ID" checked at receipt.
    Scanning the vendor's QR sticker decodes it and stores the raw text
    verbatim as vendorInventoryId - nothing about the decoded text is
    expected to match our own URL scheme."""
    tenant_id = actor["tenant_id"]
    item = _require_inventory_item(tenant_id, id)
    assert_warehouse_in_scope(actor, item.warehouse_id)

    if not item.vendor_qr_enabled:
        raise rule_violation(f"{item.inventory_id} wasn't received with \"Vendor's QR and ID\" enabled", code="VENDOR_QR_NOT_ENABLED")
    if not body.imageBase64 and not body.vendorInventoryId:
        raise rule_violation("Provide either a photo of the vendor's QR code or the Vendor Inventory ID directly", code="VENDOR_QR_INPUT_REQUIRED")

    if body.imageBase64:
        text = _decode_qr_photo_text(body.imageBase64)
        item.vendor_inventory_id = text
        try:
            image_format = Image.open(io.BytesIO(base64.b64decode(body.imageBase64, validate=True))).format or "JPEG"
        except Exception:
            image_format = "JPEG"
        content_type = _VENDOR_QR_IMAGE_CONTENT_TYPE.get(image_format, "image/jpeg")
        document_repo.upload_document(
            tenant_id,
            filename=f"{item.inventory_id}-vendor-qr.{image_format.lower()}",
            content_type=content_type,
            content_base64=body.imageBase64,
            related_type="inventory_item_vendor_qr",
            related_id=str(item.id),
            created_by=str(actor["user_id"]),
        )
    else:
        item.vendor_inventory_id = body.vendorInventoryId

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="inventory-item.vendor-qr-set", entity_type="inventory-item", entity_id=str(item.id), meta={"inventoryId": item.inventory_id, "vendorInventoryId": item.vendor_inventory_id})
    session.commit()
    return grn_repo.to_inventory_item_api(item)


@router.get("/grns/{id}/qr-codes")
def get_grn_qr_codes(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission(*_GRN_LOOKUP_PERMISSIONS))):
    """One labelled QR PNG per inventory item on this GRN, zipped - the QC
    screen's "download all" for whoever is printing stickers for a batch of
    pieces/lots instead of opening each one's own detail page."""
    tenant_id = actor["tenant_id"]
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    items = list(grn_repo.grn_items(id))
    sticker = _resolve_sticker_size_for_grn(tenant_id, grn)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            url = f"{settings.frontend_base_url}/inventory-item/{item.id}"
            img = _render_qr_label_png(url, item.inventory_id, sticker)
            img_buf = io.BytesIO()
            img.save(img_buf, format="PNG")
            zf.writestr(f"{item.inventory_id}.png", img_buf.getvalue())
    return Response(content=buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={grn.number}-qr-codes.zip"})


@router.get("/grns/{id}/qr-codes/pdf")
def get_grn_qr_codes_pdf(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission(*_GRN_LOOKUP_PERMISSIONS))):
    """One sticker sheet: every inventory item's QR code (the Inventory ID
    captioned underneath) tiled across as many pages as it takes - for
    printing onto sticker stock rather than opening/saving one PNG per item.
    Laid out to the GRN's own Sticker Size template (page size, column/row
    grid, margins, gaps) when one was chosen at receipt; otherwise falls back
    to the original fixed 5mm QR / A4 / 10mm-margin layout, unchanged."""
    tenant_id = actor["tenant_id"]
    grn = grn_repo.require_grn(tenant_id, id)
    assert_warehouse_in_scope(actor, grn.warehouse_id)
    items = grn_repo.grn_items(id)
    sticker = _resolve_sticker_size_for_grn(tenant_id, grn)

    tiles = []
    for item in items:
        url = f"{settings.frontend_base_url}/inventory-item/{item.id}"
        img = qrcode.make(url, box_size=8, border=1)
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        b64 = base64.b64encode(img_buf.getvalue()).decode("ascii")
        tiles.append(f'<div class="tile"><img class="qr" src="data:image/png;base64,{b64}"><div class="label">{item.inventory_id}</div></div>')

    if sticker is None:
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  @page {{ size: A4; margin: 10mm; }}
  body {{ margin: 0; }}
  .tile {{ display: inline-block; vertical-align: top; text-align: center; margin: 1mm; }}
  .qr {{ display: block; width: 5mm; height: 5mm; }}
  .label {{ font-size: 2mm; line-height: 1.4; white-space: nowrap; font-family: monospace; }}
</style></head>
<body>{"".join(tiles)}</body></html>"""
    else:
        qr_side_mm, text_height_mm = _qr_and_text_dimensions_mm(sticker.sticker_width_mm, sticker.sticker_height_mm)
        # CSS can't shrink-to-fit text the way _fit_font does for the PNG
        # renderer, so approximate: every Inventory ID is a fixed-width
        # "INV-######" (10 chars) - cap the font so 10 monospace characters
        # (~0.62 of font-size each) still fit within the sticker's width.
        font_size_mm = min(text_height_mm * 0.75, float(sticker.sticker_width_mm) / (10 * 0.62))

        # One .sheet per page, each holding exactly columns*rows tiles with a
        # forced page break after it - CSS grid's own auto-flow has no concept
        # of "this many rows, then a new page", so left to overflow naturally
        # it could end up with an extra row per page, or split a row's tiles
        # across two pages entirely.
        pages = _paginate_tiles(tiles, sticker.columns * sticker.rows)
        sheets = "".join(f'<div class="sheet">{"".join(page)}</div>' for page in pages)

        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  @page {{ size: {sticker.page_width_mm}mm {sticker.page_height_mm}mm; margin: 0; }}
  body {{ margin: 0; }}
  .sheet {{
    padding: {sticker.margin_top_mm}mm {sticker.margin_right_mm}mm {sticker.margin_bottom_mm}mm {sticker.margin_left_mm}mm;
    display: grid;
    grid-template-columns: repeat({sticker.columns}, {sticker.sticker_width_mm}mm);
    grid-template-rows: repeat({sticker.rows}, {sticker.sticker_height_mm}mm);
    column-gap: {sticker.gap_horizontal_mm}mm;
    row-gap: {sticker.gap_vertical_mm}mm;
    overflow: hidden;
    break-after: page;
    page-break-after: always;
  }}
  .sheet:last-child {{ break-after: auto; page-break-after: auto; }}
  .tile {{ width: {sticker.sticker_width_mm}mm; height: {sticker.sticker_height_mm}mm; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow: hidden; margin: 0; }}
  .qr {{ display: block; width: {qr_side_mm:.2f}mm; height: {qr_side_mm:.2f}mm; flex-shrink: 0; }}
  .label {{ font-size: {font_size_mm:.2f}mm; line-height: 1; white-space: nowrap; font-family: monospace; margin-top: {text_height_mm * 0.15:.2f}mm; }}
</style></head>
<body>{sheets}</body></html>"""

    result = document_pdf.html_to_pdf(html)
    extension = "pdf" if result["engine"] != "html" else "html"
    return Response(content=result["body"], media_type=result["content_type"], headers={"Content-Disposition": f"attachment; filename={grn.number}-qr-codes.{extension}"})
