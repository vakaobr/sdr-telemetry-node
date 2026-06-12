"""VesselTable + AISStream message parsing (P9 / ADR-010)."""

import pytest

from app.ingest.aisstream import AisStreamClient, bbox_around
from app.state.vessels import VesselTable

NOW = 1_765_500_000


def test_upsert_emits_only_with_position():
    t = VesselTable()
    t.upsert(123, now=NOW, name="EVER GIVEN", ship_type=70)  # static only, no pos
    upd, rem = t.collect_delta(NOW)
    assert upd == [] and rem == []  # no position yet → not emitted
    t.upsert(123, now=NOW, lat=38.7, lon=-9.1, sog=12.3, cog=270.0)
    upd, _ = t.collect_delta(NOW)
    assert len(upd) == 1
    v = upd[0]
    assert v.mmsi == 123 and v.name == "EVER GIVEN" and v.shipType == 70
    assert v.lat == 38.7 and v.sogKt == 12.3


def test_delta_only_returns_changed():
    t = VesselTable()
    t.upsert(1, now=NOW, lat=38.0, lon=-9.0)
    assert len(t.collect_delta(NOW)[0]) == 1
    assert t.collect_delta(NOW)[0] == []  # nothing changed since
    t.upsert(1, now=NOW + 1, lat=38.1, lon=-9.0)
    assert len(t.collect_delta(NOW + 1)[0]) == 1


def test_staleness_removes_vessel():
    t = VesselTable(staleness_s=1800)
    t.upsert(1, now=NOW, lat=38.0, lon=-9.0)
    t.collect_delta(NOW)
    upd, rem = t.collect_delta(NOW + 1801)
    assert rem == [1] and t.count() == 0


def test_snapshot_excludes_positionless():
    t = VesselTable()
    t.upsert(1, now=NOW, lat=38.0, lon=-9.0)
    t.upsert(2, now=NOW, name="NO POS")
    assert [v.mmsi for v in t.snapshot()] == [1]


def test_bbox_around():
    bb = bbox_around(38.7, -9.1, margin_deg=2.0)
    assert bb == [[36.7, -11.1], [40.7, -7.1]]


# -- AISStream message handling ------------------------------------------------


@pytest.fixture()
def client():
    t = VesselTable()
    c = AisStreamClient("key", bbox_around(38.7, -9.1), t, clock=lambda: NOW)
    return c, t


def test_handle_position_report(client):
    c, t = client
    c._handle(
        '{"MessageType":"PositionReport","MetaData":{"MMSI":211,"ShipName":"SAGRES ",'
        '"latitude":38.69,"longitude":-9.41,"time_utc":"x"},'
        '"Message":{"PositionReport":{"Latitude":38.69,"Longitude":-9.41,"Sog":8.5,"Cog":182.0}}}'
    )
    upd, _ = t.collect_delta(NOW)
    assert len(upd) == 1
    v = upd[0]
    assert v.mmsi == 211 and v.name == "SAGRES" and v.sogKt == 8.5 and v.cogDeg == 182.0


def test_handle_static_then_position(client):
    c, t = client
    c._handle(
        '{"MessageType":"ShipStaticData","MetaData":{"MMSI":99},'
        '"Message":{"ShipStaticData":{"Name":"CARGO X","Type":70}}}'
    )
    assert t.collect_delta(NOW)[0] == []  # no position yet
    c._handle(
        '{"MessageType":"PositionReport","MetaData":{"MMSI":99,"latitude":38.5,"longitude":-9.2},'
        '"Message":{"PositionReport":{"Latitude":38.5,"Longitude":-9.2,"Sog":0.0,"Cog":0.0}}}'
    )
    upd, _ = t.collect_delta(NOW)
    assert upd[0].name == "CARGO X" and upd[0].shipType == 70


def test_handle_sentinel_values_nulled(client):
    c, t = client
    c._handle(
        '{"MessageType":"PositionReport","MetaData":{"MMSI":5,"latitude":38.5,"longitude":-9.2},'
        '"Message":{"PositionReport":{"Latitude":38.5,"Longitude":-9.2,"Sog":102.3,"Cog":360.0}}}'
    )
    v = t.collect_delta(NOW)[0][0]
    assert v.sogKt is None and v.cogDeg is None  # AIS "not available" sentinels


def test_handle_garbage_is_ignored(client):
    c, t = client
    c._handle("not json")
    c._handle('{"MessageType":"PositionReport","MetaData":{}}')  # no MMSI
    assert t.collect_delta(NOW) == ([], [])
