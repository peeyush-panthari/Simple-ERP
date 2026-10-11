from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class MrpRunRequest(BaseModel):
    horizonDays: int = Field(default=30, ge=1, le=365)
    warehouseId: uuid.UUID | None = None
    notes: str | None = None


class MrpPlannedOrderOut(BaseModel):
    id: uuid.UUID
    mrpRunId: uuid.UUID
    productId: uuid.UUID
    sku: str
    productName: str
    orderType: Literal["purchase", "production"]
    warehouseId: uuid.UUID
    warehouseCode: str | None = None
    quantity: Decimal
    uom: str
    suggestedOrderDate: date
    requiredByDate: date
    leadTimeDays: int
    estimatedUnitCost: Decimal | None = None
    status: Literal["suggested", "released", "rejected"]
    sourceDemand: str
    releasedReferenceType: str | None = None
    releasedReferenceId: uuid.UUID | None = None
    releasedReferenceNumber: str | None = None
    releasedAt: datetime | None = None
    releasedBy: str | None = None
    createdAt: datetime

    class Config:
        from_attributes = True


class MrpRunOut(BaseModel):
    id: uuid.UUID
    number: str
    horizonDays: int
    warehouseId: uuid.UUID | None = None
    warehouseCode: str | None = None
    status: str
    totalSkusAnalyzed: int
    plannedOrdersCount: int
    notes: str | None = None
    createdBy: str | None = None
    createdAt: datetime
    plannedOrders: list[MrpPlannedOrderOut] = []

    class Config:
        from_attributes = True


class ReleaseOrdersRequest(BaseModel):
    plannedOrderIds: list[uuid.UUID]
