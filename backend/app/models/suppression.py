import uuid
from datetime import datetime

from sqlalchemy import DateTime, PrimaryKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Suppression(Base):
    __tablename__ = "suppressions"
    __table_args__ = (PrimaryKeyConstraint("tenant_id", "address"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    suppressed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
