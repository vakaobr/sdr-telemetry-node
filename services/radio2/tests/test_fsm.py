"""Exhaustive FSM transition table (P7 unit tests).

Fake runner + manual clock → deterministic, no real processes, no sleeps.
"""

import pytest

from app.fsm import (
    BACKOFF_S,
    HEARTBEAT_FRESH_S,
    MAX_RETRIES,
    STARTUP_TIMEOUT_S,
    STOP_GRACE_S,
    Radio2Fsm,
    State,
)


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class FakeRunner:
    """Test-controllable ModeRunner. The child becomes RUNNING only after beat()."""

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self._alive = False
        self._hb = 0.0
        self.mode: str | None = None
        self.starts: list[str] = []
        self.stops = 0
        self.kills = 0
        self.fail_start = False  # next start spawns a child that never comes alive

    async def start(self, mode: str) -> None:
        self.starts.append(mode)
        self.mode = mode
        self._alive = not self.fail_start
        self._hb = 0.0  # no heartbeat yet → STARTING waits for beat()

    async def stop(self) -> None:
        self.stops += 1
        self._alive = False

    async def kill(self) -> None:
        self.kills += 1
        self._alive = False

    def alive(self) -> bool:
        return self._alive

    def seconds_since_heartbeat(self) -> float:
        return self._clock.t - self._hb if self._hb else float("inf")

    # test controls
    def beat(self) -> None:
        self._hb = self._clock.t

    def die(self) -> None:
        self._alive = False


@pytest.fixture()
def rig():
    clock = FakeClock()
    runner = FakeRunner(clock)
    machine = Radio2Fsm(runner, clock=clock)
    return clock, runner, machine


async def drive(machine: Radio2Fsm, n: int = 1) -> None:
    for _ in range(n):
        await machine.step()


# -- happy path ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_idle_to_running(rig):
    clock, runner, m = rig
    m.set_target("atc")
    await m.step()
    assert m.state == State.STARTING and runner.starts == ["atc"]
    runner.beat()
    await m.step()
    assert m.state == State.RUNNING and m.active_mode == "atc"


@pytest.mark.asyncio
async def test_idle_stays_idle_without_target(rig):
    _clock, runner, m = rig
    await drive(m, 3)
    assert m.state == State.IDLE and runner.starts == []


@pytest.mark.asyncio
async def test_clean_mode_switch(rig):
    clock, runner, m = rig
    m.set_target("atc")
    await m.step()
    runner.beat()
    await m.step()
    assert m.state == State.RUNNING

    m.set_target("ais")
    await m.step()
    assert m.state == State.STOPPING and runner.stops == 1
    await m.step()  # child confirmed down → start next
    assert m.state == State.STARTING and runner.starts == ["atc", "ais"]
    runner.beat()
    await m.step()
    assert m.state == State.RUNNING and m.active_mode == "ais"


@pytest.mark.asyncio
async def test_running_to_idle(rig):
    clock, runner, m = rig
    m.set_target("atc")
    await m.step()
    runner.beat()
    await m.step()
    m.set_target("idle")
    await m.step()  # STOPPING
    await m.step()  # → IDLE
    assert m.state == State.IDLE and m.active_mode == "idle"


# -- preemption ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_preempt_during_starting(rig):
    """Satellite pass arrives while ATC is still starting → abort, switch."""
    clock, runner, m = rig
    m.set_target("atc")
    await m.step()
    assert m.state == State.STARTING  # not yet beat → still starting
    m.set_target("satellite")
    await m.step()
    assert m.state == State.STOPPING  # aborted the half-started ATC
    await m.step()
    assert m.state == State.STARTING and runner.starts == ["atc", "satellite"]


# -- faults & retries ----------------------------------------------------------


@pytest.mark.asyncio
async def test_start_failure_faults_then_retries_then_cools_down(rig):
    clock, runner, m = rig
    runner.fail_start = True
    m.set_target("atc")

    await m.step()  # STARTING (child dead on arrival)
    await m.step()  # detects not alive → FAULTED (retries=1)
    assert m.state == State.FAULTED

    # retry after backoff[0]
    clock.advance(BACKOFF_S[0])
    await m.step()
    assert m.state == State.STARTING and len(runner.starts) == 2
    await m.step()  # FAULTED (retries=2)
    clock.advance(BACKOFF_S[1])
    await m.step()
    assert len(runner.starts) == 3  # retry
    await m.step()  # FAULTED (retries=3)

    # retries >= MAX → cooldown + back to IDLE, mode skipped
    await m.step()
    assert m.state == State.IDLE
    assert "atc" in m.faulted_modes
    assert len(runner.starts) == MAX_RETRIES  # 3 total attempts


@pytest.mark.asyncio
async def test_backoff_not_elapsed_holds_in_faulted(rig):
    clock, runner, m = rig
    runner.fail_start = True
    m.set_target("atc")
    await m.step()
    await m.step()  # FAULTED
    await m.step()  # backoff not elapsed → still FAULTED
    assert m.state == State.FAULTED and len(runner.starts) == 1


@pytest.mark.asyncio
async def test_startup_timeout_faults(rig):
    clock, runner, m = rig
    m.set_target("atc")
    await m.step()  # STARTING, child alive but never beats
    clock.advance(STARTUP_TIMEOUT_S + 1)
    await m.step()
    assert m.state == State.FAULTED


@pytest.mark.asyncio
async def test_running_child_exit_faults(rig):
    clock, runner, m = rig
    m.set_target("atc")
    await m.step()
    runner.beat()
    await m.step()
    assert m.state == State.RUNNING
    runner.die()
    await m.step()
    assert m.state == State.FAULTED


@pytest.mark.asyncio
async def test_watchdog_faults_on_stale_heartbeat(rig):
    clock, runner, m = rig
    m.set_target("atc")
    await m.step()
    runner.beat()
    await m.step()
    assert m.state == State.RUNNING
    clock.advance(HEARTBEAT_FRESH_S + 1)  # heartbeat goes stale
    await m.step()
    assert m.state == State.FAULTED and m.reason.startswith("watchdog")


@pytest.mark.asyncio
async def test_fault_abandoned_when_target_changes(rig):
    clock, runner, m = rig
    runner.fail_start = True
    m.set_target("atc")
    await m.step()
    await m.step()  # FAULTED on atc
    runner.fail_start = False
    m.set_target("ais")  # operator/scheduler wants something else
    await m.step()
    assert m.state == State.STARTING and runner.starts[-1] == "ais"


# -- stop escalation -----------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_grace_then_sigkill(rig):
    clock, runner, m = rig
    m.set_target("atc")
    await m.step()
    runner.beat()
    await m.step()
    m.set_target("idle")
    await m.step()  # STOPPING; runner.stop() called
    # simulate a child that ignores SIGTERM: keep it alive
    runner._alive = True
    clock.advance(STOP_GRACE_S + 1)
    await m.step()
    assert runner.kills == 1  # escalated to SIGKILL


@pytest.mark.asyncio
async def test_single_owner_invariant_no_start_before_stop_confirmed(rig):
    """A new child must never spawn while the previous is still alive."""
    clock, runner, m = rig
    m.set_target("atc")
    await m.step()
    runner.beat()
    await m.step()
    m.set_target("ais")
    await m.step()  # STOPPING
    runner._alive = True  # pretend stop hasn't completed yet
    await m.step()
    assert m.state == State.STOPPING and len(runner.starts) == 1  # did NOT start ais yet
    runner._alive = False
    await m.step()
    assert len(runner.starts) == 2  # only now
