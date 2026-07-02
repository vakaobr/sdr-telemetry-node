"""Radio-2 supervisor: scheduler → FSM → publisher, one step() per tick.

step() is the single deterministic reconciliation (mirrors the gateway engine):
  1. ask the scheduler for the desired mode (override > pass > block > idle),
     skipping any FSM-cooled-down faulted modes
  2. set the FSM target and advance it one step
  3. publish radio2/mode on change; refresh passes + publish next-pass/health
     on their own cadences

Restart-safe: holds no durable state — on boot it recomputes the schedule from
config + cached TLEs and converges to the correct mode. Manual overrides arrive
via radio2/cmd and expire on their own.
"""

from __future__ import annotations

import logging

from app.config import Config
from app.fsm import IDLE_MODE, Radio2Fsm
from app.publish import Publisher
from app.scheduler.decision import Override, Scheduler

log = logging.getLogger("radio2.supervisor")

PASS_REFRESH_S = 30 * 60
HEALTH_EVERY_S = 30
NEXTPASS_EVERY_S = 60


class Supervisor:
    def __init__(
        self,
        config: Config,
        fsm: Radio2Fsm,
        scheduler: Scheduler,
        publisher: Publisher,
        *,
        clock,
        tle_age_days=None,
    ) -> None:
        self._cfg = config
        self._fsm = fsm
        self._scheduler = scheduler
        self._publisher = publisher
        self._clock = clock
        self._tle_age_days = tle_age_days
        self._override: Override | None = None
        self._started = clock()
        self._last_pass_refresh = -1e18
        self._last_health = -1e18
        self._last_nextpass = -1e18
        self._last_published_mode: str | None = None

    # -- command from radio2/cmd (gateway manual override) --------------------

    def on_command(self, cmd: dict) -> None:
        mode = cmd.get("mode")
        if mode == "auto":
            self._override = None
            log.info("manual override released → auto")
            return
        if mode in {"atc", "ais", "satellite", "idle"}:
            now = int(self._clock())
            expires = now + int(cmd["durationS"]) if cmd.get("durationS") else None
            self._override = Override(mode, expires)
            log.info("manual override → %s (expires=%s)", mode, expires)

    # -- one reconciliation step ----------------------------------------------

    async def step(self) -> None:
        now = int(self._clock())

        if now - self._last_pass_refresh >= PASS_REFRESH_S:
            self._scheduler.update_passes(now)
            self._last_pass_refresh = now

        desired, reason = self._scheduler.desired(
            now, override=self._override, faulted=self._fsm.faulted_modes
        )
        self._fsm.set_target(desired)
        await self._fsm.step()

        active = self._fsm.active_mode
        if active != self._last_published_mode:
            self._publisher.mode(active, reason if active != IDLE_MODE else "schedule", now)
            self._last_published_mode = active

        if now - self._last_nextpass >= NEXTPASS_EVERY_S:
            self._publisher.next_pass(self._scheduler.next_pass(now), now)
            self._last_nextpass = now

        if now - self._last_health >= HEALTH_EVERY_S:
            self._publisher.health(
                ok=True,
                decoder=active if active != IDLE_MODE else None,
                uptime_s=int(now - self._started),
                tle_age_days=self._tle_age_days,
                ts=now,
            )
            self._last_health = now
