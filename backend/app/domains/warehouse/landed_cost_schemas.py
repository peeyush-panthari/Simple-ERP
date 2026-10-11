from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class LandedCostChargeIn(BaseModel):
    charge_type: str = Field(default="freight")
    description: str | None = None
    vendor_id: uuid.UUID | None = None
    vendor_name: str | None = None
    invoice_ref: str | None = None
    amount: Decimal = Field(gt=0)
    apportion_by: str = Field(default="value")


class LandedCostReceiptIn(BaseModel):
    grn_id: uuid.UUID
    grn_number: str
    receipt_date: date
    vendor_name: str | None = None
    grand_total: Decimal = Decimal(0)


class LandedCostItemIn(BaseModel):
    grn_id: uuid.UUID
    grn_number: str
    grn_line_id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    product_name: str | None = None
    quantity: Decimal = Field(gt=0)
    uom: str = "PCS"
    weight_kg: Decimal = Decimal("1.0")
    volume_cbm: Decimal = Decimal("0.01")
    base_unit_price: Decimal = Decimal("0")
    base_total_amount: Decimal = Decimal("0")


class LandedCostCalculateRequest(BaseModel):
    items: list[LandedCostItemIn]
    charges: list[LandedCostChargeIn]


class LandedCostVoucherCreateRequest(BaseModel):
    posting_date: date = Field(default_factory=date.today)
    currency: str = "INR"
    notes: str | None = None
    receipts: list[LandedCostReceiptIn]
    charges: list[LandedCostChargeIn]
    items: list[LandedCostItemIn]


class LandedCostChargeOut(BaseModel):
    id: uuid.UUID
    charge_type: str
    description: str | None
    vendor_id: uuid.UUID | None
    vendor_name: str | None
    invoice_ref: str | None
    amount: float
    apportion_by: str


class LandedCostReceiptOut(BaseModel):
    id: uuid.UUID
    grn_id: uuid.UUID
    grn_number: str
    receipt_date: date
    vendor_name: str | None
    grand_total: float


class LandedCostItemOut(BaseModel):
    id: uuid.UUID
    grn_id: uuid.UUID
    grn_number: str
    grn_line_id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    product_name: str | None
    quantity: float
    uom: str
    weight_kg: float
    volume_cbm: float
    base_unit_price: float
    base_total_amount: float
    allocated_charges: float
    final_unit_cost: float
    cost_variance_pct: float


class GlEntryOut(BaseModel):
    account_code: str
    account_name: str
    debit: float
    credit: float
    vendor: str
    ref: str


class LandedCostVoucherOut(BaseModel):
    id: uuid.UUID
    voucher_no: str
    posting_date: date
    status: str
    currency: str
    total_charges: float
    notes: str | None
    created_by: str | None
    posted_by: str | None
    posted_at: datetime | None
    created_at: datetime
    receipts: list[LandedCostReceiptOut] = []
    charges: list[LandedCostChargeOut] = []
    items: list[LandedCostItemOut] = []
    gl_entries: list[GlEntryOut] = []
