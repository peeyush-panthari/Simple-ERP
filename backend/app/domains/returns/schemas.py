from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# RMA Schemas
class RmaLineCreate(BaseModel):
    productId: uuid.UUID
    orderLineId: uuid.UUID | None = None
    authorizedQty: Decimal = Field(..., gt=0)
    uom: str
    unitPrice: Decimal = Decimal(0)
    batchNo: str | None = None


class RmaCreateRequest(BaseModel):
    customerId: uuid.UUID
    orderId: uuid.UUID | None = None
    warehouseId: uuid.UUID
    returnReason: str
    carrier: str | None = None
    trackingNumber: str | None = None
    notes: str | None = None
    lines: list[RmaLineCreate]


class RmaReceiveLine(BaseModel):
    lineNo: int
    receivedQty: Decimal = Field(..., ge=0)


class RmaReceiveRequest(BaseModel):
    carrier: str | None = None
    trackingNumber: str | None = None
    lines: list[RmaReceiveLine]


class RmaDispositionLine(BaseModel):
    lineNo: int
    restockedQty: Decimal = Decimal(0)
    scrappedQty: Decimal = Decimal(0)
    repairedQty: Decimal = Decimal(0)
    dispositionNotes: str | None = None
    inspectionStatus: Literal["passed", "failed", "scrapped"] = "passed"


class RmaInspectRequest(BaseModel):
    dispositions: list[RmaDispositionLine]
    notes: str | None = None


class RmaLineOut(BaseModel):
    id: uuid.UUID
    lineNo: int
    productId: uuid.UUID
    sku: str
    orderLineId: uuid.UUID | None = None
    authorizedQty: Decimal
    receivedQty: Decimal
    restockedQty: Decimal
    scrappedQty: Decimal
    repairedQty: Decimal
    uom: str
    unitPrice: Decimal
    batchNo: str | None = None
    inspectionStatus: str
    dispositionNotes: str | None = None

    class Config:
        from_attributes = True


class RmaOut(BaseModel):
    id: uuid.UUID
    number: str
    customerId: uuid.UUID
    customerName: str
    orderId: uuid.UUID | None = None
    orderNumber: str | None = None
    warehouseId: uuid.UUID
    warehouseCode: str | None = None
    status: str
    returnReason: str
    carrier: str | None = None
    trackingNumber: str | None = None
    creditNoteId: uuid.UUID | None = None
    creditNoteNumber: str | None = None
    notes: str | None = None
    authorizedBy: str | None = None
    authorizedAt: datetime | None = None
    receivedAt: datetime | None = None
    inspectedBy: str | None = None
    inspectedAt: datetime | None = None
    createdAt: datetime
    lines: list[RmaLineOut] = []

    class Config:
        from_attributes = True


# RTV Schemas
class RtvLineCreate(BaseModel):
    productId: uuid.UUID
    quantity: Decimal = Field(..., gt=0)
    uom: str
    unitPrice: Decimal = Decimal(0)
    batchNo: str | None = None
    rejectionCode: str | None = None
    reason: str | None = None


class RtvCreateRequest(BaseModel):
    vendorId: uuid.UUID
    poId: uuid.UUID | None = None
    grnId: uuid.UUID | None = None
    warehouseId: uuid.UUID
    returnReason: str
    notes: str | None = None
    lines: list[RtvLineCreate]


class RtvDispatchRequest(BaseModel):
    transporter: str | None = None
    vehicleNo: str | None = None
    lrNo: str | None = None
    notes: str | None = None


class RtvLineOut(BaseModel):
    id: uuid.UUID
    lineNo: int
    productId: uuid.UUID
    sku: str
    quantity: Decimal
    uom: str
    unitPrice: Decimal
    batchNo: str | None = None
    rejectionCode: str | None = None
    reason: str | None = None

    class Config:
        from_attributes = True


class RtvOut(BaseModel):
    id: uuid.UUID
    number: str
    vendorId: uuid.UUID
    vendorName: str
    poId: uuid.UUID | None = None
    poNumber: str | None = None
    grnId: uuid.UUID | None = None
    grnNumber: str | None = None
    warehouseId: uuid.UUID
    warehouseCode: str | None = None
    status: str
    returnReason: str
    transporter: str | None = None
    vehicleNo: str | None = None
    lrNo: str | None = None
    debitNoteId: uuid.UUID | None = None
    debitNoteNumber: str | None = None
    notes: str | None = None
    approvedBy: str | None = None
    approvedAt: datetime | None = None
    dispatchedAt: datetime | None = None
    completedAt: datetime | None = None
    createdAt: datetime
    lines: list[RtvLineOut] = []

    class Config:
        from_attributes = True
