"""Desired-mode decision + scheduler state (FR-4.2 priority logic).

Priority (highest first):
  1. manual override  (pre-empts everything; the gateway gates override-during-
     pass with 409-unless-force, so anything that reaches here wins)
  2. satellite pass   (radio reserved [aos - LEAD_S, los])
  3. schedule block   (atc / ais by local time-of-day)
  4. idle

A mode in `faulted` (cooled-down by the FSM after repeated failures) is skipped
so the scheduler falls through to the next-best mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.scheduler.blocks import Block, active_block
from app.scheduler.passes import Pass, PassPredictor

LEAD_S = 60  # reserve the radio this long before AOS (retune + decoder start)
HORIZON_S = 6 * 3600  # how far ahead we predict passes


@dataclass
class Override:
    mode: str  # atc|ais|satellite|idle|auto
    expires_at: int | None  # None = until explicitly released

    def active(self, now: int) -> bool:
        return self.mode != "auto" and (self.expires_at is None or now < self.expires_at)


def desired_mode(
    now: int,
    *,
    override: Override | None,
    current_pass: Pass | None,
    block: str | None,
    faulted: set[str],
) -> tuple[str, str]:
    if override and override.active(now) and override.mode not in faulted:
        return override.mode, "manual"
    if current_pass and "satellite" not in faulted:
        return "satellite", "preempt"
    if block and block not in faulted:
        return block, "schedule"
    return "idle", "schedule"


class Scheduler:
    def __init__(
        self,
        predictor: PassPredictor,
        blocks: list[Block],
        tz: str,
        *,
        lead_s: int = LEAD_S,
        horizon_s: int = HORIZON_S,
    ) -> None:
        self._predictor = predictor
        self._blocks = blocks
        self._tz = ZoneInfo(tz)
        self._lead = lead_s
        self._horizon = horizon_s
        self._passes: list[Pass] = []

    def update_passes(self, now: int) -> None:
        self._passes = self._predictor.predict(now, now + self._horizon)

    def current_pass(self, now: int) -> Pass | None:
        for p in self._passes:
            if p.aos - self._lead <= now <= p.los:
                return p
        return None

    def next_pass(self, now: int) -> Pass | None:
        future = [p for p in self._passes if p.los > now]
        return min(future, key=lambda p: p.aos) if future else None

    def _local_minute(self, now: int) -> int:
        dt = datetime.fromtimestamp(now, self._tz)
        return dt.hour * 60 + dt.minute

    def desired(self, now: int, *, override: Override | None, faulted: set[str]) -> tuple[str, str]:
        return desired_mode(
            now,
            override=override,
            current_pass=self.current_pass(now),
            block=active_block(self._local_minute(now), self._blocks),
            faulted=faulted,
        )

    # test/diagnostic injection
    def set_passes(self, passes: list[Pass]) -> None:
        self._passes = list(passes)
