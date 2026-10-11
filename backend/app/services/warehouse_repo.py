"""Warehouse/location queries + API projections. Ported from
backend_py/app/services/warehouse_repo.py."""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import session
from app.core.errors import not_found
from app.core.money import decimal_str, to_decimal
from app.models.doc_sequence import DocSequence
from app.models.factory import Factory
from app.models.inventory_item import InventoryItem
from app.models.location import Location
from app.models.warehouse import Warehouse


def find_warehouse(tenant_id: uuid.UUID, warehouse_id: uuid.UUID) -> Warehouse | None:
    return Warehouse.query.filter_by(tenant_id=tenant_id, id=warehouse_id).first()


def require_warehouse(tenant_id: uuid.UUID, warehouse_id: uuid.UUID) -> Warehouse:
    warehouse = find_warehouse(tenant_id, warehouse_id)
    if not warehouse:
        raise not_found("Warehouse")
    return warehouse


def find_warehouse_by_code(tenant_id: uuid.UUID, code: str) -> Warehouse | None:
    from sqlalchemy import func

    return Warehouse.query.filter(Warehouse.tenant_id == tenant_id, func.upper(Warehouse.code) == code.upper()).first()


def find_warehouses_by_codes(tenant_id: uuid.UUID, codes: list[str]) -> dict[str, Warehouse]:
    from sqlalchemy import func

    wanted = {code.upper() for code in codes if code}
    if not wanted:
        return {}
    rows = Warehouse.query.filter(Warehouse.tenant_id == tenant_id, func.upper(Warehouse.code).in_(wanted)).all()
    return {w.code.upper(): w for w in rows}


def find_locations_by_codes(pairs: list[tuple[uuid.UUID, str]]) -> dict[tuple[uuid.UUID, str], Location]:
    """Batched warehouse-scoped location lookup, keyed by (warehouse_id, UPPERCASED code)."""
    from sqlalchemy import func

    wanted = {(wid, code.upper()) for wid, code in pairs if wid and code}
    if not wanted:
        return {}
    rows = Location.query.filter(
        Location.warehouse_id.in_({wid for wid, _ in wanted}),
        func.upper(Location.code).in_({code for _, code in wanted}),
    ).all()
    found = {(l.warehouse_id, l.code.upper()): l for l in rows}
    return {key: found[key] for key in wanted if key in found}


def find_location(tenant_id: uuid.UUID, location_id: uuid.UUID) -> Location | None:
    return Location.query.filter_by(tenant_id=tenant_id, id=location_id).first()


def require_location(tenant_id: uuid.UUID, location_id: uuid.UUID) -> Location:
    location = find_location(tenant_id, location_id)
    if not location:
        raise not_found("Location")
    return location


def locations_of(warehouse_id: uuid.UUID) -> list[Location]:
    return Location.query.filter_by(warehouse_id=warehouse_id).order_by(Location.code).all()


# ---- API projections --------------------------------------------------------


