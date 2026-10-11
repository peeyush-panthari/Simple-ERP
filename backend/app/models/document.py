import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Document(Base):
    """Immutable once created - reprint creates a new row rather than
    overwriting (no updated_at column, matching Node). scan_status's
    'clean'/'infected'/'failed' states are dead - the malware-scan lifecycle
    is entirely unimplemented in Node too, uploads land on 'pending' (only
    if a scanner URL is configured) or 'not_required' and never advance."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "storage_key", name="documents_storage_key_uniq"),
        CheckConstraint("kind in ('generated','uploaded')", name="documents_kind_check"),
        CheckConstraint("storage_backend in ('s3','local')", name="documents_storage_backend_check"),
        CheckConstraint("scan_status in ('not_required','pending','clean','infected','failed')", name="documents_scan_status_check"),
        Index("documents_related_idx", "tenant_id", "related_type", "related_id", "created_at"),
        Index("documents_template_idx", "tenant_id", "template", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False, default="generated")
    template: Mapped[str | None] = mapped_column(String, nullable=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False, default="application/pdf")
    bytes_: Mapped[int] = mapped_column("bytes", Integer, nullable=False, default=0)
    checksum: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_backend: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    related_type: Mapped[str | None] = mapped_column(String, nullable=True)
    related_id: Mapped[str | None] = mapped_column(String, nullable=True)
    render_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scan_status: Mapped[str] = mapped_column(String, nullable=False, default="not_required")
    scan_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
