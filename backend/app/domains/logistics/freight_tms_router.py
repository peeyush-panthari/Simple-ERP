"""FastAPI router for Container & Freight Consolidation TMS.
Endpoints:
- GET /containers: List containers with volumetric fill & demurrage risks
- POST /containers: Create container consolidation plan
- POST /containers/{id}/pack-item: Add cargo lines & recompute 3D utilization
- POST /containers/{id}/milestone: Record milestone log
- POST /containers/{id}/audit-rate: Run carrier 3-way freight rate audit
"""
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import select, func

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.core.errors import bad_request, not_found
from app.models.long_term_modules import ContainerItem, ContainerShipment, FreightMilestone
from app.models.party import Party
from app.models.product import Product

router = APIRouter(prefix="/api/v1/freight-tms", tags=["Freight TMS"])

CONTAINER_SPECS = {
    "20GP": {"max_cbm": 33.2, "max_kg": 28000.0},
    "40GP": {"max_cbm": 67.7, "max_kg": 28600.0},
    "40HC": {"max_cbm": 76.3, "max_kg": 28500.0},
    "45HC": {"max_cbm": 86.0, "max_kg": 27800.0},
}


class CreateContainerRequest(BaseModel):
    container_number: str = Field(..., min_length=4, max_length=32)
    booking_reference: str = Field(..., min_length=2, max_length=64)
    container_type: str = Field(default="40HC")
    carrier_party_id: Optional[uuid.UUID] = None
    origin_port: str
    destination_port: str
    vessel_name: Optional[str] = None
    voyage_number: Optional[str] = None
    etd: Optional[date] = None
    eta: Optional[date] = None
    port_free_days: int = 5
    detention_free_days: int = 14
    contracted_freight_cost: float = 0.0


class PackItemRequest(BaseModel):
    product_id: uuid.UUID
    quantity: float = Field(..., gt=0)
    unit_cbm: float = Field(default=0.02, gt=0)
    unit_weight_kg: float = Field(default=2.5, gt=0)
    package_type: str = "Carton"
    hsn_code: Optional[str] = None


class AddMilestoneRequest(BaseModel):
    milestone_name: str
    location: str
    notes: Optional[str] = None


@router.get("/containers")
def list_containers(
    actor: Annotated[Actor, Depends(require_any_permission("freight:read", "logistics:read"))],
    status: Optional[str] = None,
):
    query = (
        select(ContainerShipment, Party)
        .outerjoin(Party, Party.id == ContainerShipment.carrier_party_id)
        .where(ContainerShipment.tenant_id == actor["tenant_id"])
    )
    if status:
        query = query.where(ContainerShipment.status == status)

    containers = list(session.execute(query.order_by(ContainerShipment.created_at.desc())).all())
    today = date.today()

    results = []
    for c, carrier in containers:
        demurrage_days_left = None
        demurrage_risk = "safe"
        if c.discharge_date:
            days_since_discharge = (today - c.discharge_date).days
            demurrage_days_left = c.port_free_days - days_since_discharge
            if demurrage_days_left <= 0:
                demurrage_risk = "penalty_incurred"
            elif demurrage_days_left <= 2:
                demurrage_risk = "high_risk"
            else:
                demurrage_risk = "safe"

        results.append({
            "id": str(c.id),
            "container_number": c.container_number,
            "booking_reference": c.booking_reference,
            "container_type": c.container_type,
            "carrier_name": (carrier.display_name or carrier.legal_name) if carrier else "N/A",
            "origin_port": c.origin_port,
            "destination_port": c.destination_port,
            "vessel_name": c.vessel_name,
            "voyage_number": c.voyage_number,
            "etd": c.etd.isoformat() if c.etd else None,
            "eta": c.eta.isoformat() if c.eta else None,
            "discharge_date": c.discharge_date.isoformat() if c.discharge_date else None,
            "status": c.status,
            "total_volume_cbm": float(c.total_volume_cbm),
            "total_weight_kg": float(c.total_weight_kg),
            "volume_utilization_pct": float(c.volume_utilization_pct),
            "weight_utilization_pct": float(c.weight_utilization_pct),
            "demurrage_days_left": demurrage_days_left,
            "demurrage_risk": demurrage_risk,
            "contracted_freight_cost": float(c.contracted_freight_cost),
            "audited_freight_cost": float(c.audited_freight_cost),
            "items_count": len(c.items),
        })

    return {"containers": results}


