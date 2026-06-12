"""Gateway service entrypoint: wiring + lifespan.

create_app() is the injection seam — tests pass config/clients, production
loads config from CONFIG_PATH and connects to real readsb + mosquitto + SQLite.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.aircraft import load_watchlist_overrides, make_api_router
from app.api.errors import install_error_handlers
from app.api.static import mount_web
from app.api.tiles import make_tiles_router
from app.bus.mqtt import MqttBridge
from app.config import Config, load_config
from app.engine import Engine
from app.enrich import localdb
from app.enrich.service import Enricher
from app.ingest.readsb import ReadsbClient
from app.persist.db import Database
from app.persist.sightings import SightingsRecorder
from app.ws.hub import Hub
from app.ws.server import make_ws_router

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/config.yaml")
DB_PATH = os.environ.get("DB_PATH", "/data/app.db")

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","msg":"%(message)s"}',
)


def create_app(
    config: Config | None = None,
    readsb: ReadsbClient | None = None,
    bridge: MqttBridge | None = None,
    db_path: str | None = None,
    start_bus: bool = True,
) -> FastAPI:
    if config is None:
        config = load_config(CONFIG_PATH)
    readsb = readsb or ReadsbClient(config.adsb.readsb_url)
    bridge = bridge or MqttBridge(config)
    db = Database(db_path or DB_PATH)
    enricher: Enricher | None = None
    recorder: SightingsRecorder | None = None

    # engine is created in lifespan once persistence is open; routers need a
    # late-bound reference, so we use a small holder the closures read through
    holder: dict[str, Engine] = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        nonlocal enricher, recorder
        await db.open()
        enricher = Enricher(config, db)
        recorder = SightingsRecorder(db)
        engine = Engine(config, readsb, bridge, Hub(), enricher, recorder)
        engine.watchlist += load_watchlist_overrides()  # UI-managed additions
        holder["engine"] = engine
        _app.state.engine = engine
        # aircraft-DB import can take ~60 s on a Pi — never blocks startup
        import_task = asyncio.create_task(localdb.ensure_imported(db))
        if start_bus:
            bridge.start(asyncio.get_running_loop())
        engine.start()
        yield
        import_task.cancel()
        await engine.stop()
        if start_bus:
            bridge.stop()
        if enricher:
            await enricher.aclose()
        await db.close()

    app = FastAPI(title="sdr-telemetry-node gateway", version="0.1.0", lifespan=lifespan)
    app.state.config = config

    install_error_handlers(app)
    app.include_router(make_api_router(lambda: holder["engine"]))
    app.include_router(make_ws_router(lambda: holder["engine"]))
    app.include_router(make_tiles_router())
    mount_web(app)

    @app.get("/healthz")
    async def healthz() -> dict[str, bool | str]:
        return {"ok": True, "service": "gateway"}

    return app
