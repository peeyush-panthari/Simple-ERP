"""Warehouses + locations. Ported 1:1 (behavior) from backend_py/app/routes/warehouses.py."""

from __future__ import annotations

import csv
import io
import uuid as uuid_mod

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy import func, or_

from app.core.auth import Actor, require_any_permission, require_permission
from app.core.access_scope import assert_warehouse_in_scope, scope_query_by_warehouse
from app.core.audit import audit
from app.core.db import session
from app.core.errors import ProblemError, conflict, not_found, rule_violation
from app.core.pagination import ListQuery, list_response, offset_of
from app.domains.warehouses.schemas import (
    LocationBody,
    PatchLocationBody,
    PatchWarehouseBody,
    WarehouseBody,
    WarehouseBulkUploadBody,
)
from app.models.factory import Factory
from app.models.location import Location
from app.models.warehouse import Warehouse
from app.services import warehouse_repo
from app.services.sequences import next_warehouse_code

router = APIRouter(prefix="/api/v1", tags=["warehouses"])

#  Every module scoped to a warehouse depends on this list/locations pair for
#  its own dropdowns and name display, so both accept any permission from a
#  module that legitimately references warehouses - not just warehouse:read.
_WAREHOUSE_LOOKUP_PERMISSIONS = ("warehouse:read", "inventory:read", "order:read", "po:read", "user:read", "pr:read", "sourcing:read")


@router.get("/warehouses")
def list_warehouses(
    actor: Actor = Depends(require_any_permission(*_WAREHOUSE_LOOKUP_PERMISSIONS)),
    query: ListQuery = Depends(),
    status: str | None = None,
):
    q = Warehouse.query.filter(Warehouse.tenant_id == actor["tenant_id"])
    q = scope_query_by_warehouse(q, Warehouse.id, actor)
    if status:
        q = q.filter(Warehouse.status == status)
    if query.q:
        like = f"%{query.q}%"
        q = q.filter(or_(Warehouse.code.ilike(like), Warehouse.name.ilike(like)))

    total = q.count()
    rows = q.order_by(Warehouse.code).limit(query.limit).offset(offset_of(query)).all()

    location_counts = dict(
        session.query(Location.warehouse_id, func.count())
        .filter(Location.warehouse_id.in_([r.id for r in rows]))
        .group_by(Location.warehouse_id)
        .all()
    ) if rows else {}

    data = []
    for r in rows:
        api = warehouse_repo.to_warehouse_api(r)
        api["locationCount"] = location_counts.get(r.id, 0)
        data.append(api)
    return list_response(data, query, total)


@router.get("/warehouses/{id}")
def get_warehouse(id: uuid_mod.UUID, actor: Actor = Depends(require_permission("warehouse:read"))):
    warehouse = warehouse_repo.require_warehouse(actor["tenant_id"], id)
    assert_warehouse_in_scope(actor, warehouse.id)
    result = warehouse_repo.to_warehouse_api(warehouse)
    result["locations"] = [warehouse_repo.to_location_api(l) for l in warehouse_repo.locations_of(id)]
    return result


def _create_warehouse(tenant_id, actor: Actor, body: WarehouseBody) -> Warehouse:
    """Shared by the single create route and the bulk-upload route."""
    code = body.code or next_warehouse_code(tenant_id)
    clash = Warehouse.query.filter(Warehouse.tenant_id == tenant_id, func.upper(Warehouse.code) == code).first()
    if clash:
        raise conflict(f"Warehouse code {code} is already in use", code="WAREHOUSE_CODE_TAKEN")

    if body.factoryId and not Factory.query.filter_by(tenant_id=tenant_id, id=body.factoryId).first():
        raise not_found("Factory")

    warehouse = Warehouse(
        tenant_id=tenant_id,
        code=code,
        name=body.name,
        status=body.status,
        factory_id=body.factoryId,
        allowed_product_types=body.allowedProductTypes,
        address_line1=body.addressLine1,
        address_line2=body.addressLine2,
        city=body.city,
        state_code=body.stateCode,
        postal_code=body.postalCode,
        country=body.country,
        contact_email=body.contactEmail,
        contact_phone=body.contactPhone,
        capacity_units=body.capacityUnits,
        notes=body.notes,
    )
    session.add(warehouse)
    session.flush()

    # Every warehouse gets a quarantine bin up front.
    existing_quarantine = Location.query.filter_by(warehouse_id=warehouse.id, code="QUARANTINE").first()
    if not existing_quarantine:
        session.add(Location(tenant_id=tenant_id, warehouse_id=warehouse.id, code="QUARANTINE", name="Quarantine hold", type="quarantine", status="active"))

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="warehouse.created", entity_type="warehouse", entity_id=str(warehouse.id))
    session.commit()
    return warehouse


