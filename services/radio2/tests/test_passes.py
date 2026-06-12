"""Pass prediction against a recorded NOAA-19 TLE fixture (P7).

Asserts structural correctness + determinism rather than exact timestamps
(robust across skyfield/sgp4 versions). A polar LEO over a mid-latitude
observer yields several passes per 72 h — a safe lower bound.
"""

from skyfield.api import load

from app.scheduler.passes import PassPredictor, parse_tles

# Real NOAA-19 (NORAD 33591) elements — fixture, well-formed 69-char lines.
NOAA19_TLE = """NOAA 19
1 33591U 09005A   20316.49457073  .00000079  00000-0  66891-4 0  9998
2 33591  99.1969 332.7522 0014512 113.2329 247.0345 14.12466766610035
"""

# 2020-11-12 00:00 UTC, within days of the TLE epoch (315.x of 2020)
START = 1605139200
DAY = 86400
LISBON = (38.7, -9.1, 100.0)


def test_parse_multiple_satellites():
    ts = load.timescale(builtin=True)
    text = NOAA19_TLE + (
        "NOAA 18\n"
        "1 28654U 05018A   20316.51782528  .00000041  00000-0  44694-4 0  9991\n"
        "2 28654  99.0512 ififfix\n"  # deliberately broken 2nd line on NOAA 18
    )
    sats = parse_tles(NOAA19_TLE, ts)
    assert len(sats) == 1 and sats[0].name == "NOAA 19"
    # broken set: parser shouldn't crash, may yield 1 (the good one)
    assert len(parse_tles(text, ts)) >= 1


def test_predicts_passes_with_sane_geometry():
    p = PassPredictor(*LISBON, min_elevation_deg=20)
    assert p.load_tles(NOAA19_TLE) == 1
    passes = p.predict(START, START + 3 * DAY)
    assert len(passes) >= 3, "a polar LEO should pass a mid-lat observer several times in 72h"
    for ps in passes:
        assert ps.satellite == "NOAA 19"
        assert ps.aos < ps.los
        assert ps.los - ps.aos < 20 * 60  # LEO passes are minutes, not hours
        assert 20 <= ps.max_el <= 90
    # sorted ascending, non-overlapping
    for a, b in zip(passes, passes[1:], strict=False):
        assert a.los <= b.aos


def test_higher_min_elevation_yields_fewer_passes():
    low = PassPredictor(*LISBON, min_elevation_deg=10)
    low.load_tles(NOAA19_TLE)
    high = PassPredictor(*LISBON, min_elevation_deg=50)
    high.load_tles(NOAA19_TLE)
    assert len(high.predict(START, START + 3 * DAY)) <= len(low.predict(START, START + 3 * DAY))


def test_prediction_is_deterministic():
    p = PassPredictor(*LISBON, min_elevation_deg=20)
    p.load_tles(NOAA19_TLE)
    assert p.predict(START, START + DAY) == p.predict(START, START + DAY)


def test_no_satellites_no_passes():
    p = PassPredictor(*LISBON, min_elevation_deg=20)
    assert p.predict(START, START + DAY) == []
