"""radio2 smoke test: supervisor starts and stops cleanly on signal."""

import asyncio
import os
import signal

import pytest

from app.main import run


@pytest.mark.asyncio
async def test_supervisor_starts_and_stops_on_sigterm():
    task = asyncio.create_task(run())
    await asyncio.sleep(0.05)  # let it install handlers
    assert not task.done()
    os.kill(os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(task, timeout=2)
