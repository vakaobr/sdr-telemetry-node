"""REST read surface: aircraft, radio2, system (03_ARCHITECTURE §4)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.errors import Problem
from app.engine import Engine


def make_api_router(engine: Engine) -> APIRouter:
    r = APIRouter(prefix="/api/v1")

    @r.get("/aircraft")
    async def list_aircraft() -> list[dict]:
        return [
            a.model_dump(mode="json")
            for a in sorted(engine.table.snapshot(), key=lambda a: a.priority)
        ]

    @r.get("/aircraft/{icao}")
    async def get_aircraft(icao: str) -> dict:
        ac = engine.table.get(icao)
        if ac is None:
            raise Problem(404, "aircraft not tracked", f"icao {icao!r} is not in the live set")
        return ac.model_dump(mode="json")

    @r.get("/radio2")
    async def radio2() -> dict:
        return engine.radio2_status().model_dump(mode="json")

    @r.get("/system")
    async def system() -> dict:
        return engine.system_health().model_dump(mode="json")

    return r
