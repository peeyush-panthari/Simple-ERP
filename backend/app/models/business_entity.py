import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BusinessEntity(Base):
    """One of Simple's own legal entities - the seller/buyer identity (name,
    address, tax ID) stamped onto a purchase order or invoice, as opposed to
    Party which holds the *other* side's (vendor/customer) identity. Multiple
    rows let different business verticals raise POs/invoices under their own
    registration."""

    __tablename__ = "business_entities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="business_entities_tenant_code_uniq"),
        CheckConstraint("status in ('active','inactive')", name="business_entities_status_check"),
        CheckConstraint("tax_id is null or tax_id_country is not null", name="business_entities_tax_country_ck"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    address_line1: Mapped[str | None] = mapped_column(String, nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state_code: Mapped[str | None] = mapped_column(String, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str] = mapped_column(String, nullable=False, default="IN")
    tax_id: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_id_country: Mapped[str | None] = mapped_column(String, nullable=True)
    pan: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String, nullable=True)
    bank_branch: Mapped[str | None] = mapped_column(String, nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String, nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
