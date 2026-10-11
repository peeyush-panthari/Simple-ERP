"""Run one identical business scenario against the original (Flask :5001) and the new (FastAPI :8000) API and compare
every response, with ids, document numbers, timestamps and the per-run suffix normalised. Both use the same database.

The scenario is the money path: vendor -> product -> PO (GST split) -> GRN -> QC (lot + serialised) -> customer -> order
-> allocate -> pack -> ship -> invoice -> payment -> credit note -> reversal, plus a few negative cases.
"""
import json, re, sys, urllib.request, urllib.error, uuid

NEW, OLD = "http://127.0.0.1:8000", "http://127.0.0.1:5001"
EMAIL, PW = "dev-admin@example.test", "DevAdmin#Pass2026"


def call(base, path, token=None, method="GET", body=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw and "json" in r.headers.get("content-type", "") else raw.decode("latin-1")[:200])
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode("latin-1")[:200]


UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
NUM = re.compile(r"\b[A-Z]{2,5}-[A-Z0-9]{4,}\b")
TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.\d]*(\+00:00|Z)?")


def scrub(x, sfx):
    if isinstance(x, dict):
        return {k: scrub(v, sfx) for k, v in sorted(x.items()) if k != "seq"}  # seq is a global counter
    if isinstance(x, list):
        return [scrub(v, sfx) for v in x]
    if isinstance(x, str):
        x = re.sub(re.escape(sfx), "<sfx>", x, flags=re.I)
        x = UUID.sub("<uuid>", x)
        x = TS.sub("<ts>", x)
        x = NUM.sub("<num>", x)
        return x
    return x


EXPECTED_ERRORS = {'product-dup','po-bad-vendor','grn-over-receipt','adjust-too-much','invoice-again','overpay','cancel-shipped','transfer'}


