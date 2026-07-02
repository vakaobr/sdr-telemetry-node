"""readsb aircraft.json poller (loopback to the co-located ultrafeeder container)."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger("gateway.ingest")

AIRCRAFT_PATH = "/data/aircraft.json"
STATS_PATH = "/data/stats.json"


class ReadsbClient:
    """Thin async client; failures return None so the poll loop degrades, never dies."""

    def __init__(self, base_url: str, timeout_s: float = 2.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_s)
        self._consecutive_failures = 0

    @property
    def healthy(self) -> bool:
        return self._consecutive_failures < 3

    async def fetch_aircraft(self) -> dict | None:
        try:
            r = await self._client.get(AIRCRAFT_PATH)
            r.raise_for_status()
            doc = r.json()
            self._consecutive_failures = 0
            return doc
        except (httpx.HTTPError, ValueError) as e:
            self._consecutive_failures += 1
            if self._consecutive_failures == 3:  # log once at the threshold, not every second
                log.warning("readsb unreachable x3 (%s) — adsb marked degraded", e)
            return None

    async def fetch_stats(self) -> dict | None:
        try:
            r = await self._client.get(STATS_PATH)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError):
            return None

    async def aclose(self) -> None:
        await self._client.aclose()
