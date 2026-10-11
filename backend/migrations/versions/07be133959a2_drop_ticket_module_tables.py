"""drop ticket module tables

Revision ID: 07be133959a2
Revises: 089d1b60b83b
Create Date: 2026-09-05 10:10:32.016580

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '07be133959a2'
down_revision = '089d1b60b83b'
branch_labels = None
depends_on = None


def upgrade():
    # Seeded ticket.* notification templates have no code path left to send
    # them from - not restored on downgrade, since seed_templates() no
    # longer knows about them either.
    op.execute("DELETE FROM notification_templates WHERE key IN ('ticket.reply', 'ticket.acknowledged', 'ticket.sla-breach')")

    with op.batch_alter_table('ticket_messages', schema=None) as batch_op:
        batch_op.drop_index('ticket_messages_ticket_idx')
    op.drop_table('ticket_messages')

    with op.batch_alter_table('ticket_events', schema=None) as batch_op:
        batch_op.drop_index('ticket_events_ticket_idx')
    op.drop_table('ticket_events')

    with op.batch_alter_table('inbound_emails', schema=None) as batch_op:
        batch_op.drop_index('inbound_emails_ticket_idx')
    op.drop_table('inbound_emails')

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index('tickets_thread_idx')
        batch_op.drop_index('tickets_status_idx')
        batch_op.drop_index('tickets_sla_idx')
        batch_op.drop_index('tickets_external_ref_idx')
        batch_op.drop_index('tickets_assignee_idx')
    op.drop_table('tickets')

    with op.batch_alter_table('ticket_categories', schema=None) as batch_op:
        batch_op.drop_index('ticket_categories_parent_idx')
    op.drop_table('ticket_categories')

    with op.batch_alter_table('intake_api_keys', schema=None) as batch_op:
        batch_op.drop_index('intake_api_keys_active_idx')
    op.drop_table('intake_api_keys')


def downgrade():
    op.create_table('intake_api_keys',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('key_prefix', sa.String(), nullable=False),
    sa.Column('key_hash', sa.String(), nullable=False),
    sa.Column('source_label', sa.String(), nullable=False),
    sa.Column('rate_per_hour', sa.Integer(), nullable=False),
    sa.Column('allowed_origins', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_by', sa.String(), nullable=True),
    sa.CheckConstraint('rate_per_hour > 0', name='intake_api_keys_rate_check'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key_hash', name='intake_api_keys_hash_uniq'),
    sa.UniqueConstraint('tenant_id', 'name', name='intake_api_keys_name_uniq')
    )
    with op.batch_alter_table('intake_api_keys', schema=None) as batch_op:
        batch_op.create_index('intake_api_keys_active_idx', ['tenant_id', 'active'], unique=False)

    op.create_table('ticket_categories',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('parent_id', sa.UUID(), nullable=True),
    sa.Column('first_response_minutes', sa.Integer(), nullable=True),
    sa.Column('resolution_minutes', sa.Integer(), nullable=True),
    sa.Column('default_priority', sa.String(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("default_priority in ('low','medium','high','urgent') or default_priority is null", name='ticket_categories_priority_check'),
    sa.ForeignKeyConstraint(['parent_id'], ['ticket_categories.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'code', name='ticket_categories_tenant_code_uniq')
    )
    with op.batch_alter_table('ticket_categories', schema=None) as batch_op:
        batch_op.create_index('ticket_categories_parent_idx', ['parent_id'], unique=False)

    op.create_table('tickets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('number', sa.String(), nullable=False),
    sa.Column('subject', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('priority', sa.String(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('category_id', sa.UUID(), nullable=True),
    sa.Column('subcategory_id', sa.UUID(), nullable=True),
    sa.Column('party_id', sa.UUID(), nullable=True),
    sa.Column('party_name', sa.String(), nullable=True),
    sa.Column('requester_name', sa.String(), nullable=False),
    sa.Column('requester_email', sa.String(), nullable=False),
    sa.Column('requester_phone', sa.String(), nullable=True),
    sa.Column('requester_ip', sa.String(), nullable=True),
    sa.Column('assignee_id', sa.String(), nullable=True),
    sa.Column('assignee_name', sa.String(), nullable=True),
    sa.Column('thread_key', sa.String(), nullable=True),
    sa.Column('first_response_due', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolution_due', sa.DateTime(timezone=True), nullable=True),
    sa.Column('first_response_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('paused_ms', sa.BigInteger(), nullable=False),
    sa.Column('sla_state', sa.String(), nullable=False),
    sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolution_reason', sa.String(), nullable=True),
    sa.Column('reopened_from_id', sa.UUID(), nullable=True),
    sa.Column('intake_key_id', sa.UUID(), nullable=True),
    sa.Column('source_label', sa.String(), nullable=True),
    sa.Column('external_ref', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("priority in ('low','medium','high','urgent')", name='tickets_priority_check'),
    sa.CheckConstraint("sla_state in ('on_track','at_risk','breached','met')", name='tickets_sla_state_check'),
    sa.CheckConstraint("source in ('form','email','phone','portal','internal')", name='tickets_source_check'),
    sa.CheckConstraint("status in ('open','pending_customer','in_progress','resolved','closed','reopened')", name='tickets_status_check'),
    sa.ForeignKeyConstraint(['category_id'], ['ticket_categories.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['intake_key_id'], ['intake_api_keys.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['reopened_from_id'], ['tickets.id'], ),
    sa.ForeignKeyConstraint(['subcategory_id'], ['ticket_categories.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'number', name='tickets_tenant_number_uniq')
    )
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.create_index('tickets_assignee_idx', ['tenant_id', 'assignee_id'], unique=False)
        batch_op.create_index('tickets_external_ref_idx', ['tenant_id', 'external_ref'], unique=False)
        batch_op.create_index('tickets_sla_idx', ['tenant_id', 'sla_state', 'first_response_due'], unique=False)
        batch_op.create_index('tickets_status_idx', ['tenant_id', 'status', 'created_at'], unique=False)
        batch_op.create_index('tickets_thread_idx', ['tenant_id', 'thread_key'], unique=False)

    op.create_table('inbound_emails',
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('message_id', sa.String(), nullable=False),
    sa.Column('ticket_id', sa.UUID(), nullable=True),
    sa.Column('from_email', sa.String(), nullable=False),
    sa.Column('subject', sa.String(), nullable=True),
    sa.Column('in_reply_to', sa.String(), nullable=True),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("action in ('created','threaded','ignored')", name='inbound_emails_action_check'),
    sa.CheckConstraint("source in ('webhook','imap')", name='inbound_emails_source_check'),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('tenant_id', 'message_id')
    )
    with op.batch_alter_table('inbound_emails', schema=None) as batch_op:
        batch_op.create_index('inbound_emails_ticket_idx', ['tenant_id', 'ticket_id'], unique=False)

    op.create_table('ticket_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('ticket_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('actor_id', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ticket_events', schema=None) as batch_op:
        batch_op.create_index('ticket_events_ticket_idx', ['ticket_id', 'created_at'], unique=False)

    op.create_table('ticket_messages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('ticket_id', sa.UUID(), nullable=False),
    sa.Column('direction', sa.String(), nullable=False),
    sa.Column('author_id', sa.String(), nullable=True),
    sa.Column('author_name', sa.String(), nullable=False),
    sa.Column('author_email', sa.String(), nullable=True),
    sa.Column('body', sa.String(), nullable=False),
    sa.Column('is_internal', sa.Boolean(), nullable=False),
    sa.Column('email_message_id', sa.String(), nullable=True),
    sa.Column('in_reply_to', sa.String(), nullable=True),
    sa.Column('notification_id', sa.UUID(), nullable=True),
    sa.Column('attachments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("direction in ('inbound','outbound','internal')", name='ticket_messages_direction_check'),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ticket_messages', schema=None) as batch_op:
        batch_op.create_index('ticket_messages_ticket_idx', ['ticket_id', 'created_at'], unique=False)
