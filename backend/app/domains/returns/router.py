from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select

from app.core.auth import Actor, require_any_permission
from app.core.db import session
from app.domains.returns.schemas import (
    RmaCreateRequest,
    RmaInspectRequest,
    RmaLineOut,
    RmaOut,
    RmaReceiveRequest,
    RtvCreateRequest,
    RtvDispatchRequest,
    RtvLineOut,
    RtvOut,
)
from app.domains.returns.service import (
    create_customer_rma,
    create_supplier_rtv,
    dispatch_supplier_rtv,
    inspect_and_disposition_rma,
    receive_customer_rma,
)
from app.models.returns import Rma, RmaLine, Rtv, RtvLine

router = APIRouter(prefix="/api/v1/returns", tags=["returns"])


def _serialize_rma(rma: Rma) -> RmaOut:
    lines = session.execute(select(RmaLine).where(RmaLine.rma_id == rma.id).order_by(RmaLine.line_no)).scalars().all()
    return RmaOut(
        id=rma.id,
        number=rma.number,
        customerId=rma.customer_id,
        customerName=rma.customer_name,
        orderId=rma.order_id,
        orderNumber=rma.order_number,
        warehouseId=rma.warehouse_id,
        warehouseCode=rma.warehouse_code,
        status=rma.status,
        returnReason=rma.return_reason,
        carrier=rma.carrier,
        trackingNumber=rma.tracking_number,
        creditNoteId=rma.credit_note_id,
        creditNoteNumber=rma.credit_note_number,
        notes=rma.notes,
        authorizedBy=rma.authorized_by,
        authorizedAt=rma.authorized_at,
        receivedAt=rma.received_at,
        inspectedBy=rma.inspected_by,
        inspectedAt=rma.inspected_at,
        createdAt=rma.created_at,
        lines=[
            RmaLineOut(
                id=l.id,
                lineNo=l.line_no,
                productId=l.product_id,
                sku=l.sku,
                orderLineId=l.order_line_id,
                authorizedQty=l.authorized_qty,
                receivedQty=l.received_qty,
                restockedQty=l.restocked_qty,
                scrappedQty=l.scrapped_qty,
                repairedQty=l.repaired_qty,
                uom=l.uom,
                unitPrice=l.unit_price,
                batchNo=l.batch_no,
                inspectionStatus=l.inspection_status,
                dispositionNotes=l.disposition_notes,
            )
            for l in lines
        ],
    )


def _serialize_rtv(rtv: Rtv) -> RtvOut:
    lines = session.execute(select(RtvLine).where(RtvLine.rtv_id == rtv.id).order_by(RtvLine.line_no)).scalars().all()
    return RtvOut(
        id=rtv.id,
        number=rtv.number,
        vendorId=rtv.vendor_id,
        vendorName=rtv.vendor_name,
        poId=rtv.po_id,
        poNumber=rtv.po_number,
        grnId=rtv.grn_id,
        grnNumber=rtv.grn_number,
        warehouseId=rtv.warehouse_id,
        warehouseCode=rtv.warehouse_code,
        status=rtv.status,
        returnReason=rtv.return_reason,
        transporter=rtv.transporter,
        vehicleNo=rtv.vehicle_no,
        lrNo=rtv.lr_no,
        debitNoteId=rtv.debit_note_id,
        debitNoteNumber=rtv.debit_note_number,
        notes=rtv.notes,
        approvedBy=rtv.approved_by,
        approvedAt=rtv.approved_at,
        dispatchedAt=rtv.dispatched_at,
        completedAt=rtv.completed_at,
        createdAt=rtv.created_at,
        lines=[
            RtvLineOut(
                id=l.id,
                lineNo=l.line_no,
                productId=l.product_id,
                sku=l.sku,
                quantity=l.quantity,
                uom=l.uom,
                unitPrice=l.unit_price,
                batchNo=l.batch_no,
                rejectionCode=l.rejection_code,
                reason=l.reason,
            )
            for l in lines
        ],
    )


# RMA Endpoints
@router.post("/rmas", response_model=RmaOut)
def create_rma(
    body: RmaCreateRequest,
    actor: Annotated[Actor, Depends(require_any_permission("order:write", "warehouse:write"))],
):
    rma = create_customer_rma(
        tenant_id=actor["tenant_id"],
        customer_id=body.customerId,
        warehouse_id=body.warehouseId,
        return_reason=body.returnReason,
        lines_data=[
            {
                "product_id": l.productId,
                "order_line_id": l.orderLineId,
                "authorized_qty": l.authorizedQty,
                "uom": l.uom,
                "unit_price": l.unitPrice,
                "batch_no": l.batchNo,
            }
            for l in body.lines
        ],
        order_id=body.orderId,
        carrier=body.carrier,
        tracking_number=body.trackingNumber,
        notes=body.notes,
        actor_email=actor.get("email"),
    )
    return _serialize_rma(rma)


