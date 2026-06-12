"""Gateway service entrypoint: wiring + lifespan.

create_app() is the injection seam — tests pass config/clients, production
loads config from CONFIG_PATH and connects to real readsb + mosquitto.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.aircraft import make_api_router
from app.api.errors import install_error_handlers
from app.api.static import mount_web
from app.api.tiles import make_tiles_router
from app.bus.mqtt import MqttBridge
from app.config import Config, load_config
from app.engine import Engine
from app.ingest.readsb import ReadsbClient
from app.ws.hub import Hub
from app.ws.server import make_ws_router

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/config.yaml")

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","msg":"%(message)s"}',
)


def create_app(
    config: Config | None = None,
    readsb: ReadsbClient | None = None,
    bridge: MqttBridge | None = None,
    start_bus: bool = True,
) -> FastAPI:
    if config is None:
        config = load_config(CONFIG_PATH)
    readsb = readsb or ReadsbClient(config.adsb.readsb_url)
    bridge = bridge or MqttBridge(config)
    engine = Engine(config, readsb, bridge, Hub())

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if start_bus:
            bridge.start(asyncio.get_running_loop())
        engine.start()
        yield
        await engine.stop()
        if start_bus:
            bridge.stop()

    app = FastAPI(title="sdr-telemetry-node gateway", version="0.1.0", lifespan=lifespan)
    app.state.config = config
    app.state.engine = engine

    install_error_handlers(app)
    app.include_router(make_api_router(engine))
    app.include_router(make_ws_router(engine))
    app.include_router(make_tiles_router())
    mount_web(app)

    @app.get("/healthz")
    async def healthz() -> dict[str, bool | str]:
        return {"ok": True, "service": "gateway"}

    return app
