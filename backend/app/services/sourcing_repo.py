"""Sourcing: RFQ lookups, the API shape and the quotation comparison.

A requisition that Purchase has approved goes out for quotation to several vendors; the buyer records what each one
offered; the comparison lines the offers up per item (lowest landed price wins by default); an award picks a vendor
per item; purchase orders are then raised, one per winning vendor.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.core.db import session
from app.core.errors import not_found
from app.core.money import decimal_str, to_decimal
from app.models.purchase_rfq import PurchaseQuotation, PurchaseQuotationLine, PurchaseRfq, PurchaseRfqLine, PurchaseRfqVendor
from app.services.tax_codes import TaxableLine, compute_totals

STATUSES = ("open", "awarded", "ordered", "cancelled")


def find(tenant_id: uuid.UUID, rfq_id: uuid.UUID) -> PurchaseRfq | None:
    return PurchaseRfq.query.filter_by(tenant_id=tenant_id, id=rfq_id).first()


def require(tenant_id: uuid.UUID, rfq_id: uuid.UUID) -> PurchaseRfq:
    rfq = find(tenant_id, rfq_id)
    if not rfq:
        raise not_found("RFQ")
    return rfq


def lines_of(rfq_id: uuid.UUID) -> list[PurchaseRfqLine]:
    return PurchaseRfqLine.query.filter_by(rfq_id=rfq_id).order_by(PurchaseRfqLine.line_no).all()


def vendors_of(rfq_id: uuid.UUID) -> list[PurchaseRfqVendor]:
    return PurchaseRfqVendor.query.filter_by(rfq_id=rfq_id).order_by(PurchaseRfqVendor.invited_at, PurchaseRfqVendor.vendor_name).all()


def quotations_of(rfq_id: uuid.UUID) -> dict[uuid.UUID, tuple[PurchaseQuotation, dict[uuid.UUID, PurchaseQuotationLine]]]:
    """vendor_id -> (quotation, {rfq_line_id: quotation line})."""
    quotes = PurchaseQuotation.query.filter_by(rfq_id=rfq_id).all()
    by_quote: dict[uuid.UUID, dict[uuid.UUID, PurchaseQuotationLine]] = defaultdict(dict)
    if quotes:
        for ql in PurchaseQuotationLine.query.filter(PurchaseQuotationLine.quotation_id.in_([q.id for q in quotes])).all():
            by_quote[ql.quotation_id][ql.rfq_line_id] = ql
    return {q.vendor_id: (q, by_quote[q.id]) for q in quotes}


def _iso(d) -> str | None:
    return d.isoformat() if d else None


def line_to_api(l: PurchaseRfqLine, vendor_names: dict[uuid.UUID, str]) -> dict:
    return {
        "id": str(l.id),
        "lineNo": l.line_no,
        "productId": str(l.product_id) if l.product_id else None,
        "sku": l.sku,
        "itemName": l.item_name,
        "notes": l.notes,
        "quantity": decimal_str(l.quantity),
        "uom": l.uom,
        "inCatalogue": l.product_id is not None,
        "awardedVendorId": str(l.awarded_vendor_id) if l.awarded_vendor_id else None,
        "awardedVendorName": vendor_names.get(l.awarded_vendor_id) if l.awarded_vendor_id else None,
        "awardReason": l.award_reason,
        "purchaseOrderId": str(l.purchase_order_id) if l.purchase_order_id else None,
        "purchaseOrderNumber": l.purchase_order_number,
    }


def quotation_to_api(q: PurchaseQuotation, qlines: dict[uuid.UUID, PurchaseQuotationLine]) -> dict:
    return {
        "id": str(q.id),
        "vendorId": str(q.vendor_id),
        "vendorName": q.vendor_name,
        "quoteRef": q.quote_ref,
        "quoteDate": _iso(q.quote_date),
        "validUntil": _iso(q.valid_until),
        "paymentTerms": q.payment_terms,
        "deliveryDays": q.delivery_days,
        "charges": decimal_str(q.charges),
        "notes": q.notes,
        "recordedByName": q.recorded_by_name,
        "expired": bool(q.valid_until and q.valid_until < date.today()),
        "lines": [
            {
                "rfqLineId": str(lid),
                "unitPrice": decimal_str(ql.unit_price) if ql.unit_price is not None else None,
                "taxCode": ql.tax_code,
                "leadTimeDays": ql.lead_time_days,
                "notes": ql.notes,
            }
            for lid, ql in qlines.items()
        ],
    }


def vendor_to_api(v: PurchaseRfqVendor, quote: tuple | None) -> dict:
    return {
        "vendorId": str(v.vendor_id),
        "vendorName": v.vendor_name,
        "vendorEmail": v.vendor_email,
        "status": v.status,
        "emailState": v.email_state,
        "emailError": v.email_error,
        "invitedAt": v.invited_at.isoformat() if v.invited_at else None,
        "quotation": quotation_to_api(*quote) if quote else None,
    }


def to_api(rfq: PurchaseRfq, *, lines=None, vendors=None, quotes=None, summary: dict | None = None) -> dict:
    out = {
        "id": str(rfq.id),
        "number": rfq.number,
        "status": rfq.status,
        "requisitionId": str(rfq.requisition_id) if rfq.requisition_id else None,
        "requisitionNumber": rfq.requisition_number,
        "warehouseId": str(rfq.warehouse_id) if rfq.warehouse_id else None,
        "warehouseCode": rfq.warehouse_code,
        "dueDate": _iso(rfq.due_date),
        "requiredBy": _iso(rfq.required_by),
        "currency": rfq.currency,
        "terms": rfq.terms,
        "notes": rfq.notes,
        "createdByName": rfq.created_by_name,
        "createdAt": rfq.created_at.isoformat() if rfq.created_at else None,
        "awardedByName": rfq.awarded_by_name,
        "awardedAt": rfq.awarded_at.isoformat() if rfq.awarded_at else None,
        "cancelledReason": rfq.cancelled_reason,
    }
    if lines is not None:
        names = {v.vendor_id: v.vendor_name for v in (vendors or [])}
        out["lines"] = [line_to_api(l, names) for l in lines]
        pos = {}
        for l in lines:
            if l.purchase_order_id:
                pos[str(l.purchase_order_id)] = {"id": str(l.purchase_order_id), "number": l.purchase_order_number, "vendorName": names.get(l.awarded_vendor_id)}
        out["purchaseOrders"] = list(pos.values())
    if vendors is not None:
        quotes = quotes or {}
        out["vendors"] = [vendor_to_api(v, quotes.get(v.vendor_id)) for v in vendors]
    if summary:
        out.update(summary)
    return out


def list_summaries(rfq_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    if not rfq_ids:
        return {}
    out: dict[uuid.UUID, dict] = {i: {"itemsSummary": "", "lineCount": 0, "vendorCount": 0, "quotedCount": 0} for i in rfq_ids}
    names: dict[uuid.UUID, list[str]] = defaultdict(list)
    for rid, name in session.query(PurchaseRfqLine.rfq_id, PurchaseRfqLine.item_name).filter(PurchaseRfqLine.rfq_id.in_(rfq_ids)).order_by(PurchaseRfqLine.rfq_id, PurchaseRfqLine.line_no).all():
        names[rid].append(name)
    for rid, ns in names.items():
        extra = len(ns) - 2
        out[rid]["lineCount"] = len(ns)
        out[rid]["itemsSummary"] = ", ".join(ns[:2]) + (f" +{extra} more" if extra > 0 else "")
    for rid, status in session.query(PurchaseRfqVendor.rfq_id, PurchaseRfqVendor.status).filter(PurchaseRfqVendor.rfq_id.in_(rfq_ids)).all():
        out[rid]["vendorCount"] += 1
        if status == "quoted":
            out[rid]["quotedCount"] += 1
    return out


# ---- comparison ---------------------------------------------------------------------------------------------------


def _pct_over(value: Decimal, lowest: Decimal) -> str | None:
    if lowest <= 0:
        return None
    return decimal_str(((value - lowest) / lowest * 100).quantize(Decimal("0.1")))


def comparison(rfq: PurchaseRfq) -> dict:
    """Every quoted price side by side, per item and per vendor, with tax and freight included so the comparison is on
    what would actually be paid. Item level: who is lowest and by how much everyone else is above them."""
    lines = lines_of(rfq.id)
    vendors = vendors_of(rfq.id)
    quotes = quotations_of(rfq.id)
    today = date.today()

    # Per vendor: landed (net + tax) amount of each line they quoted.
    landed: dict[uuid.UUID, dict[uuid.UUID, dict]] = {}
    basket: dict[uuid.UUID, str] = {}
    for vendor_id, (q, qlines) in quotes.items():
        quoted = [(l, qlines[l.id]) for l in lines if l.id in qlines and qlines[l.id].unit_price is not None]
        if not quoted:
            landed[vendor_id], basket[vendor_id] = {}, decimal_str(0)
            continue
        totals = compute_totals([TaxableLine(quantity=l.quantity, unit_price=ql.unit_price, tax_code=ql.tax_code) for l, ql in quoted], q.charges)
        landed[vendor_id] = {l.id: {"net": c.net_amount, "gross": c.gross_amount, "taxRate": c.tax_rate} for (l, _), c in zip(quoted, totals.lines)}
        basket[vendor_id] = totals.total

    out_lines = []
    suggested: dict[str, str] = {}
    lowest_count: dict[uuid.UUID, int] = defaultdict(int)
    for l in lines:
        offers = {}
        gross_by_vendor = {vid: to_decimal(landed[vid][l.id]["gross"]) for vid in landed if l.id in landed[vid]}
        lowest = min(gross_by_vendor.values()) if gross_by_vendor else None
        for vid, gross in gross_by_vendor.items():
            q, qlines = quotes[vid]
            ql = qlines[l.id]
            is_lowest = gross == lowest
            offers[str(vid)] = {
                "unitPrice": decimal_str(ql.unit_price),
                "taxCode": ql.tax_code,
                "netAmount": landed[vid][l.id]["net"],
                "grossAmount": decimal_str(gross),
                "leadTimeDays": ql.lead_time_days if ql.lead_time_days is not None else q.delivery_days,
                "notes": ql.notes,
                "isLowest": is_lowest,
                "overLowestPct": None if is_lowest else _pct_over(gross, lowest),
                "expired": bool(q.valid_until and q.valid_until < today),
            }
            if is_lowest:
                lowest_count[vid] += 1
        # Lowest wins; a tie goes to the shorter lead time, then to the vendor the buyer invited first.
        order = {v.vendor_id: i for i, v in enumerate(vendors)}
        ranked = sorted(gross_by_vendor, key=lambda vid: (gross_by_vendor[vid], offers[str(vid)]["leadTimeDays"] if offers[str(vid)]["leadTimeDays"] is not None else 10**6, order.get(vid, 0)))
        if ranked:
            suggested[str(l.id)] = str(ranked[0])
        out_lines.append(
            {
                "rfqLineId": str(l.id),
                "lineNo": l.line_no,
                "itemName": l.item_name,
                "sku": l.sku,
                "quantity": decimal_str(l.quantity),
                "uom": l.uom,
                "inCatalogue": l.product_id is not None,
                "quoteCount": len(offers),
                "lowestGross": decimal_str(lowest) if lowest is not None else None,
                "offers": offers,
                "suggestedVendorId": suggested.get(str(l.id)),
                "awardedVendorId": str(l.awarded_vendor_id) if l.awarded_vendor_id else None,
                "awardReason": l.award_reason,
            }
        )

    vendor_rows = []
    full_basket: list[tuple[Decimal, uuid.UUID]] = []
    for v in vendors:
        quote = quotes.get(v.vendor_id)
        q = quote[0] if quote else None
        quoted_lines = len(landed.get(v.vendor_id, {}))
        covers_all = bool(lines) and quoted_lines == len(lines)
        if covers_all:
            full_basket.append((to_decimal(basket[v.vendor_id]), v.vendor_id))
        lead_days = [o["leadTimeDays"] for ln in out_lines for vid, o in ln["offers"].items() if vid == str(v.vendor_id) and o["leadTimeDays"] is not None]
        vendor_rows.append(
            {
                "vendorId": str(v.vendor_id),
                "vendorName": v.vendor_name,
                "status": v.status,
                "quoteRef": q.quote_ref if q else None,
                "validUntil": _iso(q.valid_until) if q else None,
                "expired": bool(q and q.valid_until and q.valid_until < today),
                "paymentTerms": q.payment_terms if q else None,
                "deliveryDays": q.delivery_days if q else None,
                "charges": decimal_str(q.charges) if q else decimal_str(0),
                "quotedLineCount": quoted_lines,
                "coversAllLines": covers_all,
                "lowestLineCount": lowest_count.get(v.vendor_id, 0),
                "basketTotal": basket.get(v.vendor_id, decimal_str(0)) if quote else None,
                "longestLeadDays": max(lead_days) if lead_days else None,
            }
        )

    # What the buyer would pay following the suggestion (each item to its lowest, plus the freight of each vendor used).
    used = {uuid.UUID(v) for v in suggested.values()}
    suggested_total = Decimal(0)
    for l in out_lines:
        vid = l["suggestedVendorId"]
        if vid:
            suggested_total += to_decimal(l["offers"][vid]["grossAmount"])
    for vid in used:
        suggested_total += to_decimal(quotes[vid][0].charges)
    cheapest = min(full_basket)[1] if full_basket else None
    return {
        "rfqId": str(rfq.id),
        "lines": out_lines,
        "vendors": vendor_rows,
        "suggested": suggested,
        "suggestedTotal": decimal_str(suggested_total.quantize(Decimal("0.01"))) if suggested else None,
        "cheapestSingleVendorId": str(cheapest) if cheapest else None,
        "cheapestSingleVendorTotal": decimal_str(min(full_basket)[0]) if full_basket else None,
        "unquotedLineIds": [l["rfqLineId"] for l in out_lines if not l["offers"]],
    }
