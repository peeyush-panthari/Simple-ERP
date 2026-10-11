"""Add mfa_recovery_codes table

Revision ID: b7c8d9e0f1a2
Revises: e8f7a6b5c4d3
Create Date: 2026-10-11
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "b7c8d9e0f1a2"
down_revision = "e8f7a6b5c4d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("mfa_rec_user_idx", "mfa_recovery_codes", ["user_id"])
    op.create_index("mfa_rec_code_hash_idx", "mfa_recovery_codes", ["code_hash"])


def downgrade() -> None:
    op.drop_table("mfa_recovery_codes")
