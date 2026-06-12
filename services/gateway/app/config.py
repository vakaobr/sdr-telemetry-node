"""Configuration loading and validation for sdr-telemetry-node services.

Single config.yaml ships to both nodes; each role reads its sections.
Services refuse to start on invalid config — errors are actionable, not stack traces.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ConfigError(Exception):
    """Raised when config.yaml is missing or invalid. Message is user-facing."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Receiver(_StrictModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    alt_m: float = 0


class Nodes(_StrictModel):
    gateway_url: str
    mqtt_host: str
    mqtt_port: int = Field(default=1883, ge=1, le=65535)


class Adsb(_StrictModel):
    readsb_url: str = "http://readsb:8079"
    poll_interval_s: float = Field(default=1.0, gt=0)
    staleness_pos_s: int = Field(default=60, gt=0)
    staleness_msg_s: int = Field(default=300, gt=0)
    trail_len: int = Field(default=100, ge=1, le=1000)


class ScheduleBlock(_StrictModel):
    mode: Literal["atc", "ais"]
    from_: str = Field(alias="from")
    to: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("from_", "to")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        if not _TIME_RE.match(v):
            raise ValueError(f"expected HH:MM (24h), got {v!r}")
        return v


class SatPipeline(_StrictModel):
    enabled: bool = False


class Satellite(_StrictModel):
    min_elevation_deg: float = Field(default=30, ge=0, le=90)
    apt: SatPipeline = SatPipeline(enabled=True)
    lrpt: SatPipeline = SatPipeline(enabled=False)


class Atc(_StrictModel):
    channels_mhz: list[float] = Field(default_factory=list)
    icecast_url: str | None = None
    icecast_host: str = "icecast"  # radio2-side push target (accepted here so shared
    icecast_port: int = 8000  # config.yaml validates; gateway only reads icecast_url)
    icecast_mount: str = "atc"
    gain: float = 28.0

    @field_validator("channels_mhz")
    @classmethod
    def _airband(cls, v: list[float]) -> list[float]:
        for ch in v:
            if not (118.0 <= ch <= 137.0):
                raise ValueError(f"ATC channel {ch} MHz outside airband 118–137 MHz")
        return v


class Radio2(_StrictModel):
    sdr_serial: str = "stx:0:28"  # consumed by the radio2 service; accepted here so the
    schedule: list[ScheduleBlock] = Field(default_factory=list)  # shared config validates
    satellite: Satellite = Satellite()
    atc: Atc = Atc()


class OnlineEnrichment(_StrictModel):
    enabled: bool = True
    cache_ttl_days: int = Field(default=30, ge=1)


class Enrichment(_StrictModel):
    online: OnlineEnrichment = OnlineEnrichment()


class WatchlistEntry(_StrictModel):
    match: Literal["hex", "callsign_glob", "registration", "type_code"]
    value: str = Field(min_length=1)

    @field_validator("value")
    @classmethod
    def _hex_shape(cls, v: str, info) -> str:
        # hex entries must be 6 lowercase hex chars; other kinds are free-form
        return v


class Retention(_StrictModel):
    sightings_days: int = Field(default=30, ge=1)
    passes_keep: int = Field(default=50, ge=1)


class Ui(_StrictModel):
    tv_rotation: list[str] = Field(default_factory=lambda: ["hero", "map", "stats"])


class Config(_StrictModel):
    receiver: Receiver
    nodes: Nodes
    timezone: str = "UTC"  # IANA tz; radio2 interprets schedule blocks in it
    adsb: Adsb = Adsb()
    radio2: Radio2 = Radio2()
    enrichment: Enrichment = Enrichment()
    watchlist: list[WatchlistEntry] = Field(default_factory=list)
    retention: Retention = Retention()
    ui: Ui = Ui()


def load_config(path: str | Path) -> Config:
    """Load and validate config.yaml.

    Raises ConfigError with an actionable, user-facing message on any problem.
    """
    p = Path(path)
    if not p.exists():
        raise ConfigError(
            f"config file not found: {p} — copy shared/config/config.example.yaml "
            f"to {p} and set your receiver location"
        )
    try:
        raw = yaml.safe_load(p.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"config file {p} is not valid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"config file {p} must be a YAML mapping, got {type(raw).__name__}")
    try:
        return Config.model_validate(raw)
    except Exception as e:  # pydantic.ValidationError — re-shaped for humans
        raise ConfigError(_humanize_validation_error(p, e)) from e


def _humanize_validation_error(path: Path, err: Exception) -> str:
    """Turn a pydantic ValidationError into line-per-problem guidance."""
    from pydantic import ValidationError

    if not isinstance(err, ValidationError):
        return f"invalid config in {path}: {err}"
    lines = [f"invalid config in {path}:"]
    for e in err.errors():
        loc = ".".join(str(x) for x in e["loc"])
        lines.append(f"  - {loc}: {e['msg']}")
    return "\n".join(lines)
