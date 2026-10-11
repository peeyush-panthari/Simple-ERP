"""Add email_configs (Foundation > Email Config: one outgoing mailbox per kind of email).

Revision ID: c1d2e3f4a5b6
Revises: ca16c059827a
Create Date: 2026-09-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c1d2e3f4a5b6"
down_revision = "ca16c059827a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose_key", sa.String(), nullable=False),
        sa.Column("send_enabled", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("smtp_host", sa.String(), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False),
        sa.Column("security", sa.String(), nullable=False),
        sa.Column("smtp_user", sa.String(), nullable=False),
        sa.Column("smtp_password_sealed", sa.Text(), nullable=True),
        sa.Column("from_name", sa.String(), nullable=False),
        sa.Column("from_email", sa.String(), nullable=False),
        sa.Column("reply_to", sa.String(), nullable=True),
        sa.Column("cc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bcc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("security in ('none','starttls','ssl')", name="email_configs_security_check"),
        sa.CheckConstraint("smtp_port between 1 and 65535", name="email_configs_port_check"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "purpose_key", name="email_configs_tenant_purpose_uniq"),
    )


def downgrade():
    op.drop_table("email_configs")
