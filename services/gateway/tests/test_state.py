"""AircraftTable: diff engine, staleness, geometry, trails, priority (P3 unit tests)."""

from pathlib import Path

import pytest

from app.config import load_config
from app.state import geo
from app.state.aircraft import AircraftTable

EXAMPLE = Path(__file__).parents[3] / "shared" / "config" / "config.example.yaml"
NOW = 1_765_500_000


@pytest.fixture()
def cfg():
    return load_config(EXAMPLE)  # receiver at Lisbon 38.7169,-9.1399


@pytest.fixture()
def table(cfg):
    return AircraftTable(cfg)


def raw(hex="4951ce", **kw):
    base = {
        "hex": hex,
        "seen": 0,
        "seen_pos": 0,
        "lat": 38.8,
        "lon": -9.1,
        "alt_baro": 12000,
        "gs": 250,
        "track": 90,
        "flight": "TAP123 ",
    }
    base.update(kw)
    return base


def doc(*aircraft, messages=1000):
    return {"now": NOW, "messages": messages, "aircraft": list(aircraft)}


# -- geo ----------------------------------------------------------------------


def test_geo_known_distance_lisbon_porto():
    # Lisbon → Porto ≈ 274 km
    d = geo.distance_km(38.7169, -9.1399, 41.1496, -8.6109)
    assert d == pytest.approx(274, abs=5)


def test_geo_bearing_due_north():
    assert geo.bearing_deg(38.0, -9.0, 39.0, -9.0) == pytest.approx(0, abs=0.5)


# -- diff engine ---------------------------------------------------------------


def test_new_aircraft_appears_in_updated(table):
    updated, removed = table.update_from_readsb(doc(raw()), NOW)
    assert [a.icao for a in updated] == ["4951ce"]
    assert removed == []
    assert updated[0].callsign == "TAP123"  # whitespace stripped
    assert updated[0].distanceKm == pytest.approx(9.8, abs=1.5)


def test_unchanged_aircraft_not_re_emitted(table):
    table.update_from_readsb(doc(raw()), NOW)
    updated, removed = table.update_from_readsb(doc(raw()), NOW)
    assert updated == [] and removed == []


def test_changed_field_emits_delta(table):
    table.update_from_readsb(doc(raw()), NOW)
    updated, _ = table.update_from_readsb(doc(raw(alt_baro=13000)), NOW + 1)
    assert len(updated) == 1 and updated[0].altFt == 13000


def test_absent_aircraft_removed(table):
    table.update_from_readsb(doc(raw(), raw(hex="abc123", lat=39.0)), NOW)
    _, removed = table.update_from_readsb(doc(raw()), NOW + 1)
    assert removed == ["abc123"]


def test_stale_by_seen_removed(table):
    table.update_from_readsb(doc(raw()), NOW)
    _, removed = table.update_from_readsb(doc(raw(seen=301)), NOW + 301)
    assert removed == ["4951ce"]  # staleness_msg_s=300


def test_stale_position_stripped_but_aircraft_kept(table):
    table.update_from_readsb(doc(raw()), NOW)
    updated, removed = table.update_from_readsb(doc(raw(seen_pos=61)), NOW + 61)
    assert removed == []
    assert updated[0].lat is None and updated[0].distanceKm is None


def test_non_icao_hex_ignored(table):
    updated, _ = table.update_from_readsb(doc(raw(hex="~12abc3"), raw()), NOW)
    assert [a.icao for a in updated] == ["4951ce"]


def test_ground_altitude_maps_to_zero(table):
    updated, _ = table.update_from_readsb(doc(raw(alt_baro="ground")), NOW)
    assert updated[0].altFt == 0


# -- trails ---------------------------------------------------------------------


def test_trail_grows_and_caps(cfg, table):
    for i in range(cfg.adsb.trail_len + 20):
        table.update_from_readsb(doc(raw(lat=38.0 + i * 0.001)), NOW + i)
    ac = table.get("4951ce")
    assert len(ac.trail) == cfg.adsb.trail_len
    # oldest points dropped: first retained point is the 21st
    assert ac.trail[0].root[0] == pytest.approx(38.0 + 20 * 0.001)


def test_trail_skips_duplicate_points(table):
    table.update_from_readsb(doc(raw()), NOW)
    table.update_from_readsb(doc(raw(gs=251)), NOW + 1)  # same position, other field changed
    assert len(table.get("4951ce").trail) == 1


# -- priority (FR-1.4) ------------------------------------------------------------


def test_low_altitude_outranks_nearer_overflight(table):
    high_near = raw(hex="aaaaaa", lat=38.75, lon=-9.14, alt_baro=35000)  # ~3.7 km, high
    low_far = raw(hex="bbbbbb", lat=38.78, lon=-9.14, alt_baro=3000)  # ~7 km, low → ×0.5 = 3.5
    table.update_from_readsb(doc(high_near, low_far), NOW)
    snap = {a.icao: a.priority for a in table.snapshot()}
    assert snap["bbbbbb"] < snap["aaaaaa"]


def test_no_position_sorts_last(table):
    has_pos = raw(hex="aaaaaa")
    no_pos = raw(hex="bbbbbb", lat=None, seen_pos=None)
    table.update_from_readsb(doc(no_pos, has_pos), NOW)
    snap = {a.icao: a.priority for a in table.snapshot()}
    assert snap["aaaaaa"] == 0 and snap["bbbbbb"] == 1


def test_priority_churn_emits_delta_for_displaced_aircraft(table):
    table.update_from_readsb(doc(raw(hex="aaaaaa", lat=38.75)), NOW)
    # second aircraft appears closer → aaaaaa's priority changes → both in delta
    updated, _ = table.update_from_readsb(
        doc(raw(hex="aaaaaa", lat=38.75), raw(hex="bbbbbb", lat=38.72, alt_baro=2000)), NOW + 1
    )
    assert {a.icao for a in updated} == {"aaaaaa", "bbbbbb"}
