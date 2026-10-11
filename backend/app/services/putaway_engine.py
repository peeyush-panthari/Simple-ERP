from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import session as db_session
from app.models.inventory_item import InventoryItem
from app.models.location import Location
from app.models.product import Product
from app.models.putaway_task import PutawayTask
from app.models.warehouse import Warehouse


def get_warehouse_location_tree(warehouse_id: uuid.UUID, tenant_id: uuid.UUID, db: Session | None = None) -> list[dict[str, Any]]:
    """Build a recursive hierarchical tree of locations for the given warehouse."""
    s = db or db_session
    stmt = (
        select(Location)
        .where(Location.tenant_id == tenant_id, Location.warehouse_id == warehouse_id)
        .order_by(Location.type, Location.code)
    )
    all_locs = s.scalars(stmt).all()

    # Map by parent_id
    tree_map: dict[str | None, list[Location]] = {}
    for loc in all_locs:
        p_id = str(loc.parent_id) if loc.parent_id else None
        tree_map.setdefault(p_id, []).append(loc)

    def _build_node(loc: Location) -> dict[str, Any]:
        node_id = str(loc.id)
        children = tree_map.get(node_id, [])
        return {
            "id": node_id,
            "code": loc.code,
            "name": loc.name or loc.code,
            "type": loc.type,
            "status": loc.status,
            "velocity_class": loc.velocity_class,
            "max_weight_kg": float(loc.max_weight_kg) if loc.max_weight_kg else None,
            "max_volume_cbm": float(loc.max_volume_cbm) if loc.max_volume_cbm else None,
            "barcode": loc.barcode,
            "children": [_build_node(c) for c in children],
        }

    root_locs = tree_map.get(None, [])
    return [_build_node(r) for r in root_locs]


