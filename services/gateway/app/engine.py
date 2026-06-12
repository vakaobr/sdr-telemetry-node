"""Gateway engine: the 1 Hz heartbeat tying ingest → state → rules → WS fan-out.

One asyncio task owns the whole cycle (deterministic, testable via tick()):
  1. poll readsb aircraft.json
  2. diff into AircraftTable (rules flags computed in-diff) → aircraft_delta
  3. fire interesting events for newly-hit rules (WS + MQTT)
  4. schedule async enrichment for new aircraft; results land on later ticks
  5. feed the sightings recorder (batched persistence, ADR-005)
  6. drain MQTT bridge events → typed WS messages
  7. periodic system_health broadcast
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from app.bus.mqtt import MqttBridge
from app.config import Config, WatchlistEntry
from app.enrich.service import Enricher
from app.ingest.readsb import ReadsbClient
from app.models.generated_ws import AdsbHealth, SystemHealth
from app.persist.sightings import SightingsRecorder
from app.rules import interesting as rules
from app.state.aircraft import AircraftTable
from app.state.vessels import VesselTable
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
        enricher: Enricher | None = None,
        recorder: SightingsRecorder | None = None,
    ) -> None:
        self.config = config
        self._cfg = config
        self._readsb = readsb
        self._bridge = bridge
        self.hub = hub
        self._enricher = enricher
        self._recorder = recorder
        self.watchlist: list[WatchlistEntry] = list(config.watchlist)
        self.table = AircraftTable(config, flags_fn=self._compute_flags)
        self.vessels = VesselTable()

        self._pending_enrich: set[str] = set()
        self._enriched_callsign: dict[str, str | None] = {}  # callsign used at last enrich
        self._fired_rules: dict[str, set[str]] = {}  # icao → rule ids already alerted
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
            await self._fire_rule_events(updated, now)
            self._schedule_enrichment(updated)
            if self._recorder:
                for ac in updated:
                    self._recorder.observe(ac.model_dump(mode="json"))
                await self._recorder.on_removed(removed)
                await self._recorder.maybe_flush()
            for icao in removed:
                self._fired_rules.pop(icao, None)
                self._pending_enrich.discard(icao)
                self._enriched_callsign.pop(icao, None)

        # vessels (AIS, event-driven via AISStream client) → delta
        vu, vr = self.vessels.collect_delta(now)
        if vu or vr:
            await self.hub.broadcast(
                {
                    "type": "vessel_delta",
                    "ts": now,
                    "updated": [v.model_dump(mode="json") for v in vu],
                    "removed": vr,
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

    # -- rules ------------------------------------------------------------------

    def _compute_flags(self, payload: dict[str, Any]) -> list[str]:
        """Synchronous hook called by the table pre-diff (same-tick banners)."""
        enrich = payload.get("enrich") or {}
        military = False
        if self._enricher is not None:
            military = self._enricher.military_flag_of.get(payload["icao"], False)
        flags, _ = rules.evaluate(
            icao=payload["icao"],
            callsign=payload.get("callsign"),
            squawk=payload.get("squawk"),
            registration=enrich.get("registration"),
            type_code=enrich.get("typeCode"),
            military=military,
            watchlist=self.watchlist,
        )
        return flags

    async def _fire_rule_events(self, updated: list, now: int) -> None:
        for ac in updated:
            enrich_model = ac.enrich
            military = False
            if self._enricher is not None:
                military = self._enricher.military_flag_of.get(ac.icao, False)
            _, hits = rules.evaluate(
                icao=ac.icao,
                callsign=ac.callsign,
                squawk=ac.squawk,
                registration=enrich_model.registration if enrich_model else None,
                type_code=enrich_model.typeCode if enrich_model else None,
                military=military,
                watchlist=self.watchlist,
            )
            fired = self._fired_rules.setdefault(ac.icao, set())
            for hit in hits:
                if hit.rule in fired:
                    continue
                fired.add(hit.rule)
                event = {
                    "ts": now,
                    "icao": ac.icao,
                    "severity": hit.severity,
                    "rule": hit.rule,
                    "callsign": ac.callsign,
                }
                await self.hub.broadcast({"type": "interesting", **event})
                self._bridge.publish("adsb/interesting", event)  # external consumers
                log.info("interesting: %s %s (%s)", hit.severity, ac.icao, hit.rule)

    # -- enrichment ----------------------------------------------------------------

    def _schedule_enrichment(self, updated: list) -> None:
        if self._enricher is None:
            return
        for ac in updated:
            if ac.icao in self._pending_enrich:
                continue
            if ac.enrich is None:
                pass  # first sight → enrich now (callsign may still be unknown)
            elif ac.callsign and self._enriched_callsign.get(ac.icao) != ac.callsign:
                pass  # callsign arrived/changed after first enrichment → redo once
            else:
                continue
            self._pending_enrich.add(ac.icao)
            asyncio.create_task(self._enrich_one(ac.icao, ac.callsign))

    async def _enrich_one(self, icao: str, callsign: str | None) -> None:
        try:
            result = await self._enricher.enrich(icao, callsign)
            self.table.set_enrichment(icao, result)  # emitted next cycle
            self._enriched_callsign[icao] = callsign
        except Exception:  # enrichment must never hurt tracking
            log.exception("enrichment failed for %s", icao)
        finally:
            self._pending_enrich.discard(icao)

    # -- bus event → WS message mapping ---------------------------------------

    async def _drain_bus_events(self, now: int) -> None:
        radio2_dirty = False
        while not self._bridge.events.empty():
            ev = self._bridge.events.get_nowait()
            topic, payload = ev["topic"], ev["payload"]
            if topic.startswith("radio2/") or (topic.startswith("sys/") and "health" in topic):
                radio2_dirty = True
            elif topic == "atc/activity":
                await self.hub.broadcast(
                    {
                        "type": "atc_activity",
                        "ts": payload.get("ts", now),
                        "channelMhz": payload.get("channelMhz"),
                        "active": payload.get("active"),
                    }
                )
            # adsb/interesting: we are its publisher — bus echo is NOT re-broadcast
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

    def publish_cmd(self, cmd: dict) -> None:
        """Forward a manual-override command to the radio2 supervisor (Node B)."""
        self._bridge.publish("radio2/cmd", cmd, qos=1)

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
                "dbOk": True,
            }
        )

    def snapshot_message(self, now: int | None = None) -> dict[str, Any]:
        now = now or int(time.time())
        aircraft = sorted(self.table.snapshot(), key=lambda a: a.priority)
        return {
            "type": "snapshot",
            "ts": now,
            "aircraft": [a.model_dump(mode="json") for a in aircraft],
            "vessels": [v.model_dump(mode="json") for v in self.vessels.snapshot()],
            "radio2": self._bridge.radio2_status().model_dump(mode="json"),
            "latestPass": None,  # P10
            "health": self.system_health().model_dump(mode="json"),
        }
