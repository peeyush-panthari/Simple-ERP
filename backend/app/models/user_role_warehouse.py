import uuid

from sqlalchemy import ForeignKey, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserRoleWarehouse(Base):
    """Restricts one (user, role) assignment's permissions to a single warehouse.
    An assignment with no rows here and no UserRoleFactory rows is unrestricted -
    see app/services/repo.py effective_access()."""

    __tablename__ = "user_role_warehouses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "role_id"], ["user_roles.user_id", "user_roles.role_id"], ondelete="CASCADE"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), primary_key=True
    )
