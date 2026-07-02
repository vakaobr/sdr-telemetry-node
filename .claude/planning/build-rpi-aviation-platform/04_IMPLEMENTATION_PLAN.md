# Implementation Plan: build-rpi-aviation-platform

## Overview
- **Total Phases:** 12 (mapped to PRD milestones M0–M5)
- **Estimated Effort:** XL (phased; each phase single-session, working system after each)
- **Dependencies:** Node A (`tattoine-watcher`, Pi 3B) live & SSH-able ✓ · 2× Stratux LowPowerV2 dongles on Node A ✓ · 1090 antenna chain proven (ex-FR24 beacon) ✓ · Node B Pi 3B **bare** (bring-up = Phase 8) · Docker not yet installed on Node A (Phase 2)
- **Feature Flags:** per 03_PROJECT_SPEC §6 — `radio2.satellite.apt/lrpt.enabled`, `enrichment.online.enabled`, `ui.tv_rotation`; modes land default-off until their phase's AC passes
- **Hardware note:** dev/test runs on amd64 (compose works cross-arch via buildx); every phase's AC that says "on Pi" means the real Node A/B.

---

## Phase 1: Monorepo Scaffold, Schemas & CI  *(M0)*
### Objective
Repo skeleton with contract-first schemas, toolchain, and CI green — the "boring foundation" every later phase builds on.

### Tasks
- [ ] 1.1 Monorepo layout per 03_ARCHITECTURE §12 — `services/{gateway,radio2}/`, `web/`, `shared/schemas/`, `docker/`, `scripts/`, `docs/`
- [ ] 1.2 JSON Schemas for all WS messages + MQTT payloads (from 03_PROJECT_SPEC §3) — `shared/schemas/{ws,mqtt}/*.json`
- [ ] 1.3 Codegen: schemas → pydantic models + TS types; drift check script — `scripts/codegen.py`, `services/gateway/app/models/generated.py`, `web/src/types/generated.ts`
- [ ] 1.4 Python tooling: uv/poetry, ruff, pytest scaffolds for both services — `services/*/pyproject.toml`, `services/*/tests/test_smoke.py`
- [ ] 1.5 Web tooling: Vite + React + TS + vitest scaffold — `web/package.json`, `web/vite.config.ts`
- [ ] 1.6 `config.example.yaml` + pydantic config loader with validation errors — `shared/config/config.example.yaml`, `services/gateway/app/config.py` (shared module)
- [ ] 1.7 CI: lint + test + codegen-drift + multi-arch buildx (arm64/amd64) — `.github/workflows/ci.yml`
- [ ] 1.8 Pre-commit with gitleaks (repo security policy) — `.pre-commit-config.yaml`

### Tests
- [ ] Unit: config loader rejects bad lat/lon, missing receiver, malformed schedule (table-driven)
- [ ] CI: codegen-drift job fails when a schema and generated file disagree (prove it once, then fix)

### Acceptance Criteria
- `git clone && make setup && make test` green on dev machine; CI green; buildx produces arm64 images for stub services

### Rollback
- Greenfield: `git revert` of the scaffold commits; nothing deployed

---

## Phase 2: Node A Radio Stack Live  *(M0/M1)*
### Objective
Real RF decoded on real hardware: readsb + tar1090 + mosquitto under compose on `tattoine-watcher`.

### Tasks
- [ ] 2.1 Install Docker + compose on Node A; host prep script (dvb blacklist, udev rule pinning serial `stx:0:29`→ADS-B) — `scripts/install-node.sh`, `scripts/udev/99-rtlsdr.rules`
- [ ] 2.2 `docker/node-a/compose.yml`: mosquitto (LAN-bound, retained config), readsb (device by serial, `aircraft.json` exposed), tar1090 `:8078` — + `docker/mosquitto/mosquitto.conf`
- [ ] 2.3 readsb tuned for Pi 3B (mem caps per 03_ARCHITECTURE §10) — compose resource limits
- [ ] 2.4 Verify decode with the proven FR24-era antenna; record baseline msg-rate/range — `docs/baseline.md`
- [ ] 2.5 Health: `sys/node-a/health` publisher (tiny host cron → mosquitto_pub w/ LWT) — `scripts/node-health.sh`

