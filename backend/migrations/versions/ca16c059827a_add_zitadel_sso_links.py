"""add tenants.zitadel_org_id and a unique external-identity index on users

Revision ID: ca16c059827a
Revises: c7d8e9f0a1b2
"""

import sqlalchemy as sa
from alembic import op

revision = "ca16c059827a"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("zitadel_org_id", sa.String(), nullable=True))
    op.create_unique_constraint("tenants_zitadel_org_id_key", "tenants", ["zitadel_org_id"])
    op.create_index(
        "users_external_identity_key",
        "users",
        ["tenant_id", "external_idp", "external_subject"],
        unique=True,
        postgresql_where=sa.text("external_subject IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("users_external_identity_key", table_name="users")
    op.drop_constraint("tenants_zitadel_org_id_key", "tenants", type_="unique")
    op.drop_column("tenants", "zitadel_org_id")