def to_warehouse_api(row: Warehouse) -> dict:
    factory = Factory.query.filter_by(id=row.factory_id).first() if row.factory_id else None
    return {
        "id": str(row.id),
        "code": row.code,
        "name": row.name,
        "status": row.status,
        "factoryId": str(row.factory_id) if row.factory_id else None,
        "factoryName": factory.name if factory else None,
        "allowedProductTypes": row.allowed_product_types or [],
        "addressLine1": row.address_line1,
        "addressLine2": row.address_line2,
        "city": row.city,
        "stateCode": row.state_code,
        "postalCode": row.postal_code,
        "country": row.country,
        "contactEmail": row.contact_email,
        "contactPhone": row.contact_phone,
        "capacityUnits": decimal_str(row.capacity_units) if row.capacity_units is not None else None,
        "notes": row.notes,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def to_location_api(row: Location) -> dict:
    return {
        "id": str(row.id),
        "warehouseId": str(row.warehouse_id),
        "parentId": str(row.parent_id) if row.parent_id else None,
        "code": row.code,
        "name": row.name,
        "type": row.type,
        "status": row.status,
        "allowedProductTypes": row.allowed_product_types or [],
        "capacityUnits": decimal_str(row.capacity_units) if row.capacity_units is not None else None,
        "temperatureControlled": row.temperature_controlled,
    }


# ---- direct-call helpers other domains import instead of an HTTP hop -------


def get_warehouse_summary(tenant_id: uuid.UUID, warehouse_id: uuid.UUID) -> dict | None:
    w = find_warehouse(tenant_id, warehouse_id)
    if not w:
        return None
    return {
        "id": str(w.id),
        "code": w.code,
        "name": w.name,
        "status": w.status,
        "factoryId": str(w.factory_id) if w.factory_id else None,
        "allowedProductTypes": w.allowed_product_types or [],
        "addressLine1": w.address_line1,
        "addressLine2": w.address_line2,
        "city": w.city,
        "stateCode": w.state_code,
        "postalCode": w.postal_code,
        "country": w.country,
        "contactEmail": w.contact_email,
    }


def get_location_summary(tenant_id: uuid.UUID, location_id: uuid.UUID) -> dict | None:
    location = find_location(tenant_id, location_id)
    return to_location_api(location) if location else None


def reserve_finished_good_ids(tenant_id: uuid.UUID, count: int) -> list[str]:
    """Reserves `count` consecutive FG-IDs from the tenant's FG counter, one
    atomic bump. Must be called inside the caller's transaction."""
    if count <= 0:
        return []
    stmt = (
        pg_insert(DocSequence)
        .values(tenant_id=tenant_id, prefix="FG", current_value=100000 + count)
        .on_conflict_do_update(index_elements=["tenant_id", "prefix"], set_={"current_value": DocSequence.current_value + count})
        .returning(DocSequence.current_value)
    )
    end = session.execute(stmt).scalar_one()
    start = end - count + 1
    return [f"FG-{str(v).zfill(6)}" for v in range(start, end + 1)]


def consume_inventory_items_for_production(
    tenant_id: uuid.UUID,
    *,
    production_run_id: uuid.UUID,
    number: str,
    warehouse_id: uuid.UUID,
    consumed: list[dict],
    consumed_items: list[dict] | None = None,
) -> list[dict]:
    """Retires the Inventory-ID ledger so it stays honest once raw materials
    are consumed into a build. Not yet called by anything in this port
    (production isn't ported - see the migration plan's phasing), kept here
    ready for when it is."""
    draws: list[dict] = []

    if consumed_items:
        for sel in consumed_items:
            item = session.query(InventoryItem).filter_by(tenant_id=tenant_id, id=sel["itemId"]).with_for_update().first()
            if not item:
                continue
            available = to_decimal(item.accepted_qty) - to_decimal(item.consumed_qty) - to_decimal(item.written_off_qty)
            take = to_decimal(sel["quantity"])
            applied = available if take > available else take
            if applied <= 0:
                continue
            item.consumed_qty = to_decimal(item.consumed_qty) + applied
            item.consumed_run_id = production_run_id
            item.consumed_run_number = number
            draws.append({"itemId": str(item.id), "quantity": decimal_str(applied)})
        return draws

    for line in consumed:
        remaining = to_decimal(line["quantity"])
        if remaining <= 0:
            continue
        items = (
            session.query(InventoryItem)
            .filter(
                InventoryItem.tenant_id == tenant_id,
                InventoryItem.warehouse_id == warehouse_id,
                InventoryItem.product_id == line["productId"],
                InventoryItem.accepted_qty - InventoryItem.consumed_qty - InventoryItem.written_off_qty > 0,
                InventoryItem.transfer_id.is_(None),
                InventoryItem.bucket == "available",
            )
            .order_by(InventoryItem.received_date.asc().nulls_last(), InventoryItem.inventory_id.asc())
            .with_for_update()
            .all()
        )
        for item in items:
            if remaining <= 0:
                break
            available = to_decimal(item.accepted_qty) - to_decimal(item.consumed_qty) - to_decimal(item.written_off_qty)
            take = remaining if available >= remaining else available
            item.consumed_qty = to_decimal(item.consumed_qty) + take
            remaining -= take
            draws.append({"itemId": str(item.id), "quantity": decimal_str(take)})

    return draws
