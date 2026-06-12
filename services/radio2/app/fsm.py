"""Radio-2 single-owner mode FSM (03_ARCHITECTURE §6, ADR-004).

Exactly one decoder child may hold SDR #2 at a time. The FSM reconciles the
*actual* running mode toward a *target* mode set by the scheduler, driven by
explicit ``step()`` calls against an injected clock and a ModeRunner — so the
whole transition table is deterministic and unit-testable with no real
processes and no sleeps.

States:  IDLE → STARTING(mode) → RUNNING(mode) → STOPPING → STARTING(next)
         any → FAULTED(mode) on start/run failure (retry w/ backoff, then
         cooldown so the scheduler skips the mode and picks the next).

Safety invariant: a new child is only spawned after the prior child's stop is
confirmed (runner.alive() == False) — never two owners of the device.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import StrEnum
from typing import Protocol

log = logging.getLogger("radio2.fsm")

# timing (seconds) — module constants so tests can reference them
HEARTBEAT_FRESH_S = 30.0  # RUNNING with no child heartbeat for this long → watchdog fault
STARTUP_TIMEOUT_S = 15.0  # STARTING with no heartbeat for this long → fault
STOP_GRACE_S = 10.0  # SIGTERM → (grace) → SIGKILL escalation
FAULT_COOLDOWN_S = 120.0  # how long a thrice-failed mode is skipped by the scheduler
MAX_RETRIES = 3
BACKOFF_S = (5.0, 15.0, 60.0)

IDLE_MODE = "idle"


class State(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAULTED = "faulted"


class ModeRunner(Protocol):
    """Owns the lifecycle of one decoder child process for a given mode."""

    async def start(self, mode: str) -> None: ...
    async def stop(self) -> None: ...  # graceful (SIGTERM)
    async def kill(self) -> None: ...  # forceful (SIGKILL)
    def alive(self) -> bool: ...
    def seconds_since_heartbeat(self) -> float: ...


class Radio2Fsm:
    def __init__(self, runner: ModeRunner, *, clock: Callable[[], float]) -> None:
        self._runner = runner
        self._clock = clock
        self.state: State = State.IDLE
        self.mode: str | None = None  # mode being started/run/stopped
        self.target: str = IDLE_MODE
        self.reason: str = ""
        self._retries = 0
        self._since = clock()  # time the current state was entered
        self._faulted_until: dict[str, float] = {}

    # -- inputs ----------------------------------------------------------------

    def set_target(self, mode: str) -> None:
        self.target = mode

    @property
    def faulted_modes(self) -> set[str]:
        now = self._clock()
        return {m for m, until in self._faulted_until.items() if until > now}

    @property
    def active_mode(self) -> str:
        """The mode to advertise: only RUNNING counts as truly on-air."""
        return self.mode if (self.state == State.RUNNING and self.mode) else IDLE_MODE

    # -- the one reconciliation step ------------------------------------------

    async def step(self) -> None:
        now = self._clock()
        st = self.state

        if st == State.IDLE:
            if self.target != IDLE_MODE:
                await self._begin_start(self.target)

        elif st == State.STARTING:
            if self.target != self.mode:
                await self._begin_stop()  # preempt mid-start
            elif not self._runner.alive():
                await self._fault("exited during startup")
            elif self._runner.seconds_since_heartbeat() < HEARTBEAT_FRESH_S:
                self._retries = 0  # confirmed up
                self._enter(State.RUNNING)
            elif now - self._since > STARTUP_TIMEOUT_S:
                await self._fault("startup timeout")

        elif st == State.RUNNING:
            if self.target != self.mode:
                await self._begin_stop()
            elif not self._runner.alive():
                await self._fault("child exited")
            elif self._runner.seconds_since_heartbeat() > HEARTBEAT_FRESH_S:
                await self._fault("watchdog: no heartbeat")

        elif st == State.STOPPING:
            if not self._runner.alive():
                self.mode = None
                if self.target == IDLE_MODE:
                    self._enter(State.IDLE)
                else:
                    await self._begin_start(self.target)
            elif now - self._since > STOP_GRACE_S:
                await self._runner.kill()  # SIGKILL escalation

        elif st == State.FAULTED:
            if self.target != self.mode:
                self.mode = None
                if self.target == IDLE_MODE:
                    self._enter(State.IDLE)
                else:
                    await self._begin_start(self.target)
            elif self._retries >= MAX_RETRIES:
                self._faulted_until[self.mode] = now + FAULT_COOLDOWN_S
                log.warning("mode %s faulted %dx — cooling down", self.mode, self._retries)
                self.mode = None
                self._enter(State.IDLE)
            else:
                backoff = BACKOFF_S[min(self._retries - 1, len(BACKOFF_S) - 1)]
                if now - self._since >= backoff:
                    await self._begin_start(self.target)  # retry (retries preserved)

    # -- transitions -----------------------------------------------------------

    def _enter(self, state: State) -> None:
        self.state = state
        self._since = self._clock()

    async def _begin_start(self, mode: str) -> None:
        self.mode = mode
        await self._runner.start(mode)
        self._enter(State.STARTING)

    async def _begin_stop(self) -> None:
        await self._runner.stop()
        self._enter(State.STOPPING)

    async def _fault(self, reason: str) -> None:
        self._retries += 1
        self.reason = reason
        await self._runner.stop()  # ensure the child is on its way out
        self._enter(State.FAULTED)
