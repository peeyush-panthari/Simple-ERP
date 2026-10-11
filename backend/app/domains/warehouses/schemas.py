"""Request bodies, ported from backend_py/app/routes/warehouses.py."""

from __future__ import annotations

import re
import uuid as uuid_mod

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.scalars import DecimalString

PRODUCT_TYPES = ("raw_material", "finished_good", "consumable", "service")
_WAREHOUSE_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,23}$")


def _warehouse_code(value: str) -> str:
    v = value.strip().upper()
    if not _WAREHOUSE_CODE_RE.match(v):
        raise ValueError("Warehouse codes are 3–24 characters: letters, digits and hyphens")
    return v


class WarehouseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = None
    name: str = Field(min_length=2, max_length=140)
    status: str = "active"
    factoryId: uuid_mod.UUID | None = None
    allowedProductTypes: list[str] = Field(default_factory=list)
    addressLine1: str | None = Field(default=None, max_length=200)
    addressLine2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    stateCode: str | None = Field(default=None, max_length=10)
    postalCode: str | None = Field(default=None, max_length=20)
    country: str = "IN"
    contactEmail: str | None = Field(default=None, max_length=254)
    contactPhone: str | None = Field(default=None, max_length=30)
    capacityUnits: DecimalString | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("code")
    @classmethod
    def _code_ok(cls, v: str | None) -> str | None:
        return _warehouse_code(v) if v is not None else v

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: str) -> str:
        if v not in ("active", "constrained", "inactive"):
            raise ValueError("must be one of active, constrained, inactive")
        return v

    @field_validator("allowedProductTypes")
    @classmethod
    def _types_ok(cls, v: list[str]) -> list[str]:
        for t in v:
            if t not in PRODUCT_TYPES:
                raise ValueError(f"must be one of {PRODUCT_TYPES}")
        return v

    @field_validator("country")
    @classmethod
    def _country_ok(cls, v: str) -> str:
        if len(v) != 2:
            raise ValueError("must be a 2-letter country code")
        return v.upper()


class PatchWarehouseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=140)
    status: str | None = None
    factoryId: uuid_mod.UUID | None = None
    allowedProductTypes: list[str] | None = None
    addressLine1: str | None = Field(default=None, max_length=200)
    addressLine2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    stateCode: str | None = Field(default=None, max_length=10)
    postalCode: str | None = Field(default=None, max_length=20)
    country: str | None = None
    contactEmail: str | None = Field(default=None, max_length=254)
    contactPhone: str | None = Field(default=None, max_length=30)
    capacityUnits: DecimalString | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v):
        if v is not None and v not in ("active", "constrained", "inactive"):
            raise ValueError("must be one of active, constrained, inactive")
        return v

    @field_validator("allowedProductTypes")
    @classmethod
    def _types_ok(cls, v):
        if v is not None:
            for t in v:
                if t not in PRODUCT_TYPES:
                    raise ValueError(f"must be one of {PRODUCT_TYPES}")
        return v

    @field_validator("country")
    @classmethod
    def _country_ok(cls, v):
        return v.upper() if v else v


class LocationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=40)
    name: str | None = Field(default=None, max_length=140)
    type: str
    parentId: uuid_mod.UUID | None = None
    status: str = "active"
    allowedProductTypes: list[str] = Field(default_factory=list)
    capacityUnits: DecimalString | None = None
    temperatureControlled: bool = False

    @field_validator("code")
    @classmethod
    def _code_upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        if v not in ("zone", "aisle", "rack", "bin", "staging", "quarantine"):
            raise ValueError("invalid location type")
        return v

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: str) -> str:
        if v not in ("active", "blocked", "inactive"):
            raise ValueError("must be one of active, blocked, inactive")
        return v

    @field_validator("allowedProductTypes")
    @classmethod
    def _types_ok(cls, v: list[str]) -> list[str]:
        for t in v:
            if t not in PRODUCT_TYPES:
                raise ValueError(f"must be one of {PRODUCT_TYPES}")
        return v


class PatchLocationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=140)
    type: str | None = None
    status: str | None = None
    allowedProductTypes: list[str] | None = None
    capacityUnits: DecimalString | None = None
    temperatureControlled: bool | None = None

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v):
        if v is not None and v not in ("zone", "aisle", "rack", "bin", "staging", "quarantine"):
            raise ValueError("invalid location type")
        return v

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v):
        if v is not None and v not in ("active", "blocked", "inactive"):
            raise ValueError("must be one of active, blocked, inactive")
        return v


class WarehouseBulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)
