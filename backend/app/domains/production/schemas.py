"""Request bodies, ported from backend_py/app/routes/inventory_movements.py's
production section (lines 1355-2660 of that file)."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.money import is_positive
from app.core.scalars import DecimalString, UomCode


class ConsumedItemBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    itemId: uuid_mod.UUID
    productId: uuid_mod.UUID
    quantity: DecimalString

    @field_validator("quantity")
    @classmethod
    def _positive(cls, v):
        if not is_positive(v):
            raise ValueError("Must be greater than zero")
        return v


class AdditionalComponentBody(BaseModel):
    """A raw material consumed for a production run beyond what its BOM calls
    for - e.g. rework, spillage, or an operator's real-world substitution."""

    model_config = ConfigDict(extra="forbid")
    productId: uuid_mod.UUID
    quantity: DecimalString
    uom: UomCode
    items: list[ConsumedItemBody] | None = None

    @field_validator("quantity")
    @classmethod
    def _positive(cls, v):
        if not is_positive(v):
            raise ValueError("Must be greater than zero")
        return v


class ProductionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    productId: uuid_mod.UUID
    quantity: DecimalString
    uom: UomCode
    warehouseId: uuid_mod.UUID
    locationId: uuid_mod.UUID | None = None
    batchNo: str | None = Field(default=None, max_length=60)
    expiryDate: date | None = None
    asOf: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    consumedItems: list[ConsumedItemBody] | None = None
    additionalComponents: list[AdditionalComponentBody] | None = None

    # ---- battery-pack traceability (all optional - only meaningful for a
    # finished-good pack SKU, but the run is generic across product types) ----
    productionDate: date | None = None
    packId: str | None = Field(default=None, max_length=80)
    shift: str | None = Field(default=None, max_length=40)
    bmsMakeModel: str | None = Field(default=None, max_length=120)
    screenType: str | None = Field(default=None, max_length=120)
    bmsId: str | None = Field(default=None, max_length=120)
    bluetoothId: str | None = Field(default=None, max_length=120)
    iotId: str | None = Field(default=None, max_length=120)
    cellsName: str | None = Field(default=None, max_length=120)
    cellsQuantity: int | None = Field(default=None, ge=0)
    seriesCount: int | None = Field(default=None, ge=0)
    parallelCount: int | None = Field(default=None, ge=0)
    enclosureName: str | None = Field(default=None, max_length=120)
    chargeCapacity: str | None = Field(default=None, max_length=40)
    dischargeCapacity: str | None = Field(default=None, max_length=40)
    brandingDetails: str | None = Field(default=None, max_length=1000)
    testReportFilename: str | None = Field(default=None, max_length=200)
    testReportContentType: str | None = Field(default=None, max_length=120)
    testReportContentBase64: str | None = None

    # ---- production team: who completed which assembly stage, filled in
    # up front instead of one at a time via the detail view's stage
    # checklist. Deliberately excludes 'cell_testing' (STAGE_KEYS' first
    # stage) - that one has no field on the create form and can only be
    # completed later, through the detail view. See _seed_stages(). ----
    moduleAssemblyBy: str | None = Field(default=None, max_length=120)
    cellAssemblyBy: str | None = Field(default=None, max_length=120)
    frpCuttingBy: str | None = Field(default=None, max_length=120)
    bmsSensingCableAssemblyBy: str | None = Field(default=None, max_length=120)
    enclosureAssemblyBy: str | None = Field(default=None, max_length=120)
    qcPdiBy: str | None = Field(default=None, max_length=120)

    @field_validator("quantity")
    @classmethod
    def _positive(cls, v):
        if not is_positive(v):
            raise ValueError("Must be greater than zero")
        return v


class ProductionPlanItemBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    productId: uuid_mod.UUID
    packId: str | None = Field(default=None, max_length=80)


class ProductionPlanBody(BaseModel):
    """Daily Production Planning: bulk-create bare 'planned' ProductionRun
    rows for a warehouse/date - just enough to reserve a Production ID and a
    pack ID per finished good. Everything else (batch, BOM pick, stage
    associates, pack details) is blank until Complete Production
    (ProductionCompleteBody below) fills it in and flips status to
    'posted'."""

    model_config = ConfigDict(extra="forbid")
    productionDate: date
    warehouseId: uuid_mod.UUID
    items: list[ProductionPlanItemBody] = Field(min_length=1)


