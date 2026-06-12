# Status: build-rpi-aviation-platform

**Risk:** Medium | **Updated:** 2026-06-12
**Stack:** Greenfield — proposed: Python (FastAPI) + TypeScript/React + SQLite / Docker Compose (ARM64, local-only)

## Progress
- [x] Discovery - Completed (incl. full PRD + user stories)
- [x] Research - Completed (ecosystem + architecture-feasibility)
- [x] Design - Completed (03_ARCHITECTURE + 8 ADRs + 03_PROJECT_SPEC)
- [x] Planning - Completed (04_IMPLEMENTATION_PLAN: 12 phases → M0–M5)
- [~] Implementation - In Progress (Phase 2/12)
  - Phase 1 (scaffold/schemas/CI): ✓ Complete — 23 Python tests + 1 web test green, lint clean, codegen drift-free (a5eb989)
  - Phase 2 (Node A radio stack): ✓ Complete — live ADS-B decode on tattoine-watcher (mosquitto+ultrafeeder), restart-safe (reboot test passed), health on bus, baseline recorded. 24 h passive soak running.
  - Node B (192.168.31.71, "tattoine-watcher-beacon"): base-provisioned early (docker/blacklist/udev/health→NodeA broker). ⚠️ UNDER-VOLTAGE (0x50005) — replace PSU before Phase 8.
  - Phase 3 (gateway core): ✓ Complete — ingest→state→priority→WS/REST live on Node A. 43 tests (incl. TR-1 latency probe), lint clean. Hardware-verified: 1 Hz delta cadence (median 1.01 s), topic filter live, both-node health via MQTT bridge, RAM caps enforced (gw 45 MB / readsb 56 MB / mosq 4 MB).
  - Phase 4 (web foundation): ✓ Complete — live dashboard at http://192.168.31.218:8080. WS client (reconnect-backoff, tested w/ fake sockets), zustand store (snapshot-authoritative), Leaflet canvas map (rotated icons/trails/rings, imperative sync), responsive list/detail, dark theme, tile cache (fetch-once→offline), SPA volume-mounted (UI deploys = rsync, no rebuild). 11 web tests; 54 total. **= M1 exit** (48 h soak running passively).
  - Phase 5 (enrichment + rules + sightings): ⏳ next
  - DEVIATION: readsb+tar1090 ship as ONE container (sdr-enthusiasts ultrafeeder) — community-standard packaging, fewer moving parts on 1 GB; noted in compose header.
- [ ] Review - Not started
- [ ] Security - Not started
- [ ] Deploy - Not started
- [ ] Observe - Not started
- [ ] Retro - Not started

## Detected Stack
Greenfield repository (LICENSE only). Proposed: Python 3.12 + FastAPI backend services, TypeScript + React (Vite) dashboard, SQLite (WAL) storage, Docker Compose deployment, ARM64/Raspberry Pi target, wrapped OSS decoders (readsb, AIS-catcher, rtl_airband, satdump). Stack to be ratified in `/design-system`.

## Applicable Expert Commands
- `/language/python-pro` — backend services & orchestrator patterns
- `/language/typescript-pro` + `/language/javascript-react-pro` — dashboard
- `/language/software-engineer-pro` — architecture, bounded contexts, event-driven design
- `/quality/lint-setup`, `/quality/test-strategy` — bootstrap quality tooling (all missing)