@router.post("/warehouses", status_code=201)
def create_warehouse(body: WarehouseBody, actor: Actor = Depends(require_permission("warehouse:write"))):
    tenant_id = actor["tenant_id"]
    warehouse = _create_warehouse(tenant_id, actor, body)
    return warehouse_repo.to_warehouse_api(warehouse)


BULK_UPLOAD_REQUIRED_COLUMNS = ["name"]


@router.post("/warehouses/bulk-upload")
def bulk_upload_warehouses(body: WarehouseBulkUploadBody, actor: Actor = Depends(require_permission("warehouse:write"))):
    """Creates many warehouses from one CSV in a single request - one row per
    warehouse. A bad row is reported as an error and skipped."""
    tenant_id = actor["tenant_id"]

    reader = csv.DictReader(io.StringIO(body.csvContent))
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    missing_columns = [c for c in BULK_UPLOAD_REQUIRED_COLUMNS if c not in fieldnames]
    if missing_columns:
        raise rule_violation(f"CSV is missing required column(s): {', '.join(missing_columns)}", code="BULK_CSV_INVALID_HEADERS")

    parsed = [
        (row_number, {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k})
        for row_number, raw_row in enumerate(reader, start=2)
    ]
    wanted_factories = {r.get("factoryCode") for _, r in parsed if r.get("factoryCode")}
    factories_by_code = (
        {f.code: f for f in Factory.query.filter(Factory.tenant_id == tenant_id, Factory.code.in_(wanted_factories)).all()}
        if wanted_factories
        else {}
    )

    results = []
    for row_number, row in parsed:
        if not any(row.values()):
            continue
        label = row.get("name") or f"(row {row_number})"

        factory_code = row.get("factoryCode") or ""
        factory = factories_by_code.get(factory_code) if factory_code else None
        if factory_code and not factory:
            results.append({"row": row_number, "name": label, "status": "error", "error": f"Factory code '{factory_code}' not found", "rowData": row})
            continue

        allowed_types = [t.strip() for t in (row.get("allowedProductTypes") or "").split("|") if t.strip()]

        try:
            create_body = WarehouseBody(
                code=row.get("code") or None,
                name=row.get("name") or "",
                status=row.get("status") or "active",
                factoryId=factory.id if factory else None,
                allowedProductTypes=allowed_types,
                addressLine1=row.get("addressLine1") or None,
                addressLine2=row.get("addressLine2") or None,
                city=row.get("city") or None,
                stateCode=row.get("stateCode") or None,
                postalCode=row.get("postalCode") or None,
                country=row.get("country") or "IN",
                contactEmail=row.get("contactEmail") or None,
                contactPhone=row.get("contactPhone") or None,
                capacityUnits=row.get("capacityUnits") or None,
                notes=row.get("notes") or None,
            )
        except ValidationError as exc:
            results.append({"row": row_number, "name": label, "status": "error", "error": exc.errors()[0].get("msg", "invalid data"), "rowData": row})
            continue

        try:
            warehouse = _create_warehouse(tenant_id, actor, create_body)
            results.append({"row": row_number, "name": label, "status": "success", "code": warehouse.code, "rowData": row})
        except ProblemError as exc:
            session.rollback()
            results.append({"row": row_number, "name": label, "status": "error", "error": exc.detail, "rowData": row})
        except Exception as exc:  # noqa: BLE001 - one bad row must not fail the whole batch
            session.rollback()
            results.append({"row": row_number, "name": label, "status": "error", "error": str(exc), "rowData": row})

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    return {
        "summary": {"totalRows": len(results), "successCount": success_count, "errorCount": error_count},
        "results": [
            {
                "row": r["row"],
                "name": r["name"],
                "status": r["status"],
                "code": r.get("code"),
                "error": r.get("error"),
                "rowData": r["rowData"] if r["status"] == "error" else {},
            }
            for r in results
        ],
    }


