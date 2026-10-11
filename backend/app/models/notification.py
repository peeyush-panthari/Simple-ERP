import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Notification(Base):
    """`status` allows 'suppressed' in its CHECK but no code path ever sets
    it - a fully-suppressed send is rejected with 409 before a row is even
    inserted, matching Node's dead status value exactly. attempts/
    next_attempt_at exist for schema fidelity and manual retry - there is
    no automatic background poller in this port (see plan)."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("channel in ('email','sms','push')", name="notifications_channel_check"),
        CheckConstraint("status in ('queued','sending','sent','failed','bounced','suppressed')", name="notifications_status_check"),
        Index("notifications_pending_idx", "next_attempt_at"),
        Index("notifications_related_idx", "tenant_id", "related_type", "related_id"),
        Index("notifications_status_idx", "tenant_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    template_key: Mapped[str] = mapped_column(String, nullable=False)
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channel: Mapped[str] = mapped_column(String, nullable=False, default="email")
    recipients: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    cc: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    bcc: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    body_text: Mapped[str] = mapped_column(String, nullable=False)
    body_html: Mapped[str | None] = mapped_column(String, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    attachments: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    related_type: Mapped[str | None] = mapped_column(String, nullable=True)
    related_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
