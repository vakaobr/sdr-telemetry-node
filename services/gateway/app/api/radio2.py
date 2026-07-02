"""Manual radio-2 override (FR-4.2, P7.7).

POST /api/v1/radio2/mode publishes a radio2/cmd the supervisor consumes. A
satellite pass in progress is protected: the override is rejected with 409
unless force:true (UX: don't accidentally interrupt an unrepeatable pass).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.api.errors import Problem
from app.engine import Engine

VALID_MODES = {"atc", "ais", "satellite", "idle", "auto"}


class ModeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str
    duration_s: int | None = Field(default=None, ge=1)
    force: bool = False


def make_radio2_router(get_engine: Callable[[], Engine]) -> APIRouter:
    r = APIRouter(prefix="/api/v1/radio2")

    @r.post("/mode")
    async def set_mode(body: dict) -> JSONResponse:
        try:
            cmd = ModeCommand.model_validate(body)
        except ValidationError as e:
            raise Problem(422, "invalid mode command", str(e.errors()[:3])) from e
        if cmd.mode not in VALID_MODES:
            raise Problem(422, "invalid mode", f"mode must be one of {sorted(VALID_MODES)}")

        engine = get_engine()
        status = engine.radio2_status()
        if status.mode == "satellite" and cmd.mode != "auto" and not cmd.force:
            raise Problem(
                409,
                "satellite pass in progress",
                "a pass is being captured; retry with force:true to interrupt it",
            )

        payload = {"ts": int(time.time()), "mode": cmd.mode}
        if cmd.duration_s:
            payload["durationS"] = cmd.duration_s
        if cmd.force:
            payload["force"] = True
        engine.publish_cmd(payload)
        return JSONResponse(status_code=202, content={"accepted": cmd.mode})

    return r
