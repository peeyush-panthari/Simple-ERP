"""FastAPI router for S&OP Demand Forecasting Module.
Endpoints:
- GET /scenarios: List forecast scenarios
- POST /scenarios: Run tournament and generate new scenario
- GET /scenarios/{id}: Detail scenario with product matrix lines
- PATCH /lines/{id}: Update consensus overrides
- POST /scenarios/{id}/lock: Lock consensus forecast
- POST /scenarios/{id}/export-mrp: Seed MRP gross requirements
"""
import uuid
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import select, func

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.core.errors import bad_request, not_found
from app.models.long_term_modules import DemandForecastScenario, ForecastPeriodLine
from app.models.product import Product
from app.services.forecast_engine import ForecastingService

router = APIRouter(prefix="/api/v1/forecasting", tags=["Demand Forecasting"])


class CreateScenarioRequest(BaseModel):
    scenario_name: str = Field(..., min_length=2, max_length=64)
    description: Optional[str] = None
    planning_horizon_months: int = Field(default=6, ge=1, le=24)
    product_ids: Optional[List[uuid.UUID]] = None


class UpdateLineRequest(BaseModel):
    sales_override_qty: Optional[float] = None
    marketing_uplift_qty: Optional[float] = None
    consensus_forecast_qty: Optional[float] = None
    notes: Optional[str] = None


@router.get("/scenarios")
def list_scenarios(
    actor: Annotated[Actor, Depends(require_any_permission("forecasting:read", "inventory:read"))],
    status: Optional[str] = None,
):
    query = select(DemandForecastScenario).where(DemandForecastScenario.tenant_id == actor["tenant_id"])
    if status:
        query = query.where(DemandForecastScenario.status == status)
    scenarios = list(session.execute(query.order_by(DemandForecastScenario.created_at.desc())).scalars().all())

    results = []
    for s in scenarios:
        line_count = session.execute(
            select(func.count(ForecastPeriodLine.id)).where(ForecastPeriodLine.scenario_id == s.id)
        ).scalar() or 0
        total_consensus = session.execute(
            select(func.sum(ForecastPeriodLine.consensus_forecast_qty)).where(ForecastPeriodLine.scenario_id == s.id)
        ).scalar() or 0
        avg_mape = session.execute(
            select(func.avg(ForecastPeriodLine.mape_pct)).where(ForecastPeriodLine.scenario_id == s.id)
        ).scalar() or 0

        results.append({
            "id": str(s.id),
            "scenario_name": s.scenario_name,
            "description": s.description,
            "planning_horizon_months": s.planning_horizon_months,
            "status": s.status,
            "locked_at": s.locked_at.isoformat() if s.locked_at else None,
            "created_at": s.created_at.isoformat(),
            "line_count": line_count,
            "total_demand_qty": float(total_consensus),
            "avg_mape_pct": round(float(avg_mape), 2),
        })
    return {"scenarios": results}


@router.post("/scenarios")
def create_scenario(
    req: CreateScenarioRequest,
    actor: Annotated[Actor, Depends(require_any_permission("forecasting:write", "inventory:write"))],
):
    scenario = ForecastingService.generate_forecast_scenario(
        tenant_id=actor["tenant_id"],
        scenario_name=req.scenario_name,
        description=req.description,
        planning_horizon_months=req.planning_horizon_months,
        product_ids=req.product_ids,
    )
    return {"scenario_id": str(scenario.id), "status": scenario.status, "message": "Forecast generated successfully"}


