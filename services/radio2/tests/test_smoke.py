"""radio2 smoke test: supervisor entrypoint starts and stops cleanly on signal.

With no CONFIG_PATH present it idles (off-hardware safe) and must still exit
promptly on SIGTERM.
"""

import asyncio
import os
import signal

import pytest

from app.main import run


@pytest.mark.asyncio
async def test_supervisor_starts_and_stops_on_sigterm(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "absent.yaml"))  # → idle path
    task = asyncio.create_task(run())
    await asyncio.sleep(0.05)
    assert not task.done()
    os.kill(os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(task, timeout=2)