### Tests
- [ ] Integration: `mosquitto_sub` sees retained health topic; `curl aircraft.json` returns live traffic
- [ ] Soak (passive): 24 h readsb uptime, no USB resets in `dmesg`

### Acceptance Criteria
- tar1090 shows live aircraft at `http://tattoine-watcher.local:8078`; aircraft.json msg-rate ≥ FR24-era expectations; 24 h clean

### Rollback
- `docker compose down` — Node A returns to bare OS; no host state beyond Docker + udev rule (script has `--uninstall`)

---

## Phase 3: Gateway Core — Ingest → State → WS/REST  *(M1)*
### Objective
The product's brain: aircraft state table with deltas streaming over WebSocket.

### Tasks
- [ ] 3.1 readsb poller (1 Hz, httpx, loopback) — `services/gateway/app/ingest/readsb.py`
- [ ] 3.2 State table: diff, staleness expiry (60/300 s), distance/bearing, trails ring(100) — `app/state/aircraft.py`
- [ ] 3.3 Priority engine per FR-1.4 (distance × low-alt weighting) — `app/state/priority.py`
- [ ] 3.4 WS endpoint: snapshot-then-delta protocol, 1 Hz coalesced batches, heartbeat — `app/ws/server.py`, `app/ws/broadcast.py`
- [ ] 3.5 REST: `/api/v1/aircraft[,{icao}]`, `/healthz`, RFC-7807 handler — `app/api/aircraft.py`, `app/api/errors.py`
- [ ] 3.6 MQTT client wiring (paho, sub `sys/+/health`, pub later) — `app/bus/mqtt.py`
- [ ] 3.7 Gateway Dockerfile + join node-a compose — `docker/gateway/Dockerfile`, `docker/node-a/compose.yml`

### Tests
- [ ] Unit: diff engine (new/update/expire), priority ordering fixtures, trail capping — `tests/test_state.py`, `tests/test_priority.py`
- [ ] Integration: fake `aircraft.json` server → WS client receives snapshot+correct deltas — `tests/integration/test_ws_flow.py`
- [ ] Latency: synthetic timestamp probe asserts ingest→WS ≤ 2 s p95 (TR-1, dev hardware)

### Acceptance Criteria
- `wscat` against Node A shows live snapshot + deltas; gateway RAM < 256 MB on Pi; TR-1 probe passes on Node A

### Rollback
- Remove gateway service from compose; readsb/tar1090 untouched (Phase 2 state)

---

## Phase 4: Web Foundation — Live Map & List  *(M1 exit)*
### Objective
First real UI value: aircraft live on a Leaflet map + list, fed only by WS.

### Tasks
- [ ] 4.1 ws-client: connect/reconnect-backoff/snapshot-merge — `web/src/ws/client.ts`
- [ ] 4.2 Zustand store from generated types — `web/src/state/store.ts`
- [ ] 4.3 Leaflet map (canvas): heading-rotated icons, trails, range rings, receiver marker — `web/src/components/Map/*`
- [ ] 4.4 Aircraft list + detail pane (responsive ≥360 px) — `web/src/views/interactive/*`
- [ ] 4.5 Offline raster tile pack pipeline + tile server route in gateway — `scripts/make-tilepack.sh`, `services/gateway/app/api/tiles.py`
- [ ] 4.6 Gateway serves built bundle — `app/api/static.py`, CI build step

### Tests
- [ ] Unit (vitest): reconnect → re-snapshot store merge; reducer correctness
- [ ] E2E (Playwright): map renders ≥1 mocked aircraft; list→detail navigation; mobile viewport

### Acceptance Criteria
- `http://tattoine-watcher.local:8080` shows live traffic on phone + desktop with no manual refresh; works with router's internet unplugged (offline tiles)
- **= PRD M1 exit: 48 h soak clean**

### Rollback
- Gateway flag `ui.enabled:false` falls back to 404→tar1090 link; or revert bundle — API unaffected

---

## Phase 5: Enrichment, Interesting Rules & Sightings  *(M1→M2)*
### Objective
Hex codes become *aircraft* (type/operator/reg), emergencies/military/watchlist surface, history starts recording.

