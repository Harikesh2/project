import asyncio
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Process-local registry mapping user IDs to their connected WebSockets."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._ws_to_user: Dict[int, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket):
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)
            self._ws_to_user[id(websocket)] = user_id
            logger.info(f"User {user_id} connected ({len(self._connections[user_id])} active sockets)")

    async def disconnect(self, user_id: str, websocket: WebSocket):
        async with self._lock:
            sockets = self._connections.get(user_id)
            if sockets:
                sockets.discard(websocket)
                if not sockets:
                    del self._connections[user_id]
            self._ws_to_user.pop(id(websocket), None)
            remaining = len(sockets) if sockets else 0
            logger.info(f"User {user_id} disconnected ({remaining} remaining)")

    async def send_to_users(self, user_ids: list[str], message: dict):
        """Send a JSON message to all connected sockets for the given users."""
        async with self._lock:
            targets: list[tuple[int, WebSocket]] = []
            for uid in user_ids:
                sockets = self._connections.get(uid)
                if sockets:
                    for ws in sockets:
                        targets.append((id(ws), ws))

        for ws_id, ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                async with self._lock:
                    user_id = self._ws_to_user.get(ws_id)
                    if user_id:
                        sockets = self._connections.get(user_id)
                        if sockets:
                            sockets.discard(ws)
                            if not sockets:
                                del self._connections[user_id]
                        self._ws_to_user.pop(ws_id, None)
                logger.warning("Removed failed socket from registry")


connection_manager = ConnectionManager()
