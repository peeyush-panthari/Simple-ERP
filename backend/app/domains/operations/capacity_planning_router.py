"""FastAPI router for Work Center Finite Capacity Planning & RCCP.
Endpoints:
- GET /work-centers: List manufacturing work centers with daily capacities and load status
- POST /work-centers: Create a new work center
- GET /schedule: List job assignments by date range with bottleneck overload detection
- POST /schedule: Assign a production run / task to a work center
- POST /schedule/{id}/reassign: Reassign job to an alternate work center to resolve bottleneck
- GET /rccp-summary: Rough-Cut Capacity Planning load vs capacity summary by station
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import select, func, and_

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.core.errors import bad_request, not_found
from app.models.phase3_modules import WorkCenter, WorkCenterSchedule
from app.models.production_run import ProductionRun
from app.models.warehouse import Warehouse

router = APIRouter(prefix="/api/v1/capacity-planning", tags=["Capacity Planning"])


class CreateWorkCenterRequest(BaseModel):
    code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=128)
    department: str = Field(default="Assembly", max_length=64)
    warehouse_id: Optional[uuid.UUID] = None
    daily_capacity_hours: float = Field(default=16.0, gt=0)
    efficiency_factor: float = Field(default=0.85, ge=0.1, le=1.0)
    hourly_machine_rate: float = Field(default=750.0, ge=0)
    hourly_labor_rate: float = Field(default=350.0, ge=0)
    status: str = Field(default="active", pattern="^(active|maintenance|inactive)$")
    notes: Optional[str] = None


class ScheduleJobRequest(BaseModel):
    work_center_id: uuid.UUID
    task_name: str = Field(..., max_length=128)
    schedule_date: date
    shift: str = Field(default="day", pattern="^(day|evening|night)$")
    required_hours: float = Field(..., gt=0)
    production_run_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class ReassignJobRequest(BaseModel):
    target_work_center_id: uuid.UUID
    target_date: Optional[date] = None
    target_shift: Optional[str] = Field(default=None, pattern="^(day|evening|night)$")


@router.get("/work-centers")
def list_work_centers(
    actor: Annotated[Actor, Depends(require_any_permission("capacity_planning:read", "inventory:read", "*"))],
    department: Optional[str] = None,
):
    query = select(WorkCenter).where(WorkCenter.tenant_id == actor["tenant_id"])
    if department:
        query = query.where(WorkCenter.department == department)
    query = query.order_by(WorkCenter.code.asc())

    records = session.execute(query).scalars().all()
    warehouses_map = {w.id: w for w in session.execute(select(Warehouse).where(Warehouse.tenant_id == actor["tenant_id"])).scalars().all()}

    # Calculate active scheduled load for current week
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    from collections import defaultdict
    
    wc_ids = [wc.id for wc in records]
    all_scheds = []
    if wc_ids:
        all_scheds = session.execute(
            select(WorkCenterSchedule).where(
                WorkCenterSchedule.tenant_id == actor["tenant_id"],
                WorkCenterSchedule.work_center_id.in_(wc_ids),
                WorkCenterSchedule.schedule_date >= week_start,
                WorkCenterSchedule.schedule_date <= week_end,
            )
        ).scalars().all()
        
    scheds_by_wc = defaultdict(list)
    for s in all_scheds:
        scheds_by_wc[s.work_center_id].append(s)

    res = []
    for wc in records:
        scheds = scheds_by_wc.get(wc.id, [])

        total_booked_hours = sum((float(s.required_hours) for s in scheds), 0.0)
        # Weekly effective capacity = daily_capacity_hours * 6 working days * efficiency
        weekly_effective_cap = float(wc.daily_capacity_hours) * 6.0 * float(wc.efficiency_factor)
        utilization_pct = round((total_booked_hours / weekly_effective_cap * 100.0) if weekly_effective_cap > 0 else 0.0, 1)

        res.append({
            "id": str(wc.id),
            "code": wc.code,
            "name": wc.name,
            "department": wc.department,
            "warehouse_id": str(wc.warehouse_id) if wc.warehouse_id else None,
            "warehouse_name": warehouses_map[wc.warehouse_id].name if wc.warehouse_id in warehouses_map else "Plant Floor",
            "daily_capacity_hours": float(wc.daily_capacity_hours),
            "efficiency_factor": float(wc.efficiency_factor),
            "hourly_machine_rate": float(wc.hourly_machine_rate),
            "hourly_labor_rate": float(wc.hourly_labor_rate),
            "status": wc.status,
            "weekly_effective_capacity": round(weekly_effective_cap, 1),
            "weekly_booked_hours": round(total_booked_hours, 1),
            "utilization_pct": utilization_pct,
            "is_overloaded": utilization_pct > 100.0,
            "notes": wc.notes,
        })

    return {"work_centers": res}


@router.post("/work-centers")
def create_work_center(
    req: CreateWorkCenterRequest,
    actor: Annotated[Actor, Depends(require_any_permission("capacity_planning:write", "*"))],
):
    wc = WorkCenter(
        tenant_id=actor["tenant_id"],
        code=req.code.strip().upper(),
        name=req.name.strip(),
        department=req.department.strip(),
        warehouse_id=req.warehouse_id,
        daily_capacity_hours=Decimal(str(req.daily_capacity_hours)),
        efficiency_factor=Decimal(str(req.efficiency_factor)),
        hourly_machine_rate=Decimal(str(req.hourly_machine_rate)),
        hourly_labor_rate=Decimal(str(req.hourly_labor_rate)),
        status=req.status,
        notes=req.notes,
    )
    session.add(wc)
    session.commit()

    return {
        "id": str(wc.id),
        "code": wc.code,
        "name": wc.name,
        "message": f"Work Center {wc.code} registered with {wc.daily_capacity_hours}h daily capacity.",
    }


@router.get("/schedule")
def list_schedule(
    actor: Annotated[Actor, Depends(require_any_permission("capacity_planning:read", "*"))],
    work_center_id: Optional[uuid.UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    query = select(WorkCenterSchedule).where(WorkCenterSchedule.tenant_id == actor["tenant_id"])
    if work_center_id:
        query = query.where(WorkCenterSchedule.work_center_id == work_center_id)
    if start_date:
        query = query.where(WorkCenterSchedule.schedule_date >= start_date)
    if end_date:
        query = query.where(WorkCenterSchedule.schedule_date <= end_date)
    query = query.order_by(WorkCenterSchedule.schedule_date.asc(), WorkCenterSchedule.created_at.asc())

    schedules = session.execute(query).scalars().all()
    wc_map = {wc.id: wc for wc in session.execute(select(WorkCenter).where(WorkCenter.tenant_id == actor["tenant_id"])).scalars().all()}
    run_map = {r.id: r for r in session.execute(select(ProductionRun).where(ProductionRun.tenant_id == actor["tenant_id"])).scalars().all()}

    # Calculate day-level load per work center to tag overload status
    daily_load_map: Dict[str, float] = {}
    for s in schedules:
        key = f"{s.work_center_id}_{s.schedule_date}"
        daily_load_map[key] = daily_load_map.get(key, 0.0) + float(s.required_hours)

    res = []
    for s in schedules:
        wc = wc_map.get(s.work_center_id)
        effective_daily_cap = float(wc.daily_capacity_hours * wc.efficiency_factor) if wc else 16.0
        day_total = daily_load_map.get(f"{s.work_center_id}_{s.schedule_date}", float(s.required_hours))
        is_day_overloaded = day_total > effective_daily_cap

        res.append({
            "id": str(s.id),
            "work_center_id": str(s.work_center_id),
            "work_center_code": wc.code if wc else "WC",
            "work_center_name": wc.name if wc else "Station",
            "department": wc.department if wc else "Manufacturing",
            "production_run_id": str(s.production_run_id) if s.production_run_id else None,
            "production_run_number": run_map[s.production_run_id].number if s.production_run_id in run_map else None,
            "task_name": s.task_name,
            "schedule_date": s.schedule_date.isoformat(),
            "shift": s.shift,
            "required_hours": float(s.required_hours),
            "status": "overloaded" if is_day_overloaded else s.status,
            "is_overloaded": is_day_overloaded,
            "daily_booked_hours": round(day_total, 1),
            "daily_capacity_hours": round(effective_daily_cap, 1),
            "notes": s.notes,
        })

    return {"schedules": res}


@router.post("/schedule")
def schedule_job(
    req: ScheduleJobRequest,
    actor: Annotated[Actor, Depends(require_any_permission("capacity_planning:write", "*"))],
):
    wc = session.get(WorkCenter, req.work_center_id)
    if not wc:
        raise not_found("Work center not found.")

    sched = WorkCenterSchedule(
        tenant_id=actor["tenant_id"],
        work_center_id=req.work_center_id,
        production_run_id=req.production_run_id,
        task_name=req.task_name,
        schedule_date=req.schedule_date,
        shift=req.shift,
        required_hours=Decimal(str(req.required_hours)),
        status="scheduled",
        notes=req.notes,
    )
    session.add(sched)
    session.commit()

    return {
        "id": str(sched.id),
        "task_name": sched.task_name,
        "schedule_date": sched.schedule_date.isoformat(),
        "work_center_code": wc.code,
        "message": f"Job scheduled on {wc.code} ({sched.required_hours}h on {sched.schedule_date}).",
    }


@router.post("/schedule/{schedule_id}/reassign")
def reassign_job(
    schedule_id: uuid.UUID,
    req: ReassignJobRequest,
    actor: Annotated[Actor, Depends(require_any_permission("capacity_planning:write", "*"))],
):
    sched = session.execute(
        select(WorkCenterSchedule).where(
            WorkCenterSchedule.tenant_id == actor["tenant_id"],
            WorkCenterSchedule.id == schedule_id
        )
    ).scalar_one_or_none()

    if not sched:
        raise not_found("Scheduled job record not found.")

    target_wc = session.get(WorkCenter, req.target_work_center_id)
    if not target_wc:
        raise not_found("Target alternate work center not found.")

    old_wc = session.get(WorkCenter, sched.work_center_id)
    sched.work_center_id = req.target_work_center_id
    if req.target_date:
        sched.schedule_date = req.target_date
    if req.target_shift:
        sched.shift = req.target_shift
    sched.status = "scheduled"

    session.commit()

    return {
        "id": str(sched.id),
        "new_work_center_code": target_wc.code,
        "message": f"Job reassigned from {old_wc.code if old_wc else 'Station'} to {target_wc.code} to eliminate bottleneck.",
    }


@router.get("/rccp-summary")
def get_rccp_summary(
    actor: Annotated[Actor, Depends(require_any_permission("capacity_planning:read", "*"))],
):
    """Rough-Cut Capacity Planning (RCCP) 4-week load vs capacity profile."""
    work_centers = session.execute(
        select(WorkCenter).where(WorkCenter.tenant_id == actor["tenant_id"], WorkCenter.status == "active")
    ).scalars().all()

    today = date.today()
    weeks = []
    for w in range(4):
        w_start = today + timedelta(days=w * 7)
        w_end = w_start + timedelta(days=6)
        weeks.append({"week_num": w + 1, "start": w_start, "end": w_end})

    from collections import defaultdict
    wc_ids = [wc.id for wc in work_centers]
    all_rccp_scheds = []
    if wc_ids and weeks:
        horizon_start = weeks[0]["start"]
        horizon_end = weeks[-1]["end"]
        all_rccp_scheds = session.execute(
            select(WorkCenterSchedule).where(
                WorkCenterSchedule.tenant_id == actor["tenant_id"],
                WorkCenterSchedule.work_center_id.in_(wc_ids),
                WorkCenterSchedule.schedule_date >= horizon_start,
                WorkCenterSchedule.schedule_date <= horizon_end,
            )
        ).scalars().all()
        
    scheds_by_wc = defaultdict(list)
    for s in all_rccp_scheds:
        scheds_by_wc[s.work_center_id].append(s)

    summary = []
    for wc in work_centers:
        weekly_cap = float(wc.daily_capacity_hours * 6) * float(wc.efficiency_factor)
        week_loads = []
        wc_scheds = scheds_by_wc.get(wc.id, [])

        for wk in weeks:
            scheds = [s for s in wc_scheds if wk["start"] <= s.schedule_date <= wk["end"]]
            load_hours = sum((float(s.required_hours) for s in scheds), 0.0)
            load_pct = round((load_hours / weekly_cap * 100.0) if weekly_cap > 0 else 0.0, 1)

            week_loads.append({
                "week_num": wk["week_num"],
                "start_date": wk["start"].isoformat(),
                "end_date": wk["end"].isoformat(),
                "capacity_hours": round(weekly_cap, 1),
                "load_hours": round(load_hours, 1),
                "load_percentage": load_pct,
                "is_overloaded": load_pct > 100.0,
            })

        summary.append({
            "work_center_id": str(wc.id),
            "code": wc.code,
            "name": wc.name,
            "department": wc.department,
            "weekly_capacity_hours": round(weekly_cap, 1),
            "weeks": week_loads,
        })

    return {"rccp_matrix": summary}