### Tasks
- [ ] 5.1 Bundle offline aircraft DB + license check (open Q6 — verify tar1090-db/Mictronics redistribution; fallback: download-on-first-boot script) — `data/aircraft-db/`, `scripts/fetch-aircraft-db.sh`
- [ ] 5.2 Enrichment service: local lookup → SQLite cache → optional online (adsbdb, fail-soft, `enrichment.online.enabled`) — `app/enrich/*`
- [ ] 5.3 Interesting rules: squawk 7500/7600/7700, military ranges, watchlist (hex/callsign-glob/type) — `app/rules/interesting.py`
- [ ] 5.4 SQLite layer: schema 03_ARCHITECTURE §3, migrations runner, WAL setup — `app/persist/{db.py,migrations/001_init.sql}`
- [ ] 5.5 Sightings recorder: contact-close upsert + 60 s batch — `app/persist/sightings.py`
- [ ] 5.6 Watchlist config + `PUT /api/v1/config/watchlist` — `app/api/config.py`
- [ ] 5.7 UI: enrichment fields in list/detail, interesting banner (severity-styled), graceful "— · offline" placeholders — `web/src/components/{Banner,EnrichedFields}/*`

### Tests
- [ ] Unit: fallback chain local→cache→online→placeholder (network mocked); rules table incl. glob edge cases; batch writer loss-window ≤ 60 s on SIGKILL
- [ ] Integration: **offline scenario** — full stack, network namespace cut: enrichment degrades, zero errors (TR-5 baseline)
- [ ] Migration: 001 applies on empty + is idempotent; `app.db.pre-001` backup created

### Acceptance Criteria
- ≥90% of live airframes resolve type+reg offline; 7700 test fixture → CRITICAL banner ≤ 2 s; sightings rows appear; writes measured < 1 GB/day pace

### Rollback
- `enrichment.online.enabled:false`; rules flag-off; DB: restore `.pre-001` copy (gateway refuses mismatched schema — safe)

---

## Phase 6: FlightWall Experience — Hero + TV Mode  *(M2 exit)*
### Objective
The product's face: glanceable hero view and burn-in-safe TV rotation.

### Tasks
- [ ] 6.1 Hero panel: priority aircraft, giant type (callsign/type/route/alt/dist), smooth handoff animation — `web/src/views/tv/Hero.tsx`
- [ ] 6.2 TV rotation shell: hero→map→stats (satellite panel placeholder behind `ui.tv_rotation`), cursor-hide, pixel-shift burn-in guard — `web/src/views/tv/Rotation.tsx`
- [ ] 6.3 `/tv` route: zero-chrome, autostarts rotation — `web/src/views/tv/index.tsx`
- [ ] 6.4 10-ft type scale + dark theme tokens (≥24 px @1080p) — `web/src/theme/*`
- [ ] 6.5 Receiver stats panel (msg rate, count, max range live) — `web/src/views/tv/Stats.tsx`
- [ ] 6.6 Kiosk docs for Pi/TV browser autostart — `docs/wall-display.md`

### Tests
- [ ] Unit: hero-selection (priority churn debounce — no flapping between two near aircraft)
- [ ] E2E: `/tv` rotation cycles at configured cadence; 1080p screenshot diffs for layout regression
- [ ] Soak: 7-day TV-mode run on the actual wall display, RSS slope ≈ 0 (M2 exit; runs in background while later phases proceed)

### Acceptance Criteria
- The "wow demo" exists on your TV; hero readable at 10 ft; emergency banner overrides rotation
- **= PRD M2 exit** (soak completes in parallel)

### Rollback
- `/tv` route flag-off; interactive mode unaffected

---

## Phase 7: radio2 Supervisor — FSM + Scheduler (fake decoders)  *(M3 prep)*
### Objective
The novel-risk component, fully built and tested **off hardware**: FSM, schedule, pass prediction, preemption — decoders faked.