@router.get("/rmas", response_model=list[RmaOut])
def list_rmas(
    actor: Annotated[Actor, Depends(require_any_permission("order:read", "warehouse:read"))],
):
    rmas = session.execute(
        select(Rma).where(Rma.tenant_id == actor["tenant_id"]).order_by(desc(Rma.created_at)).limit(50)
    ).scalars().all()
    return [_serialize_rma(r) for r in rmas]


@router.get("/rmas/{rma_id}", response_model=RmaOut)
def get_rma(
    rma_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("order:read", "warehouse:read"))],
):
    rma = session.execute(
        select(Rma).where(Rma.tenant_id == actor["tenant_id"], Rma.id == rma_id)
    ).scalar_one_or_none()
    if not rma:
        raise HTTPException(status_code=404, detail="RMA not found")
    return _serialize_rma(rma)


@router.post("/rmas/{rma_id}/receive", response_model=RmaOut)
def receive_rma(
    rma_id: uuid.UUID,
    body: RmaReceiveRequest,
    actor: Annotated[Actor, Depends(require_any_permission("warehouse:write"))],
):
    rma = receive_customer_rma(
        tenant_id=actor["tenant_id"],
        rma_id=rma_id,
        lines_received=[{"line_no": l.lineNo, "received_qty": l.receivedQty} for l in body.lines],
        carrier=body.carrier,
        tracking_number=body.trackingNumber,
    )
    return _serialize_rma(rma)


@router.post("/rmas/{rma_id}/inspect", response_model=RmaOut)
def inspect_rma(
    rma_id: uuid.UUID,
    body: RmaInspectRequest,
    actor: Annotated[Actor, Depends(require_any_permission("warehouse:write"))],
):
    rma = inspect_and_disposition_rma(
        tenant_id=actor["tenant_id"],
        rma_id=rma_id,
        dispositions=[
            {
                "line_no": d.lineNo,
                "restocked_qty": d.restockedQty,
                "scrapped_qty": d.scrappedQty,
                "repaired_qty": d.repairedQty,
                "disposition_notes": d.dispositionNotes,
                "inspectionStatus": d.inspectionStatus,
            }
            for d in body.dispositions
        ],
        notes=body.notes,
        actor_email=actor.get("email"),
    )
    return _serialize_rma(rma)


# RTV Endpoints
@router.post("/rtvs", response_model=RtvOut)
def create_rtv(
    body: RtvCreateRequest,
    actor: Annotated[Actor, Depends(require_any_permission("po:write", "warehouse:write"))],
):
    rtv = create_supplier_rtv(
        tenant_id=actor["tenant_id"],
        vendor_id=body.vendorId,
        warehouse_id=body.warehouseId,
        return_reason=body.returnReason,
        lines_data=[
            {
                "product_id": l.productId,
                "quantity": l.quantity,
                "uom": l.uom,
                "unit_price": l.unitPrice,
                "batch_no": l.batchNo,
                "rejection_code": l.rejectionCode,
                "reason": l.reason,
            }
            for l in body.lines
        ],
        po_id=body.poId,
        grn_id=body.grnId,
        notes=body.notes,
        actor_email=actor.get("email"),
    )
    return _serialize_rtv(rtv)


@router.get("/rtvs", response_model=list[RtvOut])
def list_rtvs(
    actor: Annotated[Actor, Depends(require_any_permission("po:read", "warehouse:read"))],
):
    rtvs = session.execute(
        select(Rtv).where(Rtv.tenant_id == actor["tenant_id"]).order_by(desc(Rtv.created_at)).limit(50)
    ).scalars().all()
    return [_serialize_rtv(r) for r in rtvs]


@router.get("/rtvs/{rtv_id}", response_model=RtvOut)
def get_rtv(
    rtv_id: uuid.UUID,
    actor: Annotated[Actor, Depends(require_any_permission("po:read", "warehouse:read"))],
):
    rtv = session.execute(
        select(Rtv).where(Rtv.tenant_id == actor["tenant_id"], Rtv.id == rtv_id)
    ).scalar_one_or_none()
    if not rtv:
        raise HTTPException(status_code=404, detail="RTV not found")
    return _serialize_rtv(rtv)


@router.post("/rtvs/{rtv_id}/dispatch", response_model=RtvOut)
def dispatch_rtv(
    rtv_id: uuid.UUID,
    body: RtvDispatchRequest,
    actor: Annotated[Actor, Depends(require_any_permission("warehouse:write"))],
):
    rtv = dispatch_supplier_rtv(
        tenant_id=actor["tenant_id"],
        rtv_id=rtv_id,
        transporter=body.transporter,
        vehicle_no=body.vehicleNo,
        lr_no=body.lrNo,
        notes=body.notes,
        actor_email=actor.get("email"),
    )
    return _serialize_rtv(rtv)
