# Roadmap

Post-v1 enhancements, ordered. Core build phases live in
`.claude/planning/build-rpi-aviation-platform/`.

## Near-term (after Node B is on air)

### R1 — Revised Node B bring-up: SoapyRemote capture-on-A / decode-on-B (ADR-009)
Both dongles stay on Node A; Node A runs SoapySDRServer for SDR #2; Node B
decoders open the remote device over the dedicated `10.55.0.x` link. Offloads
ATC/AIS/satellite decode onto Node B. Gated on the Node B PSU swap.
**Status:** dedicated link done + verified (94 Mbit/s); SoapyRemote wiring next.

### R2 — OpenAIP airspace overlay
Toggleable Leaflet overlay (CTR/TMA/airways/navaids) for the Lisbon area, served
through the gateway tile proxy with the API key server-side (key already in the
Pi `.env`). Region-cached into the existing `/tiles` store for offline use.

### R3 — Single-node profile (Pi 4 / Pi 5 / other adopters)
Make a one-host deployment first-class so newer hardware (or other users) can run
everything on one Pi:
- `install-node.sh --role single` running both compose stacks (merged
  `compose.single.yml` or `-f node-a -f node-b`)
- MQTT host + Icecast URL → localhost (already config-driven)
- **Re-enable the resource mitigations the two-node split made moot**: cgroup CPU
  caps + core-pinning on the satellite container, and satdump record-then-decode
  at `nice 19` — so SatDump can't starve ADS-B on one host (R-1)
- All SDRs local (Pi 4/5 USB-3 + separate controller makes dual-dongle a non-issue)
**Sequencing:** after R1 (the user's stated order).

## Backlog
- Multi-channel ATC selector in the UI (currently single primary mount)
- squelch → `atc/activity` event source from rtl_airband (UI pulse already wired)
- METEOR LRPT enablement once validated on the target hardware (ADR-006)
- Feeder hooks (FlightAware/FR24/ADSBx) — explicitly out of v1 scope
