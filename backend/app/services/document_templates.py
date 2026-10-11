"""PDF document templates - ported 1:1 from domain/templates.ts.

Plain Python functions building HTML strings, NOT a data-driven template
engine (Jinja etc.) - matches Node's own explicit design philosophy, quoted
verbatim from the original file: "a PO or invoice is a legal document, and a
compile error is a much better failure mode than a silently blank field."
This is a different mechanism from notification_render.py's mini-language -
don't unify them.

Two templates here (goods_receipt, logistics_note) have zero real callers in
this rewrite (same as in Node) - ported anyway as inert contract surface.
"""

from __future__ import annotations


from app.core.config import settings
from app.services.gst_states import state_name_for
from app.core.money import DecimalError, round_dp, to_decimal
from app.services.number_words import amount_in_words_inr


def _frange(start: float, stop: float, step: float):
    x = start
    while x <= stop:
        yield x
        x += step


def simple_logo_svg(height: str = "34px") -> str:
    """The Simple ERP mark (same artwork as frontend/public/logo.svg), inline so PDFs need no image fetch."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" style="height:{height};width:auto" role="img" aria-label="Simple ERP logo">'
        '<defs><linearGradient id="sl" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0e7490"/><stop offset="1" stop-color="#1d4ed8"/></linearGradient></defs>'
        '<rect width="100" height="100" rx="24" fill="url(#sl)"/>'
        '<path d="M69 34C67 26 60 22 50 22C39 22 31 28 31 36C31 44 38 47 50 50C62 53 69 56 69 64C69 72 61 78 50 78C39 78 32 73 30 66" fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="79" cy="21" r="5.5" fill="#10b981"/></svg>'
    )


def _group_in(int_part: str) -> str:
    """Indian digit grouping: keep the last 3 digits, comma-group the rest
    in pairs from the right. E.g. "1234567" -> "12,34,567"."""
    if len(int_part) <= 3:
        return int_part
    rest, last3 = int_part[:-3], int_part[-3:]
    parts: list[str] = []
    i = len(rest)
    while i > 0:
        j = max(i - 2, 0)
        parts.append(rest[j:i])
        i = j
    parts.reverse()
    return f"{','.join(parts)},{last3}"


def _format_rate(value) -> str:
    """E.g. Decimal("18.000000") -> "18", Decimal("2.500000") -> "2.5" - a
    tax rate stored with fixed 6dp precision, trimmed for display."""
    try:
        d = to_decimal(value or 0)
    except (DecimalError, TypeError, ValueError):
        return "0"
    text = format(d.normalize(), "f")
    return text if text != "-0" else "0"


def format_money(value, currency: str = "INR", symbol: str | None = None) -> str:
    """None/invalid -> em-dash. Otherwise Decimal-exact (never float),
    rounded half-up to 2dp, Indian-grouped. E.g. "INR 12,34,567.50", or with
    an explicit symbol (e.g. "₹") in place of the "<currency> " prefix."""
    if value is None:
        return "—"
    try:
        d = round_dp(value, 2)
    except (DecimalError, TypeError, ValueError):
        return "—"
    negative = d < 0
    d = abs(d)
    int_part, _, frac_part = format(d, "f").partition(".")
    frac_part = (frac_part + "00")[:2]
    sign = "-" if negative else ""
    prefix = symbol if symbol is not None else f"{currency} "
    return f"{prefix}{sign}{_group_in(int_part)}.{frac_part}"


def esc(value) -> str:
    """HTML-escapes only &amp;/&lt;/&gt; - deliberately NOT the same escape
    set as notification_render.py's escape_html (which also escapes quotes).
    Safe as-is since this is only ever used inside text nodes, never inside
    an HTML attribute value."""
    s = "" if value is None else str(value)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_SHELL_CSS = """
