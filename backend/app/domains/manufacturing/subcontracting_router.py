from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.models.business_entity import BusinessEntity
from app.models.party import Party
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.services.subcontracting import SubcontractingService

router = APIRouter(prefix="/api/v1/subcontracting", tags=["subcontracting"])


class SubcontractOrderCreateSchema(BaseModel):
    vendor_party_id: str
    fg_product_id: str
    source_warehouse_id: str
    target_qty: float
    service_rate: float
    business_entity_id: str | None = None
    bom_version_id: str | None = None
    service_sac_code: str = "9988"
    expected_delivery_date: str | None = None
    notes: str | None = None
    lines: list[dict[str, Any]] | None = None


class SubcontractChallanCreateSchema(BaseModel):
    items: list[dict[str, Any]]
    place_of_supply: str | None = None
    transport_mode: str = "Road"
    vehicle_no: str | None = None
    transporter_name: str | None = None
    eway_bill_no: str | None = None
    nature_of_processing: str = "Precision machining, coating & assembly"
    notes: str | None = None


class SubcontractReceiptCreateSchema(BaseModel):
    received_qty: float
    accepted_qty: float | None = None
    consumed_raw_material_qty: float | None = None
    actual_scrap_qty: float = 0.0
    allowed_scrap_pct: float = 5.0
    vendor_challan_ref: str | None = None
    vendor_invoice_no: str | None = None
    qc_status: str = "approved"
    notes: str | None = None


@router.get("/metadata")
def get_subcontracting_metadata(
    actor: Annotated[Actor, Depends(require_any_permission("inventory:read", "warehouse:read"))],
):
    """Metadata helper for populating order forms."""
    vendors = session.execute(
        select(Party).where(Party.tenant_id == actor["tenant_id"], Party.type.in_(["vendor", "both"]))
    ).scalars().all()

    fg_products = session.execute(
        select(Product).where(Product.tenant_id == actor["tenant_id"], Product.type.in_(["finished_good", "raw_material"]))
    ).scalars().all()

    warehouses = session.execute(
        select(Warehouse).where(Warehouse.tenant_id == actor["tenant_id"], Warehouse.status == "active")
    ).scalars().all()

    entities = session.execute(
        select(BusinessEntity).where(BusinessEntity.tenant_id == actor["tenant_id"])
    ).scalars().all()

    return {
        "vendors": [{"id": str(v.id), "code": v.code, "name": v.legal_name, "gstin": v.tax_id or "URP"} for v in vendors],
        "products": [
            {"id": str(p.id), "sku": p.sku, "name": p.name, "uom": p.uom, "hsn_code": p.hsn_code or "7204", "type": p.type}
            for p in fg_products
        ],
        "warehouses": [{"id": str(w.id), "code": w.code, "name": w.name} for w in warehouses],
        "entities": [{"id": str(e.id), "name": e.name, "gstin": e.tax_id or ""} for e in entities],
    }


@router.get("/orders")
def list_orders(
    actor: Annotated[Actor, Depends(require_any_permission("inventory:read", "warehouse:read"))],
    status: str | None = Query(None),
    vendor_id: str | None = Query(None),
):
    vendor_party_id = uuid.UUID(vendor_id) if vendor_id else None
    return SubcontractingService.list_orders(
        actor["tenant_id"],
        status=status,
        vendor_party_id=vendor_party_id,
    )


@router.post("/orders")
def create_order(
    payload: SubcontractOrderCreateSchema,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:write", "warehouse:write"))],
):
    order = SubcontractingService.create_order(
        actor["tenant_id"],
        payload.model_dump(),
        actor_id=actor["user_id"],
    )
    return {"id": str(order.id), "order_no": order.order_no, "status": order.status}


@router.get("/orders/{order_id}")
def get_order_detail(
    order_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:read", "warehouse:read"))],
):
    return SubcontractingService.get_order_detail(actor["tenant_id"], order_id)


@router.post("/orders/{order_id}/challans")
def issue_challan(
    order_id: uuid.UUID,
    payload: SubcontractChallanCreateSchema,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:write", "warehouse:write"))],
):
    ch = SubcontractingService.issue_delivery_challan(
        actor["tenant_id"],
        order_id,
        payload.model_dump(),
        actor_id=actor["user_id"],
    )
    return {"id": str(ch.id), "challan_no": ch.challan_no, "status": ch.status}


@router.get("/challans/{challan_id}/statutory")
def get_statutory_challan(
    challan_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:read", "warehouse:read"))],
):
    return SubcontractingService.get_statutory_challan(actor["tenant_id"], challan_id)


@router.post("/orders/{order_id}/receipts")
def record_receipt(
    order_id: uuid.UUID,
    payload: SubcontractReceiptCreateSchema,
    actor: Annotated[Actor, Depends(require_any_permission("inventory:write", "warehouse:write"))],
):
    rc = SubcontractingService.record_receipt(
        actor["tenant_id"],
        order_id,
        payload.model_dump(),
        actor_id=actor["user_id"],
    )
    return {"id": str(rc.id), "receipt_no": rc.receipt_no, "qc_status": rc.qc_status}
