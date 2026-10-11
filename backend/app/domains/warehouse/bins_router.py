from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.models.location import Location
from app.models.putaway_task import PutawayTask
from app.models.warehouse import Warehouse
from app.services.putaway_engine import (
    batch_generate_bins,
    get_rack_matrix,
    get_warehouse_location_tree,
    suggest_putaway_bin,
)

router = APIRouter(prefix="/api/v1/wms-bins", tags=["wms-bins"])


class BatchGenerateRequest(BaseModel):
    warehouse_id: uuid.UUID
    zone_code: str = Field(default="ZONE-A")
    aisle_prefix: str = Field(default="A01")
    racks_count: int = Field(default=4, ge=1, le=20)
    shelves_count: int = Field(default=3, ge=1, le=10)
    bins_per_shelf: int = Field(default=2, ge=1, le=10)
    default_weight_kg: float = Field(default=500.0, gt=0)


class SuggestPutawayRequest(BaseModel):
    warehouse_id: uuid.UUID
    sku: str
    quantity: float = Field(default=1.0, gt=0)
    weight_kg: float = Field(default=10.0, ge=0)


class ConfirmPutawayRequest(BaseModel):
    actual_bin_id: uuid.UUID
    note: str | None = None


@router.get("/warehouses")
def list_warehouses(
    actor: Annotated[Actor, Depends(require_any_permission("warehouse:read", "wms_bins:read", "*"))],
):
    """List warehouses for the current tenant."""
    whs = session.scalars(
        select(Warehouse)
        .where(Warehouse.tenant_id == actor["tenant_id"], Warehouse.status == "active")
        .order_by(Warehouse.code)
    ).all()
    return [{"id": str(w.id), "code": w.code, "name": w.name} for w in whs]


@router.get("/tree")
def get_tree(
    warehouse_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("warehouse:read", "wms_bins:read", "*"))],
):
    """Get recursive 3D hierarchy tree of locations in a warehouse."""
    return get_warehouse_location_tree(warehouse_id, actor["tenant_id"], session)


@router.get("/rack-matrix")
def get_matrix(
    warehouse_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("warehouse:read", "wms_bins:read", "*"))],
    aisle_code: str | None = None,
):
    """Get 2D grid matrix of bins with occupancy and stored SKUs."""
    return get_rack_matrix(warehouse_id, actor["tenant_id"], aisle_code, session)


@router.post("/batch-generate")
def generate_bins_endpoint(
    req: BatchGenerateRequest,
    actor: Annotated[Actor, Depends(require_any_permission("warehouse:write", "wms_bins:write", "*"))],
):
    """Batch generate Zone -> Aisle -> Rack -> Shelf -> Bin coordinates."""
    created = batch_generate_bins(
        tenant_id=actor["tenant_id"],
        warehouse_id=req.warehouse_id,
        zone_code=req.zone_code,
        aisle_prefix=req.aisle_prefix,
        racks_count=req.racks_count,
        shelves_count=req.shelves_count,
        bins_per_shelf=req.bins_per_shelf,
        default_weight_kg=req.default_weight_kg,
        db=session,
    )
    session.commit()
    return {"message": f"Generated {len(created)} bins successfully", "bins": created}


@router.post("/suggest")
def suggest_endpoint(
    req: SuggestPutawayRequest,
    actor: Annotated[Actor, Depends(require_any_permission("warehouse:read", "wms_bins:read", "*"))],
):
    """Recommend optimal bin using directed putaway algorithms."""
    return suggest_putaway_bin(
        tenant_id=actor["tenant_id"],
        warehouse_id=req.warehouse_id,
        sku=req.sku,
        quantity=req.quantity,
        weight_kg=req.weight_kg,
        db=session,
    )


@router.get("/tasks")
def list_putaway_tasks(
    actor: Annotated[Actor, Depends(require_any_permission("warehouse:read", "wms_bins:read", "*"))],
    warehouse_id: uuid.UUID | None = None,
):
    """List putaway tasks."""
    query = select(PutawayTask).where(PutawayTask.tenant_id == actor["tenant_id"])
    if warehouse_id:
        query = query.where(PutawayTask.warehouse_id == warehouse_id)
    query = query.order_by(desc(PutawayTask.completed_at)).limit(50)
    tasks = session.scalars(query).all()
    return [
        {
            "id": str(t.id),
            "grn_id": str(t.grn_id),
            "sku": t.sku,
            "quantity": float(t.quantity),
            "uom": t.uom,
            "from_location_code": t.from_location_code,
            "to_location_code": t.to_location_code,
            "completed_by": t.completed_by,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "note": t.note,
        }
        for t in tasks
    ]
