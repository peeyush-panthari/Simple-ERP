import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="orders_tenant_number_uniq"),
        # No 'draft' - an order is confirmed the moment it's created (see
        # routes/orders.py::_create_order). 'confirmed' is therefore the
        # initial state, not something reached only via a transition.
        CheckConstraint(
            "status in ('confirmed','allocated','partially_allocated','shipped','partially_shipped','invoiced','fulfilled','partially_fulfilled','cancelled')",
            name="orders_status_check",
        ),
        CheckConstraint(
            "logistics_state in ('not_raised','blocked','auto_raised','manually_raised','dispatched','delivered')",
            name="orders_logistics_state_check",
        ),
        CheckConstraint("exchange_rate > 0", name="orders_exchange_rate_check"),
        CheckConstraint("promised_date >= order_date", name="orders_dates_ck"),
        CheckConstraint(
            "logistics_cost_borne_by is null or logistics_cost_borne_by in ('Simple','Client','Equally shared')",
            name="orders_logistics_cost_borne_by_check",
        ),
        # Independent of `status` - a physical warehouse-floor tracking flag
        # (Production > Order Shipping), not a step in the order's own
        # confirm/allocate/ship/invoice lifecycle. ship_order asserts this is
        # 'packed' before it will move status to shipped/partially_shipped.
        CheckConstraint("packing_status in ('pending_packing','packed')", name="orders_packing_status_check"),
        Index("orders_tenant_status_idx", "tenant_id", "status", "order_date"),
        Index("orders_tenant_customer_idx", "tenant_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    customer_name: Mapped[str] = mapped_column(String, nullable=False)
    customer_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="confirmed")
    packing_status: Mapped[str] = mapped_column(String, nullable=False, default="pending_packing")
    order_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    promised_date: Mapped[date] = mapped_column(Date, nullable=False)
    # No longer assigned at order creation - "which warehouse" is only ever
    # known per-allocation now (see Reservation.warehouse_id, set from the
    # actual FinishedGoodItem/InventoryItem picked - routes/orders.py's
    # allocate-items). Nullable so new orders carry no warehouse at all;
    # historical orders created before this change keep whatever value they
    # already have.
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True)
    warehouse_code: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=1)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    charges: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    fully_paid: Mapped[bool] = mapped_column(nullable=False, default=False)
    payment_terms: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_line1: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_line2: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_city: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_state_code: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_postal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    delivery_country: Mapped[str] = mapped_column(String, nullable=False, default="IN")
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    # ---- customer-facing order intake fields (free text; inverter_details also
    # carries an optional attachment, stored as a Document with related_type
    # "order" - see order.py's _order_attachment()) ----
    inverter_details: Mapped[str | None] = mapped_column(String, nullable=True)
    accessories_required: Mapped[str | None] = mapped_column(String, nullable=True)
    branding: Mapped[str | None] = mapped_column(String, nullable=True)
    logistics_cost_borne_by: Mapped[str | None] = mapped_column(String, nullable=True)
    logistics_state: Mapped[str] = mapped_column(String, nullable=False, default="not_raised")
    # Bare uuid, no FK - matches Node exactly (transport_requests also references
    # orders.id, and FK-ing both directions would create a circular table
    # dependency between orders and transport_requests for no real benefit).
    logistics_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    logistics_override_by: Mapped[str | None] = mapped_column(String, nullable=True)
    logistics_override_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    logistics_raised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Bare uuid, no FK - same reasoning: invoices.order_id is the real FK in the
    # other direction; FK-ing this one too would create an orders<->invoices cycle.
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String, nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
