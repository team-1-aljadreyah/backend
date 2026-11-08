import asyncio
import hashlib
import json
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set, Tuple
from fastapi import WebSocket
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.database.connection import AsyncSessionLocal
from app.database.models.profile import Profile
from app.database.models.realtime import OutboxEvent, RealtimeConnectionTicket

TICKET_TTL_SECONDS = 60


def record_outbox_event(
    db: AsyncSession,
    channel: str,
    event_type: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None,
) -> OutboxEvent:
    """
    Records an event in the transactional outbox table within the caller's active database transaction.
    This guarantees that events are only published if the database transaction commits successfully.
    """
    event = OutboxEvent(
        event_uuid=str(uuid.uuid4()),
        event_type=event_type,
        channel=channel,
        payload=payload,
        created_at=datetime.now(timezone.utc),
        correlation_id=correlation_id,
        retry_count=0,
    )
    db.add(event)
    return event


class ConnectionManager:
    def __init__(self):
        # Maps WebSocket connection to a set of subscribed channel names
        self.active_connections: Dict[WebSocket, Set[str]] = {}
        # Maps channel name to a set of WebSocket connections
        self.channel_subscribers: Dict[str, Set[WebSocket]] = {}
        # Fallback in-memory tickets for testing: ticket_str -> (user_dict, expires_at)
        self.memory_tickets: Dict[str, Tuple[dict, float]] = {}
        # Lock for thread/coroutine safe connection management
        self._lock = asyncio.Lock()
        # Polling and listener tasks
        self._poll_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._last_seen_event_id: int = 0
        self._is_running: bool = False

    async def start_worker_engine(self):
        """
        Starts the worker real-time engine:
        1. Initializes last seen event id cursor.
        2. Starts the transactional outbox polling loop (recovery and delivery).
        3. Attempts to start PostgreSQL LISTEN task if running on PostgreSQL.
        """
        if self._is_running:
            return
        self._is_running = True

        # Initialize cursor to current max id so cold boot does not replay historical events
        try:
            async with AsyncSessionLocal() as db:
                stmt = select(func.coalesce(func.max(OutboxEvent.id), 0))
                res = await db.execute(stmt)
                self._last_seen_event_id = res.scalar() or 0
                logger.info(f"Realtime: Initialized outbox cursor at id {self._last_seen_event_id}")
        except Exception as e:
            logger.warning(f"Realtime: Failed to initialize outbox cursor ({e}). Starting from 0.")
            self._last_seen_event_id = 0

        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Realtime: Worker event engine started (PostgreSQL Outbox mode)")

    async def stop_worker_engine(self):
        """Gracefully cancels polling and listener background tasks."""
        self._is_running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None
        logger.info("Realtime: Worker event engine stopped")

    async def _poll_loop(self):
        """
        Periodically polls outbox_events table for new events matching id > _last_seen_event_id.
        Advances the worker-local cursor and delivers events to connected WebSockets.
        """
        interval = getattr(settings, "REALTIME_POLL_INTERVAL_SECONDS", 0.5)
        batch_size = getattr(settings, "REALTIME_BATCH_SIZE", 50)

        while self._is_running:
            try:
                await self._fetch_and_dispatch_outbox_events(batch_size)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Realtime outbox poll error: {e}")

            await asyncio.sleep(interval)

    async def _fetch_and_dispatch_outbox_events(self, batch_size: int = 50):
        try:
            async with AsyncSessionLocal() as db:
                stmt = (
                    select(OutboxEvent)
                    .where(OutboxEvent.id > self._last_seen_event_id)
                    .order_by(OutboxEvent.id.asc())
                    .limit(batch_size)
                )
                res = await db.execute(stmt)
                events = res.scalars().all()

                for ev in events:
                    payload = {
                        "channel": ev.channel,
                        "event": ev.event_type,
                        "data": ev.payload,
                        "timestamp": ev.created_at.timestamp() if ev.created_at else time.time(),
                        "event_uuid": ev.event_uuid,
                    }
                    await self._send_to_local_channel(ev.channel, payload)
                    if ev.id > self._last_seen_event_id:
                        self._last_seen_event_id = ev.id
        except Exception as e:
            logger.debug(f"Realtime fetch error: {e}")

    async def create_ticket(
        self,
        db: Optional[AsyncSession],
        user_id: int,
        role: str = "patient",
        name: str = "User",
        doctor_id: Optional[int] = None,
    ) -> str:
        """
        Generates a secure, single-use, database-backed connection ticket with a 60-second expiration.
        Multi-worker safe via atomic database storage.
        """
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=TICKET_TTL_SECONDS)

        if db is not None:
            ticket_entry = RealtimeConnectionTicket(
                token_hash=token_hash,
                user_id=user_id,
                expires_at=expires_at,
            )
            db.add(ticket_entry)
            await db.flush()
        else:
            # Fallback for unit testing where db session is not passed
            now_ts = time.time()
            self.memory_tickets[token] = (
                {
                    "user_id": user_id,
                    "role": role,
                    "name": name,
                    "doctor_id": doctor_id,
                },
                now_ts + TICKET_TTL_SECONDS,
            )

        return token

    def create_ticket_sync(
        self,
        user_id: int,
        role: str,
        name: str,
        doctor_id: Optional[int] = None,
    ) -> str:
        """Synchronous ticket creation for memory-only test setups."""
        ticket = secrets.token_urlsafe(32)
        expires_at = time.time() + TICKET_TTL_SECONDS
        self.memory_tickets[ticket] = (
            {
                "user_id": user_id,
                "role": role,
                "name": name,
                "doctor_id": doctor_id,
            },
            expires_at,
        )
        return ticket

    async def consume_ticket(
        self,
        db: Optional[AsyncSession],
        ticket: str,
    ) -> Optional[dict]:
        """
        Atomically consumes a single-use ticket across multiple workers.
        If valid, marks consumed_at = NOW() and returns user identity dict.
        Subsequent calls with the same ticket fail immediately.
        """
        if not ticket:
            return None

        # 1. Check database if session provided
        if db is not None:
            token_hash = hashlib.sha256(ticket.encode("utf-8")).hexdigest()
            now = datetime.now(timezone.utc)

            # Atomic consumption query
            stmt = (
                update(RealtimeConnectionTicket)
                .where(
                    RealtimeConnectionTicket.token_hash == token_hash,
                    RealtimeConnectionTicket.consumed_at.is_(None),
                    RealtimeConnectionTicket.revoked_at.is_(None),
                    RealtimeConnectionTicket.expires_at > now,
                )
                .values(consumed_at=now)
                .returning(RealtimeConnectionTicket.user_id)
            )
            res = await db.execute(stmt)
            user_id = res.scalar_one_or_none()

            if user_id:
                # Retrieve current profile
                p_stmt = select(Profile).where(Profile.id == user_id)
                p_res = await db.execute(p_stmt)
                profile = p_res.scalar_one_or_none()
                if profile and profile.is_active:
                    return {
                        "user_id": profile.id,
                        "role": profile.role,
                        "name": profile.name,
                        "doctor_id": profile.doctor_id,
                    }
                return None

        # 2. Check memory fallback (for unit tests)
        record = self.memory_tickets.pop(ticket, None)
        if record:
            user_data, exp = record
            if time.time() <= exp:
                return user_data

        return None

    def consume_ticket_sync(self, ticket: str) -> Optional[dict]:
        """Synchronous ticket consumption for memory-only test setups."""
        record = self.memory_tickets.pop(ticket, None)
        if not record:
            return None
        user_data, expires_at = record
        if time.time() > expires_at:
            return None
        return user_data

    async def connect(self, websocket: WebSocket, channels: Set[str]):
        await websocket.accept()
        async with self._lock:
            self.active_connections[websocket] = set(channels)
            for ch in channels:
                if ch not in self.channel_subscribers:
                    self.channel_subscribers[ch] = set()
                self.channel_subscribers[ch].add(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            channels = self.active_connections.pop(websocket, set())
            for ch in channels:
                if ch in self.channel_subscribers:
                    self.channel_subscribers[ch].discard(websocket)
                    if not self.channel_subscribers[ch]:
                        del self.channel_subscribers[ch]

    async def _send_to_local_channel(self, channel: str, message: dict):
        subscribers = list(self.channel_subscribers.get(channel, set()))
        if not subscribers:
            return

        dead_sockets = []
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                dead_sockets.append(ws)

        for ws in dead_sockets:
            await self.disconnect(ws)

    async def broadcast(self, channel: str, event_type: str, data: Any):
        """Broadcasts event directly to local active WebSocket subscribers."""
        payload = {
            "channel": channel,
            "event": event_type,
            "data": data,
            "timestamp": time.time(),
        }
        await self._send_to_local_channel(channel, payload)


realtime_manager = ConnectionManager()
