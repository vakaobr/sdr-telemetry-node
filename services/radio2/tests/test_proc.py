"""ChildProcess against real scripted fake decoders (P7 — exercises real
spawn/SIGTERM/SIGKILL/heartbeat, the path Python mocks would bypass)."""

import sys
import time
from pathlib import Path

import pytest

from app.proc import ChildProcess, ProcessModeRunner

FAKE = Path(__file__).parent / "fakes" / "fake_decoder.py"


def cmd(mode: str) -> list[str]:
    return [sys.executable, str(FAKE), mode]


async def wait_until(predicate, timeout=3.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        import asyncio

        await asyncio.sleep(interval)
    return False


@pytest.mark.asyncio
async def test_runs_heartbeats_and_terminates_gracefully():
    p = ChildProcess()
    await p.start(cmd("run"), env={"FAKE_MODE": "run"})
    assert await wait_until(lambda: p.heartbeats > 2)
    assert p.alive()
    assert p.seconds_since_heartbeat() < 1.0

    p.terminate()
    assert await wait_until(lambda: not p.alive())
    assert (await p.wait()) == 0


@pytest.mark.asyncio
async def test_fail_mode_exits_nonzero():
    p = ChildProcess()
    await p.start(cmd("fail"), env={"FAKE_MODE": "fail"})
    assert await wait_until(lambda: not p.alive())
    assert (await p.wait()) == 3


@pytest.mark.asyncio
async def test_silent_child_goes_stale_but_stays_alive():
    p = ChildProcess()
    await p.start(cmd("silent"), env={"FAKE_MODE": "silent"})
    assert await wait_until(lambda: p.heartbeats >= 1)
    await __import__("asyncio").sleep(0.3)
    assert p.alive()
    assert p.seconds_since_heartbeat() > 0.2  # watchdog would catch this
    p.terminate()
    await wait_until(lambda: not p.alive())


@pytest.mark.asyncio
async def test_hang_requires_sigkill():
    p = ChildProcess()
    await p.start(cmd("hang"), env={"FAKE_MODE": "hang"})
    assert await wait_until(lambda: p.heartbeats >= 1)
    p.terminate()  # ignored by hang mode
    still_alive = not await wait_until(lambda: not p.alive(), timeout=0.6)
    assert still_alive
    p.kill()  # SIGKILL
    assert await wait_until(lambda: not p.alive())


@pytest.mark.asyncio
async def test_mode_runner_lifecycle():
    runner = ProcessModeRunner(cmd, env={"FAKE_MODE": "run"})
    await runner.start("atc")
    assert await wait_until(lambda: runner.alive() and runner.seconds_since_heartbeat() < 1.0)
    await runner.stop()
    assert await wait_until(lambda: not runner.alive())
