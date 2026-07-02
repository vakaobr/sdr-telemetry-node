"""Manual radio-2 override API (P7.7): publish to radio2/cmd, 409-during-pass."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.bus.mqtt import MqttBridge
from app.config import load_config
from app.main import create_app

EXAMPLE = Path(__file__).parents[3] / "shared" / "config" / "config.example.yaml"


@pytest.fixture()
def rig(tmp_path):
    cfg = load_config(EXAMPLE)
    bridge = MqttBridge(cfg)
    app = create_app(config=cfg, bridge=bridge, start_bus=False, db_path=str(tmp_path / "a.db"))
    return cfg, bridge, app


def set_retained_mode(bridge: MqttBridge, mode: str) -> None:
    """Simulate radio2's retained mode topic having been received."""
    bridge._radio2_mode = {"ts": 9, "mode": mode, "since": 9, "reason": "preempt"}  # noqa: SLF001
    bridge._radio2_health = {"ts": 9_999_999_999, "ok": True}  # noqa: SLF001


def test_valid_override_publishes_cmd(rig):
    _cfg, bridge, app = rig
    published: list = []
    bridge.publish = lambda topic, payload, **kw: published.append((topic, payload))
    with TestClient(app) as client:
        r = client.post("/api/v1/radio2/mode", json={"mode": "ais", "duration_s": 600})
        assert r.status_code == 202
        assert r.json() == {"accepted": "ais"}
        assert published[0][0] == "radio2/cmd"
        assert published[0][1]["mode"] == "ais" and published[0][1]["durationS"] == 600


def test_invalid_mode_422(rig):
    _cfg, _bridge, app = rig
    with TestClient(app) as client:
        r = client.post("/api/v1/radio2/mode", json={"mode": "fm-radio"})
        assert r.status_code == 422
        assert r.headers["content-type"].startswith("application/problem+json")


def test_override_during_pass_409_unless_force(rig):
    _cfg, bridge, app = rig
    set_retained_mode(bridge, "satellite")
    published: list = []
    bridge.publish = lambda topic, payload, **kw: published.append((topic, payload))
    with TestClient(app) as client:
        blocked = client.post("/api/v1/radio2/mode", json={"mode": "atc"})
        assert blocked.status_code == 409
        assert published == []  # nothing sent

        forced = client.post("/api/v1/radio2/mode", json={"mode": "atc", "force": True})
        assert forced.status_code == 202
        assert published[0][1]["force"] is True


def test_auto_release_allowed_during_pass(rig):
    _cfg, bridge, app = rig
    set_retained_mode(bridge, "satellite")
    bridge.publish = lambda *a, **k: None
    with TestClient(app) as client:
        r = client.post("/api/v1/radio2/mode", json={"mode": "auto"})
        assert r.status_code == 202  # releasing is always allowed