## Key Decisions
- Wrap mature OSS decoders; never write DSP in-house (Guardrail #1)
- ADS-B pipeline isolated with zero runtime dependency on other contexts
- Summary-level persistence only (SD-card write budget, NFR-6)
- **Research outcomes (proposed, ratify in design):**
  - Event bus → **MQTT (Mosquitto)** over Redis — lighter, retained-state, AIS-catcher native; "Redis only if justified" → MQTT justified
  - Backend → **FastAPI/Python** (Skyfield pass-prediction); Go WS-gateway as escape hatch if fan-out hot
  - Radio #2 → **single-owner orchestrator + device-token gate** (avoid Docker-socket privilege); FSM + watchdog
  - SatDump → **record-then-decode + cgroup CPU caps + readsb core reservation** (protect ADS-B, NFR-2/4)
  - ADS-B decoder → **readsb** over dump1090-fa; tar1090 as secondary/expert view
  - Audio → **Icecast/HLS** default (simplicity); WS/Opus only if latency complaints
  - Map → **Leaflet for TV mode** (compat), MapLibre optional for interactive desktop
- **HARDWARE DECISION (user, 2026-06-12): two-node Pi 3B split.**
  - Node A (existing `tattoine-watcher`, Pi 3B): Radio #1 ADS-B (readsb+tar1090) always-on + MQTT broker + FastAPI gateway/WS + React dashboard + SQLite. Self-sufficient if Node B down.
  - Node B (second Pi 3B): Radio #2 orchestrator + rtl_airband/AIS-catcher/SatDump; all CPU-heavy decode isolated here.
  - **Dissolves R-1, R-2, R-3** via physical separation (separate CPU + USB bus + PSU per node; one dongle per host so no serial collision).
  - Tradeoff: mild distribution (two LAN nodes over MQTT, per-node compose files) — justified vs buying a Pi 4. NOT Kubernetes/clustered.
  - Watch item: METEOR LRPT decode RAM spike (~300–400 MB) on Node B's 1 GB.
- **DONGLES (confirmed 2026-06-12): 2× Stratux LowPowerV2** (`iProduct: LowPowerV2`, serials `stx:0:28`/`stx:0:29`). RTL2832U+R820T2, **stock librtlsdr — R-4 CLOSED**, no Blog-v4 driver fork. Factory-unique serials → pinning works without rtl_eeprom. Low-power design = built for 2-on-one-Pi; power risk further relaxed. Caveats: MCX antenna connectors (check pigtails); aviation-tuned — assign one to ADS-B (Node A), other to Radio #2 (Node B); satellite RX upgrade path = generic dongle ~$30 if M4 underwhelms.
- **Open (decide in design):** aircraft-DB redistribution license; cross-node Docker Compose layout (two files vs Docker contexts)

## Critical risks surfaced
- ~~R-1 SatDump CPU starving ADS-B~~ → mitigated by two-node split
- ~~R-2 dual-SDR USB power/bandwidth~~ → mitigated by two-node split
- ~~R-3 Radio-#2 device contention~~ (cross-decoder) → still applies *within* Node B's single radio; FSM + device-token gate still needed
- R-10 Pi 3B below NFR-3 → addressed by splitting load; METEOR RAM on Node B is the residual watch item
- NEW: cross-node network dependency (Node A↔B over MQTT) — mitigated by Node A self-sufficiency + MQTT reconnect/retained state

## Implementation Plan (12 phases)
P1 scaffold/CI · P2 Node A radio stack live · P3 gateway core · P4 web map/list (M1 exit) · P5 enrichment+rules+sightings · P6 hero/TV mode (M2 exit) · P7 radio2 FSM off-hardware · P8 Node B + ATC (M3 exit) · P9 AIS · P10 satellite e2e (M4 exit) · P11 history/analytics · P12 hardening/v1.0 (M5 exit)
**Hardware context:** repurposed FR24 beacon — Node A live, antennas proven, both Stratux dongles on it; dongle `stx:0:28` relocates to Node B in P8.

## Architecture Decision Records (accepted 2026-06-12)
- ADR-001 Two-node Pi 3B topology (Node A core / Node B radio-2 workhorse)
- ADR-002 MQTT/Mosquitto bus, cross-node + notifications only (ADS-B stays off-bus)
- ADR-003 All-Python backend (FastAPI gateway, asyncio radio2); Go = evidence-gated escape hatch
- ADR-004 Radio-2 decoders as supervised child processes in ONE container (token-gate protocol deleted)
- ADR-005 SQLite WAL, summary-only, single writer (gateway); Node B never touches DB
- ADR-006 Satellite record-then-decode; APT default, LRPT config-gated experimental
- ADR-007 ATC audio: rtl_airband → Icecast MP3 → browser <audio> direct (no HLS/WS-Opus)
- ADR-008 Leaflet-only mapping, canvas renderer, self-hosted raster tiles

## Artifacts
- 01_DISCOVERY.md
- 02_PRD.md (full PRD: FRs, NFRs, personas, UX principles, metrics, risks, roadmap, guardrails)
- 02_CODE_RESEARCH.md (ecosystem, decoder deps, device-contention, risks, recommendations)
- 03_USER_STORIES.md (24 stories across 9 epics, FR-traceable)
- 03_ARCHITECTURE.md (context/components/data/API/bus/state/persistence/failure/perf/security/monorepo/deps)
- 03_ADR-001…008 (8 decision records with alternatives + tradeoffs)
- 03_PROJECT_SPEC.md (TRs, measurable NFRs, TS/MQTT/config contracts, testing, flags, rollback)
- 04_IMPLEMENTATION_PLAN.md (12 phases, tasks→files, per-phase tests/AC/rollback, test strategy)
