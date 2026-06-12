"""radio2 supervisor entrypoint.

Phase 1: stub that proves the container boots. The FSM, scheduler, and decoder
runners land in Phase 7 per 04_IMPLEMENTATION_PLAN.
"""

from __future__ import annotations

import asyncio
import logging
import signal

log = logging.getLogger("radio2")


async def run() -> None:
    """Idle loop with clean SIGTERM handling — the supervisor shell."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    log.info("radio2 supervisor stub started (phase 1) — awaiting FSM in phase 7")
    await stop.wait()
    log.info("radio2 supervisor stopping")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
