import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth.clerk import get_current_websocket_user
from app.models.chat import IncomingMessageEvent
from app.services.chat_service import chat_service
from app.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat_ws"])


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    current_user = await get_current_websocket_user(websocket)
    user_id = current_user["user_id"]

    await websocket.accept()
    await websocket.send_json({"type": "ready"})
    await connection_manager.connect(user_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                event = IncomingMessageEvent(**data)
            except (json.JSONDecodeError, ValueError) as e:
                # Best-effort: pull client_message_id off the raw payload so the
                # client can target the failing optimistic bubble. If the JSON is
                # too broken to parse, this just yields None and the client falls
                # back to removing the most recent pending bubble.
                raw_client_id = None
                if isinstance(data, dict):
                    raw_client_id = data.get("client_message_id")
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_EVENT",
                    "detail": str(e),
                    "client_message_id": raw_client_id,
                })
                continue

            try:
                message = await chat_service.send_message(
                    conversation_id=event.conversation_id,
                    sender_id=user_id,
                    content=event.content,
                    client_message_id=event.client_message_id,
                )
            except ValueError as e:
                await websocket.send_json({
                    "type": "error",
                    "code": "SEND_FAILED",
                    "detail": str(e),
                    "client_message_id": event.client_message_id,
                })
                continue

            metadata = await chat_service.get_conversation_for_member(
                event.conversation_id, user_id
            )

            broadcast = {
                "type": "message.created",
                "conversation": metadata.model_dump(),
                "message": message.model_dump(),
                "client_message_id": event.client_message_id,
            }

            await connection_manager.send_to_users(metadata.participant_ids, broadcast)

    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(user_id, websocket)
