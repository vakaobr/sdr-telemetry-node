# sdr-telemetry-node

Self-hosted aviation intelligence platform for Raspberry Pi. Two RTL-SDR radios, one beautiful
local dashboard: live ADS-B aircraft tracking, ATC airband audio, AIS vessels, and NOAA/METEOR
weather-satellite imagery — local-first, offline-capable, no cloud.

**Topology:** two Pi 3B nodes.
- **Node A** — always-on core: readsb + tar1090, MQTT broker, gateway (REST/WS/UI), SQLite
- **Node B** — shared-radio workhorse: orchestrated rtl_airband / AIS-catcher / SatDump + Icecast

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
services/radio2/   SDR#2 supervisor: FSM, pass scheduler, decoder children (Node B)
web/               React + Vite dashboard (TV mode + interactive)
docker/            per-node compose files + images
scripts/           codegen, node install, operational tooling
docs/              install/runbook/baseline
```

## Design docs

Planning artifacts live in `.claude/planning/build-rpi-aviation-platform/` — PRD, architecture,
ADRs 001–008, project spec, and the phased implementation plan.

## License

See [LICENSE](LICENSE).
