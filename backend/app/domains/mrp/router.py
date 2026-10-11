from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.domains.mrp.engine import release_planned_orders, run_mrp_calculation
from app.domains.mrp.schemas import MrpPlannedOrderOut, MrpRunOut, MrpRunRequest, ReleaseOrdersRequest
from app.models.mrp import MrpPlannedOrder, MrpRun

router = APIRouter(prefix="/api/v1/mrp", tags=["mrp"])


@router.post("/runs", response_model=MrpRunOut)
def trigger_mrp_run(
    body: MrpRunRequest,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:write", "po:write"))],
):
    tenant_id = actor["tenant_id"]
    try:
        run = run_mrp_calculation(
            tenant_id=tenant_id,
            horizon_days=body.horizonDays,
            warehouse_id=body.warehouseId,
            notes=body.notes,
            actor_email=actor.get("email"),
        )
        orders = session.execute(
            select(MrpPlannedOrder).where(MrpPlannedOrder.mrp_run_id == run.id).order_by(MrpPlannedOrder.required_by_date)
        ).scalars().all()

        return MrpRunOut(
            id=run.id,
            number=run.number,
            horizonDays=run.horizon_days,
            warehouseId=run.warehouse_id,
            warehouseCode=run.warehouse_code,
            status=run.status,
            totalSkusAnalyzed=run.total_skus_analyzed,
            plannedOrdersCount=run.planned_orders_count,
            notes=run.notes,
            createdBy=run.created_by,
            createdAt=run.created_at,
            plannedOrders=[
                MrpPlannedOrderOut(
                    id=o.id,
                    mrpRunId=o.mrp_run_id,
                    productId=o.product_id,
                    sku=o.sku,
                    productName=o.product_name,
                    orderType=o.order_type,
                    warehouseId=o.warehouse_id,
                    warehouseCode=o.warehouse_code,
                    quantity=o.quantity,
                    uom=o.uom,
                    suggestedOrderDate=o.suggested_order_date,
                    requiredByDate=o.required_by_date,
                    leadTimeDays=o.lead_time_days,
                    estimatedUnitCost=o.estimated_unit_cost,
                    status=o.status,
                    sourceDemand=o.source_demand,
                    releasedReferenceType=o.released_reference_type,
                    releasedReferenceId=o.released_reference_id,
                    releasedReferenceNumber=o.released_reference_number,
                    releasedAt=o.released_at,
                    releasedBy=o.released_by,
                    createdAt=o.created_at,
                )
                for o in orders
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs", response_model=list[MrpRunOut])
def list_mrp_runs(
    actor: Annotated[Actor, Depends(require_any_permission("inventory:read", "po:read"))],
):
    tenant_id = actor["tenant_id"]
    runs = session.execute(
        select(MrpRun).where(MrpRun.tenant_id == tenant_id).order_by(desc(MrpRun.created_at)).limit(50)
    ).scalars().all()

    out = []
    for r in runs:
        orders = session.execute(
            select(MrpPlannedOrder).where(MrpPlannedOrder.mrp_run_id == r.id).order_by(MrpPlannedOrder.required_by_date)
        ).scalars().all()
        out.append(
            MrpRunOut(
                id=r.id,
                number=r.number,
                horizonDays=r.horizon_days,
                warehouseId=r.warehouse_id,
                warehouseCode=r.warehouse_code,
                status=r.status,
                totalSkusAnalyzed=r.total_skus_analyzed,
                plannedOrdersCount=r.planned_orders_count,
                notes=r.notes,
                createdBy=r.created_by,
                createdAt=r.created_at,
                plannedOrders=[
                    MrpPlannedOrderOut(
                        id=o.id,
                        mrpRunId=o.mrp_run_id,
                        productId=o.product_id,
                        sku=o.sku,
                        productName=o.product_name,
                        orderType=o.order_type,
                        warehouseId=o.warehouse_id,
                        warehouseCode=o.warehouse_code,
                        quantity=o.quantity,
                        uom=o.uom,
                        suggestedOrderDate=o.suggested_order_date,
                        requiredByDate=o.required_by_date,
                        leadTimeDays=o.lead_time_days,
                        estimatedUnitCost=o.estimated_unit_cost,
                        status=o.status,
                        sourceDemand=o.source_demand,
                        releasedReferenceType=o.released_reference_type,
                        releasedReferenceId=o.released_reference_id,
                        releasedReferenceNumber=o.released_reference_number,
                        releasedAt=o.released_at,
                        releasedBy=o.released_by,
                        createdAt=o.created_at,
                    )
                    for o in orders
                ],
            )
        )
    return out


@router.get("/runs/{run_id}", response_model=MrpRunOut)
def get_mrp_run(
    run_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:read", "po:read"))],
):
    tenant_id = actor["tenant_id"]
    r = session.execute(
        select(MrpRun).where(MrpRun.tenant_id == tenant_id, MrpRun.id == run_id)
    ).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="MRP run not found")

    orders = session.execute(
        select(MrpPlannedOrder).where(MrpPlannedOrder.mrp_run_id == r.id).order_by(MrpPlannedOrder.required_by_date)
    ).scalars().all()

    return MrpRunOut(
        id=r.id,
        number=r.number,
        horizonDays=r.horizon_days,
        warehouseId=r.warehouse_id,
        warehouseCode=r.warehouse_code,
        status=r.status,
        totalSkusAnalyzed=r.total_skus_analyzed,
        plannedOrdersCount=r.planned_orders_count,
        notes=r.notes,
        createdBy=r.created_by,
        createdAt=r.created_at,
        plannedOrders=[
            MrpPlannedOrderOut(
                id=o.id,
                mrpRunId=o.mrp_run_id,
                productId=o.product_id,
                sku=o.sku,
                productName=o.product_name,
                orderType=o.order_type,
                warehouseId=o.warehouse_id,
                warehouseCode=o.warehouse_code,
                quantity=o.quantity,
                uom=o.uom,
                suggestedOrderDate=o.suggested_order_date,
                requiredByDate=o.required_by_date,
                leadTimeDays=o.lead_time_days,
                estimatedUnitCost=o.estimated_unit_cost,
                status=o.status,
                sourceDemand=o.source_demand,
                releasedReferenceType=o.released_reference_type,
                releasedReferenceId=o.released_reference_id,
                releasedReferenceNumber=o.released_reference_number,
                releasedAt=o.released_at,
                releasedBy=o.released_by,
                createdAt=o.created_at,
            )
            for o in orders
        ],
    )


@router.post("/planned-orders/release")
def release_orders(
    body: ReleaseOrdersRequest,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:write", "po:write"))],
):
    tenant_id = actor["tenant_id"]
    released = release_planned_orders(tenant_id, body.plannedOrderIds, actor)
    return {"status": "success", "releasedCount": len(released), "items": released}
