import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth.clerk import get_current_websocket_user
from app.services.connection_manager import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notification_ws"])


@router.websocket("/ws/notifications")
async def notification_websocket(websocket: WebSocket):
    current_user = await get_current_websocket_user(websocket)
    user_id = current_user["user_id"]

    await websocket.accept()
    await websocket.send_json({"type": "ready"})
    await connection_manager.connect(user_id, websocket)

    try:
        while True:
            # Keep connection alive; no inbound messages expected
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(user_id, websocket)
