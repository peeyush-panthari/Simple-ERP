"""Generate a realistic volume of dummy data through the public API (so every business rule, sequence,
ledger and audit row is produced by the real code paths, nothing is inserted behind the API's back).

    cd backend
    .venv/bin/python scripts/dev_data.py [--scale 1] [--seed 7]

Environment: API_BASE (default http://localhost:8000), API_EMAIL / API_PASSWORD (default the dev admin).
Scale 1 creates roughly: 12 vendors, 20 customers, 3 warehouses, 40 raw materials, 10 finished goods,
36 purchase orders (received and QC'd, some partially / left under QC / cancelled), 10 BOMs, 30 production
runs, 60 sales orders spread over every state (confirmed .. shipped, invoiced, paid, credit-noted, reversed,
cancelled), and 6 transport requests taken through RFQ, award, dispatch and proof of delivery.

Everything is tagged "DD" in names/SKUs so it is easy to spot and the run is repeatable (--seed).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import urllib.error
import urllib.request
from collections import Counter

BASE = os.environ.get("API_BASE", "http://localhost:8000")
EMAIL = os.environ.get("API_EMAIL", "dev-admin@example.test")
PASSWORD = os.environ.get("API_PASSWORD", "DevAdmin#Pass2026")

stats: Counter = Counter()
failures: list[str] = []
TOKEN = ""


def call(method: str, path: str, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw and "json" in r.headers.get("content-type", "") else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"detail": raw.decode("latin-1")[:200]}


def ok(method: str, path: str, body=None, what: str = ""):
    status, data = call(method, path, body)
    if status >= 400:
        stats[f"FAILED {what or path.split('?')[0]}"] += 1
        if len(failures) < 25:
            failures.append(f"{method} {path} -> {status} {str((data or {}).get('detail'))[:140]}")
        return None
    stats[what or path.split("?")[0]] += 1
    return data


def get(path: str):
    return ok("GET", path, what="GET " + path.split("?")[0]) or {}


def rows(path: str):
    return (get(path) or {}).get("data", [])


def main() -> None:
    global TOKEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rnd = random.Random(args.seed)
    sc = lambda n: max(1, int(round(n * args.scale)))
    tag = f"DD{args.seed}"

    status, login = call("POST", "/api/v1/auth/login", {"email": EMAIL, "password": PASSWORD})
    if status != 200:
        sys.exit(f"login failed against {BASE}: {status} {login}")
    TOKEN = login["accessToken"]

    # ---- reference data ---------------------------------------------------------------------------
    cats = {c["productCategory"]: c for c in rows("/api/v1/product-categories?limit=100")}
    for name, code, types in [("Raw Materials", "CAT-RM", ["raw_material"]), ("Battery Packs", "CAT-FG", ["finished_good"]), ("Consumables", "CAT-CON", ["consumable"])]:
        if name not in cats:
            c = ok("POST", "/api/v1/product-categories", {"productCategory": name, "code": code, "productTypes": types}, what="category")
            if c:
                cats[name] = c
    if len(cats) < 3:
        sys.exit("product categories missing and could not be created")

    def party(kind: str, i: int):
        name = f"{tag} {'Vendor' if kind == 'vendor' else 'Customer'} {i:03d} {rnd.choice(['Metals', 'Cells', 'Energy', 'Traders', 'Components', 'Power', 'Systems'])} Pvt Ltd"
        city, state = rnd.choice([("Pune", "27"), ("Mumbai", "27"), ("Bengaluru", "29"), ("Chennai", "33"), ("Hyderabad", "36"), ("Ahmedabad", "24")])
        addresses = [{"type": "billing", "line1": f"{rnd.randint(1, 99)} {rnd.choice(['Industrial', 'Market', 'Station', 'Ring'])} Rd", "city": city, "stateCode": state, "postalCode": f"{rnd.randint(400000, 599999)}", "country": "IN", "isDefault": True}]
        if kind == "customer":
            addresses.append({"type": "shipping", "label": "Main Store", "line1": f"{rnd.randint(1, 99)} Depot St", "city": city, "stateCode": state, "postalCode": f"{rnd.randint(400000, 599999)}", "country": "IN", "isDefault": True})
        p = ok("POST", "/api/v1/parties", {"legalName": name, "type": kind, "paymentTerms": rnd.choice(["NET15", "NET30", "NET45"]), "currency": "INR", "creditLimit": str(rnd.choice([1000000, 2000000, 5000000])),
            "addresses": addresses, "contacts": [{"name": f"Contact {i}", "email": f"{kind}{i}.{tag.lower()}@example.test", "phone": f"99999{rnd.randint(10000, 99999)}", "isPrimary": True}]}, what=f"party:{kind}")
        if p and ok("POST", f"/api/v1/parties/{p['id']}/activate", {}, what="party:activate"):
            return p
        return None

    vendors = [v for v in (party("vendor", i) for i in range(1, sc(12) + 1)) if v]
    customers = [c for c in (party("customer", i) for i in range(1, sc(20) + 1)) if c]

    warehouses = []
    for i in range(1, 4):
        w = ok("POST", "/api/v1/warehouses", {"name": f"{tag} Warehouse {i}"}, what="warehouse")
        if w:
            warehouses.append(w)
    ok("POST", "/api/v1/factories", {"name": f"{tag} Factory"}, what="factory")
    if not (vendors and customers and warehouses):
        sys.exit("could not create vendors/customers/warehouses; aborting")

    # ---- products -----------------------------------------------------------------------------------
    rms = []
    for i in range(1, sc(40) + 1):
        uom = rnd.choice(["KG", "UNIT", "UNIT", "M"])
        p = ok("POST", "/api/v1/products", {"sku": f"{tag}-RM-{i:03d}", "name": f"{tag} Raw Material {i:03d}", "make": rnd.choice(["Acme", "Samsung", "Daly", "3M", "LG"]), "type": "raw_material",
            "categoryId": cats["Raw Materials"]["id"], "uom": uom, "batchTracked": False, "expiryTracked": False, "sellable": False, "purchasable": True}, what="product:rm")
        if p:
            rms.append(p)
    fgs = []
    for i in range(1, sc(10) + 1):
        p = ok("POST", "/api/v1/products", {"sku": f"{tag}-FG-{i:03d}", "name": f"{tag} Battery Pack {i:03d}", "make": "Simple", "type": "finished_good", "categoryId": cats["Battery Packs"]["id"], "uom": "UNIT",
            "batchTracked": False, "expiryTracked": False, "sellable": True, "purchasable": False}, what="product:fg")
        if p:
            fgs.append(p)

    # ---- purchasing: PO -> GRN -> QC --------------------------------------------------------------------
    gst = ["GST0", "GST5", "GST12", "GST18"]
    stock_wh = warehouses[0]
    for n in range(sc(36)):
        # the first few POs load the main warehouse with every raw material so production/orders have stock
        wh = stock_wh if n < 6 else rnd.choice(warehouses)
        if n < 6:
            picks = rms[n::6][:8]
        else:
            picks = rnd.sample(rms, k=min(len(rms), rnd.randint(1, 3)))
        if not picks:
            continue
        lines = [{"productId": p["id"], "quantity": str(rnd.choice([40, 60, 100, 200]) if p["uom"] != "UNIT" else rnd.choice([30, 50, 80])), "uom": p["uom"], "unitPrice": f"{rnd.uniform(20, 900):.2f}", "taxCode": rnd.choice(gst)} for p in picks]
        po = ok("POST", "/api/v1/purchase-orders", {"vendorId": rnd.choice(vendors)["id"], "warehouseId": wh["id"], "expectedDate": (dt.date.today() + dt.timedelta(days=rnd.randint(3, 40))).isoformat(),
            "paymentTerms": rnd.choice(["NET30", "NET45"]), "lines": lines}, what="po")
        if not po:
            continue
        roll = rnd.random()
        if n >= 6 and roll < 0.12:
            ok("POST", f"/api/v1/purchase-orders/{po['id']}/cancel", {"reason": "Supplier withdrew the quote"}, what="po:cancel")
            continue
        if n >= 6 and roll < 0.25:
            continue  # issued but nothing received yet
        recv = []
        for l in po["lines"]:
            qty = float(l["quantity"])
            take = qty if (n < 6 or rnd.random() < 0.7) else round(qty * rnd.choice([0.4, 0.5, 0.75]), 0)
            recv.append({"poLineId": l["id"], "receivedQty": str(take if take == int(take) else take)})
        grn = ok("POST", "/api/v1/grns", {"poId": po["id"], "invoiceNumber": f"{tag}-INV-{n:04d}", "lines": recv}, what="grn")
        if not grn:
            continue
        if n >= 6 and rnd.random() < 0.15:
            continue  # left under QC
        items = get(f"/api/v1/grns/{grn['id']}/items?limit=500").get("data", [])
        qc_items = []
        for it in items:
            if it["kind"] != "piece":
                continue
            reject = n >= 6 and rnd.random() < 0.05
            qc_items.append({"itemId": it["id"], "decision": "reject" if reject else "accept", **({"rejectionCode": "DAMAGED"} if reject else {})})
        qc_lines = [{"lineId": grn["lines"][i]["id"], "acceptedQty": recv[i]["receivedQty"], "rejectedQty": "0"} for i, pl in enumerate(po["lines"]) if pl["uom"] != "UNIT"]
        ok("POST", f"/api/v1/grns/{grn['id']}/qc", {"items": qc_items, "lines": qc_lines}, what="grn:qc")

    # ---- BOMs + production -------------------------------------------------------------------------------
    boms = {}
    for fg in fgs:
        comps = rnd.sample(rms, k=min(len(rms), rnd.randint(2, 3)))
        spec = [{"componentProductId": c["id"], "quantity": str(rnd.choice([1, 2])), "uom": c["uom"], "scrapPercent": "0", "isAlternate": False} for c in comps]
        b = ok("POST", "/api/v1/boms", {"productId": fg["id"], "yieldPercent": "100", "effectiveFrom": "2026-01-01", "components": spec}, what="bom")
        if b:
            boms[fg["id"]] = (spec, comps)

    def available(product_id: str, wh_id: str):
        return get(f"/api/v1/inventory-items?productId={product_id}&warehouseId={wh_id}&available=true&limit=200").get("data", [])

    produced = 0
    for n in range(sc(30)):
        if not boms:
            break
        fg = rnd.choice([f for f in fgs if f["id"] in boms])
        spec, comps = boms[fg["id"]]
        consumed = []
        good = True
        for c in spec:
            prod = next((x for x in rms if x["id"] == c["componentProductId"]), None)
            if not prod:
                good = False
                break
            need = float(c["quantity"])
            avail = available(prod["id"], stock_wh["id"])
            if prod["uom"] == "UNIT":
                pick = [it for it in avail if it.get("kind") == "piece"][: int(need)]
                if len(pick) < int(need):
                    good = False
                    break
                consumed += [{"itemId": it["id"], "productId": prod["id"], "quantity": "1"} for it in pick]
            else:
                lot = next((it for it in avail if float(it.get("availableQty", 0)) >= need), None)
                if not lot:
                    good = False
                    break
                consumed.append({"itemId": lot["id"], "productId": prod["id"], "quantity": str(need)})
        if not good or not consumed:
            continue
        if ok("POST", "/api/v1/inventory/production", {"productId": fg["id"], "warehouseId": stock_wh["id"], "quantity": "1", "uom": "UNIT", "packId": f"PK-{tag}-{n:04d}", "consumedItems": consumed}, what="production"):
            produced += 1

    # ---- sales: order -> allocate -> pack -> ship -> invoice -> pay ----------------------------------------------
    ar_by_invoice = {}

    def ar_row(invoice_id: str):
        if not ar_by_invoice:
            for a in rows("/api/v1/ar?limit=100"):
                ar_by_invoice[a["invoiceId"]] = a
        if invoice_id not in ar_by_invoice:
            ar_by_invoice.clear()
            for a in rows("/api/v1/ar?limit=100"):
                ar_by_invoice[a["invoiceId"]] = a
        return ar_by_invoice.get(invoice_id)

    for n in range(sc(60)):
        fg = rnd.choice(fgs)
        cust = rnd.choice(customers)
        o = ok("POST", "/api/v1/orders", {"customerId": cust["id"], "lines": [{"productId": fg["id"], "quantity": "1", "uom": "UNIT", "unitPrice": f"{rnd.uniform(9000, 24000):.2f}", "taxCode": "GST18"}]}, what="order")
        if not o:
            continue
        stage = rnd.random()
        if stage < 0.10:
            continue  # stays confirmed
        if stage < 0.16:
            ok("POST", f"/api/v1/orders/{o['id']}/cancel", {"reason": "Customer cancelled before allocation"}, what="order:cancel")
            continue
        fgi = get(f"/api/v1/inventory/finished-goods?productId={fg['id']}&available=true&limit=3").get("data", [])
        if not fgi:
            continue  # no finished stock: order stays open (a realistic backlog)
        line = o["lines"][0]
        if not ok("POST", f"/api/v1/orders/{o['id']}/allocate-items", {"orderLineId": line["id"], "items": [{"itemId": fgi[0]["id"], "quantity": "1"}]}, what="order:allocate"):
            continue
        if stage < 0.35:
            continue
        if not ok("POST", f"/api/v1/orders/lines/{line['id']}/pack", {"quantity": "1"}, what="order:pack"):
            continue
        if stage < 0.5:
            continue
        if not ok("POST", f"/api/v1/orders/lines/{line['id']}/ship", {"quantity": "1"}, what="order:ship"):
            continue
        if stage < 0.62:
            continue
        inv = ok("POST", f"/api/v1/orders/{o['id']}/invoice", {}, what="order:invoice")
        if not inv:
            continue
        a = ar_row(inv.get("invoiceId") or (inv.get("invoice") or {}).get("id") or "")
        if not a:
            od = get(f"/api/v1/orders/{o['id']}")
            a = ar_row(od.get("invoiceId", ""))
        if not a or stage < 0.72:
            continue
        total = float(a["amount"])
        pay_amt = total if stage < 0.85 else round(total * rnd.choice([0.3, 0.5, 0.6]), 2)
        pay = ok("POST", "/api/v1/ar/payments", {"partyId": cust["id"], "amount": f"{pay_amt:.2f}", "method": rnd.choice(["bank_transfer", "cheque", "upi"]), "allocations": [{"invoiceId": a["id"], "amount": f"{pay_amt:.2f}"}]}, what="ar:payment")
        if pay and stage > 0.93:
            ok("POST", f"/api/v1/payments/{pay['paymentId']}/reverse", {"reason": "Cheque bounced"}, what="ar:reverse")
        elif stage > 0.9:
            ok("POST", "/api/v1/credit-notes", {"direction": "outbound", "partyId": cust["id"], "amount": "500", "reason": "Cosmetic damage on delivery", "arInvoiceId": a["id"]}, what="ar:credit-note")

    # ---- vendor invoices ----------------------------------------------------------------------------------------
    for po in rows("/api/v1/purchase-orders?limit=20")[:sc(8)]:
        if po.get("status") in ("received", "partially_received", "issued"):
            ok("POST", "/api/v1/ap/invoices", {"vendorId": po["vendorId"], "vendorInvoiceNo": f"{tag}-V-{po['number']}", "invoiceDate": dt.date.today().isoformat(), "dueDate": (dt.date.today() + dt.timedelta(days=30)).isoformat(),
                "amount": "1000", "poId": po["id"]}, what="ap:invoice")

    # ---- logistics ---------------------------------------------------------------------------------------------------
    for n in range(sc(6)):
        tr = ok("POST", "/api/v1/transport-requests", {"destLine1": f"{n + 1} Dispatch Road", "destCity": rnd.choice(["Pune", "Nagpur", "Indore"]), "customerName": rnd.choice(customers)["legalName"], "weightKg": str(rnd.randint(10, 400))}, what="transport")
        if not tr or len(vendors) < 2:
            continue
        carriers = rnd.sample(vendors, 2)
        rfq = ok("POST", f"/api/v1/transport-requests/{tr['id']}/rfq", {"carrierIds": [c["id"] for c in carriers]}, what="rfq")
        if not rfq:
            continue
        rid = rfq["rfqs"][0]["id"]
        valid = (dt.date.today() + dt.timedelta(days=7)).isoformat()
        last = None
        for c, amt in zip(carriers, (rnd.randint(600, 900), rnd.randint(700, 1000))):
            last = ok("POST", f"/api/v1/rfqs/{rid}/quotes", {"carrierId": c["id"], "amount": str(amt), "validUntil": valid}, what="rfq:quote") or last
        if not last:
            continue
        quotes = last["rfqs"][0]["quotations"]
        best = min(quotes, key=lambda q: float(q["amount"]))
        if not ok("POST", f"/api/v1/rfqs/{rid}/award", {"quotationId": best["id"]}, what="rfq:award"):
            continue
        if n % 3 == 2:
            continue
        d = ok("POST", "/api/v1/dispatches", {"transportRequestId": tr["id"], "awbNumber": f"AWB{tag}{n}", "vehicleNumber": f"MH12DD{n:04d}"}, what="dispatch")
        if d and n % 3 == 0:
            ok("POST", f"/api/v1/dispatches/{d['id']}/pod", {"podUrl": f"https://example.test/pod/{tag}-{n}.pdf", "receivedBy": "Gate Keeper"}, what="pod")

    print(f"API {BASE}  (seed {args.seed}, scale {args.scale})")
    for k in sorted(stats):
        print(f"  {stats[k]:5d}  {k}")
    if failures:
        print("\nfirst failures:")
        for f in failures:
            print("  ", f)


if __name__ == "__main__":
    main()
