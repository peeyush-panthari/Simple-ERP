from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PublicRequestThrottle(Base):
    """Fixed-hour-bucket rate limiter, shared by every unauthenticated public
    intake route in this monolith - keyed on (scope, identity, hour_bucket),
    upserted with count+1. Generalized from an (ip, hour_bucket)-only shape
    to also support "key"-scoped identities (an intake API key's own rate
    limit), matching Node's own real schema evolution in the ticket service
    (see plan) - logistics_public.py's one call site now passes scope="ip"."""

    __tablename__ = "public_request_throttle"
    __table_args__ = (
        PrimaryKeyConstraint("scope", "identity", "hour_bucket"),
        CheckConstraint("scope in ('ip','key')", name="public_request_throttle_scope_check"),
    )

    scope: Mapped[str] = mapped_column(String, nullable=False)
    identity: Mapped[str] = mapped_column(String, nullable=False)
    hour_bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
