"""Request bodies, ported from backend_py/app/routes/boms.py."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.core.scalars import DecimalString, UomCode


class ComponentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lineNo: int | None = Field(default=None, ge=1, le=9999)
    componentProductId: uuid_mod.UUID
    quantity: DecimalString
    uom: UomCode
    scrapPercent: DecimalString = "0"
    isAlternate: bool = False
    alternateForLine: int | None = Field(default=None, ge=1, le=9999)
    notes: str | None = Field(default=None, max_length=500)


class VersionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    yieldPercent: DecimalString = "100"
    effectiveFrom: date
    effectiveTo: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    routingNotes: str | None = Field(default=None, max_length=2000)
    components: list[ComponentBody] = Field(min_length=1)


class CreateBomBody(VersionBody):
    productId: uuid_mod.UUID


class PatchVersionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    yieldPercent: DecimalString | None = None
    effectiveFrom: date | None = None
    effectiveTo: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    routingNotes: str | None = Field(default=None, max_length=2000)
    components: list[ComponentBody] | None = None


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


class RejectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)


class ReviseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    effectiveFrom: date
    notes: str | None = Field(default=None, max_length=2000)


class BomBulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)