@router.patch("/warehouses/{id}")
def patch_warehouse(id: uuid_mod.UUID, body: PatchWarehouseBody, actor: Actor = Depends(require_permission("warehouse:write"))):
    tenant_id = actor["tenant_id"]
    warehouse = warehouse_repo.require_warehouse(tenant_id, id)
    assert_warehouse_in_scope(actor, warehouse.id)
    fields_set = body.model_fields_set

    if body.name is not None:
        warehouse.name = body.name
    if body.status is not None:
        warehouse.status = body.status
    if "factoryId" in fields_set:
        if body.factoryId and not Factory.query.filter_by(tenant_id=tenant_id, id=body.factoryId).first():
            raise not_found("Factory")
        warehouse.factory_id = body.factoryId
    if body.allowedProductTypes is not None:
        warehouse.allowed_product_types = body.allowedProductTypes
    if "addressLine1" in fields_set:
        warehouse.address_line1 = body.addressLine1
    if "addressLine2" in fields_set:
        warehouse.address_line2 = body.addressLine2
    if "city" in fields_set:
        warehouse.city = body.city
    if "stateCode" in fields_set:
        warehouse.state_code = body.stateCode
    if "postalCode" in fields_set:
        warehouse.postal_code = body.postalCode
    if body.country is not None:
        warehouse.country = body.country
    if "contactEmail" in fields_set:
        warehouse.contact_email = body.contactEmail
    if "contactPhone" in fields_set:
        warehouse.contact_phone = body.contactPhone
    if "capacityUnits" in fields_set:
        warehouse.capacity_units = body.capacityUnits
    if "notes" in fields_set:
        warehouse.notes = body.notes

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="warehouse.updated", entity_type="warehouse", entity_id=str(id))
    session.commit()

    return warehouse_repo.to_warehouse_api(warehouse)


@router.get("/warehouses/{id}/locations")
def list_locations(id: uuid_mod.UUID, actor: Actor = Depends(require_any_permission(*_WAREHOUSE_LOOKUP_PERMISSIONS))):
    warehouse_repo.require_warehouse(actor["tenant_id"], id)
    assert_warehouse_in_scope(actor, id)
    return {"data": [warehouse_repo.to_location_api(l) for l in warehouse_repo.locations_of(id)]}


@router.post("/warehouses/{id}/locations", status_code=201)
def create_location(id: uuid_mod.UUID, body: LocationBody, actor: Actor = Depends(require_permission("warehouse:write"))):
    tenant_id = actor["tenant_id"]
    warehouse = warehouse_repo.require_warehouse(tenant_id, id)
    assert_warehouse_in_scope(actor, id)

    parent = None
    if body.parentId:
        parent = warehouse_repo.find_location(tenant_id, body.parentId)
        if not parent:
            raise not_found("Parent location")
        if parent.warehouse_id != id:
            raise rule_violation("The parent location belongs to a different warehouse", code="LOCATION_PARENT_MISMATCH")

    if warehouse.allowed_product_types and body.allowedProductTypes:
        widened = [t for t in body.allowedProductTypes if t not in warehouse.allowed_product_types]
        if widened:
            raise rule_violation(f"Warehouse {warehouse.code} does not stock {', '.join(widened)} — a location inside it cannot either", code="LOCATION_TYPE_WIDENS_WAREHOUSE")

    clash = Location.query.filter(Location.warehouse_id == id, func.upper(Location.code) == body.code).first()
    if clash:
        raise conflict(f"Location {body.code} already exists in {warehouse.code}", code="LOCATION_CODE_TAKEN")

    location = Location(
        tenant_id=tenant_id,
        warehouse_id=id,
        parent_id=body.parentId,
        code=body.code,
        name=body.name,
        type=body.type,
        status=body.status,
        allowed_product_types=body.allowedProductTypes,
        capacity_units=body.capacityUnits,
        temperature_controlled=body.temperatureControlled,
    )
    session.add(location)
    session.flush()

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="location.created", entity_type="location", entity_id=str(location.id))
    session.commit()

    return warehouse_repo.to_location_api(location)


@router.patch("/locations/{id}")
def patch_location(id: uuid_mod.UUID, body: PatchLocationBody, actor: Actor = Depends(require_permission("warehouse:write"))):
    tenant_id = actor["tenant_id"]
    location = warehouse_repo.require_location(tenant_id, id)
    assert_warehouse_in_scope(actor, location.warehouse_id)
    fields_set = body.model_fields_set

    if "name" in fields_set:
        location.name = body.name
    if body.type is not None:
        location.type = body.type
    if body.status is not None:
        location.status = body.status
    if body.allowedProductTypes is not None:
        location.allowed_product_types = body.allowedProductTypes
    if "capacityUnits" in fields_set:
        location.capacity_units = body.capacityUnits
    if body.temperatureControlled is not None:
        location.temperature_controlled = body.temperatureControlled

    audit(tenant_id=tenant_id, actor_id=actor["user_id"], actor_email=actor["email"], action="location.updated", entity_type="location", entity_id=str(id))
    session.commit()

    return warehouse_repo.to_location_api(location)
