"""Sightings recorder (FR-9.1, ADR-005): per-contact summaries, batched writes.

Open contacts are RAM state; rows are written on contact close and refreshed
on a 60 s batch flush — never per-message. Crash loss window ≤ 60 s (NFR-12).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.persist.db import Database

log = logging.getLogger("gateway.persist.sightings")

FLUSH_EVERY_S = 60


@dataclass
class _Contact:
    icao: str
    first_seen: int
    last_seen: int
    callsign: str | None = None
    registration: str | None = None
    type_code: str | None = None
    min_distance_km: float | None = None
    max_range_km: float | None = None
    max_alt_ft: int | None = None
    flags: set[str] = field(default_factory=set)
    squawk_emergency: str | None = None
    row_id: int | None = None
    dirty: bool = True


class SightingsRecorder:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._open: dict[str, _Contact] = {}
        self._last_flush = time.monotonic()

    @property
    def open_contacts(self) -> int:
        return len(self._open)

    def observe(self, payload: dict) -> None:
        """Feed one updated wire payload into the open-contact state (RAM only)."""
        icao = payload["icao"]
        c = self._open.get(icao)
        if c is None:
            c = self._open[icao] = _Contact(
                icao=icao, first_seen=payload["lastSeen"], last_seen=payload["lastSeen"]
            )
        c.last_seen = max(c.last_seen, payload["lastSeen"])
        c.callsign = payload.get("callsign") or c.callsign
        enrich = payload.get("enrich") or {}
        c.registration = enrich.get("registration") or c.registration
        c.type_code = enrich.get("typeCode") or c.type_code
        d = payload.get("distanceKm")
        if d is not None:
            c.min_distance_km = d if c.min_distance_km is None else min(c.min_distance_km, d)
            c.max_range_km = d if c.max_range_km is None else max(c.max_range_km, d)
        alt = payload.get("altFt")
        if alt is not None:
            c.max_alt_ft = alt if c.max_alt_ft is None else max(c.max_alt_ft, alt)
        c.flags.update(payload.get("flags") or [])
        if payload.get("squawk") in ("7500", "7600", "7700"):
            c.squawk_emergency = payload["squawk"]
        c.dirty = True

    async def on_removed(self, icaos: list[str]) -> None:
        """Contact closed — final row write for each."""
        closing = [self._open.pop(i) for i in icaos if i in self._open]
        if closing:
            await self._write(closing)

    async def maybe_flush(self) -> None:
        """60 s batch refresh of open contacts (long flights get periodic durability)."""
        if time.monotonic() - self._last_flush < FLUSH_EVERY_S:
            return
        self._last_flush = time.monotonic()
        dirty = [c for c in self._open.values() if c.dirty]
        if dirty:
            await self._write(dirty)

    async def _write(self, contacts: list[_Contact]) -> None:
        conn = self._db.conn
        for c in contacts:
            if c.row_id is None:
                cur = await conn.execute(
                    "INSERT INTO sightings (icao, callsign, registration, type_code, "
                    "first_seen, last_seen, min_distance_km, max_range_km, max_alt_ft, "
                    "flags, squawk_emergency) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        c.icao,
                        c.callsign,
                        c.registration,
                        c.type_code,
                        c.first_seen,
                        c.last_seen,
                        c.min_distance_km,
                        c.max_range_km,
                        c.max_alt_ft,
                        ",".join(sorted(c.flags)),
                        c.squawk_emergency,
                    ),
                )
                c.row_id = cur.lastrowid
            else:
                await conn.execute(
                    "UPDATE sightings SET callsign=?, registration=?, type_code=?, "
                    "last_seen=?, min_distance_km=?, max_range_km=?, max_alt_ft=?, "
                    "flags=?, squawk_emergency=? WHERE id=?",
                    (
                        c.callsign,
                        c.registration,
                        c.type_code,
                        c.last_seen,
                        c.min_distance_km,
                        c.max_range_km,
                        c.max_alt_ft,
                        ",".join(sorted(c.flags)),
                        c.squawk_emergency,
                        c.row_id,
                    ),
                )
            c.dirty = False
        await conn.commit()
        log.debug("sightings flush: %d rows", len(contacts))