def run(base, sfx):
    s, b = call(base, "/api/v1/auth/login", method="POST", body={"email": EMAIL, "password": PW})
    tok = b["accessToken"]
    log = []
    ids = {}

    def step(name, method, path, body=None, save=None):
        status, resp = call(base, path, tok, method, body)
        log.append((name, status, resp))
        if status >= 400 and name not in EXPECTED_ERRORS:
            print("  !! unexpected", base, name, status, str(resp)[:300])
        if save and isinstance(resp, dict):
            for k, src in save.items():
                v = resp
                for part in src.split("."):
                    v = v[int(part)] if part.isdigit() else v.get(part) if isinstance(v, dict) else None
                    if v is None:
                        break
                ids[k] = v
        return status, resp

    cats = call(base, "/api/v1/product-categories?limit=100", tok)[1]["data"]
    cat = next(c for c in cats if c["productCategory"] == "Raw Materials")["id"]
    fgcat = next(c for c in cats if c["productCategory"] == "Battery Packs")["id"]

    step("vendor", "POST", "/api/v1/parties", {"legalName": f"Cmp Vendor {sfx}", "type": "vendor", "paymentTerms": "NET30", "currency": "INR", "creditLimit": "100000",
        "addresses": [{"type": "billing", "line1": "1 Road", "city": "Pune", "stateCode": "27", "postalCode": "411001", "country": "IN", "isDefault": True}],
        "contacts": [{"name": "V Contact", "email": f"v-{sfx}@example.test", "phone": "9999900000", "isPrimary": True}]}, save={"vendor": "id"})
    step("vendor-activate", "POST", f"/api/v1/parties/{ids['vendor']}/activate", {})
    step("customer", "POST", "/api/v1/parties", {"legalName": f"Cmp Customer {sfx}", "type": "customer", "paymentTerms": "NET15", "currency": "INR", "creditLimit": "500000",
        "addresses": [{"type": "billing", "line1": "2 Road", "city": "Pune", "stateCode": "27", "postalCode": "411001", "country": "IN", "isDefault": True}, {"type": "shipping", "label": "Main", "line1": "3 Road", "city": "Mumbai", "stateCode": "27", "postalCode": "400001", "country": "IN", "isDefault": True}],
        "contacts": [{"name": "C Contact", "email": f"c-{sfx}@example.test", "phone": "9999900001", "isPrimary": True}]}, save={"customer": "id"})
    step("customer-activate", "POST", f"/api/v1/parties/{ids['customer']}/activate", {})

    step("rm-kg", "POST", "/api/v1/products", {"sku": f"CMPK-{sfx}", "name": f"Cmp Steel {sfx}", "make": "Acme", "type": "raw_material", "categoryId": cat, "uom": "KG", "batchTracked": False, "expiryTracked": False, "sellable": False}, save={"rm_kg": "id"})
    step("rm-unit", "POST", "/api/v1/products", {"sku": f"CMPU-{sfx}", "name": f"Cmp Cell {sfx}", "make": "Acme", "type": "raw_material", "categoryId": cat, "uom": "UNIT", "batchTracked": False, "expiryTracked": False, "sellable": False}, save={"rm_unit": "id"})
    step("fg", "POST", "/api/v1/products", {"sku": f"CMPF-{sfx}", "name": f"Cmp Pack {sfx}", "make": "Acme", "type": "finished_good", "categoryId": fgcat, "uom": "UNIT", "batchTracked": False, "expiryTracked": False, "sellable": True}, save={"fg": "id"})
    step("product-dup", "POST", "/api/v1/products", {"sku": f"CMPK-{sfx}", "name": f"Cmp Steel {sfx}", "make": "Acme", "type": "raw_material", "categoryId": cat, "uom": "KG"})
    step("warehouse", "POST", "/api/v1/warehouses", {"name": f"Cmp WH {sfx}"}, save={"wh": "id"})

    step("po", "POST", "/api/v1/purchase-orders", {"vendorId": ids["vendor"], "warehouseId": ids["wh"], "expectedDate": "2026-12-01", "paymentTerms": "NET30",
        "lines": [{"productId": ids["rm_kg"], "quantity": "100", "uom": "KG", "unitPrice": "45.555", "taxCode": "GST18"}, {"productId": ids["rm_unit"], "quantity": "20", "uom": "UNIT", "unitPrice": "150.25", "taxCode": "GST12"}]}, save={"po": "id", "po_l1": "lines.0.id", "po_l2": "lines.1.id"})
    step("po-bad-vendor", "POST", "/api/v1/purchase-orders", {"vendorId": str(uuid.uuid4()), "warehouseId": ids["wh"], "expectedDate": "2026-12-01", "lines": [{"productId": ids["rm_kg"], "quantity": "1", "uom": "KG", "unitPrice": "1", "taxCode": "GST0"}]})
    step("po-get", "GET", f"/api/v1/purchase-orders/{ids['po']}")
    step("grn-over-receipt", "POST", "/api/v1/grns", {"poId": ids["po"], "invoiceNumber": f"CMP-{sfx}-X", "lines": [{"poLineId": ids["po_l1"], "receivedQty": "500"}]})
    step("grn", "POST", "/api/v1/grns", {"poId": ids["po"], "invoiceNumber": f"CMP-{sfx}", "lines": [{"poLineId": ids["po_l1"], "receivedQty": "60"}, {"poLineId": ids["po_l2"], "receivedQty": "5"}]}, save={"grn": "id", "grn_l1": "lines.0.id"})
    status, items = step("grn-items", "GET", f"/api/v1/grns/{ids['grn']}/items")
    unit_items = [i["id"] for i in items["data"] if i["kind"] == "piece"]
    step("qc", "POST", f"/api/v1/grns/{ids['grn']}/qc", {"items": [{"itemId": unit_items[0], "decision": "accept"}, {"itemId": unit_items[1], "decision": "accept"}, {"itemId": unit_items[2], "decision": "reject", "rejectionCode": "DAMAGED"}, {"itemId": unit_items[3], "decision": "accept"}, {"itemId": unit_items[4], "decision": "accept"}], "lines": [{"lineId": ids["grn_l1"], "acceptedQty": "58", "rejectedQty": "2", "rejectionCode": "DENT"}]})
    step("po-after", "GET", f"/api/v1/purchase-orders/{ids['po']}")
    step("balances", "GET", f"/api/v1/inventory/balances?warehouseId={ids['wh']}&limit=50")
    step("valuation", "GET", f"/api/v1/inventory/valuation?warehouseId={ids['wh']}")
    step("ledger", "GET", f"/api/v1/inventory/ledger?warehouseId={ids['wh']}&limit=50")
    step("transfer", "POST", "/api/v1/inventory/transfers", {"productId": ids["rm_kg"], "sourceWarehouseId": ids["wh"], "destWarehouseId": ids["wh"], "quantity": "1", "uom": "KG"})
    step("adjust", "POST", "/api/v1/inventory/adjustments", {"productId": ids["rm_kg"], "warehouseId": ids["wh"], "quantity": "-3", "uom": "KG", "bucket": "available", "reason": "Cycle count"})
    step("status-change", "POST", "/api/v1/inventory/status-change", {"productId": ids["rm_kg"], "warehouseId": ids["wh"], "quantity": "2", "uom": "KG", "from": "available", "to": "damaged", "reason": "Dropped in handling"})
    step("adjust-too-much", "POST", "/api/v1/inventory/adjustments", {"productId": ids["rm_kg"], "warehouseId": ids["wh"], "quantity": "-9999", "uom": "KG", "bucket": "available", "reason": "Too much"})

    step("bom", "POST", "/api/v1/boms", {"productId": ids["fg"], "yieldPercent": "100", "effectiveFrom": "2026-09-01", "components": [{"componentProductId": ids["rm_kg"], "quantity": "2.5", "uom": "KG", "scrapPercent": "0", "isAlternate": False}, {"componentProductId": ids["rm_unit"], "quantity": "2", "uom": "UNIT", "scrapPercent": "0", "isAlternate": False}]}, save={"bom": "id"})
    step("bom-explode", "GET", f"/api/v1/boms/{ids['bom']}/explode?quantity=3")
    status, avail = step("avail-units", "GET", f"/api/v1/inventory-items?productId={ids['rm_unit']}&warehouseId={ids['wh']}&available=true&limit=10")
    status, avail_kg = step("avail-kg", "GET", f"/api/v1/inventory-items?productId={ids['rm_kg']}&warehouseId={ids['wh']}&available=true&limit=10")
    consumed = [{"itemId": avail["data"][0]["id"], "productId": ids["rm_unit"], "quantity": "1"}, {"itemId": avail["data"][1]["id"], "productId": ids["rm_unit"], "quantity": "1"}, {"itemId": avail_kg["data"][0]["id"], "productId": ids["rm_kg"], "quantity": "2.5"}]
    step("production", "POST", "/api/v1/inventory/production", {"productId": ids["fg"], "warehouseId": ids["wh"], "quantity": "1", "uom": "UNIT", "packId": f"PK-{sfx}", "consumedItems": consumed}, save={"run": "id"})
    step("production-get", "GET", f"/api/v1/inventory/production/{ids['run']}")
    step("fg-items", "GET", f"/api/v1/inventory/finished-goods?productId={ids['fg']}&limit=10")

    step("order", "POST", "/api/v1/orders", {"customerId": ids["customer"], "lines": [{"productId": ids["fg"], "quantity": "1", "uom": "UNIT", "unitPrice": "12345.67", "taxCode": "GST18"}]}, save={"order": "id", "order_l": "lines.0.id"})
    status, fgi = call(base, f"/api/v1/inventory/finished-goods?productId={ids['fg']}&available=true&limit=5", tok)
    step("allocate", "POST", f"/api/v1/orders/{ids['order']}/allocate-items", {"orderLineId": ids["order_l"], "items": [{"itemId": fgi["data"][0]["id"], "quantity": "1"}]})
    step("pack", "POST", f"/api/v1/orders/lines/{ids['order_l']}/pack", {"quantity": "1"})
    step("ship", "POST", f"/api/v1/orders/lines/{ids['order_l']}/ship", {"quantity": "1"})
    step("invoice", "POST", f"/api/v1/orders/{ids['order']}/invoice", {})
    step("invoice-again", "POST", f"/api/v1/orders/{ids['order']}/invoice", {})
    step("order-get", "GET", f"/api/v1/orders/{ids['order']}")
    status, ar = call(base, f"/api/v1/ar?limit=100", tok)
    ar_row = next(a for a in ar["data"] if a.get("orderId") == ids["order"] or a.get("orderNumber") == log[-1][2].get("number")) if False else None
    step("order-for-ar", "GET", f"/api/v1/orders/{ids['order']}")
    inv = log[-1][2].get("invoiceId")
    status, arl = call(base, "/api/v1/ar?limit=100", tok)
    ar_id = next(a["id"] for a in arl["data"] if a["invoiceId"] == inv)
    step("ar-get", "GET", f"/api/v1/ar/{ar_id}", save={"ar": "id"})
    step("payment", "POST", "/api/v1/ar/payments", {"partyId": ids["customer"], "amount": "5000", "method": "bank_transfer", "allocations": [{"invoiceId": ar_id, "amount": "5000"}]}, save={"pay": "paymentId"})
    step("overpay", "POST", "/api/v1/ar/payments", {"partyId": ids["customer"], "amount": "999999", "method": "bank_transfer", "allocations": [{"invoiceId": ar_id, "amount": "999999"}]})
    step("credit-note", "POST", "/api/v1/credit-notes", {"direction": "outbound", "partyId": ids["customer"], "amount": "1000", "reason": "Damaged unit", "arInvoiceId": ar_id})
    step("ar-after", "GET", f"/api/v1/ar/{ar_id}")
    step("reverse", "POST", f"/api/v1/payments/{ids['pay']}/reverse", {"reason": "Cheque bounced"})
    step("ar-final", "GET", f"/api/v1/ar/{ar_id}")
    step("order-final", "GET", f"/api/v1/orders/{ids['order']}")
    step("cancel-shipped", "POST", f"/api/v1/orders/{ids['order']}/cancel", {"reason": "too late to cancel"})
    return log


sfx = uuid.uuid4().hex[:6].upper()
old_sfx, new_sfx = f"{sfx}O", f"{sfx}N"
old = run(OLD, old_sfx)
new = run(NEW, new_sfx)

problems = 0


def diff(a, b, path=""):
    if type(a) != type(b):
        return f"{path}: {str(a)[:80]!r} != {str(b)[:80]!r}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                return f"{path}.{k}: only in ORIGINAL ({str(b[k])[:60]!r})"
            if k not in b:
                return f"{path}.{k}: only in NEW ({str(a[k])[:60]!r})"
            d = diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if a == b else f"{path}: new={str(a)[:80]!r} original={str(b)[:80]!r}"


print(f"steps: original={len(old)} new={len(new)}")
for (name, so, ro), (_, sn, rn) in zip(old, new):
    d = None if so == sn else f"status original={so} new={sn}"
    if d is None:
        d = diff(scrub(rn, new_sfx), scrub(ro, old_sfx))
    flag = "OK  " if d is None else "DIFF"
    if d:
        problems += 1
    print(f"{flag} {name:18s} {so}", d or "")
print("\nDIFFERENCES:", problems)
