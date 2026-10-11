import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Dispatch(Base):
    __tablename__ = "dispatches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="dispatches_tenant_number_uniq"),
        # in_transit/failed are schema-valid but unreachable from any current
        # route (only dispatched->delivered via POD is reachable) - matches Node.
        CheckConstraint("status in ('dispatched','in_transit','delivered','failed')", name="dispatches_status_check"),
        CheckConstraint("warehouse_notify_state in ('not_sent','sent','failed')", name="dispatches_warehouse_notify_state_check"),
        Index("dispatches_transport_request_idx", "transport_request_id"),
        Index("dispatches_tenant_status_idx", "tenant_id", "status", "dispatched_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    transport_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("transport_requests.id", ondelete="RESTRICT"), nullable=False)
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quotations.id", ondelete="RESTRICT"), nullable=True)
    carrier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False)
    carrier_name: Mapped[str] = mapped_column(String, nullable=False)
    awb_number: Mapped[str | None] = mapped_column(String, nullable=True)
    vehicle_number: Mapped[str | None] = mapped_column(String, nullable=True)
    driver_name: Mapped[str | None] = mapped_column(String, nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="dispatched")
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    eta: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pod_document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pod_url: Mapped[str | None] = mapped_column(String, nullable=True)
    pod_received_by: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)  # dead column - unreachable, matches Node
    warehouse_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warehouse_notify_state: Mapped[str] = mapped_column(String, nullable=False, default="not_sent")
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
