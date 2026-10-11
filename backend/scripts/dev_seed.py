"""Seed a running dev API with a small, realistic data set (categories, products, a BOM, parties) for browser checks.

    .venv/bin/python scripts/dev_seed.py [http://localhost:8000]

Logs in as the dev admin (scripts/dev_admin.py) and is safe to re-run: things that already exist are skipped.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def call(method: str, path: str, body=None, token: str | None = None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            text = r.read().decode()
            return r.status, (json.loads(text) if text else None)
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except ValueError:
            return e.code, {"detail": text}


_, login = call("POST", "/api/v1/auth/login", {"email": "dev-admin@example.test", "password": "DevAdmin#Pass2026"})
TOKEN = login["accessToken"]


def get(path):
    status, data = call("GET", path, token=TOKEN)
    assert status == 200, (path, status, data)
    return data


def post(path, body):
    status, data = call("POST", path, body, TOKEN)
    if status >= 400:
        print(f"  ! POST {path} -> {status} {data.get('detail') if isinstance(data, dict) else data}")
        return None
    return data


def main():
    cats = {c["productCategory"]: c for c in get("/api/v1/product-categories?limit=100")["data"]}
    for name, code, types in [("Raw Materials", "CAT-RM", ["raw_material"]), ("Battery Packs", "CAT-FG", ["finished_good"]), ("Consumables", "CAT-CON", ["consumable"])]:
        if name not in cats:
            created = post("/api/v1/product-categories", {"productCategory": name, "code": code, "productTypes": types})
            if created:
                cats[name] = created
    print("categories:", sorted(cats))

    existing = {p["sku"] for p in get("/api/v1/products?limit=100")["data"]}
    specs = [
        ("SEED-RM-CELL", "Li-ion Cell 18650", "Samsung", "raw_material", "Raw Materials", "UNIT"),
        ("SEED-RM-NICKEL", "Nickel Strip", "Acme Metals", "raw_material", "Raw Materials", "M"),
        ("SEED-RM-BMS", "BMS Board 13S", "Daly", "raw_material", "Raw Materials", "UNIT"),
        ("SEED-CON-TAPE", "Kapton Tape", "3M", "consumable", "Consumables", "M"),
        ("SEED-FG-PACK", "48V 20Ah Battery Pack", "Simple", "finished_good", "Battery Packs", "UNIT"),
    ]
    for sku, name, make, ptype, cat, uom in specs:
        if sku in existing or cat not in cats:
            continue
        post("/api/v1/products", {"sku": sku, "name": name, "make": make, "type": ptype, "categoryId": cats[cat]["id"], "uom": uom, "batchTracked": False, "expiryTracked": False, "sellable": ptype == "finished_good"})
    print("products:", len(get("/api/v1/products?limit=100")["data"]))

    parties = {p["legalName"]: p for p in get("/api/v1/parties?limit=200")["data"]}
    for legal, ptype in [("Seed Vendor Pvt Ltd", "vendor"), ("Seed Customer Ltd", "customer")]:
        party = parties.get(legal) or post("/api/v1/parties", {"legalName": legal, "type": ptype, "paymentTerms": "NET30", "currency": "INR", "creditLimit": "500000", "addresses": [], "contacts": []})
        if party and party.get("status") != "active":
            detail = get(f"/api/v1/parties/{party['id']}")
            if not detail.get("addresses"):
                post(f"/api/v1/parties/{party['id']}/addresses", {"type": "billing", "line1": "12 Industrial Rd", "city": "Pune", "stateCode": "27", "postalCode": "411001", "country": "IN", "isDefault": True})
                if ptype == "customer":
                    post(f"/api/v1/parties/{party['id']}/addresses", {"type": "shipping", "label": "Main Store", "line1": "90 Market St", "city": "Pune", "stateCode": "27", "postalCode": "411002", "country": "IN", "isDefault": True})
            if not detail.get("contacts"):
                post(f"/api/v1/parties/{party['id']}/contacts", {"name": "Raj Kumar", "email": f"{ptype}@seed.example.test", "phone": "9999900001", "isPrimary": True})
            post(f"/api/v1/parties/{party['id']}/activate", {})
    print("parties ok")

    for kind, name in [("warehouses", "Seed Warehouse"), ("factories", "Seed Factory")]:
        if not any(x["name"] == name for x in get(f"/api/v1/{kind}?limit=200")["data"]):
            post(f"/api/v1/{kind}", {"name": name})
    print("sites ok")


main()