### Tasks
- [ ] 7.1 FSM per 03_ARCHITECTURE §6: states, transitions, watchdog, SIGKILL escalation, max-duration — `services/radio2/app/fsm.py`
- [ ] 7.2 Child-process runner (spawn/SIGTERM/waitpid, tini PID-1) — `app/proc.py`
- [ ] 7.3 Decoder adapters as **config-declared commands** + fake-decoder harness (scripted stdout/exit/hang modes) — `app/decoders/{base,fake}.py`, `tests/fakes/`
- [ ] 7.4 Skyfield scheduler: TLE cache/refresh/staleness, pass computation, AOS−60 s preempt hook — `app/scheduler/{tle.py,passes.py}`
- [ ] 7.5 Schedule blocks from config (atc/ais windows) — `app/scheduler/blocks.py`
- [ ] 7.6 MQTT publishing: `radio2/{mode,pass/next,health}` retained + LWT — `app/publish.py`
- [ ] 7.7 Manual override path: gateway `POST /api/v1/radio2/mode` → MQTT cmd topic → FSM (409 during pass unless force) — `services/gateway/app/api/radio2.py`, `app/fsm.py`
- [ ] 7.8 radio2 Dockerfile (python + decoder binaries layered for Phase 8) — `docker/radio2/Dockerfile`

### Tests
- [ ] Unit: **exhaustive FSM transition table** — incl. preempt-during-STARTING, fault-during-STOPPING, watchdog fire, hang→SIGKILL; pass math vs recorded TLE fixtures (known NOAA-19 passes)
- [ ] Integration: fake decoders + real mosquitto — full day simulated at 60×: schedule honored, satellite preempts ATC, returns after LOS, retained topics correct after broker restart
- [ ] Chaos: kill -9 supervisor mid-RUNNING → restart converges to scheduled mode ≤ 10 s

### Acceptance Criteria
- Simulated-day integration green; gateway UI shows live radio2 panel (mode/countdown) driven by retained topics; mode-switch ≤ 10 s p95 in tests (TR-4)

### Rollback
- radio2 not yet deployed to hardware — pure code revert

---

## Phase 8: Node B Bring-up + ATC Live  *(M3 exit)*
### Objective
Second Pi online; tower audio in the browser.

### Tasks
- [ ] 8.1 Node B flash + headless bring-up runbook (reuse tattoine-watcher procedure: Imager, SSH, 2.4 GHz `Quarto`, hostname `nodeb`) — `scripts/flash-node-b.md`
- [ ] 8.2 Move dongle `stx:0:28` to Node B; `install-node.sh --role node-b` (Docker, blacklist, udev) — script reuse
- [ ] 8.3 `docker/node-b/compose.yml`: radio2 + icecast; mounts, tmpfs, mem caps per §10 — + `docker/icecast/icecast.xml`
- [ ] 8.4 rtl_airband real adapter: config-gen from `atc.channels_mhz`, Icecast output, squelch-log → `atc/activity` MQTT — `app/decoders/rtl_airband.py`, `docker/radio2/rtl_airband.conf.tmpl`
- [ ] 8.5 Gateway: `audioUrl` in Radio2Status; UI audio player (tap-to-play, channel select, activity pulse) — `web/src/components/AtcPlayer/*`
- [ ] 8.6 Cross-node validation: LWT offline test (pull Node B power → UI shows offline ≤ 15 s) — TR-8 evidence in `docs/baseline.md`

### Tests
- [ ] Integration: real rtl_airband on Node B, local AM broadcast or airband test → audio reachable, latency ≤ 5 s measured
- [ ] Chaos: Node B power-pull mid-stream → Node A dashboard unaffected, radio2 panel → "offline"; reboot → FSM resumes schedule unattended

### Acceptance Criteria
- Tower/ATIS audible in browser on phone + TV; `atc/activity` pulses UI; Node B reboot self-heals
- **= PRD M3 exit**

### Rollback
- Node B compose down → system = Phase 6 state (Node A fully functional); UI radio2 panel shows offline (designed state, not breakage)

---

## Phase 9: AIS Mode  *(M4 part 1)*
### Objective
Vessels decoded during AIS schedule windows, rendered on the shared map.

