"""Receive stock into the dev API's Seed Warehouse: PO -> GRN -> QC accept-all, so browser checks have something to consume.

    .venv/bin/python scripts/dev_stock.py SEED-RM-CELL 20 [unit_price]
"""
from __future__ import annotations

import sys

sys.argv, _args = [sys.argv[0]], sys.argv[1:]
exec(open(__file__.replace("dev_stock.py", "dev_seed.py")).read().split("def main")[0])

sku, qty = _args[0], _args[1]
price = _args[2] if len(_args) > 2 else "40"


def main():
    product = next(p for p in get(f"/api/v1/products?q={sku}&limit=50")["data"] if p["sku"] == sku)
    vendor = next(p for p in get("/api/v1/parties?type=vendor&limit=200")["data"] if p["legalName"] == "Seed Vendor Pvt Ltd")
    warehouse = next(w for w in get("/api/v1/warehouses?limit=200")["data"] if w["name"] == "Seed Warehouse")
    po = post("/api/v1/purchase-orders", {"vendorId": vendor["id"], "warehouseId": warehouse["id"], "expectedDate": "2026-12-01", "lines": [{"productId": product["id"], "quantity": qty, "uom": product["uom"], "unitPrice": price, "taxCode": "GST0"}]})
    grn = post("/api/v1/grns", {"poId": po["id"], "invoiceNumber": f"SEED-{po['number']}", "lines": [{"poLineId": po["lines"][0]["id"], "receivedQty": qty}]})
    if product["uom"] == "UNIT":
        items = [{"itemId": i["id"], "decision": "accept"} for i in get(f"/api/v1/grns/{grn['id']}/items")["data"]]
        result = post(f"/api/v1/grns/{grn['id']}/qc", {"items": items, "lines": []})
    else:
        result = post(f"/api/v1/grns/{grn['id']}/qc", {"items": [], "lines": [{"lineId": grn["lines"][0]["id"], "acceptedQty": qty, "rejectedQty": "0"}]})
    print(po["number"], grn["number"], result and result["status"])


main()