@router.post("/containers")
def create_container(
    req: CreateContainerRequest,
    actor: Annotated[Actor, Depends(require_any_permission("freight:write", "logistics:write"))],
):
    container = ContainerShipment(
        tenant_id=actor["tenant_id"],
        container_number=req.container_number.strip().upper(),
        booking_reference=req.booking_reference,
        container_type=req.container_type,
        carrier_party_id=req.carrier_party_id,
        origin_port=req.origin_port,
        destination_port=req.destination_port,
        vessel_name=req.vessel_name,
        voyage_number=req.voyage_number,
        etd=req.etd,
        eta=req.eta,
        port_free_days=req.port_free_days,
        detention_free_days=req.detention_free_days,
        contracted_freight_cost=req.contracted_freight_cost,
        status="stuffing",
    )
    session.add(container)
    session.commit()
    return {"id": str(container.id), "container_number": container.container_number}


@router.post("/containers/{container_id}/pack-item")
def pack_item(
    container_id: uuid.UUID,
    req: PackItemRequest,
    actor: Annotated[Actor, Depends(require_any_permission("freight:write", "logistics:write"))],
):
    container = session.execute(
        select(ContainerShipment).where(
            ContainerShipment.tenant_id == actor["tenant_id"],
            ContainerShipment.id == container_id,
        )
    ).scalar_one_or_none()
    if not container:
        raise not_found("Container not found")

    item = ContainerItem(
        tenant_id=actor["tenant_id"],
        container_id=container.id,
        product_id=req.product_id,
        quantity=req.quantity,
        unit_cbm=req.unit_cbm,
        unit_weight_kg=req.unit_weight_kg,
        package_type=req.package_type,
        hsn_code=req.hsn_code,
    )
    session.add(item)
    session.flush()

    all_items = list(
        session.execute(
            select(ContainerItem).where(ContainerItem.container_id == container.id)
        ).scalars().all()
    )
    total_cbm = sum(float(i.quantity) * float(i.unit_cbm) for i in all_items)
    total_kg = sum(float(i.quantity) * float(i.unit_weight_kg) for i in all_items)

    specs = CONTAINER_SPECS.get(container.container_type, CONTAINER_SPECS["40HC"])
    cbm_pct = min(100.0, round((total_cbm / specs["max_cbm"]) * 100, 2))
    kg_pct = min(100.0, round((total_kg / specs["max_kg"]) * 100, 2))

    container.total_volume_cbm = round(total_cbm, 3)
    container.total_weight_kg = round(total_kg, 2)
    container.volume_utilization_pct = cbm_pct
    container.weight_utilization_pct = kg_pct

    session.commit()
    return {
        "message": "Cargo packed into container",
        "total_volume_cbm": float(container.total_volume_cbm),
        "total_weight_kg": float(container.total_weight_kg),
        "volume_utilization_pct": float(container.volume_utilization_pct),
        "weight_utilization_pct": float(container.weight_utilization_pct),
    }


@router.post("/containers/{container_id}/milestone")
def add_milestone(
    container_id: uuid.UUID,
    req: AddMilestoneRequest,
    actor: Annotated[Actor, Depends(require_any_permission("freight:write", "logistics:write"))],
):
    container = session.execute(
        select(ContainerShipment).where(
            ContainerShipment.tenant_id == actor["tenant_id"],
            ContainerShipment.id == container_id,
        )
    ).scalar_one_or_none()
    if not container:
        raise not_found("Container not found")

    m = FreightMilestone(
        tenant_id=actor["tenant_id"],
        container_id=container.id,
        milestone_name=req.milestone_name,
        milestone_time=datetime.utcnow(),
        location=req.location,
        notes=req.notes,
    )
    session.add(m)
    session.commit()
    return {"message": "Milestone logged"}


@router.post("/containers/{container_id}/audit-rate")
def audit_rate(
    container_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("freight:write", "logistics:write"))],
    billed_cost: float = Query(..., gt=0),
):
    container = session.execute(
        select(ContainerShipment).where(
            ContainerShipment.tenant_id == actor["tenant_id"],
            ContainerShipment.id == container_id,
        )
    ).scalar_one_or_none()
    if not container:
        raise not_found("Container not found")

    container.audited_freight_cost = billed_cost
    variance = billed_cost - float(container.contracted_freight_cost)
    session.commit()

    return {
        "contracted_freight_cost": float(container.contracted_freight_cost),
        "billed_freight_cost": billed_cost,
        "variance_amount": round(variance, 2),
        "audit_verdict": "Rate Matched" if abs(variance) < 1.0 else ("Surcharge Overcharge" if variance > 0 else "Discount Applied"),
    }