### Tasks
- [ ] 9.1 AIS-catcher real adapter (native MQTT out → `ais/vessel` topic mapping) — `app/decoders/ais_catcher.py`
- [ ] 9.2 Gateway vessel state table (staleness 30 min) + `vessel_delta` WS + `/api/v1/vessels` — `app/state/vessels.py`, `app/api/vessels.py`
- [ ] 9.3 `vessels_seen` persistence (upsert) — `app/persist/vessels.py`, `migrations/002_vessels.sql`
- [ ] 9.4 Map vessel layer: distinct icons, toggle persisted per device — `web/src/components/Map/VesselLayer.tsx`

### Tests
- [ ] Unit: NMEA/JSON payload mapping fixtures (incl. partial messages — name arrives late); staleness 30 min
- [ ] Integration: replayed AIS capture file through AIS-catcher → vessels on dev map

### Acceptance Criteria
- During an AIS window, real vessels appear (coastal reception permitting — else replay-file validation counts); layer toggle works; mode switches ATC↔AIS per schedule cleanly on hardware

### Rollback
- Remove `ais` from schedule config — mode never granted; code dormant

---

## Phase 10: Satellite Pipeline End-to-End  *(M4 exit)*
### Objective
NOAA APT passes captured, decoded, in the gallery and TV rotation.

### Tasks
- [ ] 10.1 SatDump APT adapter: record-to-tmpfs during AOS..LOS, decode `nice 19` post-LOS (ADR-006) — `app/decoders/satdump.py`
- [ ] 10.2 Pass lifecycle: `satellite_passes` rows scheduled→captured→decoded/failed — `app/scheduler/passes.py`, gateway `migrations/003_passes.sql`
- [ ] 10.3 Image upload: radio2 → `POST /passes/{id}/images` w/ `X-Node-Key`; gateway media store + downscale — `app/upload.py`, `services/gateway/app/api/passes.py`
- [ ] 10.4 Gallery UI + pass metadata; TV rotation satellite panel (flag flip `ui.tv_rotation`) — `web/src/views/interactive/Gallery.tsx`, `web/src/views/tv/SatPanel.tsx`
- [ ] 10.5 LRPT behind `lrpt.enabled:false` + 1 GB empirical test (the ADR-006 watch item) — decode a recorded LRPT baseband on Node B, record RAM/result in `docs/baseline.md`
- [ ] 10.6 tmpfs sizing + OOM-failure marking (pass `failed`, note, no crash) — compose + `app/decoders/satdump.py`

### Tests
- [ ] Unit: pass state machine; upload retry (gateway briefly down → retries, idempotent by pass id)
- [ ] Integration: **recorded baseband fixture** → decode → upload → gallery (no sky needed in CI)
- [ ] Hardware: ≥ 3 real NOAA passes ≥ 30° captured over a week; ≥ 90% yield images (NFR satellite-capture)

### Acceptance Criteria
- Your own weather image from space on the wall TV; preempt-and-return verified live with ATC interrupted mid-pass
- **= PRD M4 exit; full priority chain proven**

### Rollback
- `satellite.apt.enabled:false` → scheduler never books passes; ATC/AIS schedule unaffected

---

## Phase 11: History, Analytics & System Page  *(M5 part 1)*
### Objective
The "what flew over while I was out" layer + operational self-service.

### Tasks
- [ ] 11.1 Sighting log API: cursor pagination, date/flag/type filters — `app/api/history.py`
- [ ] 11.2 Rollups job (hourly) + range/hourly stats endpoints — `app/jobs/rollups.py`, `app/api/stats.py`, `migrations/004_rollups.sql`
- [ ] 11.3 Retention job (04:00: sightings 30 d, passes keep-50, cache TTL, vacuum) — `app/jobs/retention.py`
- [ ] 11.4 Analytics UI: polar max-range plot, aircraft/day, busiest hours, interesting log — `web/src/views/interactive/Analytics.tsx`
- [ ] 11.5 System page: per-node health, SDR/decoder status, disk, temp/throttle, plain-language hints — `web/src/views/interactive/System.tsx`, `app/api/system.py`
- [ ] 11.6 Weekly backup script + restore runbook — `scripts/backup.sh`, `docs/runbook.md`

