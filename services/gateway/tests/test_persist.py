"""Persistence: migrations + sightings recorder batching semantics (P5)."""

import pytest

from app.persist.db import Database
from app.persist.sightings import SightingsRecorder


@pytest.fixture()
async def db(tmp_path):
    d = Database(tmp_path / "test.db")
    await d.open()
    yield d
    await d.close()


def payload(icao="4951ce", **kw):
    base = {
        "icao": icao,
        "callsign": "TAP123",
        "lastSeen": 1000,
        "distanceKm": 20.0,
        "altFt": 12000,
        "flags": [],
        "squawk": "2041",
        "enrich": {"registration": "CS-TVA", "typeCode": "A20N"},
    }
    base.update(kw)
    return base


# -- migrations -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migrations_apply_once_and_are_idempotent(tmp_path):
    d = Database(tmp_path / "m.db")
    await d.open()
    cur = await d.conn.execute("SELECT MAX(version) FROM schema_version")
    v1 = (await cur.fetchone())[0]
    await d.close()
    # re-open: no re-apply, same version
    d2 = Database(tmp_path / "m.db")
    await d2.open()
    cur = await d2.conn.execute("SELECT COUNT(*) FROM schema_version")
    assert (await cur.fetchone())[0] == v1  # one row per applied migration
    await d2.close()


@pytest.mark.asyncio
async def test_newer_schema_refuses_start(tmp_path):
    d = Database(tmp_path / "m.db")
    await d.open()
    await d.conn.execute("INSERT INTO schema_version VALUES (999)")
    await d.conn.commit()
    await d.close()
    d2 = Database(tmp_path / "m.db")
    with pytest.raises(RuntimeError, match="newer"):
        await d2.open()
    await d2.close()


# -- sightings ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contact_close_writes_row(db):
    rec = SightingsRecorder(db)
    rec.observe(payload(distanceKm=30.0))
    rec.observe(payload(distanceKm=10.0, altFt=15000, lastSeen=1100))
    await rec.on_removed(["4951ce"])

    cur = await db.conn.execute(
        "SELECT icao, callsign, registration, type_code, first_seen, last_seen, "
        "min_distance_km, max_range_km, max_alt_ft FROM sightings"
    )
    rows = await cur.fetchall()
    assert len(rows) == 1
    icao, cs, reg, tc, first, last, mind, maxr, maxa = rows[0]
    assert (icao, cs, reg, tc) == ("4951ce", "TAP123", "CS-TVA", "A20N")
    assert (first, last) == (1000, 1100)
    assert (mind, maxr, maxa) == (10.0, 30.0, 15000)
    assert rec.open_contacts == 0


@pytest.mark.asyncio
async def test_emergency_and_flags_recorded(db):
    rec = SightingsRecorder(db)
    rec.observe(payload(squawk="7700", flags=["emergency", "military"]))
    await rec.on_removed(["4951ce"])
    cur = await db.conn.execute("SELECT flags, squawk_emergency FROM sightings")
    flags, sq = await cur.fetchone()
    assert flags == "emergency,military" and sq == "7700"


@pytest.mark.asyncio
async def test_periodic_flush_updates_same_row(db, monkeypatch):
    rec = SightingsRecorder(db)
    rec.observe(payload())
    monkeypatch.setattr(rec, "_last_flush", 0)  # force the 60 s window open
    await rec.maybe_flush()
    rec.observe(payload(altFt=20000, lastSeen=1200))
    monkeypatch.setattr(rec, "_last_flush", 0)
    await rec.maybe_flush()

    cur = await db.conn.execute("SELECT COUNT(*), MAX(max_alt_ft) FROM sightings")
    count, alt = await cur.fetchone()
    assert count == 1 and alt == 20000  # updated in place, not duplicated


@pytest.mark.asyncio
async def test_no_writes_between_flush_windows(db):
    """Write-budget guard (NFR-6): observe() alone must not touch the DB."""
    rec = SightingsRecorder(db)
    for i in range(100):
        rec.observe(payload(lastSeen=1000 + i))
    await rec.maybe_flush()  # window not yet open (fresh recorder)
    cur = await db.conn.execute("SELECT COUNT(*) FROM sightings")
    assert (await cur.fetchone())[0] == 0
