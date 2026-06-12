"""Offline-first raster tile cache (ADR-008, NFR-5).

Two layers, same strategy — serve from local cache; on miss, fetch upstream once
and cache forever, so viewed areas become permanently offline-capable; offline
misses return 404 (Leaflet shows the dark background, no broken layout):
  /tiles/{z}/{x}/{y}.png          OSM base map
  /tiles/openaip/{z}/{x}/{y}.png  OpenAIP airspace overlay (R2) — the API key
                                  stays server-side, never reaches the browser
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, Response
from fastapi.responses import FileResponse

from app.api.errors import Problem

log = logging.getLogger("gateway.tiles")

OSM_UPSTREAM = "https://tile.openstreetmap.org"
USER_AGENT = "sdr-telemetry-node/0.1 (self-hosted aviation dashboard; LAN-local cache)"
OSM_MAX_ZOOM = 12

# OpenAIP overlay (transparent PNG tiles: airspaces, airports, navaids)
OPENAIP_UPSTREAM = "https://api.tiles.openaip.net/api/data/openaip"
OPENAIP_MAX_ZOOM = 14

TILE_DIR = Path("/data/tiles")
CACHE_HEADERS = {"Cache-Control": "public, max-age=2592000"}

_fetch_semaphore = asyncio.Semaphore(2)  # be gentle to upstreams


def openaip_key() -> str | None:
    return os.environ.get("OPENAIP_API_KEY") or None


def _valid(z: int, x: int, y: int, max_zoom: int) -> bool:
    return 0 <= z <= max_zoom and 0 <= x < 2**z and 0 <= y < 2**z


def make_tiles_router(tile_dir: Path = TILE_DIR) -> APIRouter:
    r = APIRouter()
    client = httpx.AsyncClient(timeout=10, headers={"User-Agent": USER_AGENT})

    @r.get("/tiles/{z}/{x}/{y}.png")
    async def osm_tile(z: int, x: int, y: int) -> Response:
        if not _valid(z, x, y, OSM_MAX_ZOOM):
            raise Problem(404, "tile out of range")
        path = tile_dir / "osm" / str(z) / str(x) / f"{y}.png"
        return await _serve(client, f"{OSM_UPSTREAM}/{z}/{x}/{y}.png", path, {})

    @r.get("/tiles/openaip/{z}/{x}/{y}.png")
    async def openaip_tile(z: int, x: int, y: int) -> Response:
        key = openaip_key()
        if not key:
            raise Problem(404, "airspace overlay not configured", "no OPENAIP_API_KEY set")
        if not _valid(z, x, y, OPENAIP_MAX_ZOOM):
            raise Problem(404, "tile out of range")
        path = tile_dir / "openaip" / str(z) / str(x) / f"{y}.png"
        # key via header (current) + query (legacy) — exact method confirmed at deploy
        url = f"{OPENAIP_UPSTREAM}/{z}/{x}/{y}.png?apiKey={key}"
        return await _serve(client, url, path, {"x-openaip-api-key": key})

    return r


async def _serve(client: httpx.AsyncClient, url: str, path: Path, headers: dict) -> Response:
    if path.exists():
        return FileResponse(path, media_type="image/png", headers=CACHE_HEADERS)
    content = await _fetch_and_cache(client, url, path, headers)
    if content is None:
        raise Problem(404, "tile unavailable offline", "not cached and no internet")
    return Response(content, media_type="image/png", headers=CACHE_HEADERS)


async def _fetch_and_cache(
    client: httpx.AsyncClient, url: str, path: Path, headers: dict
) -> bytes | None:
    """Fetch upstream; cache best-effort. Returns tile bytes, or None when offline."""
    async with _fetch_semaphore:
        if path.exists():  # raced with a concurrent request
            return path.read_bytes()
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.debug("tile fetch failed (%s): %s", path, e)
            return None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(resp.content)
            tmp.rename(path)  # atomic: no partial tiles
        except OSError as e:  # unowned/full volume — still serve, just uncached
            log.warning("tile cache write failed (%s) — serving uncached", e)
        return resp.content
