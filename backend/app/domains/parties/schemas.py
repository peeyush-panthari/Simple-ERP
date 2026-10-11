"""Request bodies, ported from backend_py/app/routes/party_schemas.py +
routes/parties.py."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.money import DecimalError, decimal_str, is_negative


def _decimal_string(value) -> str:
    try:
        return decimal_str(value)
    except DecimalError as exc:
        raise ValueError(f'"{value}" is not a decimal amount') from exc


def _non_negative(value: str) -> str:
    if is_negative(value):
        raise ValueError("Amount cannot be negative")
    return value


DecimalString = Annotated[str | int | float, AfterValidator(_decimal_string)]
NonNegativeDecimal = Annotated[str | int | float, AfterValidator(_decimal_string), AfterValidator(_non_negative)]


def _currency_code(value: str) -> str:
    v = value.strip().upper()
    if not re.match(r"^[A-Z]{3}$", v):
        raise ValueError("Use a 3-letter ISO 4217 currency code, e.g. INR")
    return v


def _country_code(value: str) -> str:
    v = value.strip().upper()
    if not re.match(r"^[A-Z]{2}$", v):
        raise ValueError("Use a 2-letter ISO 3166-1 country code, e.g. IN")
    return v


def _party_code(value: str) -> str:
    v = value.strip().upper()
    if not re.match(r"^[A-Z0-9][A-Z0-9-]{2,23}$", v):
        raise ValueError("Party codes are 3–24 characters: letters, digits and hyphens")
    return v


CurrencyCode = Annotated[str, AfterValidator(_currency_code)]
CountryCode = Annotated[str, AfterValidator(_country_code)]
PartyCode = Annotated[str, AfterValidator(_party_code)]


class AddressBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    label: str | None = Field(default=None, max_length=120)
    line1: str = Field(min_length=3, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    stateCode: str | None = Field(default=None, max_length=10)
    postalCode: str | None = Field(default=None, max_length=20)
    country: CountryCode = "IN"
    isDefault: bool = False

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        if v not in ("billing", "shipping", "registered"):
            raise ValueError("must be 'billing', 'shipping' or 'registered'")
        return v


class ContactBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    role: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    isPrimary: bool = False


class CreatePartyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: PartyCode | None = None
    legalName: str = Field(min_length=2, max_length=200)
    displayName: str | None = Field(default=None, min_length=2, max_length=200)
    type: str
    subtype: str | None = Field(default=None, max_length=60)
    taxId: str | None = Field(default=None, max_length=40)
    taxIdCountry: CountryCode | None = None
    registrationNo: str | None = Field(default=None, max_length=60)
    paymentTerms: str | None = Field(default=None, max_length=60)
    creditLimit: NonNegativeDecimal = "0"
    currency: CurrencyCode | None = None
    riskFlag: str = "low"
    industry: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    addresses: list[AddressBody] = Field(default_factory=list)
    contacts: list[ContactBody] = Field(default_factory=list)
    allowDuplicate: bool = False

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        if v not in ("vendor", "customer", "both"):
            raise ValueError("must be 'vendor', 'customer' or 'both'")
        return v

    @field_validator("riskFlag")
    @classmethod
    def _risk_ok(cls, v: str) -> str:
        if v not in ("low", "medium", "high"):
            raise ValueError("must be 'low', 'medium' or 'high'")
        return v


class PatchPartyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    legalName: str | None = Field(default=None, min_length=2, max_length=200)
    displayName: str | None = Field(default=None, min_length=2, max_length=200)
    type: str | None = None
    subtype: str | None = Field(default=None, max_length=60)
    taxId: str | None = Field(default=None, max_length=40)
    taxIdCountry: CountryCode | None = None
    registrationNo: str | None = Field(default=None, max_length=60)
    paymentTerms: str | None = Field(default=None, max_length=60)
    creditLimit: NonNegativeDecimal | None = None
    currency: CurrencyCode | None = None
    riskFlag: str | None = None
    industry: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v):
        if v is not None and v not in ("vendor", "customer", "both"):
            raise ValueError("must be 'vendor', 'customer' or 'both'")
        return v

    @field_validator("riskFlag")
    @classmethod
    def _risk_ok(cls, v):
        if v is not None and v not in ("low", "medium", "high"):
            raise ValueError("must be 'low', 'medium' or 'high'")
        return v


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)


class PartyBulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)


class BankAccountBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accountName: str = Field(min_length=2, max_length=140)
    accountNumber: str = Field(pattern=r"(?i)^[0-9A-Z]{6,34}$")
    ifsc: str | None = Field(default=None, pattern=r"^[A-Za-z]{4}0[A-Za-z0-9]{6}$")
    swift: str | None = Field(default=None, pattern=r"^[A-Za-z]{6}[A-Za-z0-9]{2}([A-Za-z0-9]{3})?$")
    bankName: str = Field(min_length=2, max_length=140)
    branch: str | None = Field(default=None, max_length=140)

    @model_validator(mode="after")
    def _routable(self):
        if self.ifsc:
            self.ifsc = self.ifsc.upper()
        if self.swift:
            self.swift = self.swift.upper()
        if not self.ifsc and not self.swift:
            raise ValueError("Provide an IFSC (domestic) or a SWIFT/BIC (international) — a payment cannot be routed without one")
        return self


class ApproveBankAccountBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


class RejectBankAccountBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)
