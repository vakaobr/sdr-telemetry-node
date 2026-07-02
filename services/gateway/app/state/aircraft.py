"""Live aircraft state table.

RAM-only (rebuildable from readsb within one poll — 03_ARCHITECTURE §7).
Each update cycle ingests a readsb aircraft.json document, applies staleness
rules, computes receiver-relative geometry, maintains trails, and returns the
delta (changed + removed) for WS fan-out.

Implementation note: wire payloads are built as plain dicts and validated into
the generated Aircraft model once per cycle — the generated models don't
validate on attribute assignment, so mutate-in-place would bypass the contract.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.config import Config
from app.models.generated_ws import Aircraft
from app.state import geo
from app.state.priority import LOW_ALT_FT, LOW_ALT_WEIGHT

# synchronous hook: wire payload → flags list (rules engine plugs in here)
FlagsFn = Callable[[dict[str, Any]], list[str]]


@dataclass
class _Tracked:
    payload: dict[str, Any]
    trail: list[list[float]] = field(default_factory=list)
    last_wire: dict | None = None  # payload as last sent to clients
    model: Aircraft | None = None


def _score(p: dict[str, Any]) -> float:
    """Priority score on a wire payload — lower wins (FR-1.4)."""
    if p.get("distanceKm") is None:
        return float("inf")
    alt = p.get("altFt")
    weight = LOW_ALT_WEIGHT if alt is not None and alt < LOW_ALT_FT else 1.0
    return p["distanceKm"] * weight


class AircraftTable:
    """Holds live aircraft; produces deltas. Not thread-safe — single asyncio owner."""

    def __init__(self, config: Config, flags_fn: FlagsFn | None = None) -> None:
        self._cfg = config
        self._flags_fn = flags_fn
        self._tracked: dict[str, _Tracked] = {}

    # -- public ---------------------------------------------------------------

    def snapshot(self) -> list[Aircraft]:
        return [t.model for t in self._tracked.values() if t.model is not None]

    def count(self) -> int:
        return len(self._tracked)

    def get(self, icao: str) -> Aircraft | None:
        t = self._tracked.get(icao.lower())
        return t.model if t else None

    def set_enrichment(self, icao: str, enrich: dict[str, Any] | None) -> None:
        """Apply an async enrichment result; emitted as a delta on the next cycle."""
        t = self._tracked.get(icao.lower())
        if t and t.payload:
            t.payload["enrich"] = enrich

    def flags_of(self, icao: str) -> list[str]:
        t = self._tracked.get(icao.lower())
        return list(t.payload.get("flags", [])) if t and t.payload else []

    def update_from_readsb(self, doc: dict, now: int) -> tuple[list[Aircraft], list[str]]:
        """Ingest one aircraft.json document.

        Returns (updated, removed_icaos): aircraft whose wire form changed
        (including priority churn), and aircraft expired by staleness/absence.
        """
        seen_icaos: set[str] = set()

        for raw in doc.get("aircraft", []):
            icao = (raw.get("hex") or "").lower()
            if len(icao) != 6 or not all(c in "0123456789abcdef" for c in icao):
                continue  # non-ICAO synthetics (~hex TIS-B) and malformed entries
            if float(raw.get("seen", 0)) > self._cfg.adsb.staleness_msg_s:
                continue  # readsb still lists it; we consider it gone
            seen_icaos.add(icao)
            entry = self._tracked.setdefault(icao, _Tracked(payload={}))
            self._apply(entry, icao, raw, now)

        removed = [icao for icao in list(self._tracked) if icao not in seen_icaos]
        for icao in removed:
            del self._tracked[icao]

        # global priority ordering, stamped into payloads (FR-1.4)
        ordered = sorted(
            self._tracked.values(),
            key=lambda t: (_score(t.payload), -t.payload["lastSeen"], t.payload["icao"]),
        )
        for i, t in enumerate(ordered):
            t.payload["priority"] = i

        # wire-level change detection → validated models for changed aircraft
        updated: list[Aircraft] = []
        for icao in seen_icaos:
            t = self._tracked[icao]
            if t.payload != t.last_wire:
                t.last_wire = dict(t.payload)
                t.model = Aircraft.model_validate(t.payload)
                updated.append(t.model)

        return updated, removed

    # -- internals ------------------------------------------------------------

    def _apply(self, entry: _Tracked, icao: str, raw: dict, now: int) -> None:
        cfg = self._cfg

        alt = raw.get("alt_baro", raw.get("alt_geom"))
        alt_ft = 0 if alt == "ground" else (int(alt) if alt is not None else None)
        vr = raw.get("baro_rate", raw.get("geom_rate"))

        p: dict[str, Any] = {
            "icao": icao,
            "callsign": (raw.get("flight") or "").strip() or None,
            "altFt": alt_ft,
            "gsKt": raw.get("gs"),
            "vrFpm": int(vr) if vr is not None else None,
            "track": raw.get("track"),
            "squawk": raw.get("squawk"),
            "rssi": raw.get("rssi"),
            "lastSeen": now - int(float(raw.get("seen", 0))),
            "priority": entry.payload.get("priority", 0),
            "flags": entry.payload.get("flags", []),  # interesting-rules fill these in P5
            "enrich": entry.payload.get("enrich"),  # enrichment fills this in P5
            "lat": None,
            "lon": None,
            "distanceKm": None,
            "bearingDeg": None,
        }

        # position is only trusted while fresh (FR-1.3)
        seen_pos = raw.get("seen_pos")
        if (
            raw.get("lat") is not None
            and seen_pos is not None
            and float(seen_pos) <= cfg.adsb.staleness_pos_s
        ):
            lat, lon = float(raw["lat"]), float(raw["lon"])
            p["lat"], p["lon"] = lat, lon
            p["distanceKm"] = round(
                geo.distance_km(cfg.receiver.lat, cfg.receiver.lon, lat, lon), 2
            )
            p["bearingDeg"] = round(
                geo.bearing_deg(cfg.receiver.lat, cfg.receiver.lon, lat, lon), 1
            )
            point = [round(lat, 5), round(lon, 5)]
            if not entry.trail or entry.trail[-1] != point:
                entry.trail.append(point)
                if len(entry.trail) > cfg.adsb.trail_len:
                    del entry.trail[: -cfg.adsb.trail_len]

        p["trail"] = [list(pt) for pt in entry.trail]
        if self._flags_fn is not None:
            p["flags"] = self._flags_fn(p)  # rules run pre-diff: same-tick banners (B1 AC)
        entry.payload = p
