"""Request bodies, ported from backend_py/app/routes/purchase_orders.py.
`IssueBody` is left out - see router.py's module docstring (issue/send-email/
pdf are deferred, they need document rendering + notifications, not ported
yet)."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.scalars import DecimalString, UomCode


class LineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    productId: uuid_mod.UUID
    description: str | None = Field(default=None, max_length=500)
    quantity: DecimalString
    uom: UomCode
    unitPrice: DecimalString
    discount: DecimalString = "0"
    taxCode: str | None = Field(default=None, max_length=20)
    expectedDate: date | None = None


class PoBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vendorId: uuid_mod.UUID
    warehouseId: uuid_mod.UUID
    businessEntityId: uuid_mod.UUID | None = None
    poDate: date | None = None
    expectedDate: date
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    exchangeRate: DecimalString = "1"
    charges: DecimalString = "0"
    paymentTerms: str | None = Field(default=None, max_length=60)
    paymentMode: str | None = Field(default=None, max_length=60)
    incoterms: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[LineBody] = Field(min_length=1)
    expectedTotal: DecimalString | None = None

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, v):
        return v.upper() if v else v


class PatchPoBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vendorId: uuid_mod.UUID | None = None
    warehouseId: uuid_mod.UUID | None = None
    businessEntityId: uuid_mod.UUID | None = None
    poDate: date | None = None
    expectedDate: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    exchangeRate: DecimalString | None = None
    charges: DecimalString | None = None
    paymentTerms: str | None = Field(default=None, max_length=60)
    paymentMode: str | None = Field(default=None, max_length=60)
    incoterms: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[LineBody] | None = None
    expectedTotal: DecimalString | None = None


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


class RejectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)


class ShortCloseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)


class AmendBody(PatchPoBody):
    reason: str = Field(min_length=5, max_length=500)


class PoBulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)


class IssueBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: list[str] | None = Field(default=None, max_length=10)
    cc: list[str] | None = Field(default=None, max_length=10)
