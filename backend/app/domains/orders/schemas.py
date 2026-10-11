"""Request bodies, ported from backend_py/app/routes/orders.py. Schemas for
the deferred endpoints (invoice/manual-logistics/fulfill - see router.py's
module docstring) are left out until those land."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class DeliveryAddressBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line1: str = Field(min_length=3, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    stateCode: str | None = Field(default=None, max_length=10)
    postalCode: str | None = Field(default=None, max_length=20)
    country: str = "IN"


LogisticsCostBorneBy = Literal["Simple", "Client", "Equally shared"]


class OrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customerId: uuid_mod.UUID
    customerRef: str | None = Field(default=None, max_length=60)
    orderDate: date | None = None
    promisedDate: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    charges: DecimalString = "0"
    paymentTerms: str | None = Field(default=None, max_length=60)
    deliveryAddress: DeliveryAddressBody | None = None
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[LineBody] = Field(min_length=1)
    expectedTotal: DecimalString | None = None
    allowCreditOverride: bool = False
    inverterDetails: str | None = Field(default=None, max_length=2000)
    inverterDetailsFilename: str | None = Field(default=None, max_length=200)
    inverterDetailsContentType: str | None = Field(default=None, max_length=120)
    inverterDetailsContentBase64: str | None = None
    accessoriesRequired: str | None = Field(default=None, max_length=2000)
    branding: str | None = Field(default=None, max_length=500)
    logisticsCostBorneBy: LogisticsCostBorneBy | None = None


class PatchOrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customerId: uuid_mod.UUID | None = None
    customerRef: str | None = Field(default=None, max_length=60)
    promisedDate: date | None = None
    charges: DecimalString | None = None
    paymentTerms: str | None = Field(default=None, max_length=60)
    # Accepted for request-shape parity with the create body but silently
    # ignored - matches the original PATCH handler exactly (see router.py).
    deliveryAddress: DeliveryAddressBody | None = None
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[LineBody] | None = None
    expectedTotal: DecimalString | None = None
    inverterDetails: str | None = Field(default=None, max_length=2000)
    inverterDetailsFilename: str | None = Field(default=None, max_length=200)
    inverterDetailsContentType: str | None = Field(default=None, max_length=120)
    inverterDetailsContentBase64: str | None = None
    accessoriesRequired: str | None = Field(default=None, max_length=2000)
    branding: str | None = Field(default=None, max_length=500)
    logisticsCostBorneBy: LogisticsCostBorneBy | None = None


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)


class ConfirmBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowCreditOverride: bool = False


class BulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)


class AllocateOrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warehouseId: uuid_mod.UUID


class AllocateItemPick(BaseModel):
    model_config = ConfigDict(extra="forbid")
    itemId: uuid_mod.UUID
    quantity: DecimalString


class AllocateItemsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    orderLineId: uuid_mod.UUID
    items: list[AllocateItemPick] = Field(min_length=1)


class PackLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: DecimalString


class ShipLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: DecimalString


class ManualLogisticsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=10, max_length=500)


class FulfillBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    partial: bool = False


class InvoiceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: list[str] | None = Field(default=None, max_length=10)
    dueDate: date | None = None
    businessEntityId: uuid_mod.UUID | None = None
