"""Satellite pass prediction via Skyfield SGP4 (FR-4.3, offline-capable).

Self-contained: topocentric rise/culminate/set of an EarthSatellite over the
receiver needs only the TLE — no ephemeris download, no network. The timescale
is built-in so we never reach for IERS files (offline-first).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from skyfield.api import EarthSatellite, load, wgs84

log = logging.getLogger("radio2.passes")


@dataclass(frozen=True)
class Pass:
    satellite: str
    aos: int  # unix seconds, acquisition of signal (rise above min elevation)
    los: int  # loss of signal (set below min elevation)
    max_el: float  # peak elevation degrees


def parse_tles(text: str, ts) -> list[EarthSatellite]:
    """Parse CelesTrak TLE text (name / line1 / line2 triples)."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    sats: list[EarthSatellite] = []

    def _try(line1: str, line2: str, name: str) -> None:
        try:
            sats.append(EarthSatellite(line1, line2, name, ts))
        except (ValueError, IndexError):  # malformed element set in the feed → skip it
            log.debug("skipping malformed TLE %r", name)

    i = 0
    while i < len(lines):
        if lines[i].startswith("1 ") and i + 1 < len(lines) and lines[i + 1].startswith("2 "):
            _try(lines[i], lines[i + 1], "UNKNOWN")  # nameless pair (rare)
            i += 2
        elif i + 2 < len(lines) and lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            _try(lines[i + 1], lines[i + 2], lines[i].strip())
            i += 3
        else:
            i += 1
    return sats


class PassPredictor:
    def __init__(self, lat: float, lon: float, alt_m: float, min_elevation_deg: float) -> None:
        self._ts = load.timescale(builtin=True)
        self._obs = wgs84.latlon(lat, lon, elevation_m=alt_m)
        self._min_el = min_elevation_deg
        self._sats: list[EarthSatellite] = []

    @property
    def satellite_count(self) -> int:
        return len(self._sats)

    def load_tles(self, text: str) -> int:
        self._sats = parse_tles(text, self._ts)
        return len(self._sats)

    def predict(self, start_unix: int, end_unix: int) -> list[Pass]:
        t0 = self._ts.from_datetime(datetime.fromtimestamp(start_unix, UTC))
        t1 = self._ts.from_datetime(datetime.fromtimestamp(end_unix, UTC))
        out: list[Pass] = []
        for sat in self._sats:
            try:
                times, events = sat.find_events(self._obs, t0, t1, altitude_degrees=self._min_el)
            except Exception:  # bad/expired TLE — skip that satellite, never crash
                log.debug("find_events failed for %s", sat.name, exc_info=True)
                continue
            aos: int | None = None
            culm_el = 0.0
            for t, ev in zip(times, events, strict=False):
                if ev == 0:  # rise
                    aos = int(t.utc_datetime().timestamp())
                    culm_el = 0.0
                elif ev == 1 and aos is not None:  # culminate
                    alt, _az, _d = (sat - self._obs).at(t).altaz()
                    culm_el = alt.degrees
                elif ev == 2 and aos is not None:  # set
                    los = int(t.utc_datetime().timestamp())
                    out.append(Pass(sat.name, aos, los, round(culm_el, 1)))
                    aos = None
        return sorted(out, key=lambda p: p.aos)
