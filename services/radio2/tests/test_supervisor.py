"""Supervisor integration (P7):
- simulated 24 h at 60×: schedule honored, satellite preempts & returns
- manual override wins and expires
- chaos: a fresh supervisor converges to the scheduled mode quickly
- real-subprocess end-to-end via the scripted fake decoder
"""

import sys
import time
from pathlib import Path

import pytest

from app.config import Config
from app.fsm import Radio2Fsm
from app.proc import ProcessModeRunner
from app.publish import FakePublisher
from app.scheduler.blocks import make_blocks
from app.scheduler.decision import Scheduler
from app.scheduler.passes import Pass
from app.supervisor import Supervisor

FAKE = Path(__file__).parent / "fakes" / "fake_decoder.py"
DAY = 86400
# 2020-11-12 00:00:00 UTC (a midnight, so UTC local minute == wall minute)
MIDNIGHT = 1605139200


class FakeClock:
    def __init__(self, t: float) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class AutoRunner:
    """Instant-ready fake decoder: alive immediately, heartbeat always fresh."""

    def __init__(self) -> None:
        self._alive = False
        self.mode = None
        self.starts: list[str] = []

    async def start(self, mode):
        self.starts.append(mode)
        self.mode = mode
        self._alive = True

    async def stop(self):
        self._alive = False

    async def kill(self):
        self._alive = False

    def alive(self):
        return self._alive

    def seconds_since_heartbeat(self):
        return 0.0


class FakePredictor:
    def __init__(self, passes: list[Pass]) -> None:
        self._passes = passes

    def predict(self, start, end):
        return [p for p in self._passes if p.los >= start and p.aos <= end]


def build(passes=None, blocks=None, clock_t=MIDNIGHT):
    clock = FakeClock(clock_t)
    cfg = Config.model_validate({"receiver": {"lat": 38.7, "lon": -9.1}, "timezone": "UTC"})
    scheduler = Scheduler(
        FakePredictor(passes or []),
        make_blocks(blocks or [("atc", "07:00", "23:00"), ("ais", "23:00", "07:00")]),
        "UTC",
    )
    runner = AutoRunner()
    fsm = Radio2Fsm(runner, clock=clock)
    pub = FakePublisher()
    sup = Supervisor(cfg, fsm, scheduler, pub, clock=clock)
    return clock, fsm, scheduler, runner, pub, sup


async def settle(sup, clock, until_t, step_s=30):
    """Advance the fake clock to until_t, stepping every step_s seconds."""
    while clock.t < until_t:
        clock.t = min(clock.t + step_s, until_t)
        await sup.step()


@pytest.mark.asyncio
async def test_simulated_day_schedule_and_preemption():
    # one NOAA pass at 12:00 UTC for 10 min
    aos = MIDNIGHT + 12 * 3600
    passes = [Pass("NOAA 19", aos, aos + 600, 45.0)]
    clock, fsm, _sched, _runner, pub, sup = build(passes=passes)

    # 02:00 → AIS (night block)
    await settle(sup, clock, MIDNIGHT + 2 * 3600)
    assert fsm.active_mode == "ais"

    # 08:00 → ATC (day block)
    await settle(sup, clock, MIDNIGHT + 8 * 3600)
    assert fsm.active_mode == "atc"

    # 12:05 → satellite preempts ATC
    await settle(sup, clock, aos + 300)
    assert fsm.active_mode == "satellite"

    # 12:30 → pass over (LOS 12:10), back to ATC
    await settle(sup, clock, aos + 1800)
    assert fsm.active_mode == "atc"

    # publisher saw the preempt→return as mode changes
    modes = [m["mode"] for m in pub.modes]
    assert "satellite" in modes
    assert modes.index("satellite") < len(modes) - 1  # something after satellite
    assert modes[-1] == "atc"


@pytest.mark.asyncio
async def test_manual_override_wins_then_expires():
    clock, fsm, _s, _r, _pub, sup = build(clock_t=MIDNIGHT + 8 * 3600)  # daytime=atc
    await settle(sup, clock, clock.t + 120)
    assert fsm.active_mode == "atc"

    sup.on_command({"mode": "ais", "durationS": 600})  # force AIS for 10 min
    await settle(sup, clock, clock.t + 120)
    assert fsm.active_mode == "ais"

    await settle(sup, clock, clock.t + 1200)  # past expiry → back to scheduled atc
    assert fsm.active_mode == "atc"


@pytest.mark.asyncio
async def test_auto_command_releases_override():
    clock, fsm, _s, _r, _pub, sup = build(clock_t=MIDNIGHT + 8 * 3600)
    sup.on_command({"mode": "satellite"})
    await settle(sup, clock, clock.t + 120)
    assert fsm.active_mode == "satellite"
    sup.on_command({"mode": "auto"})
    await settle(sup, clock, clock.t + 120)
    assert fsm.active_mode == "atc"


@pytest.mark.asyncio
async def test_chaos_fresh_supervisor_converges_within_10_steps():
    """kill -9 → restart: a fresh supervisor reaches the scheduled mode ≤10 ticks (≤10 s)."""
    clock, fsm, _s, _r, _pub, sup = build(clock_t=MIDNIGHT + 8 * 3600)
    steps = 0
    while fsm.active_mode != "atc" and steps < 10:
        clock.t += 1
        await sup.step()
        steps += 1
    assert fsm.active_mode == "atc"
    assert steps <= 10


# -- real subprocess end-to-end -----------------------------------------------


async def wait_step(sup, predicate, *, timeout=5.0):
    import asyncio

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await sup.step()
        if predicate():
            return True
        await asyncio.sleep(0.1)
    return False


@pytest.mark.asyncio
async def test_real_decoder_process_switch():
    """Real spawn → SIGTERM → respawn through ProcessModeRunner + fake executable."""
    cfg = Config.model_validate({"receiver": {"lat": 38.7, "lon": -9.1}})
    scheduler = Scheduler(FakePredictor([]), make_blocks([]), "UTC")
    runner = ProcessModeRunner(
        lambda mode: [sys.executable, str(FAKE), mode],
        clock=time.monotonic,
        env={"FAKE_MODE": "run", "PATH": __import__("os").environ.get("PATH", "")},
    )
    fsm = Radio2Fsm(runner, clock=time.monotonic)
    pub = FakePublisher()
    sup = Supervisor(cfg, fsm, scheduler, pub, clock=time.time)

    sup.on_command({"mode": "atc"})
    assert await wait_step(sup, lambda: fsm.active_mode == "atc"), "atc never came up"
    assert runner.alive()

    sup.on_command({"mode": "ais"})
    assert await wait_step(sup, lambda: fsm.active_mode == "ais"), "ais never came up"
    assert runner.alive()

    sup.on_command({"mode": "idle"})
    assert await wait_step(sup, lambda: fsm.active_mode == "idle" and not runner.alive())
    assert {"atc", "ais"} <= {m["mode"] for m in pub.modes}
