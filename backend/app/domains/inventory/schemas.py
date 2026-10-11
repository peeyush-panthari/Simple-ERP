"""Request bodies, ported from backend_py/app/routes/inventory_movements.py
- production's schemas (ProductionBody etc.) are left out, see router.py's
module docstring."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.money import is_positive
from app.core.scalars import DecimalString, UomCode


class ReservationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    productId: uuid_mod.UUID
    warehouseId: uuid_mod.UUID
    quantity: DecimalString
    uom: UomCode
    batchNo: str | None = Field(default=None, max_length=60)
    orderId: uuid_mod.UUID | None = None
    orderLineId: uuid_mod.UUID | None = None
    referenceType: str = Field(default="order", max_length=40)
    referenceNo: str | None = Field(default=None, max_length=60)
    expiresAt: datetime | None = None

    @field_validator("quantity")
    @classmethod
    def _positive(cls, v):
        if not is_positive(v):
            raise ValueError("Must be greater than zero")
        return v


class ReleaseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


class AdjustmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    productId: uuid_mod.UUID
    warehouseId: uuid_mod.UUID
    locationId: uuid_mod.UUID | None = None
    batchNo: str | None = Field(default=None, max_length=60)
    expiryDate: date | None = None
    quantity: str = Field(pattern=r"^-?\d+(\.\d+)?$")
    uom: UomCode
    bucket: str = "available"
    reason: str = Field(min_length=5, max_length=500)
    unitCost: DecimalString | None = None
    itemId: uuid_mod.UUID | None = None

    @field_validator("bucket")
    @classmethod
    def _bucket_ok(cls, v):
        if v not in ("available", "quarantine", "damaged", "expired"):
            raise ValueError("invalid bucket")
        return v


class AdjustmentBulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)


class StatusChangeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    productId: uuid_mod.UUID
    warehouseId: uuid_mod.UUID
    locationId: uuid_mod.UUID | None = None
    batchNo: str | None = Field(default=None, max_length=60)
    quantity: DecimalString
    uom: UomCode
    from_: str = Field(alias="from")
    to: str
    reason: str = Field(min_length=5, max_length=500)
    itemId: uuid_mod.UUID | None = None

    @field_validator("quantity")
    @classmethod
    def _positive(cls, v):
        if not is_positive(v):
            raise ValueError("Must be greater than zero")
        return v

    @field_validator("from_", "to")
    @classmethod
    def _bucket_ok(cls, v):
        if v not in ("available", "quarantine", "damaged", "expired"):
            raise ValueError("invalid bucket")
        return v


class TransferBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    productId: uuid_mod.UUID
    batchNo: str | None = Field(default=None, max_length=60)
    quantity: DecimalString
    uom: UomCode
    sourceWarehouseId: uuid_mod.UUID
    sourceLocationId: uuid_mod.UUID | None = None
    destWarehouseId: uuid_mod.UUID
    destLocationId: uuid_mod.UUID | None = None
    reason: str | None = Field(default=None, max_length=500)
    itemId: uuid_mod.UUID | None = None

    @field_validator("quantity")
    @classmethod
    def _positive(cls, v):
        if not is_positive(v):
            raise ValueError("Must be greater than zero")
        return v


class TransferBulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)


class CompleteTransferBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destLocationId: uuid_mod.UUID | None = None
