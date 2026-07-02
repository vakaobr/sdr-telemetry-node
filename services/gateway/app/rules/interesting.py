"""Interesting-aircraft rules (FR-3): emergency squawks, military, watchlist.

evaluate() is pure: payload + enrichment + config → flags and fired events.
The engine diffs flags against the previous cycle so each rule fires its
event once per contact, not once per tick.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch

from app.config import WatchlistEntry

EMERGENCY_SQUAWKS = {"7500": "hijack", "7600": "radio failure", "7700": "emergency"}


@dataclass(frozen=True)
class RuleHit:
    severity: str  # "critical" | "notable"
    rule: str


def evaluate(
    *,
    icao: str,
    callsign: str | None,
    squawk: str | None,
    registration: str | None,
    type_code: str | None,
    military: bool,
    watchlist: list[WatchlistEntry],
) -> tuple[list[str], list[RuleHit]]:
    """→ (flags for the wire payload, rule hits)."""
    flags: list[str] = []
    hits: list[RuleHit] = []

    if squawk in EMERGENCY_SQUAWKS:
        flags.append("emergency")
        hits.append(RuleHit("critical", f"squawk-{squawk} ({EMERGENCY_SQUAWKS[squawk]})"))

    if military:
        flags.append("military")
        hits.append(RuleHit("notable", "military"))

    for entry in watchlist:
        matched = (
            (entry.match == "hex" and icao.lower() == entry.value.lower())
            or (
                entry.match == "callsign_glob"
                and callsign
                and fnmatch(callsign.upper(), entry.value.upper())
            )
            or (
                entry.match == "registration"
                and registration
                and registration.upper() == entry.value.upper()
            )
            or (
                entry.match == "type_code"
                and type_code
                and type_code.upper() == entry.value.upper()
            )
        )
        if matched:
            if "watchlist" not in flags:
                flags.append("watchlist")
            hits.append(RuleHit("notable", f"watchlist:{entry.match}={entry.value}"))

    return flags, hits
