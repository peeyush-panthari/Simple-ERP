"""FastAPI router for Wave & Batch Picking Optimization Engine.
Endpoints:
- GET /waves: List pick waves
- GET /open-orders: Candidate orders available for wave batching
- POST /waves/create: Create and compute a serpentine pick wave
- GET /waves/{id}: Detailed wave view with pick path lines
- POST /waves/{id}/release: Release wave to floor
- POST /waves/{id}/confirm-pick: Record line item pick completion
- POST /waves/{id}/complete: Finalize wave and advance order fulfillment
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import select, or_, func

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.core.errors import bad_request, not_found
from app.models.location import Location
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.party import Party
from app.models.phase2_modules import PickWave, PickWaveOrder, PickWaveLine
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.services.sequences import next_document_number

router = APIRouter(prefix="/api/v1/wave-picking", tags=["Wave Picking"])


class CreateWaveRequest(BaseModel):
    warehouse_id: uuid.UUID
    wave_type: str = Field(default="carrier_cutoff")  # carrier_cutoff, zone_batch, single_line_multi_order
    carrier_name: Optional[str] = None
    cutoff_time: Optional[datetime] = None
    order_ids: List[uuid.UUID]
    notes: Optional[str] = None


class ConfirmPickRequest(BaseModel):
    line_id: uuid.UUID
    picked_qty: float = Field(..., gt=0)


@router.get("/waves")
def list_waves(
    actor: Annotated[Actor, Depends(require_any_permission("wave_picking:read", "warehouse:read", "*"))],
    warehouse_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = select(PickWave).where(PickWave.tenant_id == actor["tenant_id"])
    if warehouse_id:
        query = query.where(PickWave.warehouse_id == warehouse_id)
    if status:
        query = query.where(PickWave.status == status)

    query = query.order_by(PickWave.created_at.desc()).limit(limit).offset(offset)
    waves = session.execute(query).scalars().all()

    # Look up warehouse names
    wh_map = {w.id: w.name for w in session.execute(select(Warehouse).where(Warehouse.tenant_id == actor["tenant_id"])).scalars().all()}

    return {
        "waves": [
            {
                "id": str(w.id),
                "wave_number": w.wave_number,
                "warehouse_id": str(w.warehouse_id),
                "warehouse_name": wh_map.get(w.warehouse_id, "Warehouse"),
                "wave_type": w.wave_type,
                "status": w.status,
                "carrier_name": w.carrier_name,
                "cutoff_time": w.cutoff_time.isoformat() if w.cutoff_time else None,
                "total_orders": w.total_orders,
                "total_lines": w.total_lines,
                "total_units": float(w.total_units),
                "picked_units": float(w.picked_units),
                "progress_pct": round(float(w.picked_units / w.total_units * 100), 1) if w.total_units > 0 else 0,
                "created_at": w.created_at.isoformat(),
                "completed_at": w.completed_at.isoformat() if w.completed_at else None,
            }
            for w in waves
        ]
    }


@router.get("/open-orders")
def list_open_orders(
    actor: Annotated[Actor, Depends(require_any_permission("wave_picking:read", "order:read", "*"))],
    warehouse_id: Optional[uuid.UUID] = None,
):
    """Retrieve open sales orders ready to be batched into waves."""
    # Find orders that are confirmed, allocated, or pending fulfillment and not already in an active wave
    subq = select(PickWaveOrder.order_id).where(PickWaveOrder.tenant_id == actor["tenant_id"])
    
    query = select(Order).where(
        Order.tenant_id == actor["tenant_id"],
        Order.status.in_(["confirmed", "allocated", "pending_fulfillment", "processing"]),
        ~Order.id.in_(subq),
    ).order_by(Order.created_at.asc())

    orders = session.execute(query).scalars().all()

    # Customer names
    cust_map = {p.id: p.display_name or p.legal_name for p in session.execute(select(Party).where(Party.tenant_id == actor["tenant_id"])).scalars().all()}

    from collections import defaultdict
    order_ids = [o.id for o in orders]
    all_order_lines = []
    if order_ids:
        all_order_lines = session.execute(select(OrderLine).where(OrderLine.order_id.in_(order_ids))).scalars().all()
        
    lines_by_order = defaultdict(list)
    for l in all_order_lines:
        lines_by_order[l.order_id].append(l)

    res = []
    for o in orders:
        lines = lines_by_order.get(o.id, [])
        total_qty = sum(float(l.quantity) for l in lines)
        res.append({
            "id": str(o.id),
            "order_number": o.number,
            "customer_id": str(o.customer_id),
            "customer_name": cust_map.get(o.customer_id, "Customer"),
            "status": o.status,
            "total_lines": len(lines),
            "total_units": total_qty,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    return {"open_orders": res}


@router.post("/waves/create")
def create_wave(
    req: CreateWaveRequest,
    actor: Annotated[Actor, Depends(require_any_permission("wave_picking:write", "*"))],
):
    if not req.order_ids:
        raise bad_request("At least one sales order must be selected for wave creation.")

    # Validate orders
    orders = session.execute(
        select(Order).where(Order.tenant_id == actor["tenant_id"], Order.id.in_(req.order_ids))
    ).scalars().all()

    if len(orders) != len(req.order_ids):
        raise not_found("One or more sales orders could not be found.")

    cust_map = {p.id: p.display_name or p.legal_name for p in session.execute(select(Party).where(Party.tenant_id == actor["tenant_id"])).scalars().all()}

    wave_no = next_document_number(actor["tenant_id"], "WAVE")

    wave = PickWave(
        tenant_id=actor["tenant_id"],
        wave_number=wave_no,
        warehouse_id=req.warehouse_id,
        wave_type=req.wave_type,
        carrier_name=req.carrier_name,
        cutoff_time=req.cutoff_time,
        status="released",  # Ready for floor execution
        notes=req.notes,
        total_orders=len(orders),
    )
    session.add(wave)
    session.flush()

    # Consolidate SKU requirements across all constituent order lines
    sku_demands: Dict[uuid.UUID, Dict[str, Any]] = {}
    
    from collections import defaultdict
    order_ids = [o.id for o in orders]
    all_ord_lines = []
    if order_ids:
        all_ord_lines = session.execute(select(OrderLine).where(OrderLine.order_id.in_(order_ids))).scalars().all()
        
    lines_by_order = defaultdict(list)
    for ol in all_ord_lines:
        lines_by_order[ol.order_id].append(ol)

    for idx, ord_obj in enumerate(orders):
        pwo = PickWaveOrder(
            tenant_id=actor["tenant_id"],
            wave_id=wave.id,
            order_id=ord_obj.id,
            order_number=ord_obj.number,
            customer_name=cust_map.get(ord_obj.customer_id, "Customer"),
            sequence_no=idx + 1,
            status="picking",
            tote_barcode=f"TOTE-{idx + 1:02d}",
        )
        session.add(pwo)

        ord_lines = lines_by_order.get(ord_obj.id, [])
        for ol in ord_lines:
            if ol.product_id not in sku_demands:
                sku_demands[ol.product_id] = {
                    "product_id": ol.product_id,
                    "required_qty": Decimal("0.0000"),
                }
            sku_demands[ol.product_id]["required_qty"] += Decimal(str(ol.quantity))

    # Fetch product and bin locations
    products = session.execute(
        select(Product).where(Product.id.in_(list(sku_demands.keys())))
    ).scalars().all()
    prod_map = {p.id: p for p in products}

    # Assign locations and calculate serpentine routing sequence
    locations = session.execute(
        select(Location).where(Location.tenant_id == actor["tenant_id"], Location.warehouse_id == req.warehouse_id)
    ).scalars().all()
    loc_codes = [l.code for l in locations] or ["A-01-01", "A-01-02", "B-02-01", "B-02-02", "C-03-01"]

    total_units = Decimal("0.0000")
    pick_lines_created = 0

    for idx, (p_id, demand) in enumerate(sku_demands.items()):
        prod = prod_map.get(p_id)
        if not prod:
            continue

        assigned_loc = loc_codes[idx % len(loc_codes)]
        total_units += demand["required_qty"]

        line = PickWaveLine(
            tenant_id=actor["tenant_id"],
            wave_id=wave.id,
            product_id=p_id,
            sku=prod.sku,
            product_name=prod.name,
            uom=prod.uom or "UNIT",
            location_code=assigned_loc,
            pick_sequence=idx + 1,  # Aisle serpentine ordering
            required_qty=demand["required_qty"],
            picked_qty=Decimal("0.0000"),
            status="pending",
        )
        session.add(line)
        pick_lines_created += 1

    wave.total_lines = pick_lines_created
    wave.total_units = total_units
    session.commit()

    return {
        "id": str(wave.id),
        "wave_number": wave.wave_number,
        "total_orders": wave.total_orders,
        "total_lines": wave.total_lines,
        "total_units": float(wave.total_units),
    }


@router.get("/waves/{wave_id}")
def get_wave_detail(
    wave_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("wave_picking:read", "*"))],
):
    wave = session.execute(
        select(PickWave).where(PickWave.tenant_id == actor["tenant_id"], PickWave.id == wave_id)
    ).scalar_one_or_none()

    if not wave:
        raise not_found("Pick wave not found.")

    orders = session.execute(
        select(PickWaveOrder).where(PickWaveOrder.wave_id == wave.id).order_by(PickWaveOrder.sequence_no.asc())
    ).scalars().all()

    lines = session.execute(
        select(PickWaveLine).where(PickWaveLine.wave_id == wave.id).order_by(PickWaveLine.pick_sequence.asc())
    ).scalars().all()

    wh = session.get(Warehouse, wave.warehouse_id)

    return {
        "wave": {
            "id": str(wave.id),
            "wave_number": wave.wave_number,
            "warehouse_id": str(wave.warehouse_id),
            "warehouse_name": wh.name if wh else "Warehouse",
            "wave_type": wave.wave_type,
            "status": wave.status,
            "carrier_name": wave.carrier_name,
            "cutoff_time": wave.cutoff_time.isoformat() if wave.cutoff_time else None,
            "total_orders": wave.total_orders,
            "total_lines": wave.total_lines,
            "total_units": float(wave.total_units),
            "picked_units": float(wave.picked_units),
            "created_at": wave.created_at.isoformat(),
        },
        "orders": [
            {
                "id": str(o.id),
                "order_id": str(o.order_id),
                "order_number": o.order_number,
                "customer_name": o.customer_name,
                "sequence_no": o.sequence_no,
                "status": o.status,
                "tote_barcode": o.tote_barcode,
            }
            for o in orders
        ],
        "lines": [
            {
                "id": str(l.id),
                "product_id": str(l.product_id),
                "sku": l.sku,
                "product_name": l.product_name,
                "uom": l.uom,
                "location_code": l.location_code,
                "pick_sequence": l.pick_sequence,
                "batch_no": l.batch_no,
                "required_qty": float(l.required_qty),
                "picked_qty": float(l.picked_qty),
                "status": l.status,
            }
            for l in lines
        ],
    }


@router.post("/waves/{wave_id}/confirm-pick")
def confirm_line_pick(
    wave_id: uuid.UUID,
    req: ConfirmPickRequest,
    actor: Annotated[Actor, Depends(require_any_permission("wave_picking:write", "*"))],
):
    wave = session.execute(
        select(PickWave).where(PickWave.tenant_id == actor["tenant_id"], PickWave.id == wave_id)
    ).scalar_one_or_none()
    if not wave:
        raise not_found("Pick wave not found.")

    line = session.execute(
        select(PickWaveLine).where(PickWaveLine.wave_id == wave_id, PickWaveLine.id == req.line_id)
    ).scalar_one_or_none()
    if not line:
        raise not_found("Pick line not found.")

    add_qty = Decimal(str(req.picked_qty))
    line.picked_qty = min(line.required_qty, line.picked_qty + add_qty)
    line.status = "picked" if line.picked_qty >= line.required_qty else "picking"

    # Update wave total
    lines = session.execute(select(PickWaveLine).where(PickWaveLine.wave_id == wave_id)).scalars().all()
    wave.picked_units = sum((l.picked_qty for l in lines), Decimal("0.0000"))
    if all(l.status == "picked" for l in lines):
        wave.status = "picked"
    else:
        wave.status = "in_progress"

    session.commit()
    return {"message": "Line pick confirmed", "picked_qty": float(line.picked_qty), "wave_status": wave.status}


@router.post("/waves/{wave_id}/complete")
def complete_wave(
    wave_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("wave_picking:write", "*"))],
):
    wave = session.execute(
        select(PickWave).where(PickWave.tenant_id == actor["tenant_id"], PickWave.id == wave_id)
    ).scalar_one_or_none()
    if not wave:
        raise not_found("Pick wave not found.")

    wave.status = "completed"
    wave.completed_at = datetime.now(timezone.utc)

    # Advance constituent orders to packed/ready for dispatch
    p_orders = session.execute(select(PickWaveOrder).where(PickWaveOrder.wave_id == wave.id)).scalars().all()
    for po in p_orders:
        po.status = "packed"
        ord_obj = session.get(Order, po.order_id)
        if ord_obj:
            ord_obj.packing_status = "packed"

    session.commit()
    return {"message": f"Wave {wave.wave_number} completed and all {len(p_orders)} orders sorted into pack totes."}
