"""Engine integration (P5): enrichment lands on later ticks; rules fire once.

Drives Engine.tick() directly — deterministic, no sleeps, offline posture.
"""

import asyncio
import gzip
from pathlib import Path

import pytest

from app.bus.mqtt import MqttBridge
from app.config import load_config
from app.engine import Engine
from app.enrich import localdb
from app.enrich.service import Enricher
from app.persist.db import Database
from app.persist.sightings import SightingsRecorder
from app.ws.hub import Hub

EXAMPLE = Path(__file__).parents[3] / "shared" / "config" / "config.example.yaml"
NOW = 1_765_500_000


class FakeReadsb:
    def __init__(self) -> None:
        self.doc = {"messages": 0, "aircraft": []}
        self.healthy = True

    async def fetch_aircraft(self):
        return self.doc

    async def aclose(self):
        pass


class CaptureHub(Hub):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[dict] = []

    async def broadcast(self, message):
        self.messages.append(message)
        await super().broadcast(message)


def plane(hex="4951ce", squawk="2041", flight="TAP123"):
    return {
        "hex": hex,
        "seen": 0,
        "seen_pos": 0,
        "lat": 38.8,
        "lon": -9.1,
        "alt_baro": 12000,
        "gs": 250,
        "track": 90,
        "squawk": squawk,
        "flight": flight,
    }


@pytest.fixture()
async def rig(tmp_path):
    cfg = load_config(EXAMPLE)
    cfg.enrichment.online.enabled = False  # offline posture
    db = Database(tmp_path / "app.db")
    await db.open()
    csv = tmp_path / "aircraft.csv.gz"
    csv.write_bytes(gzip.compress(b"4951ce;CS-TVA;A20N;00\n3e8413;14+04;A400;01"))
    await localdb.ensure_imported(db, csv)

    fake = FakeReadsb()
    hub = CaptureHub()
    engine = Engine(
        cfg,
        fake,
        MqttBridge(cfg),
        hub,
        enricher=Enricher(cfg, db),
        recorder=SightingsRecorder(db),
    )
    yield cfg, fake, hub, engine, db
    await db.close()


@pytest.mark.asyncio
async def test_enrichment_lands_in_a_later_delta(rig):
    _cfg, fake, hub, engine, _db = rig
    fake.doc = {"messages": 10, "aircraft": [plane()]}
    await engine.tick(NOW)  # first sight: enrich scheduled async
    for i in range(5):  # let the enrich task run (real awaits), then tick again
        await asyncio.sleep(0.05)
        await engine.tick(NOW + 1 + i)
        enriched = [
            a
            for m in hub.messages
            if m["type"] == "aircraft_delta"
            for a in m["updated"]
            if a.get("enrich")
        ]
        if enriched:
            break
    assert enriched, "enrichment never appeared in a delta"
    e = enriched[0]["enrich"]
    assert e["registration"] == "CS-TVA"
    assert e["typeName"] == "Airbus A320neo"
    assert e["operator"] == "TAP Air Portugal"
    assert e["country"] == "Portugal"


@pytest.mark.asyncio
async def test_emergency_fires_once_and_persists_in_sighting(rig):
    _cfg, fake, hub, engine, db = rig
    fake.doc = {"messages": 10, "aircraft": [plane(squawk="7700")]}
    await engine.tick(NOW)
    await engine.tick(NOW + 1)
    await engine.tick(NOW + 2)

    interesting = [m for m in hub.messages if m["type"] == "interesting"]
    assert len(interesting) == 1, "emergency must fire exactly once per contact"
    assert interesting[0]["severity"] == "critical"
    assert "7700" in interesting[0]["rule"]

    # delta carries the flag the same tick the squawk appeared
    first_delta = next(m for m in hub.messages if m["type"] == "aircraft_delta")
    assert "emergency" in first_delta["updated"][0]["flags"]

    # contact close → sighting row with the emergency recorded
    fake.doc = {"messages": 20, "aircraft": []}
    await engine.tick(NOW + 3)
    cur = await db.conn.execute("SELECT squawk_emergency, flags FROM sightings")
    sq, flags = await cur.fetchone()
    assert sq == "7700" and "emergency" in flags


@pytest.mark.asyncio
async def test_military_flag_appears_after_enrichment(rig):
    _cfg, fake, hub, engine, _db = rig
    fake.doc = {"messages": 10, "aircraft": [plane(hex="3e8413", flight="GAF891")]}
    await engine.tick(NOW)
    military_seen = False
    for i in range(5):
        await asyncio.sleep(0.05)
        await engine.tick(NOW + 1 + i)
        for m in hub.messages:
            if m["type"] == "aircraft_delta" and any(
                "military" in a["flags"] for a in m["updated"]
            ):
                military_seen = True
        if military_seen:
            break
    assert military_seen
    hits = [m for m in hub.messages if m["type"] == "interesting" and m["rule"] == "military"]
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_late_callsign_triggers_re_enrichment(rig):
    """Callsign often decodes a few messages after first contact — operator
    must still resolve (the NJE312K bug found live on Node A)."""
    _cfg, fake, hub, engine, _db = rig
    anon = plane()
    anon["flight"] = None  # first contact: no callsign yet
    fake.doc = {"messages": 10, "aircraft": [anon]}
    await engine.tick(NOW)
    await asyncio.sleep(0.05)
    await engine.tick(NOW + 1)

    fake.doc = {"messages": 20, "aircraft": [plane()]}  # callsign appears
    for i in range(5):
        await asyncio.sleep(0.05)
        await engine.tick(NOW + 2 + i)
        ac = engine.table.get("4951ce")
        if ac and ac.enrich and ac.enrich.operator:
            break
    assert ac.enrich.operator == "TAP Air Portugal"
