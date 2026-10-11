"""Remove Zitadel columns and external identity index

Revision ID: b1c2d3e4f5a6
Revises: f3a4b5c6d7e8
Create Date: 2026-10-11
"""
import sqlalchemy as sa
from alembic import op

revision = "a9b8c7d6e5f4"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop external identity index on users
    op.drop_index("users_external_identity_key", table_name="users")

    # 2. Drop external identity columns from users
    op.drop_column("users", "external_idp")
    op.drop_column("users", "external_subject")

    # 3. Drop zitadel_org_id constraint and column from tenants
    op.drop_constraint("tenants_zitadel_org_id_key", "tenants", type_="unique")
    op.drop_column("tenants", "zitadel_org_id")


def downgrade() -> None:
    op.add_column("tenants", sa.Column("zitadel_org_id", sa.String(), nullable=True))
    op.create_unique_constraint("tenants_zitadel_org_id_key", "tenants", ["zitadel_org_id"])
    op.add_column("users", sa.Column("external_subject", sa.String(), nullable=True))
    op.add_column("users", sa.Column("external_idp", sa.String(), nullable=True))
    op.create_index(
        "users_external_identity_key",
        "users",
        ["tenant_id", "external_idp", "external_subject"],
        unique=True,
        postgresql_where=sa.text("external_subject IS NOT NULL"),
    )
