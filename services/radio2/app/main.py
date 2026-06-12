"""radio2 supervisor entrypoint.

Builds scheduler + FSM + MQTT publisher from config and runs the reconciliation
loop. Off-hardware-safe: if config is absent it idles cleanly (the Phase-1 smoke
behaviour); decoders are real on Node B, or the scripted fake when RADIO2_FAKE
points at the fake-decoder script.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import sys
import time

from app.config import ConfigError, load_config
from app.decoders import real_command_for
from app.fsm import Radio2Fsm
from app.proc import ProcessModeRunner
from app.publish import PahoPublisher
from app.scheduler.blocks import make_blocks
from app.scheduler.decision import Scheduler
from app.scheduler.passes import PassPredictor
from app.scheduler.tle import TleCache
from app.supervisor import Supervisor

log = logging.getLogger("radio2")

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/config.yaml")
TLE_PATH = os.environ.get("TLE_PATH", "/data/tles.txt")
TICK_S = 1.0


def _command_for():
    """Real decoder commands, or the scripted fake when RADIO2_FAKE is set."""
    fake = os.environ.get("RADIO2_FAKE")
    if fake:
        return lambda mode: [sys.executable, fake, mode]
    cfg = load_config(CONFIG_PATH)
    return real_command_for(cfg.radio2, cfg.radio2.sdr_serial)


async def run() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format='{"ts":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","msg":"%(message)s"}',
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    try:
        cfg = load_config(CONFIG_PATH)
    except ConfigError as e:
        log.warning("no config (%s) — idling", e)
        await stop.wait()
        return

    tle = TleCache(TLE_PATH)
    predictor = PassPredictor(
        cfg.receiver.lat,
        cfg.receiver.lon,
        cfg.receiver.alt_m,
        cfg.radio2.satellite.min_elevation_deg,
    )
    if text := tle.load():
        predictor.load_tles(text)
        log.info(
            "loaded %d satellites (TLEs %.1f d old)", predictor.satellite_count, tle.age_days() or 0
        )

    scheduler = Scheduler(
        predictor,
        make_blocks([(b.mode, b.from_, b.to) for b in cfg.radio2.schedule]),
        cfg.timezone,
    )
    runner = ProcessModeRunner(_command_for(), clock=time.monotonic)
    fsm = Radio2Fsm(runner, clock=time.monotonic)
    publisher = PahoPublisher(cfg.nodes.mqtt_host, cfg.nodes.mqtt_port)
    sup = Supervisor(cfg, fsm, scheduler, publisher, clock=time.time, tle_age_days=tle.age_days())
    publisher.set_command_handler(sup.on_command)
    publisher.start()

    # opportunistic TLE refresh on boot (fail-soft)
    if tle.stale and await tle.refresh():
        predictor.load_tles(tle.load() or "")

    log.info("radio2 supervisor running (tz=%s, %d sats)", cfg.timezone, predictor.satellite_count)
    try:
        while not stop.is_set():
            await sup.step()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=TICK_S)
    finally:
        publisher.stop()
        log.info("radio2 supervisor stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
