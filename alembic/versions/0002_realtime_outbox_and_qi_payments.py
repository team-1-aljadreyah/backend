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
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. realtime_connection_tickets
    if 'realtime_connection_tickets' not in existing_tables:
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
    
    # Check indexes for realtime_connection_tickets
    existing_indexes_tickets = set()
    if 'realtime_connection_tickets' in set(sa.inspect(bind).get_table_names()):
        existing_indexes_tickets = {idx['name'] for idx in sa.inspect(bind).get_indexes('realtime_connection_tickets')}
    if 'idx_realtime_tickets_hash' not in existing_indexes_tickets:
        op.create_index('idx_realtime_tickets_hash', 'realtime_connection_tickets', ['token_hash'], unique=True)
    if 'idx_realtime_tickets_user' not in existing_indexes_tickets:
        op.create_index('idx_realtime_tickets_user', 'realtime_connection_tickets', ['user_id'])

    # 2. outbox_events
    if 'outbox_events' not in existing_tables:
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

    # Check indexes for outbox_events
    existing_indexes_outbox = set()
    if 'outbox_events' in set(sa.inspect(bind).get_table_names()):
        existing_indexes_outbox = {idx['name'] for idx in sa.inspect(bind).get_indexes('outbox_events')}
    if 'idx_outbox_events_uuid' not in existing_indexes_outbox:
        op.create_index('idx_outbox_events_uuid', 'outbox_events', ['event_uuid'], unique=True)
    if 'idx_outbox_events_channel' not in existing_indexes_outbox:
        op.create_index('idx_outbox_events_channel', 'outbox_events', ['channel'])
    if 'idx_outbox_events_type' not in existing_indexes_outbox:
        op.create_index('idx_outbox_events_type', 'outbox_events', ['event_type'])
    if 'idx_outbox_events_created' not in existing_indexes_outbox:
        op.create_index('idx_outbox_events_created', 'outbox_events', ['created_at'])

    # 3. rate_limit_entries
    if 'rate_limit_entries' not in existing_tables:
        op.create_table(
            'rate_limit_entries',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('bucket_key', sa.String(length=128), nullable=False),
            sa.Column('counter', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('window_start', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )

    # Check indexes for rate_limit_entries
    existing_indexes_rate = set()
    if 'rate_limit_entries' in set(sa.inspect(bind).get_table_names()):
        existing_indexes_rate = {idx['name'] for idx in sa.inspect(bind).get_indexes('rate_limit_entries')}
    if 'idx_rate_limit_entries_key' not in existing_indexes_rate:
        op.create_index('idx_rate_limit_entries_key', 'rate_limit_entries', ['bucket_key'], unique=True)
    if 'idx_rate_limit_entries_expires' not in existing_indexes_rate:
        op.create_index('idx_rate_limit_entries_expires', 'rate_limit_entries', ['expires_at'])

    # 4. user_sessions
    if 'user_sessions' not in existing_tables:
        op.create_table(
            'user_sessions',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('jti', sa.String(length=64), nullable=False),
            sa.Column('device_info', sa.String(length=256), nullable=True),
            sa.Column('ip_address', sa.String(length=64), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )

    # Check indexes for user_sessions
    existing_indexes_sessions = set()
    if 'user_sessions' in set(sa.inspect(bind).get_table_names()):
        existing_indexes_sessions = {idx['name'] for idx in sa.inspect(bind).get_indexes('user_sessions')}
    if 'idx_user_sessions_token_hash' not in existing_indexes_sessions:
        op.create_index('idx_user_sessions_token_hash', 'user_sessions', ['token_hash'], unique=True)
    if 'idx_user_sessions_jti' not in existing_indexes_sessions:
        op.create_index('idx_user_sessions_jti', 'user_sessions', ['jti'], unique=True)
    if 'idx_user_sessions_user_id' not in existing_indexes_sessions:
        op.create_index('idx_user_sessions_user_id', 'user_sessions', ['user_id'])
    if 'idx_user_sessions_expires_at' not in existing_indexes_sessions:
        op.create_index('idx_user_sessions_expires_at', 'user_sessions', ['expires_at'])

    # 5. password_reset_otps
    if 'password_reset_otps' not in existing_tables:
        op.create_table(
            'password_reset_otps',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('phone', sa.String(length=32), nullable=False),
            sa.Column('otp_hash', sa.String(length=128), nullable=False),
            sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('cooldown_until', sa.DateTime(timezone=True), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id')
        )

    # Check indexes for password_reset_otps
    existing_indexes_otps = set()
    if 'password_reset_otps' in set(sa.inspect(bind).get_table_names()):
        existing_indexes_otps = {idx['name'] for idx in sa.inspect(bind).get_indexes('password_reset_otps')}
    if 'idx_password_reset_otps_phone' not in existing_indexes_otps:
        op.create_index('idx_password_reset_otps_phone', 'password_reset_otps', ['phone'], unique=True)

    if is_postgres:
        postgres_statements = [
            """
            CREATE OR REPLACE FUNCTION notify_outbox_event()
            RETURNS TRIGGER AS $$
            BEGIN
                PERFORM pg_notify('realtime_events', NEW.id::text);
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """,
            "DROP TRIGGER IF EXISTS trg_outbox_event_notify ON outbox_events;",
            """
            CREATE TRIGGER trg_outbox_event_notify
            AFTER INSERT ON outbox_events
            FOR EACH ROW
            EXECUTE FUNCTION notify_outbox_event();
            """,
            "ALTER TABLE rate_limit_entries ENABLE ROW LEVEL SECURITY;",
            'DROP POLICY IF EXISTS "Manager only view rate limits" ON rate_limit_entries;',
            'DROP POLICY IF EXISTS "Backend service manages rate limits" ON rate_limit_entries;',
            """
            CREATE POLICY "Backend service manages rate limits" ON rate_limit_entries FOR ALL
                USING (true) WITH CHECK (true);
            """,
            "REVOKE ALL ON TABLE rate_limit_entries FROM public, anon;",

            "ALTER TABLE realtime_connection_tickets ENABLE ROW LEVEL SECURITY;",
            'DROP POLICY IF EXISTS "Users manage own tickets" ON realtime_connection_tickets;',
            'DROP POLICY IF EXISTS "Backend service manages tickets" ON realtime_connection_tickets;',
            """
            CREATE POLICY "Backend service manages tickets" ON realtime_connection_tickets FOR ALL
                USING (true) WITH CHECK (true);
            """,
            "REVOKE ALL ON TABLE realtime_connection_tickets FROM public, anon;",

            "ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;",
            'DROP POLICY IF EXISTS "Staff read outbox events" ON outbox_events;',
            'DROP POLICY IF EXISTS "Backend service manages outbox" ON outbox_events;',
            """
            CREATE POLICY "Backend service manages outbox" ON outbox_events FOR ALL
                USING (true) WITH CHECK (true);
            """,
            "REVOKE ALL ON TABLE outbox_events FROM public, anon;",

            "ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;",
            'DROP POLICY IF EXISTS "Users manage own sessions" ON user_sessions;',
            """
            CREATE POLICY "Users manage own sessions" ON user_sessions FOR ALL TO authenticated
                USING (user_id = get_current_profile_id() OR get_current_user_role() = 'manager');
            """,
            'DROP POLICY IF EXISTS "Backend service manages user sessions" ON user_sessions;',
            """
            CREATE POLICY "Backend service manages user sessions" ON user_sessions FOR ALL
                USING (true) WITH CHECK (true);
            """,
            "REVOKE ALL ON TABLE user_sessions FROM public, anon;",

            "ALTER TABLE password_reset_otps ENABLE ROW LEVEL SECURITY;",
            'DROP POLICY IF EXISTS "Manager only direct access to OTPs" ON password_reset_otps;',
            """
            CREATE POLICY "Manager only direct access to OTPs" ON password_reset_otps FOR ALL TO authenticated
                USING (get_current_user_role() = 'manager');
            """,
            'DROP POLICY IF EXISTS "Backend service manages OTPs" ON password_reset_otps;',
            """
            CREATE POLICY "Backend service manages OTPs" ON password_reset_otps FOR ALL
                USING (true) WITH CHECK (true);
            """,
            "REVOKE ALL ON TABLE password_reset_otps FROM public, anon;",
        ]

        for stmt in postgres_statements:
            cleaned = stmt.strip()
            if cleaned:
                op.execute(cleaned)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("DROP TRIGGER IF EXISTS trg_outbox_event_notify ON outbox_events;")
        op.execute("DROP FUNCTION IF EXISTS notify_outbox_event();")

    op.drop_table('password_reset_otps')
    op.drop_table('user_sessions')
    op.drop_table('rate_limit_entries')
    op.drop_table('outbox_events')
    op.drop_table('realtime_connection_tickets')