@page { size: A4 portrait; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; color: #0f172a; font-size: 11px; margin: 0; }
.head { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #0f172a; padding-bottom: 12px; }
.brand { font-size: 17px; font-weight: 700; letter-spacing: -0.01em; }
.muted { color: #64748b; }
.doc-title { text-align: right; }
.doc-title h1 { margin: 0; font-size: 20px; letter-spacing: -0.02em; }
.grid { display: flex; gap: 24px; margin: 18px 0; }
.grid > div { flex: 1; }
.label { text-transform: uppercase; letter-spacing: 0.08em; font-size: 8.5px; color: #64748b; margin-bottom: 4px; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; }
th { background: #f1f5f9; text-align: left; padding: 7px 8px; font-size: 8.5px; text-transform: uppercase; letter-spacing: 0.06em; color: #475569; border-bottom: 1px solid #cbd5e1; }
td { padding: 7px 8px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.totals { margin-left: auto; width: 260px; margin-top: 12px; }
.totals td { border: none; padding: 4px 8px; }
.totals .grand td { border-top: 2px solid #0f172a; font-weight: 700; font-size: 13px; padding-top: 8px; }
.foot { margin-top: 26px; padding-top: 10px; border-top: 1px solid #e2e8f0; font-size: 9px; color: #64748b; }

/* Purchase-order-specific boxed layout, matching a standard Indian PO's
   bordered-grid look - deliberately not reusing .grid/.label/table above,
   which are tuned for the lighter invoice layout instead. */
.po-title { text-align: center; margin: 4px 0 14px; }
.po-title h1 { display: inline-block; font-size: 15px; letter-spacing: 0.04em; text-decoration: underline; margin: 0; }
.po-outer { border: 1px solid #0f172a; border-collapse: collapse; margin-top: 0; }
.po-outer td { border: 1px solid #0f172a; padding: 6px 8px; vertical-align: top; font-size: 10px; }
.po-label { font-weight: 700; text-decoration: underline; font-size: 9px; }
.po-items th { background: #d8b4c8; text-align: left; padding: 6px 8px; font-size: 9px; border: 1px solid #0f172a; }
.po-items td { border: 1px solid #0f172a; padding: 5px 8px; font-size: 10px; }
.po-items .totals-row td { font-weight: 700; }
.po-full { border: 1px solid #0f172a; border-top: none; padding: 6px 8px; font-size: 10px; }
"""


def shell(title: str, body: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{esc(title)}</title><style>{_SHELL_CSS}</style></head><body>{body}</body></html>"""


def _format_address(entity: dict) -> str:
    line3 = ", ".join(p for p in [entity.get("city"), entity.get("stateCode"), entity.get("postalCode")] if p)
    return ", ".join(p for p in [entity.get("addressLine1"), entity.get("addressLine2"), line3] if p)


def header(title: str, number: str, meta: list[tuple[str, str]], seller: dict | None = None) -> str:
    """`seller` is the Foundation > PO & Invoice business entity resolved for
    this document (the tenant's default, or one explicitly picked) - falls
    back to the single tenant-wide settings.company_* identity when no
    business entity has been configured yet."""
    name = seller.get("name") if seller else None
    address = _format_address(seller) if seller else None
    tax_id = seller.get("taxId") if seller else None
    pan = seller.get("pan") if seller else None
    pan_html = f'<div class="muted">PAN {esc(pan)}</div>' if pan else ""
    meta_html = "".join(f'<div class="muted">{esc(label)}: {esc(value)}</div>' for label, value in meta if value)
    return f"""
<div class="head">
  <div>
    <div class="brand">{esc(name or settings.company_name)}</div>
    <div class="muted">{esc(address or settings.company_address)}</div>
    <div class="muted">GSTIN {esc(tax_id or settings.company_gstin)}</div>
    {pan_html}
  </div>
  <div class="doc-title">
    <h1>{esc(title)}</h1>
    <div class="muted">{esc(number)}</div>
    {meta_html}
  </div>
</div>
"""


def line_table(lines: list[dict], currency: str) -> str:
    rows = "".join(
        f"""<tr>
  <td style="width:14%">{esc(l.get("sku"))}</td>
  <td>{esc(l.get("description"))}</td>
  <td class="num" style="width:12%">{esc(l.get("quantity"))} {esc(l.get("uom"))}</td>
  <td class="num" style="width:13%">{format_money(l.get("unitPrice"), currency)}</td>
  <td class="num" style="width:8%">{esc(l.get("taxRate") if l.get("taxRate") is not None else 0)}%</td>
  <td class="num" style="width:15%">{format_money(l.get("grossAmount"), currency)}</td>
</tr>"""
        for l in lines
    )
    return f"""
<table>
  <thead><tr><th>SKU</th><th>Description</th><th class="num">Quantity</th><th class="num">Unit price</th><th class="num">Tax</th><th class="num">Amount</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
"""


def totals(rows: list[tuple[str, str]], grand: tuple[str, str], currency: str) -> str:
    row_html = "".join(f"<tr><td>{esc(label)}</td><td class=\"num\">{format_money(value, currency)}</td></tr>" for label, value in rows)
    grand_label, grand_value = grand
    return f"""
<table class="totals">
  {row_html}
  <tr class="grand"><td>{esc(grand_label)}</td><td class="num">{format_money(grand_value, currency)}</td></tr>
</table>
"""


def _address_lines_html(entity: dict) -> str:
    """E.g. "Bengaluru, Karnataka 560037" - city and state comma-separated,
    postal code space-separated after the state (no comma), matching the
    reference template's convention. Accepts either a business-entity-shaped
    dict (addressLine1/addressLine2/postalCode) or a party-address-shaped
    one (line1/line2/postalCode, e.g. party_summary.py's billing/shipping
    address) - both carry the same city/stateCode/postalCode keys."""
    parts = [entity.get("addressLine1") or entity.get("line1"), entity.get("addressLine2") or entity.get("line2")]
    state_name = state_name_for(entity.get("stateCode"))
    city_state = ", ".join(p for p in [entity.get("city"), state_name] if p)
    line3 = f"{city_state} {entity['postalCode']}".strip() if entity.get("postalCode") else city_state
    if line3:
        parts.append(line3)
    return "".join(f"<div>{esc(p)}</div>" for p in parts if p)


def purchase_order(d: dict) -> str:
    """A faithful bordered-grid layout matching a standard Indian purchase
    order (Invoice To / PO details / Supplier / Ship To boxes, then a line
    table with Sub Total, CGST+SGST or IGST, Grand Total, and the amount in
    words) - a deliberately different visual style from the lighter
    header()/grid() layout the other templates share, since this one is
    reproducing a specific reference template rather than a generic one."""
    currency = d.get("currency") or "INR"
    seller = d.get("seller") or {}
    vendor = d.get("vendor") or {}
    delivery = d.get("deliveryAddress") or {}
    lines = d.get("lines") or []

    try:
        revision_html = f'<div>Revision: {int(to_decimal(d.get("revision")))}</div>' if to_decimal(d.get("revision") or 0) > 0 else ""
    except (DecimalError, TypeError, ValueError):
        revision_html = ""

    seller_state_code = seller.get("stateCode")
    vendor_state_code = vendor.get("stateCode")
    intra_state = bool(seller_state_code and vendor_state_code and seller_state_code == vendor_state_code)

    cgst = d.get("cgst")
    sgst = d.get("sgst")
    igst = d.get("igst")
    try:
        tax_rate = to_decimal(lines[0].get("taxRate")) if lines else to_decimal(0)
    except (DecimalError, TypeError, ValueError):
        tax_rate = to_decimal(0)
    half_rate = round_dp(tax_rate / 2, 2) if tax_rate else to_decimal(0)

    if intra_state:
        gst_rows_html = f"""
<tr><td colspan="4" class="num"><b>CGST@{_format_rate(half_rate)}%</b></td><td class="num">{format_money(cgst, currency)}</td></tr>
<tr><td colspan="4" class="num"><b>SGST@{_format_rate(half_rate)}%</b></td><td class="num">{format_money(sgst, currency)}</td></tr>"""
    else:
        gst_rows_html = f"""
<tr><td colspan="4" class="num"><b>IGST@{_format_rate(tax_rate)}%</b></td><td class="num">{format_money(igst, currency)}</td></tr>"""

    line_rows_html = "".join(
        f"""<tr>
  <td>{i + 1}</td>
  <td>{esc(l.get("description") or l.get("sku"))}</td>
  <td class="num">{esc(l.get("quantity"))}</td>
  <td class="num">{format_money(l.get("unitPrice"), currency)}</td>
  <td>{esc(l.get("uom"))}</td>
  <td class="num">{format_money(l.get("netAmount"), currency)}</td>
</tr>"""
        for i, l in enumerate(lines)
    )

    seller_html = f"""
<div class="po-label">Invoice To:-</div>
<div><b>{esc(seller.get("name") or settings.company_name)}</b></div>
{_address_lines_html(seller) or f'<div>{esc(settings.company_address)}</div>'}
<div>GSTIN:{esc(seller.get("taxId") or settings.company_gstin)}</div>
<div>State Name: {esc(state_name_for(seller_state_code) or "—")}, Code:{esc(seller_state_code or "—")}</div>
"""

    vendor_html = f"""
<div class="po-label">Supplier (Bill from):</div>
<div><b>{esc(vendor.get("name"))}</b></div>
{_address_lines_html(vendor)}
"""

    ship_html = f"""
<div class="po-label">Ship To</div>
<div><b>{esc(delivery.get("name") or d.get("warehouse"))}</b></div>
{_address_lines_html(delivery)}
"""

    notes_html = f"""
<div class="po-full">
  <div class="po-label">Other Terms and Conditions:</div>
  <div>{esc(d.get("notes"))}</div>
</div>""" if d.get("notes") else ""

    body = f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">{simple_logo_svg()}</div>
<div class="po-title"><h1>PURCHASE ORDER</h1></div>
<table class="po-outer" style="width:100%;">
  <tr>
    <td rowspan="3" style="width:55%">{seller_html}</td>
    <td style="width:23%"><span class="po-label">Purchase order No:</span>{esc(d.get("number"))}</td>
    <td style="width:22%"><span class="po-label">Date:</span> {esc(d.get("poDate"))}</td>
  </tr>
  <tr>
    <td colspan="2">
      <div><span class="po-label">Mode of Payment:</span> {esc(d.get("paymentMode") or "—")}</div>
      <div><span class="po-label">Terms of Payment:</span> {esc(d.get("paymentTerms") or "—")}</div>
      {revision_html}
    </td>
  </tr>
  <tr>
    <td colspan="2">&nbsp;</td>
  </tr>
  <tr>
    <td>{vendor_html}</td>
    <td colspan="2">&nbsp;</td>
  </tr>
  <tr>
    <td>{ship_html}</td>
    <td colspan="2"><span class="po-label">Expected Delivery:</span> {esc(d.get("expectedDate") or "—")}</td>
  </tr>
</table>
<table class="po-items" style="width:100%;border-collapse:collapse;">
  <thead>
    <tr><th>Sl.No.</th><th>Description of Goods</th><th>Quantity</th><th>Rate</th><th>per</th><th>Amount</th></tr>
  </thead>
  <tbody>
    {line_rows_html}
    <tr class="totals-row"><td colspan="4" class="num"><b>Sub Total</b></td><td class="num">{format_money(d.get("subtotal"), currency)}</td></tr>
    {gst_rows_html}
    <tr class="totals-row"><td colspan="4" class="num"><b>Grand Total</b></td><td class="num">{format_money(d.get("total"), currency)}</td></tr>
  </tbody>
</table>
<div class="po-full"><b>Amount Chargeable (in words)</b>: <i>{esc(amount_in_words_inr(d.get("total")))}</i></div>
{notes_html}
<div class="po-full">
  Company Pan: <b>{esc(seller.get("pan") or "—")}</b><br/>
  For {esc(seller.get("name") or settings.company_name)}<br/>
  Digitally created
</div>
<div class="foot" style="text-align:center;">This is a system generated document and does not need signature</div>
"""
    return shell(f"Purchase order {d.get('number')}", body)


def customer_invoice(d: dict) -> str:
    """A faithful bordered-grid TAX INVOICE layout matching Simple's real
    reference invoice (Bill From/Bill To/Ship To boxes, a per-line HSN/Qty/
    Rate/GST-split item table, amount in words, and the issuing business
    entity's own bank details for payment) - the invoice counterpart of
    purchase_order()'s reference-template reproduction, sharing its
    .po-outer/.po-items/.po-label/.po-full bordered-grid CSS since both are
    the same style of formal GST document."""
    currency = d.get("currency") or "INR"
    money = lambda v: format_money(v, currency, symbol="₹" if currency == "INR" else None)  # noqa: E731

    seller = d.get("seller") or {}
    bill_to = d.get("billTo") or {}
    ship_to = d.get("shipTo") or {}
    lines = d.get("lines") or []
    intra_state = bool(d.get("intraState"))

    seller_html = f"""
<div class="po-label">BILL FROM</div>
<div><b>{esc(seller.get("name") or settings.company_name)}</b></div>
{_address_lines_html(seller) or f'<div>{esc(settings.company_address)}</div>'}
<div>GST No: {esc(seller.get("taxId") or settings.company_gstin)}</div>
<div>PAN: {esc(seller.get("pan") or "—")}</div>
"""

    bill_to_html = f"""
<div class="po-label">BILL TO</div>
<div><b>{esc(bill_to.get("name"))}</b></div>
{_address_lines_html(bill_to)}
<div>GSTIN: {esc(bill_to.get("taxId") or "—")}</div>
"""

    ship_to_html = f"""
<div class="po-label">SHIP TO</div>
<div><b>{esc(ship_to.get("name") or bill_to.get("name"))}</b></div>
{_address_lines_html(ship_to) or _address_lines_html(bill_to)}
<div>GSTIN: {esc(ship_to.get("taxId") or bill_to.get("taxId") or "—")}</div>
"""

    qty_total = to_decimal(0)
    line_rows_html = ""
    for i, l in enumerate(lines):
        qty = to_decimal(l.get("quantity") or 0)
        qty_total += qty
        rate = _format_rate(l.get("taxRate"))
        if intra_state:
            igst_pct, sgst_pct, cgst_pct = "0", rate, rate
        else:
            igst_pct, sgst_pct, cgst_pct = rate, "0", "0"
        description = l.get("description")
        item = f"{esc(l.get('sku'))} ({esc(description)})" if description else esc(l.get("sku"))
        line_rows_html += f"""<tr>
  <td>{i + 1}</td>
  <td>{item}</td>
  <td>{esc(l.get("hsnCode") or "—")}</td>
  <td class="num">{_format_rate(qty)} {esc(l.get("uom") or "")}</td>
  <td class="num">{money(l.get("unitPrice"))}</td>
  <td class="num">{money(l.get("netAmount"))}</td>
  <td class="num">{igst_pct}%</td>
  <td class="num">{sgst_pct}%</td>
  <td class="num">{cgst_pct}%</td>
  <td class="num">{money(l.get("grossAmount"))}</td>
</tr>"""

    gst = d.get("gst") or {}
    # Bank details come straight off the resolved business entity
    # (org_repo.resolve_seller / to_business_entity_api) - same seller dict
    # the BILL FROM block above reads name/address/GST/PAN from.
    bank_name = seller.get("bankName")
    bank_branch = seller.get("bankBranch")
    bank_account = seller.get("bankAccountNumber")
    bank_ifsc = seller.get("bankIfsc")
    bank_html = (
        f"""
<div class="po-full">
  <div class="po-label">Bank details for payment:</div>
  <div>Name- {esc(seller.get("name") or settings.company_name)}</div>
  <div>Bank and Branch- {esc(bank_name or "—")}{f", {esc(bank_branch)}" if bank_branch else ""}</div>
  <div>A/C No- {esc(bank_account or "—")} IFSC Code- {esc(bank_ifsc or "—")}</div>
</div>"""
        if bank_name or bank_account
        else ""
    )

    body = f"""
<div style="display:flex;justify-content:flex-end;margin-bottom:6px;">{simple_logo_svg()}</div>
<table class="po-outer" style="width:100%;">
  <tr>
    <td rowspan="2" style="width:55%">{seller_html}</td>
    <td style="width:45%;text-align:right;"><span style="font-size:20px;font-weight:700;letter-spacing:0.04em;">TAX INVOICE</span></td>
  </tr>
  <tr>
    <td>
      <div><span class="po-label">Invoice No :</span> {esc(d.get("number"))}</div>
      <div><span class="po-label">Invoice date :</span> {esc(d.get("invoiceDate"))}</div>
      <div><span class="po-label">PO No :</span> {esc(d.get("poNumber") or "")}</div>
      <div><span class="po-label">PO Date :</span> {esc(d.get("poDate") or "")}</div>
    </td>
  </tr>
  <tr>
    <td>{bill_to_html}</td>
    <td>{ship_to_html}</td>
  </tr>
</table>
<table class="po-items" style="width:100%;border-collapse:collapse;">
  <thead>
    <tr><th>S No</th><th>Item and Description</th><th>HSN</th><th>Qty</th><th>Rate</th><th>Basic Amount</th><th>IGST</th><th>SGST</th><th>CGST</th><th>Amount</th></tr>
  </thead>
  <tbody>
    {line_rows_html}
    <tr class="totals-row">
      <td colspan="3"><b>TOTALS</b></td>
      <td class="num">{_format_rate(qty_total)}</td>
      <td class="num">&nbsp;</td>
      <td class="num">{money(d.get("subtotal"))}</td>
      <td class="num">{money(gst.get("igst"))}</td>
      <td class="num">{money(gst.get("sgst"))}</td>
      <td class="num">{money(gst.get("cgst"))}</td>
      <td class="num">{money(d.get("total"))}</td>
    </tr>
  </tbody>
</table>
<div class="po-full"><b>Amount in words</b>: <i>{esc(amount_in_words_inr(d.get("total")))}</i></div>
{bank_html}
<div class="foot" style="text-align:center;">This is Electronically generated Invoice, Signature not needed</div>
"""
    return shell(f"Invoice {d.get('number')}", body)


def goods_receipt(d: dict) -> str:
    """No real caller in this rewrite (same as Node) - ported for contract
    completeness only. No money formatting - quantities only."""
    lines = d.get("lines") or []
    rows = "".join(
        f"""<tr>
  <td>{esc(l.get("sku"))}</td>
  <td>{esc(l.get("batchNo") or "—")}</td>
  <td class="num">{esc(l.get("quantity"))} {esc(l.get("uom"))}</td>
  <td class="num">{esc(l.get("acceptedQty"))}</td>
  <td class="num">{esc(l.get("rejectedQty"))}</td>
</tr>"""
        for l in lines
    )
    meta = [("Date", d.get("receivedDate")), ("Against", d.get("poNumber"))]
    body = f"""
{header("Goods receipt note", str(d.get("number")), meta)}
<div class="grid">
  <div><div class="label">Vendor</div><div>{esc(d.get("vendorName"))}</div></div>
  <div><div class="label">Warehouse</div><div>{esc(d.get("warehouseCode"))}</div></div>
  <div><div class="label">Vehicle</div><div>{esc(d.get("vehicleNumber") or "—")}</div></div>
</div>
<table>
  <thead><tr><th>SKU</th><th>Batch</th><th class="num">Received</th><th class="num">Accepted</th><th class="num">Rejected</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
<div class="foot">Received and inspected on behalf of {esc(settings.company_name)}.</div>
"""
    return shell(f"Goods receipt {d.get('number')}", body)


def logistics_note(d: dict) -> str:
    """No real caller in this rewrite (same as Node) - ported for contract
    completeness only. No line table at all."""
    meta = [("Date", d.get("dispatchedAt")), ("Carrier", d.get("carrierName"))]
    body = f"""
{header("Dispatch note", str(d.get("number")), meta)}
<div class="grid">
  <div><div class="label">From</div><div>{esc(d.get("origin"))}</div></div>
  <div><div class="label">To</div><div>{esc(d.get("destination"))}</div></div>
  <div><div class="label">AWB</div><div>{esc(d.get("awbNumber") or "—")}</div></div>
</div>
<div class="foot">Goods received in good order and condition. Signature: ______________________</div>
"""
    return shell(f"Dispatch note {d.get('number')}", body)


TEMPLATES = {
    "purchase-order": purchase_order,
    "customer-invoice": customer_invoice,
    "goods-receipt": goods_receipt,
    "logistics-note": logistics_note,
}