### Tests
- [ ] Unit: rollup math vs fixtures; retention boundary cases (exactly 30 d, empty tables)
- [ ] Integration: 90-day synthetic DB → retention prunes correctly + analytics endpoints stay < 200 ms on Pi-class CPU

### Acceptance Criteria
- 30 d of history queryable; analytics render offline; system page diagnoses pulled-SDR in plain language; daily writes verified < 1 GB

### Rollback
- Jobs flag-off (`retention.enabled:false` would be added if needed); endpoints additive — no breaking surface

---

## Phase 12: Hardening & v1.0 Release  *(M5 exit)*
### Objective
Prove the §6 PRD metrics on the real rig; ship v1.0.

### Tasks
- [ ] 12.1 Offline CI scenario completed for **all** P0 suites (network-cut compose harness) — `.github/workflows/ci.yml`, `tests/offline/`
- [ ] 12.2 Chaos suite scripted: per-container kill -9, Node B power-pull, SDR replug, broker restart — `scripts/chaos.sh` + assertions
- [ ] 12.3 Security pass: container hardening checklist (no-new-privs, read-only rootfs, non-root), `X-Node-Key` enforcement test, gitleaks clean — compose files, `tests/test_security.py`
- [ ] 12.4 Resource verification: TR-2 budgets measured over 72 h both nodes → `docs/baseline.md` final numbers
- [ ] 12.5 Docs: install guide (both nodes), antenna/MCX notes, config reference, troubleshooting, upgrade/rollback — `docs/*`, `README.md`
- [ ] 12.6 Release eng: image digest pinning, `v1.0.0` tags, support-bundle script — `scripts/support-bundle.sh`, compose digest pins
- [ ] 12.7 Final 7-day full-stack soak (all modes scheduled, ≥5 sat passes) against PRD §6 metrics table — sign-off in `00_STATUS.md`

### Tests
- [ ] The phase **is** tests: offline suite, chaos suite, soak metrics = release gate

### Acceptance Criteria
- Every PRD §6 metric green on the two-Pi-3B rig; rollback rehearsed once for real; `v1.0.0` tagged
- **= PRD M5 / v1.0**

### Rollback
- Release-candidate tags: `git checkout v0.x -- docker/ && compose up -d` per node (per 03_PROJECT_SPEC §7); Node A last

---

## Test Strategy

### Unit Tests
- **Coverage target:** 85% on `services/*/app` core logic (state, fsm, scheduler, rules, persist); UI store/reducers 80%. No coverage theater on adapters — they're integration-tested.
- **Key areas:** FSM transition table (exhaustive), state diffing/staleness, priority/hero selection, pass math vs recorded TLEs, enrichment fallback chain, retention boundaries.
- **Mocking strategy:** decoders are *processes*, so fakes are **scripted executables** (stdout/exit/hang modes), not Python mocks — the proc-runner is always exercised for real. Network mocked with `respx`; time injected (no sleeps; FSM takes a clock).

### Integration Tests
- API contract: pydantic/TS both codegen'd from `shared/schemas`; drift fails CI (the contract test).
- Real mosquitto in compose for bus tests; real SQLite (tmp file) for persistence; fake-decoder harness for radio2; recorded baseband + AIS capture fixtures so CI never needs RF or sky.
- **Offline-first posture:** the default integration profile runs with networking cut; online enrichment has its own opt-in suite.

### E2E Tests
- Playwright: live-map flow, list→detail, TV rotation, emergency banner override, audio tap-to-play (stream mocked), reconnect storm (kill WS ×5).
- Matrix: Chromium desktop, mobile viewport (390×844), 1080p TV viewport; real smart-TV browser = manual checklist per release.

### Performance Tests
- Baselines captured in Phase 2 (RF msg-rate/range) and re-measured each phase in `docs/baseline.md`.
- TR-1 latency probe (synthetic timestamp through ingest→WS) in CI per merge; TR-2 budgets on real Pis at phase exits; 7-day soaks at M2 and v1.0 gates.
- Load: 5 concurrent WS clients + reconnect storm script (NFR-8).

---

## Phase → Milestone map
P1–P2 = M0 · P3–P5 = M1 · P6 = M2 · P7–P8 = M3 · P9–P10 = M4 · P11–P12 = M5/v1.0
