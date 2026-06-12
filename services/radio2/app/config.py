"""Config for the radio2 supervisor — the subset of the shared config.yaml this
service needs (receiver, radio2, nodes, timezone). Independent of the gateway's
loader so the two services stay decoupled (one container = one bounded context).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfigError(Exception):
    """Invalid/missing config — message is user-facing."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore")  # ignore gateway-only sections


class Receiver(_Strict):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    alt_m: float = 0


class ScheduleBlock(_Strict):
    mode: Literal["atc", "ais"]
    from_: str = Field(alias="from")
    to: str
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class SatPipeline(_Strict):
    enabled: bool = False


class Satellite(_Strict):
    min_elevation_deg: float = Field(default=30, ge=0, le=90)
    apt: SatPipeline = SatPipeline(enabled=True)
    lrpt: SatPipeline = SatPipeline(enabled=False)


class Atc(_Strict):
    channels_mhz: list[float] = Field(default_factory=list)
    icecast_url: str | None = None  # browser pull URL (via the gateway)
    icecast_host: str = "icecast"  # rtl_airband push target (compose-internal)
    icecast_port: int = Field(default=8000, ge=1, le=65535)
    icecast_mount: str = "atc"
    gain: float = 28.0


class Radio2Config(_Strict):
    schedule: list[ScheduleBlock] = Field(default_factory=list)
    satellite: Satellite = Satellite()
    atc: Atc = Atc()
    sdr_serial: str = "stx:0:28"  # SDR #2 serial
    # when set (e.g. tcp://10.55.0.1:55132), decoders read SDR #2 over SoapyRemote
    # from Node A instead of a local USB dongle (ADR-009 capture-on-A/decode-on-B)
    sdr_remote: str | None = None


class Nodes(_Strict):
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = Field(default=1883, ge=1, le=65535)


class Config(_Strict):
    receiver: Receiver
    radio2: Radio2Config = Radio2Config()
    nodes: Nodes = Nodes()
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"unknown timezone {v!r}") from e
        return v


def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"config not found: {p}")
    try:
        raw = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"{p} is not valid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{p} must be a YAML mapping")
    try:
        return Config.model_validate(raw)
    except Exception as e:
        raise ConfigError(f"invalid config in {p}: {e}") from e
