"""Config loader validation — table-driven per 04_IMPLEMENTATION_PLAN P1 tests."""

from pathlib import Path

import pytest

from app.config import Config, ConfigError, load_config

EXAMPLE = Path(__file__).parents[3] / "shared" / "config" / "config.example.yaml"

MINIMAL = """
receiver: {lat: 38.7169, lon: -9.1399}
nodes: {gateway_url: "http://a:8080", mqtt_host: a}
"""


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p


def test_example_config_is_valid():
    """The shipped example must always load — it is the user's starting point."""
    cfg = load_config(EXAMPLE)
    assert isinstance(cfg, Config)
    assert cfg.receiver.lat == pytest.approx(38.7169)
    assert cfg.radio2.satellite.apt.enabled is True
    assert cfg.radio2.satellite.lrpt.enabled is False  # ADR-006 gate


def test_minimal_config_applies_defaults(tmp_path):
    cfg = load_config(_write(tmp_path, MINIMAL))
    assert cfg.adsb.poll_interval_s == 1.0
    assert cfg.adsb.trail_len == 100
    assert cfg.nodes.mqtt_port == 1883
    assert cfg.retention.sightings_days == 30
    assert cfg.radio2.schedule == []


def test_missing_file_message_is_actionable(tmp_path):
    with pytest.raises(ConfigError, match="config.example.yaml"):
        load_config(tmp_path / "nope.yaml")


def test_invalid_yaml_rejected(tmp_path):
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(_write(tmp_path, "receiver: [unclosed"))


def test_non_mapping_rejected(tmp_path):
    with pytest.raises(ConfigError, match="YAML mapping"):
        load_config(_write(tmp_path, "- just\n- a list\n"))


@pytest.mark.parametrize(
    ("snippet", "expect"),
    [
        # bad latitude
        ("receiver: {lat: 91, lon: 0}\nnodes: {gateway_url: u, mqtt_host: h}", "receiver.lat"),
        # bad longitude
        ("receiver: {lat: 0, lon: -181}\nnodes: {gateway_url: u, mqtt_host: h}", "receiver.lon"),
        # missing receiver entirely
        ("nodes: {gateway_url: u, mqtt_host: h}", "receiver"),
        # missing nodes
        ("receiver: {lat: 0, lon: 0}", "nodes"),
        # malformed schedule time
        (
            MINIMAL + 'radio2: {schedule: [{mode: atc, from: "7:00", to: "23:00"}]}',
            "HH:MM",
        ),
        # unknown schedule mode (satellite is scheduler-driven, not block-schedulable)
        (
            MINIMAL + 'radio2: {schedule: [{mode: satellite, from: "07:00", to: "08:00"}]}',
            "schedule",
        ),
        # ATC channel outside airband
        (MINIMAL + "radio2: {atc: {channels_mhz: [99.5]}}", "118"),
        # typo'd key rejected (extra=forbid catches silent misconfiguration)
        (MINIMAL + "adsbx: {}", "adsbx"),
        # bad watchlist match kind
        (MINIMAL + "watchlist: [{match: tail_number, value: x}]", "watchlist"),
        # mqtt port out of range
        (
            "receiver: {lat: 0, lon: 0}\nnodes: {gateway_url: u, mqtt_host: h, mqtt_port: 70000}",
            "mqtt_port",
        ),
    ],
)
def test_invalid_configs_rejected_with_location(tmp_path, snippet, expect):
    with pytest.raises(ConfigError) as ei:
        load_config(_write(tmp_path, snippet))
    assert expect in str(ei.value)


def test_error_lists_every_problem_not_just_first(tmp_path):
    bad = "receiver: {lat: 91, lon: -181}\nnodes: {gateway_url: u, mqtt_host: h}"
    with pytest.raises(ConfigError) as ei:
        load_config(_write(tmp_path, bad))
    msg = str(ei.value)
    assert "receiver.lat" in msg and "receiver.lon" in msg
