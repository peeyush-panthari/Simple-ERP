import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Party(Base):
    __tablename__ = "parties"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="parties_tenant_code_uniq"),
        CheckConstraint("type in ('vendor','customer','both')", name="parties_type_check"),
        CheckConstraint("status in ('draft','active','blocked','inactive')", name="parties_status_check"),
        CheckConstraint("risk_flag in ('low','medium','high')", name="parties_risk_flag_check"),
        CheckConstraint("credit_limit >= 0", name="parties_credit_limit_check"),
        CheckConstraint("credit_used >= 0", name="parties_credit_used_check"),
        CheckConstraint("tax_id is null or tax_id_country is not null", name="parties_tax_country_ck"),
        Index("parties_tenant_status_idx", "tenant_id", "status", "type"),
        # Tax ID unique per (tenant, country) where applicable - functional/partial
        # index skipped here (kept enforced at the application layer in
        # party_repo.find_tax_id_owner instead); everything else is ported.
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    legal_name: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    subtype: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    tax_id: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_id_country: Mapped[str | None] = mapped_column(String, nullable=True)
    registration_no: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String, nullable=True)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    credit_used: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_flag: Mapped[str] = mapped_column(String, nullable=False, default="low")
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
