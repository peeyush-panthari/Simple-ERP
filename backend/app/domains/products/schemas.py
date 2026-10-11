"""Request bodies, ported from backend_py/app/routes/products.py."""

from __future__ import annotations

import uuid as uuid_mod

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.scalars import PRODUCT_TYPES, DecimalString, UomCode


class CreateProductBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str | None = Field(default=None, min_length=3, max_length=32)
    name: str = Field(min_length=2, max_length=200)
    make: str = Field(min_length=1, max_length=200)
    modelNumber: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    type: str
    categoryId: uuid_mod.UUID | None = None
    uom: UomCode
    alternateUoms: list[UomCode] = Field(default_factory=list)
    hsnCode: str | None = Field(default=None, max_length=20)
    batchTracked: bool = False
    expiryTracked: bool = False
    storageConditions: str | None = Field(default=None, max_length=500)
    reorderPoint: DecimalString | None = None
    reorderQty: DecimalString | None = None
    leadTimeDays: int | None = Field(default=None, ge=0, le=365)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    purchasable: bool = True
    sellable: bool = False
    weightKg: DecimalString | None = None
    volumeM3: DecimalString | None = None

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        if v not in PRODUCT_TYPES:
            raise ValueError(f"must be one of {PRODUCT_TYPES}")
        return v

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, v):
        return v.upper() if v else v


class PatchProductBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str | None = Field(default=None, min_length=3, max_length=32)
    name: str | None = Field(default=None, min_length=2, max_length=200)
    make: str | None = Field(default=None, min_length=1, max_length=200)
    modelNumber: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    type: str | None = None
    categoryId: uuid_mod.UUID | None = None
    uom: UomCode | None = None
    alternateUoms: list[UomCode] | None = None
    hsnCode: str | None = Field(default=None, max_length=20)
    batchTracked: bool | None = None
    expiryTracked: bool | None = None
    storageConditions: str | None = Field(default=None, max_length=500)
    reorderPoint: DecimalString | None = None
    reorderQty: DecimalString | None = None
    leadTimeDays: int | None = Field(default=None, ge=0, le=365)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    purchasable: bool | None = None
    sellable: bool | None = None
    weightKg: DecimalString | None = None
    volumeM3: DecimalString | None = None
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v):
        if v is not None and v not in PRODUCT_TYPES:
            raise ValueError(f"must be one of {PRODUCT_TYPES}")
        return v

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, v):
        return v.upper() if v else v


class DeprecateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)
    force: bool = False


class ConvertBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: DecimalString
    from_: str = Field(alias="from", min_length=1, max_length=10)
    to: str = Field(min_length=1, max_length=10)


class SetConversionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fromUom: UomCode
    toUom: UomCode
    factor: DecimalString


class AddAliasBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aliasSku: str = Field(min_length=3, max_length=32)
    reason: str | None = Field(default=None, max_length=500)


class AddImageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=1000)
    alt: str | None = Field(default=None, max_length=200)
    isPrimary: bool = False
    sortOrder: int = Field(default=0, ge=0, le=999)
    bytes: int | None = Field(default=None, gt=0)
    mime: str | None = None

    @field_validator("mime")
    @classmethod
    def _mime_ok(cls, v):
        if v is not None and v not in ("image/png", "image/jpeg", "image/webp", "image/avif"):
            raise ValueError("unsupported mime type")
        return v


class AddSpecBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)
    unit: str | None = Field(default=None, max_length=20)
    sortOrder: int = Field(default=0, ge=0, le=999)


class ProductBulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)