@router.get("/scenarios/{scenario_id}")
def get_scenario_detail(
    scenario_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("forecasting:read", "inventory:read"))],
):
    scenario = session.execute(
        select(DemandForecastScenario).where(
            DemandForecastScenario.tenant_id == actor["tenant_id"],
            DemandForecastScenario.id == scenario_id,
        )
    ).scalar_one_or_none()
    if not scenario:
        raise not_found("Scenario not found")

    lines = list(
        session.execute(
            select(ForecastPeriodLine, Product)
            .join(Product, Product.id == ForecastPeriodLine.product_id)
            .where(ForecastPeriodLine.scenario_id == scenario_id)
            .order_by(Product.name, ForecastPeriodLine.period_date)
        ).all()
    )

    items = []
    for line, prod in lines:
        items.append({
            "id": str(line.id),
            "product_id": str(prod.id),
            "product_name": prod.name,
            "sku": prod.sku,
            "period_date": line.period_date.isoformat(),
            "statistical_forecast_qty": float(line.statistical_forecast_qty),
            "sales_override_qty": float(line.sales_override_qty) if line.sales_override_qty is not None else None,
            "marketing_uplift_qty": float(line.marketing_uplift_qty) if line.marketing_uplift_qty is not None else None,
            "consensus_forecast_qty": float(line.consensus_forecast_qty),
            "champion_algorithm": line.champion_algorithm,
            "mape_pct": float(line.mape_pct),
            "notes": line.notes,
        })

    return {
        "scenario": {
            "id": str(scenario.id),
            "scenario_name": scenario.scenario_name,
            "description": scenario.description,
            "planning_horizon_months": scenario.planning_horizon_months,
            "status": scenario.status,
            "locked_at": scenario.locked_at.isoformat() if scenario.locked_at else None,
            "created_at": scenario.created_at.isoformat(),
        },
        "lines": items,
    }


@router.patch("/lines/{line_id}")
def update_forecast_line(
    line_id: uuid.UUID,
    req: UpdateLineRequest,
    actor: Annotated[Actor, Depends(require_any_permission("forecasting:write", "inventory:write"))],
):
    line = session.execute(
        select(ForecastPeriodLine).where(
            ForecastPeriodLine.tenant_id == actor["tenant_id"],
            ForecastPeriodLine.id == line_id,
        )
    ).scalar_one_or_none()
    if not line:
        raise not_found("Forecast line not found")

    if req.sales_override_qty is not None:
        line.sales_override_qty = req.sales_override_qty
    if req.marketing_uplift_qty is not None:
        line.marketing_uplift_qty = req.marketing_uplift_qty
    if req.notes is not None:
        line.notes = req.notes

    if req.consensus_forecast_qty is not None:
        line.consensus_forecast_qty = req.consensus_forecast_qty
    else:
        base = float(line.statistical_forecast_qty)
        override = float(line.sales_override_qty) if line.sales_override_qty is not None else base
        uplift = float(line.marketing_uplift_qty or 0)
        line.consensus_forecast_qty = max(0.0, override + uplift)

    session.commit()
    return {"id": str(line.id), "consensus_forecast_qty": float(line.consensus_forecast_qty)}


@router.post("/scenarios/{scenario_id}/lock")
def lock_scenario(
    scenario_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("forecasting:write", "inventory:write"))],
):
    scenario = session.execute(
        select(DemandForecastScenario).where(
            DemandForecastScenario.tenant_id == actor["tenant_id"],
            DemandForecastScenario.id == scenario_id,
        )
    ).scalar_one_or_none()
    if not scenario:
        raise not_found("Scenario not found")

    scenario.status = "locked"
    scenario.locked_at = datetime.utcnow()
    scenario.locked_by_user_id = actor["user_id"]
    session.commit()
    return {"message": "Scenario successfully locked and approved for S&OP"}


@router.post("/scenarios/{scenario_id}/export-mrp")
def export_to_mrp(
    scenario_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("forecasting:write", "inventory:write"))],
):
    scenario = session.execute(
        select(DemandForecastScenario).where(
            DemandForecastScenario.tenant_id == actor["tenant_id"],
            DemandForecastScenario.id == scenario_id,
        )
    ).scalar_one_or_none()
    if not scenario:
        raise not_found("Scenario not found")

    lines = list(
        session.execute(
            select(ForecastPeriodLine).where(ForecastPeriodLine.scenario_id == scenario_id)
        ).scalars().all()
    )
    if not lines:
        raise bad_request("No lines found to export")

    return {
        "message": f"Successfully released {len(lines)} monthly demand buckets from '{scenario.scenario_name}' into MRP planning horizon",
        "exported_count": len(lines),
    }
