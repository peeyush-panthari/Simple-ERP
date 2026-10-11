import uuid

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuthPolicy(Base):
    __tablename__ = "auth_policies"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    password_min_length: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    password_require_symbol: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    password_require_number: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    password_require_mixed_case: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    password_max_age_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    password_history: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    mfa_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    lockout_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    session_idle_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    inactive_user_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
