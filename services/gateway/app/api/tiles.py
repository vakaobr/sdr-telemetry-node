"""Offline-first raster tile cache (ADR-008, NFR-5).

Strategy: serve from local cache; on miss, fetch from OSM once (online) and
cache forever — viewed areas become permanently offline-capable. Offline
misses return 404 (Leaflet shows the dark background; no broken layout).
Bulk pre-seeding around the receiver is scripts/make-tilepack.sh's job.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Response
from fastapi.responses import FileResponse

from app.api.errors import Problem

log = logging.getLogger("gateway.tiles")

UPSTREAM = "https://tile.openstreetmap.org"
USER_AGENT = "sdr-telemetry-node/0.1 (self-hosted aviation dashboard; LAN-local cache)"
MAX_ZOOM = 12
TILE_DIR = Path("/data/tiles")
CACHE_HEADERS = {"Cache-Control": "public, max-age=2592000"}

_fetch_semaphore = asyncio.Semaphore(2)  # OSM tile-usage policy: be gentle


def make_tiles_router(tile_dir: Path = TILE_DIR) -> APIRouter:
    r = APIRouter()
    client = httpx.AsyncClient(timeout=10, headers={"User-Agent": USER_AGENT})

    @r.get("/tiles/{z}/{x}/{y}.png")
    async def tile(z: int, x: int, y: int) -> Response:
        if not (0 <= z <= MAX_ZOOM) or not (0 <= x < 2**z) or not (0 <= y < 2**z):
            raise Problem(404, "tile out of range")
        path = tile_dir / str(z) / str(x) / f"{y}.png"
        if path.exists():
            return FileResponse(path, media_type="image/png", headers=CACHE_HEADERS)
        content = await _fetch_and_cache(client, z, x, y, path)
        if content is None:
            raise Problem(404, "tile unavailable offline", "not cached and no internet")
        return Response(content, media_type="image/png", headers=CACHE_HEADERS)

    return r


async def _fetch_and_cache(
    client: httpx.AsyncClient, z: int, x: int, y: int, path: Path
) -> bytes | None:
    """Fetch upstream; cache best-effort. Returns tile bytes, or None when offline."""
    async with _fetch_semaphore:
        if path.exists():  # raced with a concurrent request
            return path.read_bytes()
        try:
            resp = await client.get(f"{UPSTREAM}/{z}/{x}/{y}.png")
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.debug("tile fetch %s/%s/%s failed: %s", z, x, y, e)
            return None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(resp.content)
            tmp.rename(path)  # atomic: no partial tiles
        except OSError as e:  # unowned/full volume — still serve, just uncached
            log.warning("tile cache write failed (%s) — serving uncached", e)
        return resp.content
