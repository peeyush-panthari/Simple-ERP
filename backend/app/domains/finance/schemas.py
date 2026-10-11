"""Request bodies, ported from backend_py/app/routes/finance.py."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.core.scalars import DecimalString


class ApInvoiceLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    poLineId: uuid_mod.UUID | None = None
    sku: str | None = Field(default=None, max_length=64)
    description: str = Field(min_length=1, max_length=500)
    quantity: DecimalString | None = None
    uom: str | None = None
    unitPrice: DecimalString | None = None
    amount: DecimalString
    taxCode: str | None = Field(default=None, max_length=20)
    taxAmount: DecimalString = "0"


class ApInvoiceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vendorId: uuid_mod.UUID
    vendorName: str | None = Field(default=None, max_length=200)
    vendorInvoiceNo: str = Field(min_length=1, max_length=60)
    poId: uuid_mod.UUID | None = None
    grnId: uuid_mod.UUID | None = None
    invoiceDate: date | None = None
    dueDate: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    amount: DecimalString
    taxAmount: DecimalString = "0"
    lines: list[ApInvoiceLineBody] = Field(default_factory=list)
    varianceReason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class CreditNoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    direction: str = "outbound"
    arInvoiceId: uuid_mod.UUID | None = None
    apInvoiceId: uuid_mod.UUID | None = None
    partyId: uuid_mod.UUID
    partyName: str | None = Field(default=None, max_length=200)
    amount: DecimalString
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    reason: str = Field(min_length=5, max_length=500)


class AllocationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoiceId: uuid_mod.UUID
    amount: DecimalString


class PaymentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    partyId: uuid_mod.UUID
    partyName: str | None = Field(default=None, max_length=200)
    amount: DecimalString
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    exchangeRate: DecimalString = "1"
    paymentDate: date | None = None
    method: str = "bank_transfer"
    reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    allocations: list[AllocationBody] = Field(min_length=1)


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)
