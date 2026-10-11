import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class SubcontractOrder(Base):
    """Subcontracting / Job-Work Order.
    Issued by Principal to a third-party Job Worker (Vendor) to perform
    manufacturing/processing services on materials supplied by Principal.
    """

    __tablename__ = "subcontract_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_no", name="subcontract_orders_tenant_order_no_uniq"),
        CheckConstraint(
            "status in ('draft','confirmed','dispatched','partially_received','completed','cancelled')",
            name="subcontract_orders_status_check",
        ),
        Index("subcontract_orders_tenant_status_idx", "tenant_id", "status"),
        Index("subcontract_orders_vendor_idx", "tenant_id", "vendor_party_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_no: Mapped[str] = mapped_column(String(32), nullable=False)
    vendor_party_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False
    )
    business_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_entities.id", ondelete="SET NULL"), nullable=True
    )
    source_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )

    # Finished / Semi-Finished good to produce
    fg_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    fg_sku: Mapped[str] = mapped_column(String(64), nullable=False)
    fg_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bom_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    target_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    service_rate: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    service_sac_code: Mapped[str] = mapped_column(String(16), nullable=False, default="9988")
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["SubcontractOrderLine"]] = relationship(
        "SubcontractOrderLine", back_populates="order", cascade="all, delete-orphan"
    )
    challans: Mapped[list["SubcontractChallan"]] = relationship(
        "SubcontractChallan", back_populates="order", cascade="all, delete-orphan"
    )
    receipts: Mapped[list["SubcontractReceipt"]] = relationship(
        "SubcontractReceipt", back_populates="order", cascade="all, delete-orphan"
    )


class SubcontractOrderLine(Base):
    """Raw material / component supplied by Principal for subcontracting."""

    __tablename__ = "subcontract_order_lines"
    __table_args__ = (
        Index("subcontract_order_lines_order_idx", "order_id"),
        Index("subcontract_order_lines_product_idx", "tenant_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subcontract_orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hsn_code: Mapped[str | None] = mapped_column(String(16), nullable=True)

    required_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    dispatched_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    consumed_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    scrap_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    uom: Mapped[str] = mapped_column(String(16), nullable=False, default="unit")
    estimated_unit_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["SubcontractOrder"] = relationship("SubcontractOrder", back_populates="lines")


class SubcontractChallan(Base):
    """Statutory Delivery Challan for Job-Work under CGST Rule 55 & Section 143.
    Accompanies goods sent from Principal to Job Worker.
    Tracks 1-year statutory return period for raw materials/inputs under Section 143(1)(a).
    """

    __tablename__ = "subcontract_challans"
    __table_args__ = (
        UniqueConstraint("tenant_id", "challan_no", name="subcontract_challans_tenant_no_uniq"),
        CheckConstraint(
            "status in ('draft','dispatched','delivered','reconciled')",
            name="subcontract_challans_status_check",
        ),
        Index("subcontract_challans_tenant_due_idx", "tenant_id", "statutory_due_date"),
        Index("subcontract_challans_order_idx", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subcontract_orders.id", ondelete="CASCADE"), nullable=False
    )
    challan_no: Mapped[str] = mapped_column(String(32), nullable=False)
    challan_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    statutory_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )

    # Principal (Consignor) Details
    consignor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    consignor_gstin: Mapped[str] = mapped_column(String(32), nullable=False)
    consignor_address: Mapped[str] = mapped_column(Text, nullable=False)
    consignor_state: Mapped[str] = mapped_column(String(64), nullable=False)
    consignor_state_code: Mapped[str] = mapped_column(String(8), nullable=False)

    # Job Worker (Consignee) Details
    consignee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    consignee_gstin: Mapped[str] = mapped_column(String(32), nullable=False, default="URP")
    consignee_address: Mapped[str] = mapped_column(Text, nullable=False)
    consignee_state: Mapped[str] = mapped_column(String(64), nullable=False)
    consignee_state_code: Mapped[str] = mapped_column(String(8), nullable=False)

    # Transport & Dispatch Details
    place_of_supply: Mapped[str] = mapped_column(String(64), nullable=False)
    transport_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="Road")
    vehicle_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transporter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    eway_bill_no: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Statutory & Process Declaration
    nature_of_processing: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Job-Work / Processing on inputs"
    )
    statutory_declaration: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=(
            "Goods dispatched for job-work under Section 143 of CGST Act, 2017 read with Rule 55 "
            "of CGST Rules, 2017. Returnable within 1 year from the date of dispatch. "
            "Not an outward taxable supply/sale."
        ),
    )

    # Financial Valuation
    total_taxable_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    total_cgst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    total_sgst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    total_igst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    total_challan_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="dispatched")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["SubcontractOrder"] = relationship("SubcontractOrder", back_populates="challans")
    items: Mapped[list["SubcontractChallanItem"]] = relationship(
        "SubcontractChallanItem", back_populates="challan", cascade="all, delete-orphan"
    )


class SubcontractChallanItem(Base):
    """Delivery Challan line item as per Rule 55 statutory particulars."""

    __tablename__ = "subcontract_challan_items"
    __table_args__ = (
        Index("subcontract_challan_items_challan_idx", "challan_id"),
        Index("subcontract_challan_items_product_idx", "tenant_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    challan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subcontract_challans.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    hsn_code: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    uom: Mapped[str] = mapped_column(String(16), nullable=False, default="unit")

    taxable_rate: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    gst_rate_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=18.0)
    cgst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=9.0)
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    sgst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=9.0)
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    igst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)

    challan: Mapped["SubcontractChallan"] = relationship("SubcontractChallan", back_populates="items")


class SubcontractReceipt(Base):
    """Goods Receipt from Job-Worker with scrap and consumption reconciliation."""

    __tablename__ = "subcontract_receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "receipt_no", name="subcontract_receipts_tenant_no_uniq"),
        CheckConstraint("qc_status in ('pending','approved','rejected')", name="subcontract_receipts_qc_check"),
        Index("subcontract_receipts_order_idx", "order_id"),
        Index("subcontract_receipts_tenant_idx", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subcontract_orders.id", ondelete="CASCADE"), nullable=False
    )
    receipt_no: Mapped[str] = mapped_column(String(32), nullable=False)
    receipt_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )

    # Finished Goods Output
    received_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    accepted_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    rejected_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)

    # Material Consumption & Scrap Audit
    consumed_raw_material_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    actual_scrap_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    allowable_scrap_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    scrap_variance_qty: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    scrap_variance_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=0)

    # Commercial & Invoicing
    vendor_challan_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vendor_invoice_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    service_charges: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)

    qc_status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["SubcontractOrder"] = relationship("SubcontractOrder", back_populates="receipts")
