"""AISStream.io WebSocket client (ADR-010): real-time AIS → VesselTable.

Subscribes to a bounding box around the receiver, parses PositionReport (lat/
lon/sog/cog) and ShipStaticData (name/type), and upserts into the VesselTable.
Fail-soft: reconnects with backoff; AIS going dark never affects ADS-B or the
rest of the dashboard (vessels just go stale).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import Callable

import websockets

from app.state.vessels import VesselTable

log = logging.getLogger("gateway.ais")

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"


class AisStreamClient:
    def __init__(
        self,
        api_key: str,
        bbox: list[list[float]],  # [[lat_min, lon_min], [lat_max, lon_max]]
        table: VesselTable,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._key = api_key
        self._bbox = bbox
        self._table = table
        self._clock = clock
        self._task: asyncio.Task | None = None
        self.connected = False

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="aisstream")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _run(self) -> None:
        sub = {
            "APIKey": self._key,
            "BoundingBoxes": [self._bbox],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        }
        backoff = 2
        while True:
            try:
                async with websockets.connect(AISSTREAM_URL, open_timeout=15) as ws:
                    await ws.send(json.dumps(sub))
                    self.connected = True
                    backoff = 2
                    log.info("aisstream connected (bbox=%s)", self._bbox)
                    async for raw in ws:
                        self._handle(raw)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — any failure: log, back off, retry
                self.connected = False
                log.info("aisstream disconnected (%s) — retry in %ss", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def _handle(self, raw: str | bytes) -> None:
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            return
        meta = msg.get("MetaData") or {}
        mmsi = meta.get("MMSI")
        if not isinstance(mmsi, int):
            return
        now = int(self._clock())
        name = (meta.get("ShipName") or "").strip() or None
        lat, lon = meta.get("latitude"), meta.get("longitude")
        sog = cog = ship_type = None

        body = msg.get("Message") or {}
        mtype = msg.get("MessageType")
        if mtype == "PositionReport":
            pr = body.get("PositionReport") or {}
            lat = pr.get("Latitude", lat)
            lon = pr.get("Longitude", lon)
            sog = pr.get("Sog")
            cog = pr.get("Cog")
        elif mtype == "ShipStaticData":
            sd = body.get("ShipStaticData") or {}
            ship_type = sd.get("Type")
            name = name or ((sd.get("Name") or "").strip() or None)

        # AIS uses sentinel values for "not available"
        if sog is not None and sog >= 102.3:
            sog = None
        if cog is not None and cog >= 360:
            cog = None

        self._table.upsert(
            mmsi,
            now=now,
            lat=lat,
            lon=lon,
            sog=sog,
            cog=cog,
            name=name,
            ship_type=ship_type,
        )


def bbox_around(lat: float, lon: float, margin_deg: float = 2.0) -> list[list[float]]:
    return [[lat - margin_deg, lon - margin_deg], [lat + margin_deg, lon + margin_deg]]
