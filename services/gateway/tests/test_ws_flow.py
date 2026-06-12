"""Integration: fake readsb → engine → WS snapshot+delta flow, REST surface, latency probe.

The fake readsb is an injected ReadsbClient double whose payload the test
mutates between engine ticks — no network, fully deterministic.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.bus.mqtt import MqttBridge
from app.config import load_config
from app.engine import Engine
from app.main import create_app
from app.models.generated_ws import SnapshotMessage
from app.ws.hub import Hub

EXAMPLE = Path(__file__).parents[3] / "shared" / "config" / "config.example.yaml"


class FakeReadsb:
    """Stands in for ReadsbClient; payload is test-controlled."""

    def __init__(self) -> None:
        self.doc: dict | None = {"messages": 0, "aircraft": []}
        self.healthy = True

    async def fetch_aircraft(self) -> dict | None:
        return self.doc

    async def fetch_stats(self) -> dict | None:
        return None

    async def aclose(self) -> None:
        pass


def plane(hex="4951ce", lat=38.8, alt=12000):
    return {
        "hex": hex,
        "seen": 0,
        "seen_pos": 0,
        "lat": lat,
        "lon": -9.1,
        "alt_baro": alt,
        "gs": 250,
        "track": 90,
        "flight": "TAP123",
    }


@pytest.fixture()
def rig():
    cfg = load_config(EXAMPLE)
    fake = FakeReadsb()
    bridge = MqttBridge(cfg)  # never started — no broker in unit CI (offline posture)
    app = create_app(config=cfg, readsb=fake, bridge=bridge, start_bus=False)
    return cfg, fake, bridge, app


def test_ws_snapshot_then_delta(rig):
    _cfg, fake, _bridge, app = rig
    fake.doc = {"messages": 100, "aircraft": [plane()]}
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        # engine may not have ticked yet — first frame is always a snapshot
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        SnapshotMessage.model_validate(first)  # snapshot honors the contract
        assert first["radio2"]["mode"] == "offline"  # no radio2 deployed yet (LWT default)

        # mutate the sky → expect an aircraft_delta within a couple of ticks
        fake.doc = {"messages": 200, "aircraft": [plane(), plane(hex="abc123", lat=39.0)]}
        for _ in range(10):
            msg = ws.receive_json()
            if msg["type"] == "aircraft_delta" and any(
                a["icao"] == "abc123" for a in msg["updated"]
            ):
                break
        else:
            pytest.fail("aircraft_delta for abc123 never arrived")


@pytest.mark.asyncio
async def test_hub_subscribe_filters_topics():
    """Topic filtering is Hub behavior — test it directly (no blocking WS receive)."""
    hub = Hub()
    received: list[dict] = []

    class CaptureWS:
        async def send_json(self, m):
            received.append(m)

    ws = CaptureWS()
    await hub.join(ws)  # type: ignore[arg-type]
    await hub.broadcast({"type": "aircraft_delta", "ts": 1, "updated": [], "removed": []})
    assert len(received) == 1  # default subscription = everything

    await hub.set_topics(ws, ["system"])  # type: ignore[arg-type]
    await hub.broadcast({"type": "aircraft_delta", "ts": 2, "updated": [], "removed": []})
    await hub.broadcast({"type": "radio2_status", "ts": 3, "status": {}})
    await hub.broadcast({"type": "system_health", "ts": 4, "health": {}})
    types = [m["type"] for m in received[1:]]
    assert types == ["system_health"], f"filter leaked: {types}"

    await hub.set_topics(ws, ["bogus-topic"])  # type: ignore[arg-type]  # unknown names ignored
    await hub.broadcast({"type": "system_health", "ts": 5, "health": {}})
    assert len(received) == 2


@pytest.mark.asyncio
async def test_hub_evicts_dead_client():
    hub = Hub()

    class DeadWS:
        async def send_json(self, m):
            raise RuntimeError("gone")

    ws = DeadWS()
    await hub.join(ws)  # type: ignore[arg-type]
    assert hub.client_count == 1
    await hub.broadcast({"type": "system_health", "ts": 1, "health": {}})
    assert hub.client_count == 0  # evicted, broadcast didn't raise


def test_rest_aircraft_list_and_detail(rig):
    _cfg, fake, _bridge, app = rig
    fake.doc = {"messages": 100, "aircraft": [plane(), plane(hex="abc123", lat=38.72, alt=2000)]}
    with TestClient(app) as client:
        for _ in range(20):
            items = client.get("/api/v1/aircraft").json()
            if len(items) == 2:
                break
            time.sleep(0.2)
        assert len(items) == 2
        assert items[0]["priority"] == 0
        assert items[0]["icao"] == "abc123"  # low + near wins (FR-1.4)

        one = client.get("/api/v1/aircraft/ABC123")  # case-insensitive
        assert one.status_code == 200

        missing = client.get("/api/v1/aircraft/000000")
        assert missing.status_code == 404
        assert missing.headers["content-type"].startswith("application/problem+json")
        body = missing.json()
        assert body["status"] == 404 and "000000" in body["detail"]


def test_rest_system_health_shape(rig):
    _cfg, fake, _bridge, app = rig
    with TestClient(app) as client:
        h = client.get("/api/v1/system").json()
        assert h["nodeB"] is None  # never seen → offline
        assert h["adsb"]["ok"] is True
        assert h["dbOk"] is True


@pytest.mark.asyncio
async def test_latency_probe_rf_to_ws_under_2s():
    """TR-1: ingest→WS p95 ≤ 2 s. In-process probe: inject → measure delta arrival."""
    cfg = load_config(EXAMPLE)
    fake = FakeReadsb()
    bridge = MqttBridge(cfg)
    hub = Hub()
    engine = Engine(cfg, fake, bridge, hub)

    received = asyncio.Queue()

    class CaptureWS:
        async def send_json(self, m):
            await received.put((time.monotonic(), m))

    ws = CaptureWS()
    await hub.join(ws)  # type: ignore[arg-type]

    engine.start()
    try:
        latencies = []
        for i in range(5):
            t0 = time.monotonic()
            fake.doc = {
                "messages": i * 100,
                "aircraft": [plane(hex=f"{i:06x}", lat=38.8 + i * 0.01)],
            }
            while True:
                ts, msg = await asyncio.wait_for(received.get(), timeout=3)
                if msg["type"] == "aircraft_delta" and any(
                    a["icao"] == f"{i:06x}" for a in msg["updated"]
                ):
                    latencies.append(ts - t0)
                    break
        worst = max(latencies)
        assert worst < 2.0, f"latencies {latencies}"
    finally:
        await engine.stop()
