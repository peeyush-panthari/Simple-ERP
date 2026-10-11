import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Fixed 7-stage assembly sequence for a battery-pack production run, in the
# order the pack actually moves through the floor. Seeded onto every run at
# creation (all unstarted) so the UI always has a full checklist to render -
# stage N can only be completed once stage N-1 is (see production route).
STAGE_KEYS = (
    "cell_testing",
    "module_assembly",
    "cell_assembly",
    "frp_cutting",
    "bms_sensing_cable_assembly",
    "enclosure_assembly",
    "qc_pdi",
)

STAGE_LABELS = {
    "cell_testing": "Cell Testing",
    "module_assembly": "Module Assembly",
    "cell_assembly": "Cell Assembly",
    "frp_cutting": "FRP Cutting",
    "bms_sensing_cable_assembly": "BMS & Sensing Cable Assembly",
    "enclosure_assembly": "Enclosure Assembly",
    "qc_pdi": "QC & PDI (Warranty Sticker / Branding Sticker / Screw Quality Checking)",
}


class ProductionRunStage(Base):
    __tablename__ = "production_run_stages"
    __table_args__ = (
        UniqueConstraint("production_run_id", "stage_key", name="production_run_stages_run_stage_uniq"),
        CheckConstraint("stage_key in " + str(STAGE_KEYS), name="production_run_stages_stage_key_check"),
        Index("production_run_stages_run_idx", "production_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    production_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_runs.id", ondelete="CASCADE"), nullable=False)
    stage_key: Mapped[str] = mapped_column(String, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    associate_name: Mapped[str | None] = mapped_column(String, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
