"""Schedule blocks: local time-of-day → atc | ais | None (FR-4.4).

Operates on minute-of-day so it's timezone-agnostic and trivially testable;
the supervisor converts wall-clock to local minute-of-day before calling.
Handles blocks that wrap past midnight (e.g. AIS 23:00→07:00).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Block:
    mode: str  # "atc" | "ais"
    start_min: int
    end_min: int


def hhmm_to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def make_blocks(raw: list[tuple[str, str, str]]) -> list[Block]:
    """raw items: (mode, 'HH:MM' from, 'HH:MM' to)."""
    return [Block(mode, hhmm_to_min(a), hhmm_to_min(b)) for mode, a, b in raw]


def active_block(minute_of_day: int, blocks: list[Block]) -> str | None:
    for b in blocks:
        if b.start_min <= b.end_min:
            if b.start_min <= minute_of_day < b.end_min:
                return b.mode
        else:  # wraps midnight
            if minute_of_day >= b.start_min or minute_of_day < b.end_min:
                return b.mode
    return None
