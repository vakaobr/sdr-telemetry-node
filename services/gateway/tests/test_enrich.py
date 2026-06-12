"""Enrichment chain: local DB → cache → online, fail-soft at every step (P5)."""

import gzip
from pathlib import Path

import httpx
import pytest
import respx

from app.config import load_config
from app.enrich import localdb, staticdata
from app.enrich.service import ADSBDB_URL, Enricher
from app.persist.db import Database

EXAMPLE = Path(__file__).parents[3] / "shared" / "config" / "config.example.yaml"


@pytest.fixture()
def cfg():
    return load_config(EXAMPLE)


@pytest.fixture()
async def db(tmp_path):
    d = Database(tmp_path / "test.db")
    await d.open()
    yield d
    await d.close()


async def seed_aircraft_db(db: Database, tmp_path: Path) -> None:
    csv = tmp_path / "aircraft.csv.gz"
    rows = [
        "4951ce;CS-TVA;A20N;00",
        "3e8413;14+04;A400;01",  # db_flags bit0 = military
        "abcdef;;;00",  # known hex, empty fields
    ]
    csv.write_bytes(gzip.compress(("\n".join(rows)).encode()))
    imported = await localdb.ensure_imported(db, csv)
    assert imported == 3


# -- static data ----------------------------------------------------------------


def test_country_for_hex():
    assert staticdata.country_for_hex("4951ce") == "Portugal"
    assert staticdata.country_for_hex("3e8413") == "Germany"
    assert staticdata.country_for_hex("a12345") == "United States"
    assert staticdata.country_for_hex("zzzzzz") is None


def test_operator_for_callsign():
    assert staticdata.operator_for_callsign("TAP123") == "TAP Air Portugal"
    assert staticdata.operator_for_callsign("RCH4136") == "US Air Mobility Command"
    assert staticdata.operator_for_callsign("ZZZ1") is None
    assert staticdata.operator_for_callsign(None) is None


def test_type_name():
    assert staticdata.type_name_for("A20N") == "Airbus A320neo"
    assert staticdata.type_name_for("a20n") == "Airbus A320neo"
    assert staticdata.type_name_for("XQ99") is None


# -- local DB import + lookup ------------------------------------------------------


@pytest.mark.asyncio
async def test_localdb_import_and_lookup(db, tmp_path):
    await seed_aircraft_db(db, tmp_path)
    assert await localdb.lookup(db, "4951CE") == ("CS-TVA", "A20N", 0)
    assert await localdb.lookup(db, "3e8413") == ("14+04", "A400", 1)
    assert await localdb.lookup(db, "abcdef") == (None, None, 0)
    assert await localdb.lookup(db, "000000") is None


@pytest.mark.asyncio
async def test_localdb_import_is_idempotent(db, tmp_path):
    await seed_aircraft_db(db, tmp_path)
    # same mtime → no reimport, same count
    assert await localdb.ensure_imported(db, tmp_path / "aircraft.csv.gz") == 3


@pytest.mark.asyncio
async def test_localdb_missing_file_is_nonfatal(db, tmp_path):
    assert await localdb.ensure_imported(db, tmp_path / "nope.csv.gz") == 0


# -- enrichment chain ---------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_offline_chain_fills_local_fields(cfg, db, tmp_path):
    """Local DB + static data resolve with the network hard-down (TR-5)."""
    await seed_aircraft_db(db, tmp_path)
    respx.get(ADSBDB_URL.format(callsign="TAP123")).mock(side_effect=httpx.ConnectError)
    e = Enricher(cfg, db)
    result = await e.enrich("4951ce", "TAP123")
    assert result["registration"] == "CS-TVA"
    assert result["typeCode"] == "A20N"
    assert result["typeName"] == "Airbus A320neo"
    assert result["operator"] == "TAP Air Portugal"  # prefix fallback, no network
    assert result["country"] == "Portugal"
    assert result["route"] is None  # online-only field degrades
    await e.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_online_adds_route_and_caches(cfg, db, tmp_path):
    await seed_aircraft_db(db, tmp_path)
    respx.get(ADSBDB_URL.format(callsign="TAP123")).mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "flightroute": {
                        "origin": {"icao_code": "LPPT"},
                        "destination": {"icao_code": "LFPO"},
                        "airline": {"name": "TAP Air Portugal"},
                    }
                }
            },
        )
    )
    e = Enricher(cfg, db)
    r1 = await e.enrich("4951ce", "TAP123")
    assert r1["route"] == "LPPT → LFPO"

    # second lookup must hit the cache, not the API
    respx.get(ADSBDB_URL.format(callsign="TAP123")).mock(side_effect=AssertionError)
    r2 = await e.enrich("4951ce", "TAP123")
    assert r2["route"] == "LPPT → LFPO"
    await e.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_military_flag_captured(cfg, db, tmp_path):
    await seed_aircraft_db(db, tmp_path)
    respx.get(url__startswith="https://api.adsbdb.com").mock(return_value=httpx.Response(404))
    e = Enricher(cfg, db)
    await e.enrich("3e8413", "GAF891")
    assert e.military_flag_of["3e8413"] is True
    await e.aclose()


@pytest.mark.asyncio
async def test_online_disabled_never_touches_network(cfg, db, tmp_path):
    await seed_aircraft_db(db, tmp_path)
    cfg.enrichment.online.enabled = False
    e = Enricher(cfg, db)  # no respx mock active: a real request would error loudly
    result = await e.enrich("4951ce", "TAP123")
    assert result["registration"] == "CS-TVA" and result["route"] is None
    await e.aclose()
