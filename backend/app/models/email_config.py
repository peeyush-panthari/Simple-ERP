import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EmailConfig(Base):
    """One outgoing-email setup for ONE kind of email - Foundation > Email Config. `purpose_key` is the notification
    template key (purchase-order.issued, invoice.issued, logistics.rfq, ...), so purchase orders, customer invoices and
    logistics quotation requests can each leave from a different mailbox. A row that is absent, or has `enabled` false
    (own mailbox switched off), sends through the deployment's SMTP_* environment settings. `send_enabled` false stops
    that kind of email altogether. The SMTP password is stored sealed (services/secret_box.py), never returned."""

    __tablename__ = "email_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "purpose_key", name="email_configs_tenant_purpose_uniq"),
        CheckConstraint("security in ('none','starttls','ssl')", name="email_configs_security_check"),
        CheckConstraint("smtp_port between 1 and 65535", name="email_configs_port_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    purpose_key: Mapped[str] = mapped_column(String, nullable=False)
    send_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_host: Mapped[str] = mapped_column(String, nullable=False, default="")
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    security: Mapped[str] = mapped_column(String, nullable=False, default="starttls")
    smtp_user: Mapped[str] = mapped_column(String, nullable=False, default="")
    smtp_password_sealed: Mapped[str | None] = mapped_column(Text)
    from_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    from_email: Mapped[str] = mapped_column(String, nullable=False, default="")
    reply_to: Mapped[str | None] = mapped_column(String)
    cc: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    bcc: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_test_error: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
