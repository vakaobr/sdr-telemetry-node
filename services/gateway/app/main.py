"""Gateway service entrypoint.

Phase 1: minimal app with health endpoint (the deployable stub the buildx CI
job exercises). Ingest/state/WS arrive in Phase 3 per 04_IMPLEMENTATION_PLAN.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from app.config import Config, load_config

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/config.yaml")


def create_app(config: Config | None = None) -> FastAPI:
    """App factory. Tests inject config; production loads from CONFIG_PATH."""
    if config is None:
        config = load_config(CONFIG_PATH)

    app = FastAPI(title="sdr-telemetry-node gateway", version="0.1.0")
    app.state.config = config

    @app.get("/healthz")
    async def healthz() -> dict[str, bool | str]:
        return {"ok": True, "service": "gateway"}

    return app
