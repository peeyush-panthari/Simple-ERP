from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.auth import Actor, require_any_permission
from app.services.drp_engine import DrpEngineService

router = APIRouter(prefix="/api/v1/drp", tags=["drp"])


class LanePayload(BaseModel):
    source_warehouse_id: str
    dest_warehouse_id: str
    transit_days: int = 2
    shipping_mode: str = "Road"
    carrier_name: str | None = None
    cost_per_kg: float = 0.0
    is_active: bool = True


class PolicyPayload(BaseModel):
    dest_warehouse_id: str
    product_id: str
    policy_type: str = "min_max"
    safety_stock_qty: float = 0.0
    reorder_point_qty: float = 0.0
    min_order_qty: float = 1.0
    order_multiple: float = 1.0
    target_stock_qty: float = 0.0


class CalculatePayload(BaseModel):
    commit: bool = True


@router.get("/lanes")
def list_lanes(
    actor: Annotated[Actor, Depends(require_any_permission("inventory:read", "warehouse:read"))],
):
    return DrpEngineService.list_lanes(actor["tenant_id"])


@router.post("/lanes")
def save_lane(
    payload: LanePayload,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:write", "warehouse:write"))],
):
    lane = DrpEngineService.create_or_update_lane(actor["tenant_id"], payload.model_dump())
    return {"id": str(lane.id), "status": "saved"}


@router.get("/policies")
def list_policies(
    actor: Annotated[Actor, Depends(require_any_permission("inventory:read", "warehouse:read"))],
    warehouse_id: str | None = Query(None),
):
    wh_id = uuid.UUID(warehouse_id) if warehouse_id else None
    return DrpEngineService.list_policies(actor["tenant_id"], warehouse_id=wh_id)


@router.post("/policies")
def save_policy(
    payload: PolicyPayload,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:write", "warehouse:write"))],
):
    policy = DrpEngineService.save_policy(actor["tenant_id"], payload.model_dump())
    return {"id": str(policy.id), "status": "saved"}


@router.post("/calculate")
def calculate_drp(
    payload: CalculatePayload,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:write", "warehouse:write"))],
):
    return DrpEngineService.run_drp_calculation(actor["tenant_id"], commit=payload.commit)


@router.get("/planned-orders")
def list_planned_orders(
    actor: Annotated[Actor, Depends(require_any_permission("inventory:read", "warehouse:read"))],
    status: str | None = Query(None),
    dest_warehouse_id: str | None = Query(None),
):
    dst_id = uuid.UUID(dest_warehouse_id) if dest_warehouse_id else None
    return DrpEngineService.list_planned_orders(
        actor["tenant_id"],
        status=status,
        dest_warehouse_id=dst_id,
    )


@router.post("/planned-orders/{pto_id}/release")
def release_pto(
    pto_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:write", "warehouse:write"))],
):
    transfer = DrpEngineService.release_to_transfer(actor["tenant_id"], pto_id, actor_id=actor["user_id"])
    return {
        "pto_id": str(pto_id),
        "transfer_id": str(transfer.id),
        "transfer_number": transfer.number,
        "status": transfer.status,
    }
