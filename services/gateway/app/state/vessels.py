"""Live vessel (AIS) state table — RAM-only, mirrors AircraftTable in spirit.

Fed by an AIS source (AISStream client, ADR-010); event-driven rather than
polled, so it accumulates upserts and emits a delta of changed vessels plus
stale removals each engine cycle. Only vessels with a position are emitted
(a name-only ShipStaticData waits for its first PositionReport).
"""

from __future__ import annotations

from typing import Any

from app.models.generated_ws import Vessel

DEFAULT_STALENESS_S = 1800  # AIS is intermittent; 30 min (FR-6.3)


class VesselTable:
    def __init__(self, staleness_s: int = DEFAULT_STALENESS_S) -> None:
        self._v: dict[int, dict[str, Any]] = {}
        self._dirty: set[int] = set()
        self._staleness = staleness_s

    def count(self) -> int:
        return sum(1 for v in self._v.values() if v.get("lat") is not None)

    def upsert(
        self,
        mmsi: int,
        *,
        now: int,
        lat: float | None = None,
        lon: float | None = None,
        sog: float | None = None,
        cog: float | None = None,
        name: str | None = None,
        ship_type: int | None = None,
    ) -> None:
        v = self._v.get(mmsi) or {
            "mmsi": mmsi,
            "name": None,
            "lat": None,
            "lon": None,
            "sogKt": None,
            "cogDeg": None,
            "shipType": None,
            "lastSeen": now,
        }
        if lat is not None and lon is not None:
            v["lat"], v["lon"] = lat, lon
        if sog is not None:
            v["sogKt"] = sog
        if cog is not None:
            v["cogDeg"] = cog
        if name:
            v["name"] = name
        if ship_type is not None:
            v["shipType"] = ship_type
        v["lastSeen"] = now
        self._v[mmsi] = v
        self._dirty.add(mmsi)

    def collect_delta(self, now: int) -> tuple[list[Vessel], list[int]]:
        """Vessels changed since last call (with a position) + stale removals."""
        removed = [m for m, v in self._v.items() if now - v["lastSeen"] > self._staleness]
        for m in removed:
            del self._v[m]
            self._dirty.discard(m)
        updated: list[Vessel] = []
        for m in self._dirty:
            v = self._v.get(m)
            if v and v["lat"] is not None:
                updated.append(Vessel.model_validate(v))
        self._dirty.clear()
        return updated, removed

    def snapshot(self) -> list[Vessel]:
        return [Vessel.model_validate(v) for v in self._v.values() if v["lat"] is not None]
