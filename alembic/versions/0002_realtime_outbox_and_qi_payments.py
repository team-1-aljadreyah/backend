"""realtime outbox, tickets, rate limiting, and qi payments

Revision ID: 0002_realtime_outbox_qi
Revises: 0001_initial_schema
Create Date: 2026-11-08

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0002_realtime_outbox_qi'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. realtime_connection_tickets
    op.create_table(
        'realtime_connection_tickets',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_realtime_tickets_hash', 'realtime_connection_tickets', ['token_hash'], unique=True)
    op.create_index('idx_realtime_tickets_user', 'realtime_connection_tickets', ['user_id'])

    # 2. outbox_events
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('event_uuid', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('channel', sa.String(length=150), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_outbox_events_uuid', 'outbox_events', ['event_uuid'], unique=True)
    op.create_index('idx_outbox_events_channel', 'outbox_events', ['channel'])
    op.create_index('idx_outbox_events_type', 'outbox_events', ['event_type'])
    op.create_index('idx_outbox_events_created', 'outbox_events', ['created_at'])

    # 3. rate_limit_entries
    op.create_table(
        'rate_limit_entries',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('bucket_key', sa.String(length=128), nullable=False),
        sa.Column('counter', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_rate_limit_entries_key', 'rate_limit_entries', ['bucket_key'], unique=True)
    op.create_index('idx_rate_limit_entries_expires', 'rate_limit_entries', ['expires_at'])

    if is_postgres:
        op.execute("""
            CREATE OR REPLACE FUNCTION notify_outbox_event()
            RETURNS TRIGGER AS $$
            BEGIN
                PERFORM pg_notify('realtime_events', NEW.id::text);
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_outbox_event_notify ON outbox_events;
            CREATE TRIGGER trg_outbox_event_notify
            AFTER INSERT ON outbox_events
            FOR EACH ROW
            EXECUTE FUNCTION notify_outbox_event();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS trg_outbox_event_notify ON outbox_events;")
        op.execute("DROP FUNCTION IF EXISTS notify_outbox_event();")

    op.drop_table('rate_limit_entries')
    op.drop_table('outbox_events')
    op.drop_table('realtime_connection_tickets')
