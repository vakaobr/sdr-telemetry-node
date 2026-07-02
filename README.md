# sdr-telemetry-node

Self-hosted aviation intelligence platform for Raspberry Pi. Two RTL-SDR radios, one beautiful
local dashboard: live ADS-B aircraft tracking, ATC airband audio, AIS vessels, and a roadmap toward
NOAA/METEOR weather-satellite imagery. Local-first, offline-capable, no cloud.

**Topology:** two Pi 3B nodes joined by a dedicated point-to-point Ethernet link (`10.55.0.x`).
- **Node A** (always-on core): readsb + tar1090 (ADS-B), MQTT broker, gateway (REST/WS/UI + AIS
  via the AISStream internet feed), SQLite, and radio2 + Icecast for ATC airband decode. Both SDR
  dongles live here.
- **Node B**: currently a spare, reserved for future satellite decode (SatDump) once a 137 MHz
  antenna exists.

ATC decode runs on Node A directly rather than on Node B over SoapyRemote (ADR-009 reversed): AIS
is an internet feed and satellite is deferred, so SDR #2's only job is a light ATC decode next to
the dongle it already uses. A single-node deployment (Pi 4/5 or other adopters) is also supported
(`scripts/up-single.sh`). See the [Roadmap](ROADMAP.md) for what is done and what is planned.

## Quick start (development)

```bash
make setup     # python venv + editable installs + web npm install
make test      # gateway, radio2, web suites
make lint      # ruff + eslint + tsc
make codegen   # regenerate models/types from shared/schemas
```

## Repository layout

```
shared/schemas/    contract source of truth (WS + MQTT JSON Schemas)
shared/config/     config.example.yaml
services/gateway/  FastAPI: ingest, state, enrichment, REST+WS, persistence (Node A)
services/radio2/   SDR#2 supervisor: FSM, pass scheduler, decoder children (runs on Node A)
web/               React + Vite dashboard (TV mode + interactive)
docker/            per-node compose files + images
scripts/           codegen, node install, operational tooling
docs/              install/runbook/baseline
```

## Design docs

Planning artifacts live in `.claude/planning/build-rpi-aviation-platform/`: PRD, architecture,
ADRs 001 to 010, project spec, and the phased implementation plan. Outstanding work is tracked in
the [Roadmap](ROADMAP.md).

## License

See [LICENSE](LICENSE).
