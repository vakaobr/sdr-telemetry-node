"""WebSocket hub: connection registry + topic-filtered broadcast.

Protocol (03_PROJECT_SPEC §3.1): snapshot on connect, then typed deltas.
Clients may narrow with a `subscribe` message; default = everything.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("gateway.ws")

# message type → subscription topic
_TOPIC_OF = {
    "aircraft_delta": "aircraft",
    "interesting": "aircraft",
    "vessel_delta": "vessels",
    "radio2_status": "radio2",
    "atc_activity": "radio2",
    "pass_update": "radio2",
    "system_health": "system",
}
ALL_TOPICS = frozenset({"aircraft", "vessels", "radio2", "system"})


class Hub:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, set[str]] = {}
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def join(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients[ws] = set(ALL_TOPICS)

    async def set_topics(self, ws: WebSocket, topics: list[str]) -> None:
        async with self._lock:
            if ws in self._clients:
                self._clients[ws] = set(topics) & ALL_TOPICS

    async def leave(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.pop(ws, None)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send to all subscribed clients; dead sockets are evicted, never fatal."""
        topic = _TOPIC_OF.get(message.get("type", ""))
        async with self._lock:
            targets = [
                ws for ws, topics in self._clients.items() if topic is None or topic in topics
            ]
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 — any send failure means: drop the client
                dead.append(ws)
        for ws in dead:
            await self.leave(ws)
            log.info("evicted dead WS client (%d remain)", self.client_count)
