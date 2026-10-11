import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TransportRequest(Base):
    __tablename__ = "transport_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="transport_requests_tenant_number_uniq"),
        CheckConstraint("source in ('order','manual','external')", name="transport_requests_source_check"),
        CheckConstraint(
            "status in ('pending','rfq_sent','quotation_received','approved','dispatched','delivered','cancelled')",
            name="transport_requests_status_check",
        ),
        CheckConstraint("service_level in ('economy','standard','express','same_day')", name="transport_requests_service_level_check"),
        Index("transport_requests_tenant_status_idx", "tenant_id", "status", "created_at"),
        Index("transport_requests_tenant_order_idx", "tenant_id", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="order")
    # SET NULL (nullable) - see Order.logistics_request_id for why this stays a
    # real FK in only one direction (avoids an orders<->transport_requests cycle).
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    order_number: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="SET NULL"), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    source_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    source_warehouse_code: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_line1: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_city: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_state_code: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_postal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_country: Mapped[str] = mapped_column(String, nullable=False, default="IN")
    dest_line1: Mapped[str] = mapped_column(String, nullable=False)
    dest_city: Mapped[str] = mapped_column(String, nullable=False)
    dest_state_code: Mapped[str | None] = mapped_column(String, nullable=True)
    dest_postal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    dest_country: Mapped[str] = mapped_column(String, nullable=False, default="IN")
    goods: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    package_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_level: Mapped[str] = mapped_column(String, nullable=False, default="standard")
    insurance_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    insured_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    special_instructions: Mapped[str | None] = mapped_column(String, nullable=True)
    trigger: Mapped[str | None] = mapped_column(String, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    raised_by: Mapped[str | None] = mapped_column(String, nullable=True)
    requester_email: Mapped[str | None] = mapped_column(String, nullable=True)
    requester_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(String, nullable=True)  # dead column - no cancel route, matches Node
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
