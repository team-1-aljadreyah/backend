import asyncio
from typing import Optional, Set
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, status
from app.core.dependencies import get_current_user
from app.core.envelope import success_response
from app.core.security import decode_token
from app.database.connection import get_db, AsyncSessionLocal
from app.database.models.profile import Profile
from app.services.realtime_service import realtime_manager
from app.core.logging import logger
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["Realtime"])


@router.post("/realtime/ticket")
async def create_realtime_ticket(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a short-lived (60s) single-use ticket for establishing a secure
    WebSocket connection without leaking long-lived tokens into query strings.
    Multi-worker synchronized via database storage.
    """
    ticket = await realtime_manager.create_ticket(
        db=db,
        user_id=user.id,
        role=user.role,
        name=user.name,
        doctor_id=user.doctor_id,
    )
    return success_response({"ticket": ticket, "expires_in": 60})


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    ticket: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
):
    """
    Real-time WebSocket endpoint supporting live queue updates, doctor call alerts,
    and instant patient notifications.
    """
    user_data = None

    # 1. Try single-use ticket first (recommended)
    if ticket:
        try:
            async with AsyncSessionLocal() as session:
                user_data = await realtime_manager.consume_ticket(session, ticket)
                await session.commit()
        except Exception as e:
            logger.debug(f"DB ticket consumption failed, checking memory: {e}")
            user_data = await realtime_manager.consume_ticket(None, ticket)

    # 2. Fallback to direct token if provided
    if not user_data and token:
        try:
            payload = decode_token(token)
            if payload.get("type") == "access":
                user_data = {
                    "user_id": int(payload["sub"]),
                    "role": payload.get("role", "patient"),
                    "name": payload.get("name", "User"),
                    "doctor_id": payload.get("doctor_id"),
                }
        except Exception:
            pass

    # Determine allowed channels based on authorization
    channels: Set[str] = {"queue"}  # Everyone gets the public waiting room queue

    if user_data:
        uid = user_data["user_id"]
        role = user_data["role"]
        channels.add(f"user:{uid}")
        channels.add(f"staff:{role}")

        doc_id = user_data.get("doctor_id")
        if doc_id:
            channels.add(f"doctor:{doc_id}")

    await realtime_manager.connect(websocket, channels)

    try:
        # Initial greeting and channel confirmation
        await websocket.send_json({
            "event": "connected",
            "channels": list(channels),
            "authenticated": user_data is not None,
        })

        while True:
            # Handle client messages / heartbeats
            data = await websocket.receive_json()
            msg_type = data.get("type") or data.get("event")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await realtime_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket connection closed: {e}")
        await realtime_manager.disconnect(websocket)
