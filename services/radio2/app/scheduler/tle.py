"""TLE cache with opportunistic online refresh (FR-4.3, NFR-5).

Cached to disk so pass prediction works offline; refreshed from CelesTrak when
the network is up. Stale beyond STALE_WARN_DAYS surfaces a warning the UI shows
(FR-4.3); we keep using stale TLEs rather than going blind.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger("radio2.tle")

CELESTRAK_WEATHER = "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle"
STALE_WARN_DAYS = 14.0


class TleCache:
    def __init__(self, path: str | Path, url: str = CELESTRAK_WEATHER) -> None:
        self._path = Path(path)
        self._url = url

    def load(self) -> str | None:
        return self._path.read_text() if self._path.exists() else None

    def age_days(self) -> float | None:
        if not self._path.exists():
            return None
        return (time.time() - self._path.stat().st_mtime) / 86400.0

    @property
    def stale(self) -> bool:
        age = self.age_days()
        return age is None or age > STALE_WARN_DAYS

    async def refresh(self, client: httpx.AsyncClient | None = None) -> bool:
        """Fetch fresh TLEs; return True on success. Fail-soft (keeps old cache)."""
        owns = client is None
        client = client or httpx.AsyncClient(timeout=15)
        try:
            r = await client.get(self._url)
            r.raise_for_status()
            text = r.text
            if "1 " not in text or len(text) < 100:
                log.warning("TLE refresh returned suspicious content; keeping cache")
                return False
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(text)
            tmp.rename(self._path)
            log.info("TLEs refreshed (%d bytes)", len(text))
            return True
        except httpx.HTTPError as e:
            log.info("TLE refresh failed (%s) — using cached", e)
            return False
        finally:
            if owns:
                await client.aclose()