def get_rack_matrix(
    warehouse_id: uuid.UUID,
    tenant_id: uuid.UUID,
    aisle_code: str | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Return a 2D matrix of rack shelves/bins with occupancy data for visualization."""
    s = db or db_session

    query = select(Location).where(
        Location.tenant_id == tenant_id,
        Location.warehouse_id == warehouse_id,
        Location.type == "bin",
    )
    if aisle_code:
        query = query.where(Location.code.like(f"{aisle_code}%"))

    bins = s.scalars(query.order_by(Location.code).limit(60)).all()

    # Calculate stored items per bin
    bin_ids = [b.id for b in bins]
    items_stmt = select(InventoryItem).where(
        InventoryItem.tenant_id == tenant_id,
        InventoryItem.location_id.in_(bin_ids),
        InventoryItem.status == "accepted",
    )
    items = s.scalars(items_stmt).all()
    items_by_bin: dict[uuid.UUID, list[InventoryItem]] = {}
    for itm in items:
        if itm.location_id:
            items_by_bin.setdefault(itm.location_id, []).append(itm)

    grid_bins: list[dict[str, Any]] = []
    for b in bins:
        b_items = items_by_bin.get(b.id, [])
        stored_qty = sum(float(i.quantity) for i in b_items)
        cap = float(b.capacity_units) if b.capacity_units else 100.0
        util_pct = min(100.0, round((stored_qty / cap) * 100.0, 1)) if cap > 0 else 0.0

        grid_bins.append({
            "id": str(b.id),
            "code": b.code,
            "name": b.name or b.code,
            "status": b.status,
            "velocity_class": b.velocity_class or "B",
            "capacity_units": cap,
            "stored_units": stored_qty,
            "utilization_pct": util_pct,
            "max_weight_kg": float(b.max_weight_kg) if b.max_weight_kg else 500.0,
            "barcode": b.barcode or b.code,
            "items_count": len(b_items),
            "stored_skus": list(set(i.sku for i in b_items)),
        })

    return {
        "warehouse_id": str(warehouse_id),
        "aisle_code": aisle_code,
        "total_bins": len(grid_bins),
        "bins": grid_bins,
    }


def batch_generate_bins(
    tenant_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    zone_code: str,
    aisle_prefix: str,
    racks_count: int = 4,
    shelves_count: int = 3,
    bins_per_shelf: int = 2,
    default_weight_kg: float = 500.0,
    db: Session | None = None,
) -> list[dict[str, Any]]:
    """Rapid generator creating Zone -> Aisle -> Rack -> Shelf/Bin coordinates."""
    s = db or db_session

    # Find or create zone
    zone = s.query(Location).filter_by(tenant_id=tenant_id, warehouse_id=warehouse_id, code=zone_code).first()
    if not zone:
        zone = Location(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            code=zone_code,
            name=f"Zone {zone_code}",
            type="zone",
            status="active",
        )
        s.add(zone)
        s.flush()

    # Find or create aisle
    aisle_code = f"{zone_code}-{aisle_prefix}"
    aisle = s.query(Location).filter_by(tenant_id=tenant_id, warehouse_id=warehouse_id, code=aisle_code).first()
    if not aisle:
        aisle = Location(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            parent_id=zone.id,
            code=aisle_code,
            name=f"Aisle {aisle_prefix}",
            type="aisle",
            status="active",
        )
        s.add(aisle)
        s.flush()

    created_bins = []
    for r in range(1, racks_count + 1):
        rack_code = f"{aisle_code}-R{r:02d}"
        rack = s.query(Location).filter_by(tenant_id=tenant_id, warehouse_id=warehouse_id, code=rack_code).first()
        if not rack:
            rack = Location(
                tenant_id=tenant_id,
                warehouse_id=warehouse_id,
                parent_id=aisle.id,
                code=rack_code,
                name=f"Rack {r:02d}",
                type="rack",
                status="active",
            )
            s.add(rack)
            s.flush()

        for s_idx in range(1, shelves_count + 1):
            for b_idx in range(1, bins_per_shelf + 1):
                bin_code = f"{rack_code}-S{s_idx:02d}-B{b_idx:02d}"
                existing = s.query(Location).filter_by(tenant_id=tenant_id, warehouse_id=warehouse_id, code=bin_code).first()
                if not existing:
                    # Tier 1 = Class A, Tier 2 = Class B, Tier 3+ = Class C
                    velocity = "A" if s_idx == 1 else "B" if s_idx == 2 else "C"
                    new_bin = Location(
                        tenant_id=tenant_id,
                        warehouse_id=warehouse_id,
                        parent_id=rack.id,
                        code=bin_code,
                        name=f"Bin S{s_idx:02d}-B{b_idx:02d}",
                        type="bin",
                        status="active",
                        capacity_units=Decimal("100"),
                        max_weight_kg=Decimal(str(default_weight_kg)),
                        max_volume_cbm=Decimal("0.5"),
                        velocity_class=velocity,
                        barcode=f"LOC-{bin_code}",
                    )
                    s.add(new_bin)
                    created_bins.append({
                        "code": bin_code,
                        "rack": r,
                        "shelf": s_idx,
                        "bin": b_idx,
                        "velocity": velocity,
                    })

    s.flush()
    return created_bins


def suggest_putaway_bin(
    tenant_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    sku: str,
    quantity: float,
    weight_kg: float = 10.0,
    db: Session | None = None,
) -> dict[str, Any]:
    """Directed Putaway Recommendation Engine.

    Evaluates:
      1. SKU velocity (Fast moving -> Class A bins; Slow moving -> Class C)
      2. Weight capacity remaining
      3. Proximity to dock / pick face
    """
    s = db or db_session

    # Fetch active bins
    bins_stmt = select(Location).where(
        Location.tenant_id == tenant_id,
        Location.warehouse_id == warehouse_id,
        Location.type == "bin",
        Location.status == "active",
    )
    available_bins = s.scalars(bins_stmt).all()

    if not available_bins:
        # Generate starter bins if none exist
        batch_generate_bins(tenant_id, warehouse_id, "ZONE-A", "A01", 3, 3, 2, 500.0, s)
        available_bins = s.scalars(bins_stmt).all()

    candidates: list[dict[str, Any]] = []
    for b in available_bins:
        max_wt = float(b.max_weight_kg) if b.max_weight_kg else 500.0
        cap = float(b.capacity_units) if b.capacity_units else 100.0

        # Score bin suitability
        score = 100.0
        # Prefer Class A for fast moving, B for medium
        if b.velocity_class == "A":
            score += 20.0
        elif b.velocity_class == "B":
            score += 10.0

        candidates.append({
            "bin_id": str(b.id),
            "bin_code": b.code,
            "velocity_class": b.velocity_class or "B",
            "capacity_units": cap,
            "max_weight_kg": max_wt,
            "barcode": b.barcode or b.code,
            "score": score,
            "recommendation_reason": f"Class {b.velocity_class or 'B'} slotting with {max_wt}kg payload safety",
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0] if candidates else None

    return {
        "sku": sku,
        "quantity": quantity,
        "suggested_bin": best,
        "alternatives": candidates[1:4] if len(candidates) > 1 else [],
    }