class ProductionCompleteBody(BaseModel):
    """Completing a 'planned' run - the same shape as ProductionBody minus
    productId/warehouseId/packId/quantity/uom, which are fixed at planning
    time and never change here (see complete_production, which reads them
    off the existing ProductionRun row instead of the request)."""

    model_config = ConfigDict(extra="forbid")
    locationId: uuid_mod.UUID | None = None
    batchNo: str | None = Field(default=None, max_length=60)
    expiryDate: date | None = None
    asOf: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    consumedItems: list[ConsumedItemBody] | None = None
    additionalComponents: list[AdditionalComponentBody] | None = None

    productionDate: date | None = None
    shift: str | None = Field(default=None, max_length=40)
    bmsMakeModel: str | None = Field(default=None, max_length=120)
    screenType: str | None = Field(default=None, max_length=120)
    bmsId: str | None = Field(default=None, max_length=120)
    bluetoothId: str | None = Field(default=None, max_length=120)
    iotId: str | None = Field(default=None, max_length=120)
    cellsName: str | None = Field(default=None, max_length=120)
    cellsQuantity: int | None = Field(default=None, ge=0)
    seriesCount: int | None = Field(default=None, ge=0)
    parallelCount: int | None = Field(default=None, ge=0)
    enclosureName: str | None = Field(default=None, max_length=120)
    chargeCapacity: str | None = Field(default=None, max_length=40)
    dischargeCapacity: str | None = Field(default=None, max_length=40)
    brandingDetails: str | None = Field(default=None, max_length=1000)
    testReportFilename: str | None = Field(default=None, max_length=200)
    testReportContentType: str | None = Field(default=None, max_length=120)
    testReportContentBase64: str | None = None

    moduleAssemblyBy: str | None = Field(default=None, max_length=120)
    cellAssemblyBy: str | None = Field(default=None, max_length=120)
    frpCuttingBy: str | None = Field(default=None, max_length=120)
    bmsSensingCableAssemblyBy: str | None = Field(default=None, max_length=120)
    enclosureAssemblyBy: str | None = Field(default=None, max_length=120)
    qcPdiBy: str | None = Field(default=None, max_length=120)


class UpdateProductionBody(BaseModel):
    """Editing a posted run - deliberately a much narrower body than
    ProductionBody. Everything that already posted stock-ledger entries or
    ProductionConsumption rows at creation time (productId, quantity, uom,
    warehouseId, locationId, batchNo, expiryDate, consumedItems,
    additionalComponents) is absent on purpose: extra="forbid" means the
    client can't send them even by mistake. Only the descriptive
    battery-pack traceability block plus notes can change after posting -
    "who completed which stage" already has its own edit path via the
    stage-complete endpoint."""

    model_config = ConfigDict(extra="forbid")
    notes: str | None = Field(default=None, max_length=1000)
    productionDate: date | None = None
    packId: str | None = Field(default=None, max_length=80)
    shift: str | None = Field(default=None, max_length=40)
    bmsMakeModel: str | None = Field(default=None, max_length=120)
    screenType: str | None = Field(default=None, max_length=120)
    bmsId: str | None = Field(default=None, max_length=120)
    bluetoothId: str | None = Field(default=None, max_length=120)
    iotId: str | None = Field(default=None, max_length=120)
    cellsName: str | None = Field(default=None, max_length=120)
    cellsQuantity: int | None = Field(default=None, ge=0)
    seriesCount: int | None = Field(default=None, ge=0)
    parallelCount: int | None = Field(default=None, ge=0)
    enclosureName: str | None = Field(default=None, max_length=120)
    chargeCapacity: str | None = Field(default=None, max_length=40)
    dischargeCapacity: str | None = Field(default=None, max_length=40)
    brandingDetails: str | None = Field(default=None, max_length=1000)
    testReportFilename: str | None = Field(default=None, max_length=200)
    testReportContentType: str | None = Field(default=None, max_length=120)
    testReportContentBase64: str | None = None


class StageCompleteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    associateName: str = Field(min_length=1, max_length=120)


class ProductionBulkUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csvContent: str = Field(min_length=1)


class FinishedGoodTransferBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    toWarehouseId: uuid_mod.UUID
    toLocationId: uuid_mod.UUID | None = None
    reason: str | None = Field(default=None, max_length=500)


class FinishedGoodStatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    toStatus: str
    reason: str | None = Field(default=None, max_length=500)
