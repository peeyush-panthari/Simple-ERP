import uuid

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DocSequence(Base):
    """Gapless per-tenant document numbering (PTY-0100, and future PO/GRN/invoice
    numbers). Reusable platform table - ported from packages/shared's doc_sequences."""

    __tablename__ = "doc_sequences"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    prefix: Mapped[str] = mapped_column(String, primary_key=True)
    current_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
