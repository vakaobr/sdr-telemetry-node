"""Gateway engine: the 1 Hz heartbeat tying ingest → state → WS fan-out.

One asyncio task owns the whole cycle (deterministic, testable via tick()):
  1. poll readsb aircraft.json
  2. diff into AircraftTable → aircraft_delta broadcast
  3. drain MQTT bridge events → typed WS messages
  4. periodic system_health broadcast
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from app.bus.mqtt import MqttBridge
from app.config import Config
from app.ingest.readsb import ReadsbClient
from app.models.generated_ws import AdsbHealth, SystemHealth
from app.state.aircraft import AircraftTable
from app.ws.hub import Hub

log = logging.getLogger("gateway.engine")

HEALTH_BROADCAST_EVERY_S = 10


class Engine:
    def __init__(
        self,
        config: Config,
        readsb: ReadsbClient,
        bridge: MqttBridge,
        hub: Hub,
    ) -> None:
        self.config = config
        self._cfg = config
        self._readsb = readsb
        self._bridge = bridge
        self.hub = hub
        self.table = AircraftTable(config)

        self._last_msg_count: int | None = None
        self._last_msg_ts: float | None = None
        self.msg_rate: float = 0.0
        self.max_range_km: float = 0.0
        self._last_health_ts: float = 0.0
        self._task: asyncio.Task | None = None

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="engine")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self._readsb.aclose()

    async def _run(self) -> None:
        interval = self._cfg.adsb.poll_interval_s
        while True:
            started = time.monotonic()
            try:
                await self.tick()
            except Exception:  # the heartbeat must never die
                log.exception("engine tick failed")
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(0.05, interval - elapsed))

    # -- one deterministic cycle (tests drive this directly) ------------------

    async def tick(self, now: int | None = None) -> None:
        now = now or int(time.time())

        doc = await self._readsb.fetch_aircraft()
        if doc is not None:
            self._update_msg_rate(doc)
            updated, removed = self.table.update_from_readsb(doc, now)
            for ac in self.table.snapshot():
                if ac.distanceKm is not None and ac.distanceKm > self.max_range_km:
                    self.max_range_km = ac.distanceKm
            if updated or removed:
                await self.hub.broadcast(
                    {
                        "type": "aircraft_delta",
                        "ts": now,
                        "updated": [a.model_dump(mode="json") for a in updated],
                        "removed": removed,
                    }
                )

        await self._drain_bus_events(now)

        if time.time() - self._last_health_ts >= HEALTH_BROADCAST_EVERY_S:
            self._last_health_ts = time.time()
            await self.hub.broadcast(
                {
                    "type": "system_health",
                    "ts": now,
                    "health": self.system_health().model_dump(mode="json"),
                }
            )

    # -- bus event → WS message mapping ---------------------------------------

    async def _drain_bus_events(self, now: int) -> None:
        radio2_dirty = False
        while not self._bridge.events.empty():
            ev = self._bridge.events.get_nowait()
            topic, payload = ev["topic"], ev["payload"]
            if topic.startswith("radio2/") or (topic.startswith("sys/") and "health" in topic):
                radio2_dirty = True  # status/health snapshot shape rebuilt below
            elif topic == "atc/activity":
                await self.hub.broadcast(
                    {
                        "type": "atc_activity",
                        "ts": payload.get("ts", now),
                        "channelMhz": payload.get("channelMhz"),
                        "active": payload.get("active"),
                    }
                )
            elif topic == "adsb/interesting":
                await self.hub.broadcast(
                    {
                        "type": "interesting",
                        "ts": payload.get("ts", now),
                        "icao": payload.get("icao"),
                        "severity": payload.get("severity"),
                        "rule": payload.get("rule"),
                        "callsign": payload.get("callsign"),
                    }
                )
            # ais/vessel → P9, satellite/pass/event → P10

        if radio2_dirty:
            await self.hub.broadcast(
                {
                    "type": "radio2_status",
                    "ts": now,
                    "status": self._bridge.radio2_status().model_dump(mode="json"),
                }
            )

    # -- snapshot building -----------------------------------------------------

    def _update_msg_rate(self, doc: dict) -> None:
        msgs, ts = doc.get("messages"), time.monotonic()
        if isinstance(msgs, int) and self._last_msg_count is not None and ts > self._last_msg_ts:
            delta = msgs - self._last_msg_count
            self.msg_rate = round(max(0.0, delta / (ts - self._last_msg_ts)), 1)
        if isinstance(msgs, int):
            self._last_msg_count, self._last_msg_ts = msgs, ts

    def radio2_status(self):
        return self._bridge.radio2_status()

    def adsb_health(self) -> AdsbHealth:
        return AdsbHealth.model_validate(
            {
                "ok": self._readsb.healthy,
                "msgRate": self.msg_rate,
                "aircraftCount": self.table.count(),
                "maxRangeKm": self.max_range_km,
            }
        )

    def system_health(self) -> SystemHealth:
        node_a = self._bridge.node_health("node-a")
        return SystemHealth.model_validate(
            {
                "nodeA": (
                    node_a.model_dump()
                    if node_a
                    else {
                        "ok": True,
                        "cpuPct": 0,
                        "memMb": 0,
                        "tempC": 0,
                        "throttled": False,
                        "diskFreePct": 0,
                    }
                ),  # gateway runs ON node-a: if we're answering, the node is up
                "nodeB": (h.model_dump() if (h := self._bridge.node_health("node-b")) else None),
                "adsb": self.adsb_health().model_dump(),
                "dbOk": True,  # persistence arrives in P5
            }
        )

    def snapshot_message(self, now: int | None = None) -> dict[str, Any]:
        now = now or int(time.time())
        aircraft = sorted(self.table.snapshot(), key=lambda a: a.priority)
        return {
            "type": "snapshot",
            "ts": now,
            "aircraft": [a.model_dump(mode="json") for a in aircraft],
            "vessels": [],  # P9
            "radio2": self._bridge.radio2_status().model_dump(mode="json"),
            "latestPass": None,  # P10
            "health": self.system_health().model_dump(mode="json"),
        }
