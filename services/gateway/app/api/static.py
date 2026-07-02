"""Serve the built web bundle (volume-mounted — UI updates need no image rebuild)."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

WEB_DIST = Path(os.environ.get("WEB_DIST", "/web/dist"))


def mount_web(app: FastAPI) -> None:
    """Mount the SPA if a build exists; otherwise / explains itself (dev/API-only)."""
    index = WEB_DIST / "index.html"
    if index.exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        async def spa_index() -> FileResponse:
            return FileResponse(index)

        @app.get("/tv", include_in_schema=False)
        async def spa_tv() -> FileResponse:
            return FileResponse(index)  # client routes on pathname (kiosk URL)
    else:

        @app.get("/", include_in_schema=False)
        async def no_ui() -> dict:
            return {
                "service": "sdr-telemetry-node gateway",
                "ui": "not built — see /api/v1/aircraft, /healthz, or tar1090 on :8078",
            }
