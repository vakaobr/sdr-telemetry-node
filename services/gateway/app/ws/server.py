"""WebSocket endpoint: snapshot on connect, then hub-driven deltas."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.engine import Engine

log = logging.getLogger("gateway.ws")

router = APIRouter()


def make_ws_router(engine: Engine) -> APIRouter:
    r = APIRouter()

    @r.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        await engine.hub.join(ws)
        try:
            await ws.send_json(engine.snapshot_message())
            while True:
                msg = await ws.receive_json()
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") == "subscribe" and isinstance(msg.get("topics"), list):
                    await engine.hub.set_topics(ws, [str(t) for t in msg["topics"]])
                # "ping" needs no reply: the 1 Hz delta stream is the liveness signal
        except WebSocketDisconnect:
            pass
        except Exception:  # malformed frames etc. — drop this client only
            log.debug("ws client error", exc_info=True)
        finally:
            await engine.hub.leave(ws)

    return r
