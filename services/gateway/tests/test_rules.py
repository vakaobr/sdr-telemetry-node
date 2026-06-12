"""Interesting rules: emergency squawks, military, watchlist matchers (P5)."""

import pytest

from app.config import WatchlistEntry
from app.rules.interesting import evaluate


def run(**kw):
    base = dict(
        icao="4951ce",
        callsign="TAP123",
        squawk="2041",
        registration="CS-TVA",
        type_code="A20N",
        military=False,
        watchlist=[],
    )
    base.update(kw)
    return evaluate(**base)


@pytest.mark.parametrize(
    "squawk,word", [("7500", "hijack"), ("7600", "radio"), ("7700", "emergency")]
)
def test_emergency_squawks_critical(squawk, word):
    flags, hits = run(squawk=squawk)
    assert "emergency" in flags
    assert hits[0].severity == "critical" and word in hits[0].rule


def test_normal_squawk_no_flags():
    flags, hits = run()
    assert flags == [] and hits == []


def test_military_notable():
    flags, hits = run(military=True)
    assert flags == ["military"]
    assert hits == [type(hits[0])("notable", "military")]


@pytest.mark.parametrize(
    "entry,expect",
    [
        (WatchlistEntry(match="hex", value="4951CE"), True),  # case-insensitive
        (WatchlistEntry(match="hex", value="000000"), False),
        (WatchlistEntry(match="callsign_glob", value="TAP*"), True),
        (WatchlistEntry(match="callsign_glob", value="rch*"), False),
        (WatchlistEntry(match="registration", value="cs-tva"), True),
        (WatchlistEntry(match="type_code", value="A20N"), True),
        (WatchlistEntry(match="type_code", value="B738"), False),
    ],
)
def test_watchlist_matchers(entry, expect):
    flags, hits = run(watchlist=[entry])
    assert ("watchlist" in flags) is expect
    assert any(h.rule.startswith("watchlist:") for h in hits) is expect


def test_watchlist_null_fields_never_match():
    flags, _ = run(
        callsign=None,
        registration=None,
        type_code=None,
        watchlist=[
            WatchlistEntry(match="callsign_glob", value="*"),
            WatchlistEntry(match="registration", value="X"),
            WatchlistEntry(match="type_code", value="X"),
        ],
    )
    assert flags == []


def test_combined_emergency_and_military():
    flags, hits = run(squawk="7700", military=True)
    assert flags == ["emergency", "military"]
    assert {h.severity for h in hits} == {"critical", "notable"}
