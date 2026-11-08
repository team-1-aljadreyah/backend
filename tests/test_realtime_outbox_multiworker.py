import unittest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.database.connection import AsyncSessionLocal
from app.database.models.profile import Profile
from app.database.models.realtime import OutboxEvent, RealtimeConnectionTicket
from app.services.realtime_service import realtime_manager, record_outbox_event
from tests.conftest import get_test_client


class TestRealtimeOutboxMultiworker(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = await get_test_client()

    async def test_database_backed_ticket_single_use_enforcement(self):
        """Verifies that connection tickets are single-use and cannot be consumed twice."""
        async with AsyncSessionLocal() as session:
            # Look up existing user (e.g., patient user id=1)
            p_stmt = select(Profile).where(Profile.id == 1)
            user = (await session.execute(p_stmt)).scalar_one_or_none()
            if not user:
                user = Profile(id=1, name="Ahmed Ali", phone="07700000001", role="patient")
                session.add(user)
                await session.commit()

            ticket = await realtime_manager.create_ticket(session, user_id=1)
            await session.commit()

            self.assertTrue(len(ticket) >= 32)

            # First consumption -> returns user data
            user_data = await realtime_manager.consume_ticket(session, ticket)
            await session.commit()
            self.assertIsNotNone(user_data)
            self.assertEqual(user_data["user_id"], 1)

            # Second consumption of the same ticket -> strictly None (cannot be replayed)
            replayed = await realtime_manager.consume_ticket(session, ticket)
            await session.commit()
            self.assertIsNone(replayed)

    async def test_expired_ticket_rejection(self):
        """Verifies that an expired connection ticket is rejected."""
        async with AsyncSessionLocal() as session:
            ticket = await realtime_manager.create_ticket(session, user_id=1)
            await session.commit()

            # Artificially expire the ticket in the database
            import hashlib
            h = hashlib.sha256(ticket.encode("utf-8")).hexdigest()
            t_stmt = select(RealtimeConnectionTicket).where(RealtimeConnectionTicket.token_hash == h)
            t_entry = (await session.execute(t_stmt)).scalar_one()
            t_entry.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
            await session.commit()

            consumed = await realtime_manager.consume_ticket(session, ticket)
            await session.commit()
            self.assertIsNone(consumed)

    async def test_transactional_outbox_rollback_integrity(self):
        """Verifies that rolling back a database transaction rolls back outbox events (no phantom publishes)."""
        async with AsyncSessionLocal() as session:
            ev = record_outbox_event(
                db=session,
                channel="public:queue",
                event_type="test.rollback",
                payload={"info": "should_not_exist"},
            )
            ev_uuid = ev.event_uuid
            await session.flush()

            # Explicit rollback
            await session.rollback()

            # Confirm event is not in outbox_events
            chk_stmt = select(OutboxEvent).where(OutboxEvent.event_uuid == ev_uuid)
            res = await session.execute(chk_stmt)
            self.assertIsNone(res.scalar_one_or_none())
