"""Request bodies for the foundation/master-data domain: factories, auth
policy, party types, sticker sizes. Ported from backend_py/app/routes/
{factories,tenants,party_types,sticker_sizes}.py."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,23}$")


def _factory_code(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip().upper()
    if not _CODE_RE.match(v):
        raise ValueError("Factory codes are 2–24 characters: letters, digits and hyphens")
    return v


def _active_inactive(v: str | None) -> str | None:
    if v is not None and v not in ("active", "inactive"):
        raise ValueError("must be 'active' or 'inactive'")
    return v


class FactoryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(default=None, min_length=2, max_length=24)
    name: str = Field(min_length=2, max_length=120)
    addressLine1: str | None = Field(default=None, max_length=200)
    addressLine2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    stateCode: str | None = Field(default=None, max_length=10)
    postalCode: str | None = Field(default=None, max_length=20)
    country: str = Field(default="IN", min_length=2, max_length=2)
    contactEmail: str | None = Field(default=None, max_length=120)
    contactPhone: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    status: str = "active"

    _code_ok = field_validator("code")(classmethod(lambda cls, v: _factory_code(v)))
    _status_ok = field_validator("status")(classmethod(lambda cls, v: _active_inactive(v)))


class PatchFactoryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(default=None, min_length=2, max_length=24)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    addressLine1: str | None = Field(default=None, max_length=200)
    addressLine2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    stateCode: str | None = Field(default=None, max_length=10)
    postalCode: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    contactEmail: str | None = Field(default=None, max_length=120)
    contactPhone: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    status: str | None = None

    _code_ok = field_validator("code")(classmethod(lambda cls, v: _factory_code(v)))
    _status_ok = field_validator("status")(classmethod(lambda cls, v: _active_inactive(v)))


class BulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)


class AuthPolicyPatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passwordMinLength: int | None = Field(default=None, ge=8, le=128)
    passwordMaxAgeDays: int | None = Field(default=None, ge=0, le=3650)
    mfaRequired: bool | None = None
    maxFailedAttempts: int | None = Field(default=None, ge=3, le=20)
    lockoutMinutes: int | None = Field(default=None, ge=1, le=1440)
    sessionIdleMinutes: int | None = Field(default=None, ge=5, le=1440)
    inactiveUserDays: int | None = Field(default=None, ge=7, le=3650)


class CreatePartyTypeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=2, max_length=80)
    baseType: str
    code: str | None = Field(default=None, max_length=60)

    @field_validator("baseType")
    @classmethod
    def _base_type_ok(cls, v: str) -> str:
        if v not in ("vendor", "customer", "both"):
            raise ValueError("must be 'vendor', 'customer' or 'both'")
        return v


class PatchPartyTypeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = Field(default=None, min_length=2, max_length=80)
    status: str | None = None

    _status_ok = field_validator("status")(classmethod(lambda cls, v: _active_inactive(v)))


PAGE_SIZES = ("A4", "A5", "Letter", "Custom")


def _mm_value(value) -> str:
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("must be a number") from None
    if d < 0:
        raise ValueError("must not be negative")
    return str(d.quantize(Decimal("0.01")))


MmValue = Annotated[str | int | float, AfterValidator(_mm_value)]


def _page_size_ok(v: str | None) -> str | None:
    if v is not None and v not in PAGE_SIZES:
        raise ValueError(f"must be one of {', '.join(PAGE_SIZES)}")
    return v


class StickerSizeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    pageSize: str = "A4"
    pageWidthMm: MmValue | None = None
    pageHeightMm: MmValue | None = None
    stickerWidthMm: MmValue
    stickerHeightMm: MmValue
    columns: int = Field(gt=0, le=100)
    rows: int = Field(gt=0, le=100)
    marginLeftMm: MmValue
    marginRightMm: MmValue
    marginTopMm: MmValue
    marginBottomMm: MmValue
    gapHorizontalMm: MmValue
    gapVerticalMm: MmValue
    status: str = "active"

    _page_size_ok = field_validator("pageSize")(classmethod(lambda cls, v: _page_size_ok(v)))
    _status_ok = field_validator("status")(classmethod(lambda cls, v: _active_inactive(v)))


class PatchStickerSizeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    pageSize: str | None = None
    pageWidthMm: MmValue | None = None
    pageHeightMm: MmValue | None = None
    stickerWidthMm: MmValue | None = None
    stickerHeightMm: MmValue | None = None
    columns: int | None = Field(default=None, gt=0, le=100)
    rows: int | None = Field(default=None, gt=0, le=100)
    marginLeftMm: MmValue | None = None
    marginRightMm: MmValue | None = None
    marginTopMm: MmValue | None = None
    marginBottomMm: MmValue | None = None
    gapHorizontalMm: MmValue | None = None
    gapVerticalMm: MmValue | None = None
    status: str | None = None

    _page_size_ok = field_validator("pageSize")(classmethod(lambda cls, v: _page_size_ok(v)))
    _status_ok = field_validator("status")(classmethod(lambda cls, v: _active_inactive(v)))


# ---- product categories --------------------------------------------------

import uuid as uuid_mod  # noqa: E402

from app.core.scalars import PRODUCT_TYPES  # noqa: E402
from app.domains.parties.schemas import CountryCode  # noqa: E402


def _category_code(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip().upper()
    if not _CODE_RE.match(v):
        raise ValueError("Category codes are 2–24 characters: letters, digits and hyphens")
    return v


class CategoryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(default=None, min_length=2, max_length=24)
    productCategory: str = Field(min_length=2, max_length=120)
    parentId: uuid_mod.UUID | None = None
    productTypes: list[str] = Field(default_factory=list)
    requiresBatch: bool = False
    requiresExpiry: bool = False
    defaultTaxCode: str | None = Field(default=None, max_length=20)
    status: str = "active"

    _code_ok = field_validator("code")(classmethod(lambda cls, v: _category_code(v)))
    _status_ok = field_validator("status")(classmethod(lambda cls, v: _active_inactive(v)))

    @field_validator("productTypes")
    @classmethod
    def _types_ok(cls, v: list[str]) -> list[str]:
        for t in v:
            if t not in PRODUCT_TYPES:
                raise ValueError(f"unknown product type: {t}")
        return v


class PatchCategoryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(default=None, min_length=2, max_length=24)
    productCategory: str | None = Field(default=None, min_length=2, max_length=120)
    parentId: uuid_mod.UUID | None = None
    productTypes: list[str] | None = None
    requiresBatch: bool | None = None
    requiresExpiry: bool | None = None
    defaultTaxCode: str | None = Field(default=None, max_length=20)
    status: str | None = None

    _code_ok = field_validator("code")(classmethod(lambda cls, v: _category_code(v)))
    _status_ok = field_validator("status")(classmethod(lambda cls, v: _active_inactive(v)))


# ---- business entities ----------------------------------------------------

_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_IFSC_RE = re.compile(r"^[A-Za-z]{4}0[A-Za-z0-9]{6}$")


def _entity_code(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip().upper()
    if not _CODE_RE.match(v):
        raise ValueError("Codes are 2–24 characters: letters, digits and hyphens")
    return v


def _pan_ok(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip().upper()
    if not _PAN_RE.match(v):
        raise ValueError("PAN must be 10 characters: 5 letters, 4 digits, 1 letter (e.g. AAPFU0939F)")
    return v


def _ifsc_ok(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip().upper()
    if not _IFSC_RE.match(v):
        raise ValueError("IFSC code must be 11 characters: 4 letters, a 0, then 6 alphanumeric characters (e.g. HDFC0001234)")
    return v


class BusinessEntityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(default=None, min_length=2, max_length=24)
    name: str = Field(min_length=2, max_length=120)
    addressLine1: str | None = Field(default=None, max_length=200)
    addressLine2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    stateCode: str | None = Field(default=None, max_length=10)
    postalCode: str | None = Field(default=None, max_length=20)
    country: str = Field(default="IN", min_length=2, max_length=2)
    taxId: str | None = Field(default=None, max_length=40)
    taxIdCountry: CountryCode | None = None
    pan: str | None = Field(default=None, max_length=10)
    contactEmail: str | None = Field(default=None, max_length=120)
    contactPhone: str | None = Field(default=None, max_length=30)
    bankName: str | None = Field(default=None, max_length=140)
    bankBranch: str | None = Field(default=None, max_length=140)
    bankAccountNumber: str | None = Field(default=None, pattern=r"(?i)^[0-9A-Z]{6,34}$")
    bankIfsc: str | None = Field(default=None, max_length=11)
    isDefault: bool = False
    status: str = "active"

    _code_ok = field_validator("code")(classmethod(lambda cls, v: _entity_code(v)))
    _pan_v = field_validator("pan")(classmethod(lambda cls, v: _pan_ok(v)))
    _ifsc_v = field_validator("bankIfsc")(classmethod(lambda cls, v: _ifsc_ok(v)))
    _status_ok = field_validator("status")(classmethod(lambda cls, v: _active_inactive(v)))


class PatchBusinessEntityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(default=None, min_length=2, max_length=24)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    addressLine1: str | None = Field(default=None, max_length=200)
    addressLine2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    stateCode: str | None = Field(default=None, max_length=10)
    postalCode: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    taxId: str | None = Field(default=None, max_length=40)
    taxIdCountry: CountryCode | None = None
    pan: str | None = Field(default=None, max_length=10)
    contactEmail: str | None = Field(default=None, max_length=120)
    contactPhone: str | None = Field(default=None, max_length=30)
    bankName: str | None = Field(default=None, max_length=140)
    bankBranch: str | None = Field(default=None, max_length=140)
    bankAccountNumber: str | None = Field(default=None, pattern=r"(?i)^[0-9A-Z]{6,34}$")
    bankIfsc: str | None = Field(default=None, max_length=11)
    isDefault: bool | None = None
    status: str | None = None

    _code_ok = field_validator("code")(classmethod(lambda cls, v: _entity_code(v)))
    _pan_v = field_validator("pan")(classmethod(lambda cls, v: _pan_ok(v)))
    _ifsc_v = field_validator("bankIfsc")(classmethod(lambda cls, v: _ifsc_ok(v)))
    _status_ok = field_validator("status")(classmethod(lambda cls, v: _active_inactive(v)))
