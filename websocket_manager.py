import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    """
    Gestiona conexiones WebSocket activas.
    Soporta broadcast global y por sala (floor/zone).
    """

    def __init__(self):
        # client_id -> WebSocket
        self._active: Dict[str, WebSocket] = {}
        # room -> set of client_ids  (room = "baja" | "primera" | "all")
        self._rooms: Dict[str, Set[str]] = {}

    async def connect(self, ws: WebSocket, client_id: str, room: str = "all"):
        await ws.accept()
        self._active[client_id] = ws
        self._rooms.setdefault(room, set()).add(client_id)
        self._rooms.setdefault("all", set()).add(client_id)

    def disconnect(self, client_id: str):
        self._active.pop(client_id, None)
        for members in self._rooms.values():
            members.discard(client_id)

    async def broadcast(self, event: str, payload: dict, room: str = "all"):
        """Envía a todos los clientes suscritos a 'room'."""
        message = json.dumps({"event": event, "payload": payload})
        dead: list[str] = []

        for cid in list(self._rooms.get(room, set())):
            ws = self._active.get(cid)
            if ws is None:
                dead.append(cid)
                continue
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(cid)

        for cid in dead:
            self.disconnect(cid)

    async def send_personal(self, client_id: str, event: str, payload: dict):
        ws = self._active.get(client_id)
        if ws:
            try:
                await ws.send_text(json.dumps({"event": event, "payload": payload}))
            except Exception:
                self.disconnect(client_id)

    @property
    def connected_count(self) -> int:
        return len(self._active)


# Singleton compartido por toda la app
manager = ConnectionManager()
