import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="invoices_tenant_number_uniq"),
        CheckConstraint("status in ('issued','cancelled')", name="invoices_status_check"),
        CheckConstraint("email_state in ('not_sent','queued','sent','failed')", name="invoices_email_state_check"),
        Index("invoices_tenant_customer_idx", "tenant_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    customer_name: Mapped[str] = mapped_column(String, nullable=False)
    business_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("business_entities.id", ondelete="SET NULL"), nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    charges: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    cgst: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    sgst: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    igst: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    place_of_supply: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="issued")
    document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    email_state: Mapped[str] = mapped_column(String, nullable=False, default="not_sent")
    email_error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
