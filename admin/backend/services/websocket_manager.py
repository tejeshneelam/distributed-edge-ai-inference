import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        logger.info("WS client connected. Total: %d", len(self._clients))

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)
        logger.info("WS client disconnected. Total: %d", len(self._clients))

    async def broadcast(self, message: dict) -> None:
        disconnected: Set[WebSocket] = set()
        for client in list(self._clients):
            try:
                await client.send_json(message)
            except Exception:
                disconnected.add(client)
        for client in disconnected:
            self._clients.discard(client)


websocket_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    return websocket_manager
