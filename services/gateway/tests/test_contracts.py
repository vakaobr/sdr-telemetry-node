"""Contract smoke: generated pydantic models accept canonical payloads.

Guards the codegen pipeline itself — if schemas and generated code drift,
or generation produces unusable models, this fails before CI's diff check.
"""

import pytest
from pydantic import ValidationError

from app.models.generated_mqtt import Radio2Health, Radio2Mode, SysHealth
from app.models.generated_ws import AircraftDeltaMessage, InterestingMessage


def test_ws_aircraft_delta_roundtrip():
    msg = AircraftDeltaMessage.model_validate(
        {
            "type": "aircraft_delta",
            "ts": 1765500000,
            "updated": [
                {
                    "icao": "4951ce",
                    "callsign": "TAP123",
                    "lat": 38.7,
                    "lon": -9.1,
                    "altFt": 12000,
                    "gsKt": 280.5,
                    "vrFpm": -800,
                    "track": 215.0,
                    "squawk": "2041",
                    "distanceKm": 12.4,
                    "bearingDeg": 184.2,
                    "priority": 0,
                    "flags": [],
                    "enrich": None,
                    "trail": [[38.71, -9.09], [38.7, -9.1]],
                    "lastSeen": 1765500000,
                    "rssi": -12.5,
                }
            ],
            "removed": ["3e8413"],
        }
    )
    assert msg.updated[0].icao == "4951ce"
    # round-trips without loss
    assert msg.model_dump(mode="json")["updated"][0]["callsign"] == "TAP123"


def test_ws_rejects_bad_icao():
    with pytest.raises(ValidationError):
        InterestingMessage.model_validate(
            {
                "type": "interesting",
                "ts": 1,
                "icao": "ZZZZZZ",
                "severity": "critical",
                "rule": "squawk-7700",
                "callsign": None,
            }
        )


def test_mqtt_radio2_mode_enum_enforced():
    ok = Radio2Mode.model_validate({"ts": 1, "mode": "satellite", "since": 1, "reason": "preempt"})
    assert ok.mode.value == "satellite"
    with pytest.raises(ValidationError):
        Radio2Mode.model_validate({"ts": 1, "mode": "fm-radio", "since": 1, "reason": "manual"})


def test_mqtt_lwt_health_shape():
    """The broker-published LWT payload must validate — it's written in mosquitto config."""
    lwt = Radio2Health.model_validate({"ts": 0, "ok": False, "reason": "offline"})
    assert lwt.ok is False


def test_mqtt_sys_health_bounds():
    with pytest.raises(ValidationError):
        SysHealth.model_validate(
            {
                "ts": 1,
                "ok": True,
                "cpuPct": 5,
                "memMb": 100,
                "tempC": 50,
                "throttled": False,
                "diskFreePct": 150,
            }
        )
