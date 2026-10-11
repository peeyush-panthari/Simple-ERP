"""Request bodies, ported from backend_py/app/routes/grns.py. QR/sticker
bodies (DecodeInventoryQrBody, VendorQrBody) are left out - see router.py's
module docstring (deferred, need PIL/zxingcpp photo decode + PDF sticker
sheet rendering, not ported yet)."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.scalars import DecimalString


class LineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    poLineId: uuid_mod.UUID
    receivedQty: DecimalString
    batchNo: str | None = Field(default=None, max_length=60)
    expiryDate: date | None = None
    manufactureDate: date | None = None
    locationId: uuid_mod.UUID | None = None


class GrnBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    poId: uuid_mod.UUID
    warehouseId: uuid_mod.UUID | None = None
    receivedDate: date | None = None
    vehicleNumber: str | None = Field(default=None, max_length=40)
    deliveryNote: str | None = Field(default=None, max_length=80)
    gateEntryNo: str | None = Field(default=None, max_length=40)
    invoiceNumber: str = Field(min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)
    stickerSizeId: uuid_mod.UUID | None = None
    vendorQrEnabled: bool = False
    lines: list[LineBody] = Field(min_length=1)


class GrnLineEditBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid_mod.UUID | None = None
    poLineId: uuid_mod.UUID
    receivedQty: DecimalString
    batchNo: str | None = Field(default=None, max_length=60)
    expiryDate: date | None = None
    manufactureDate: date | None = None
    locationId: uuid_mod.UUID | None = None


class GrnEditBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warehouseId: uuid_mod.UUID | None = None
    lines: list[GrnLineEditBody] = Field(min_length=1)


class InspectLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lineId: uuid_mod.UUID
    acceptedQty: DecimalString
    rejectedQty: DecimalString
    rejectionCode: str | None = Field(default=None, max_length=40)
    rejectionNote: str | None = Field(default=None, max_length=500)
    locationId: uuid_mod.UUID | None = None


class InspectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[InspectLine] = Field(min_length=1)


class QcItemDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    itemId: uuid_mod.UUID
    decision: str
    rejectionCode: str | None = Field(default=None, max_length=40)
    rejectionNote: str | None = Field(default=None, max_length=500)


class QcLineDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lineId: uuid_mod.UUID
    acceptedQty: DecimalString
    rejectedQty: DecimalString
    rejectionCode: str | None = Field(default=None, max_length=40)
    rejectionNote: str | None = Field(default=None, max_length=500)


class QcBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[QcItemDecision] = Field(default_factory=list)
    lines: list[QcLineDecision] = Field(default_factory=list)


class RejectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)


class PutawayLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grnLineId: uuid_mod.UUID
    toLocationId: uuid_mod.UUID
    quantity: DecimalString | None = None
    note: str | None = Field(default=None, max_length=500)


class PutawayBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[PutawayLineBody] = Field(min_length=1, max_length=200)


class RejectionCodeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=2, max_length=40)
    description: str = Field(min_length=2, max_length=200)


class DisposeInventoryItemBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    disposition: str

    @field_validator("disposition")
    @classmethod
    def _known_disposition(cls, v):
        if v not in ("returned_to_vendor", "discarded"):
            raise ValueError("Must be 'returned_to_vendor' or 'discarded'")
        return v


class ResolveInventoryScanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)


class GrnBulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)


class QcBulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)
