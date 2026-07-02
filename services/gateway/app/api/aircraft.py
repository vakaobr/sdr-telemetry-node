"""REST surface: aircraft, radio2, system, config, watchlist (03_ARCHITECTURE §4)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter
from pydantic import ValidationError

from app.api.errors import Problem
from app.config import WatchlistEntry
from app.engine import Engine

WATCHLIST_PATH = Path(os.environ.get("WATCHLIST_PATH", "/data/watchlist.json"))


def load_watchlist_overrides(path: Path = WATCHLIST_PATH) -> list[WatchlistEntry]:
    """Runtime watchlist additions (UI-managed), merged on top of config.yaml's."""
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
        return [WatchlistEntry.model_validate(e) for e in raw]
    except (ValueError, ValidationError):
        return []  # corrupt overrides never block boot; UI can rewrite them


def make_api_router(get_engine: Callable[[], Engine]) -> APIRouter:
    r = APIRouter(prefix="/api/v1")

    @r.get("/aircraft")
    async def list_aircraft() -> list[dict]:
        engine = get_engine()
        return [
            a.model_dump(mode="json")
            for a in sorted(engine.table.snapshot(), key=lambda a: a.priority)
        ]

    @r.get("/aircraft/{icao}")
    async def get_aircraft(icao: str) -> dict:
        ac = get_engine().table.get(icao)
        if ac is None:
            raise Problem(404, "aircraft not tracked", f"icao {icao!r} is not in the live set")
        return ac.model_dump(mode="json")

    @r.get("/vessels")
    async def list_vessels() -> list[dict]:
        return [v.model_dump(mode="json") for v in get_engine().vessels.snapshot()]

    @r.get("/radio2")
    async def radio2() -> dict:
        return get_engine().radio2_status().model_dump(mode="json")

    @r.get("/system")
    async def system() -> dict:
        return get_engine().system_health().model_dump(mode="json")

    @r.get("/config")
    async def config() -> dict:
        """Client-safe config subset: receiver location + UI hints (no secrets)."""
        from app.api.tiles import openaip_key

        cfg = get_engine().config
        return {
            "receiver": {"lat": cfg.receiver.lat, "lon": cfg.receiver.lon},
            "ui": {
                "rangeRingsKm": [50, 100, 150],
                "tvRotation": cfg.ui.tv_rotation,
                "airspaceOverlay": openaip_key() is not None,  # show toggle only if keyed
            },
        }

    @r.get("/config/watchlist")
    async def get_watchlist() -> list[dict]:
        return [e.model_dump(by_alias=True) for e in get_engine().watchlist]

    @r.put("/config/watchlist")
    async def put_watchlist(entries: list[dict]) -> dict:
        """Replace the runtime watchlist overrides (config.yaml entries persist).

        Overrides live in /data/watchlist.json — config.yaml stays read-only
        and authoritative for its own entries (FR-10.1).
        """
        try:
            validated = [WatchlistEntry.model_validate(e) for e in entries]
        except ValidationError as e:
            raise Problem(422, "invalid watchlist", str(e.errors()[:3])) from e
        WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        WATCHLIST_PATH.write_text(
            json.dumps([v.model_dump(by_alias=True) for v in validated], indent=1)
        )
        engine = get_engine()
        engine.watchlist = list(engine.config.watchlist) + validated
        return {"active": len(engine.watchlist)}

    return r
