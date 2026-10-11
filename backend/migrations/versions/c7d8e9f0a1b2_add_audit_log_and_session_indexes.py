"""add audit_log and sessions indexes - audit_log had none at all despite being
filtered by tenant_id (+ entity_type/entity_id) and ordered by created_at on
every dashboard load and every entity detail page's history tab; sessions had
none on user_id despite being filtered by it on every login/refresh rotation

Revision ID: c7d8e9f0a1b2
Revises: f2a7c4e8b1d9
Create Date: 2026-09-14 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d8e9f0a1b2'
down_revision = 'f2a7c4e8b1d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.create_index('audit_log_tenant_created_idx', ['tenant_id', 'created_at'])
        batch_op.create_index('audit_log_tenant_entity_idx', ['tenant_id', 'entity_type', 'entity_id', 'created_at'])

    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.create_index('sessions_user_idx', ['user_id'])


def downgrade():
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_index('sessions_user_idx')

    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.drop_index('audit_log_tenant_entity_idx')
        batch_op.drop_index('audit_log_tenant_created_idx')
