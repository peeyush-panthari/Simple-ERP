"""FastAPI router for Perpetual Cycle Counting & Inventory Audits.
Endpoints:
- GET /sessions: List audit sessions with variance totals
- POST /generate: Generate a new cycle count session (ABC-based or full)
- GET /sessions/{id}: Count sheet details with line items
- POST /sessions/{id}/record-count: Submit physical counts
- POST /sessions/{id}/recount-request: Flag item for recount
- POST /sessions/{id}/approve-adjust: Supervisor signs off and posts adjustments
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import select, func

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.core.errors import bad_request, not_found
from app.models.inventory_item import InventoryItem
from app.models.location import Location
from app.models.phase1_modules import CycleCountLine, CycleCountSession
from app.models.product import Product
from app.models.stock_balance import StockBalance
from app.models.stock_ledger import StockLedger
from app.models.warehouse import Warehouse
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1/cycle-counts", tags=["Cycle Counting"])


class GenerateSessionRequest(BaseModel):
    warehouse_id: uuid.UUID
    counting_type: str = Field(default="abc_scheduled")  # abc_scheduled, annual_full, spot_audit
    target_abc_class: Optional[str] = "A"  # 'A', 'B', 'C', 'ALL'
    blind_count: bool = True
    scheduled_date: Optional[date] = None
    notes: Optional[str] = None


class RecordCountItem(BaseModel):
    line_id: uuid.UUID
    counted_qty: float = Field(..., ge=0)
    notes: Optional[str] = None


class RecordCountRequest(BaseModel):
    counts: List[RecordCountItem]


class RecountRequest(BaseModel):
    line_ids: List[uuid.UUID]
    reason: Optional[str] = None


class ApproveAdjustRequest(BaseModel):
    supervisor_notes: Optional[str] = None


@router.get("/sessions")
def list_cycle_count_sessions(
    actor: Annotated[Actor, Depends(require_any_permission("cycle_count:read", "inventory:read", "*"))],
    warehouse_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = (
        select(CycleCountSession, Warehouse)
        .join(Warehouse, Warehouse.id == CycleCountSession.warehouse_id)
        .where(CycleCountSession.tenant_id == actor["tenant_id"])
    )
    if warehouse_id:
        query = query.where(CycleCountSession.warehouse_id == warehouse_id)
    if status:
        query = query.where(CycleCountSession.status == status)

    rows = list(session.execute(query.order_by(CycleCountSession.created_at.desc()).limit(limit).offset(offset)).all())
    return {
        "sessions": [
            {
                "id": str(s.id),
                "session_number": s.session_number,
                "warehouse_id": str(s.warehouse_id),
                "warehouse_name": w.name,
                "warehouse_code": w.code,
                "counting_type": s.counting_type,
                "target_abc_class": s.target_abc_class,
                "status": s.status,
                "blind_count": s.blind_count,
                "scheduled_date": s.scheduled_date.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "total_items_count": s.total_items_count,
                "discrepancy_items_count": s.discrepancy_items_count,
                "net_variance_value": float(s.net_variance_value),
                "notes": s.notes,
                "created_at": s.created_at.isoformat(),
            }
            for s, w in rows
        ]
    }


@router.post("/generate")
def generate_cycle_count_session(
    req: GenerateSessionRequest,
    actor: Annotated[Actor, Depends(require_any_permission("cycle_count:write", "inventory:write", "*"))],
):
    wh = session.get(Warehouse, req.warehouse_id)
    if not wh or wh.tenant_id != actor["tenant_id"]:
        raise not_found("Warehouse not found")

    session_no = next_document_number(actor["tenant_id"], "CC")

    # Find candidate locations and items
    loc_query = select(Location).where(
        Location.tenant_id == actor["tenant_id"],
        Location.warehouse_id == req.warehouse_id,
        Location.status == "active",
    )
    if req.target_abc_class and req.target_abc_class != "ALL":
        loc_query = loc_query.where(Location.velocity_class == req.target_abc_class)
    target_locations = list(session.execute(loc_query).scalars().all())
    target_loc_ids = [l.id for l in target_locations]

    # Query active inventory items in these locations (or whole warehouse)
    item_query = select(InventoryItem, Product).join(Product, Product.id == InventoryItem.product_id).where(
        InventoryItem.tenant_id == actor["tenant_id"],
        InventoryItem.warehouse_id == req.warehouse_id,
        InventoryItem.status == "accepted",
    )
    if target_loc_ids:
        item_query = item_query.where(InventoryItem.location_id.in_(target_loc_ids))

    candidate_items = list(session.execute(item_query.limit(200)).all())

    # If no piece inventory items found, seed from stock balances
    if not candidate_items:
        balance_query = (
            select(StockBalance, Product)
            .join(Product, Product.id == StockBalance.product_id)
            .where(
                StockBalance.tenant_id == actor["tenant_id"],
                StockBalance.warehouse_id == req.warehouse_id,
                StockBalance.quantity > 0,
            )
            .limit(100)
        )
        balances = list(session.execute(balance_query).all())

    cc_session = CycleCountSession(
        tenant_id=actor["tenant_id"],
        session_number=session_no,
        warehouse_id=req.warehouse_id,
        counting_type=req.counting_type,
        target_abc_class=req.target_abc_class,
        status="in_progress",
        blind_count=req.blind_count,
        scheduled_date=req.scheduled_date or date.today(),
        audited_by_user_id=actor["user_id"],
        notes=req.notes or f"ABC Scheduled Cycle Count for Class {req.target_abc_class}",
    )
    session.add(cc_session)
    session.flush()

    total_lines = 0
    if candidate_items:
        for itm, prod in candidate_items:
            unit_cost = Decimal("100.00")
            line = CycleCountLine(
                tenant_id=actor["tenant_id"],
                session_id=cc_session.id,
                product_id=prod.id,
                location_id=getattr(itm, "location_id", None),
                batch_no=itm.batch_no,
                system_qty=Decimal(str(itm.accepted_qty if itm.status == "accepted" else itm.quantity)),
                unit_cost=unit_cost,
                status="pending",
            )
            session.add(line)
            total_lines += 1
    elif 'balances' in locals() and balances:
        for bal, prod in balances:
            unit_cost = Decimal("100.00")
            line = CycleCountLine(
                tenant_id=actor["tenant_id"],
                session_id=cc_session.id,
                product_id=prod.id,
                location_id=bal.location_id,
                batch_no=bal.batch_no,
                system_qty=Decimal(str(bal.quantity)),
                unit_cost=unit_cost,
                status="pending",
            )
            session.add(line)
            total_lines += 1
    else:
        # Create at least 1 mock line for sample testing if empty
        prods = list(session.execute(select(Product).where(Product.tenant_id == actor["tenant_id"]).limit(3)).scalars().all())
        for p in prods:
            line = CycleCountLine(
                tenant_id=actor["tenant_id"],
                session_id=cc_session.id,
                product_id=p.id,
                batch_no="B-TEST-01",
                system_qty=Decimal("25.00"),
                unit_cost=Decimal("150.00"),
                status="pending",
            )
            session.add(line)
            total_lines += 1

    cc_session.total_items_count = total_lines
    session.commit()

    return {
        "id": str(cc_session.id),
        "session_number": cc_session.session_number,
        "total_items_count": total_lines,
        "status": cc_session.status,
    }


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("cycle_count:read", "inventory:read", "*"))],
):
    cc_session = session.execute(
        select(CycleCountSession).where(
            CycleCountSession.tenant_id == actor["tenant_id"],
            CycleCountSession.id == session_id,
        )
    ).scalar_one_or_none()
    if not cc_session:
        raise not_found("Cycle count session not found")

    wh = session.get(Warehouse, cc_session.warehouse_id)

    lines_query = (
        select(CycleCountLine, Product, Location)
        .join(Product, Product.id == CycleCountLine.product_id)
        .outerjoin(Location, Location.id == CycleCountLine.location_id)
        .where(CycleCountLine.session_id == session_id)
        .order_by(CycleCountLine.created_at)
    )
    lines_data = list(session.execute(lines_query).all())

    # Blind mode masking rule: hide system_qty if blind_count is on and status is in_progress
    hide_system = cc_session.blind_count and cc_session.status == "in_progress"

    items = []
    for l, prod, loc in lines_data:
        items.append({
            "id": str(l.id),
            "product_id": str(prod.id),
            "sku": prod.sku,
            "product_name": prod.name,
            "location_code": loc.code if loc else "RACK-01",
            "batch_no": l.batch_no or "N/A",
            "system_qty": None if hide_system else float(l.system_qty),
            "counted_qty": float(l.counted_qty) if l.counted_qty is not None else None,
            "variance_qty": float(l.variance_qty) if l.variance_qty is not None and not hide_system else None,
            "unit_cost": float(l.unit_cost),
            "variance_value": float(l.variance_value) if l.variance_value is not None and not hide_system else None,
            "status": l.status,
            "recount_count": l.recount_count,
            "notes": l.notes,
        })

    return {
        "session": {
            "id": str(cc_session.id),
            "session_number": cc_session.session_number,
            "warehouse_name": wh.name if wh else "Central Warehouse",
            "warehouse_code": wh.code if wh else "WH-MAIN",
            "counting_type": cc_session.counting_type,
            "target_abc_class": cc_session.target_abc_class,
            "status": cc_session.status,
            "blind_count": cc_session.blind_count,
            "scheduled_date": cc_session.scheduled_date.isoformat(),
            "completed_at": cc_session.completed_at.isoformat() if cc_session.completed_at else None,
            "total_items_count": cc_session.total_items_count,
            "discrepancy_items_count": cc_session.discrepancy_items_count,
            "net_variance_value": float(cc_session.net_variance_value),
            "notes": cc_session.notes,
        },
        "lines": items,
    }


@router.post("/sessions/{session_id}/record-count")
def record_counts(
    session_id: uuid.UUID,
    req: RecordCountRequest,
    actor: Annotated[Actor, Depends(require_any_permission("cycle_count:write", "inventory:write", "*"))],
):
    cc_session = session.execute(
        select(CycleCountSession).where(
            CycleCountSession.tenant_id == actor["tenant_id"],
            CycleCountSession.id == session_id,
        )
    ).scalar_one_or_none()
    if not cc_session:
        raise not_found("Session not found")

    discrepancy_count = 0
    net_variance_val = Decimal("0.00")

    line_ids = [item.line_id for item in req.counts]
    lines_db = []
    if line_ids:
        lines_db = session.execute(
            select(CycleCountLine).where(
                CycleCountLine.tenant_id == actor["tenant_id"],
                CycleCountLine.id.in_(line_ids),
                CycleCountLine.session_id == session_id
            )
        ).scalars().all()
    lines_map = {l.id: l for l in lines_db}

    for item in req.counts:
        line = lines_map.get(item.line_id)
        if not line:
            continue
        line.counted_qty = Decimal(str(item.counted_qty))
        line.variance_qty = line.counted_qty - line.system_qty
        line.variance_value = line.variance_qty * line.unit_cost
        line.status = "counted" if line.variance_qty == 0 else "pending_review"
        line.counter_user_id = actor["user_id"]
        if item.notes:
            line.notes = item.notes

        if line.variance_qty != 0:
            discrepancy_count += 1
            net_variance_val += line.variance_value

    cc_session.discrepancy_items_count = discrepancy_count
    cc_session.net_variance_value = net_variance_val
    cc_session.status = "pending_review"
    session.commit()

    return {
        "message": f"Recorded physical counts for {len(req.counts)} lines",
        "discrepancy_items_count": discrepancy_count,
        "net_variance_value": float(net_variance_val),
    }


@router.post("/sessions/{session_id}/recount-request")
def request_recount(
    session_id: uuid.UUID,
    req: RecountRequest,
    actor: Annotated[Actor, Depends(require_any_permission("cycle_count:write", "inventory:write", "*"))],
):
    if req.line_ids:
        lines = session.execute(
            select(CycleCountLine).where(
                CycleCountLine.tenant_id == actor["tenant_id"],
                CycleCountLine.id.in_(req.line_ids),
                CycleCountLine.session_id == session_id
            )
        ).scalars().all()
        for line in lines:
            line.status = "recount_requested"
            line.recount_count += 1
            if req.reason:
                line.notes = f"Recount Reason: {req.reason}"
    session.commit()
    return {"message": f"Recount requested for {len(req.line_ids)} line items"}


@router.post("/sessions/{session_id}/approve-adjust")
def approve_and_adjust_variances(
    session_id: uuid.UUID,
    req: ApproveAdjustRequest,
    actor: Annotated[Actor, Depends(require_any_permission("cycle_count:write", "inventory:write", "*"))],
):
    cc_session = session.execute(
        select(CycleCountSession).where(
            CycleCountSession.tenant_id == actor["tenant_id"],
            CycleCountSession.id == session_id,
        )
    ).scalar_one_or_none()
    if not cc_session:
        raise not_found("Session not found")

    lines = list(session.execute(select(CycleCountLine).where(CycleCountLine.session_id == session_id)).scalars().all())

    adjusted_count = 0
    
    prod_ids = [l.product_id for l in lines if l.variance_qty and l.variance_qty != 0]
    prod_map = {}
    bal_map = {}
    
    if prod_ids:
        prods = session.execute(
            select(Product).where(Product.tenant_id == actor["tenant_id"], Product.id.in_(prod_ids))
        ).scalars().all()
        prod_map = {p.id: p for p in prods}
        
        bals = session.execute(
            select(StockBalance).where(
                StockBalance.tenant_id == actor["tenant_id"],
                StockBalance.warehouse_id == cc_session.warehouse_id,
                StockBalance.product_id.in_(prod_ids)
            )
        ).scalars().all()
        bal_map = {b.product_id: b for b in bals}

    for l in lines:
        if l.variance_qty and l.variance_qty != 0:
            prod = prod_map.get(l.product_id)
            ledger_entry = StockLedger(
                tenant_id=actor["tenant_id"],
                product_id=l.product_id,
                sku=prod.sku if prod else "SKU",
                uom=prod.uom if prod else "UNIT",
                warehouse_id=cc_session.warehouse_id,
                movement_type="adjustment",
                bucket="available",
                quantity=l.variance_qty,
                reference_type="cycle_count",
                reference_id=str(cc_session.session_number),
                reason=f"Approved cycle count variance adjustment: {l.variance_qty:+f}",
            )
            session.add(ledger_entry)

            # Update InventoryItem / StockBalance
            bal = bal_map.get(l.product_id)
            if bal and l.counted_qty is not None:
                bal.quantity = l.counted_qty

            l.status = "adjusted"
            adjusted_count += 1
        else:
            l.status = "approved"

    cc_session.status = "completed"
    cc_session.completed_at = datetime.utcnow()
    cc_session.approved_by_user_id = actor["user_id"]
    if req.supervisor_notes:
        cc_session.notes = f"Supervisor Approval: {req.supervisor_notes}\n" + (cc_session.notes or "")

    session.commit()
    return {
        "message": f"Cycle count session {cc_session.session_number} approved and finalized",
        "adjusted_lines_count": adjusted_count,
        "status": cc_session.status,
    }
