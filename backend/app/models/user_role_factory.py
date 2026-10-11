import uuid

from sqlalchemy import ForeignKey, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserRoleFactory(Base):
    """Restricts one (user, role) assignment's permissions to a single factory
    (and, by extension, every warehouse under it - see effective_access()).
    Sibling of UserRoleWarehouse."""

    __tablename__ = "user_role_factories"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "role_id"], ["user_roles.user_id", "user_roles.role_id"], ondelete="CASCADE"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    factory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factories.id", ondelete="CASCADE"), primary_key=True
    )
