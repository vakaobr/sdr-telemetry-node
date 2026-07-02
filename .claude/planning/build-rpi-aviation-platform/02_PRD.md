# PRD: sdr-telemetry-node — Self-Hosted Raspberry Pi Aviation Intelligence Platform

**Version:** 1.0 · **Date:** 2026-06-12 · **Status:** Ready for Architecture (`/design-system`)
**Issue:** `build-rpi-aviation-platform`

---

## 1. Product Overview

A self-hosted aviation intelligence platform running entirely on a Raspberry Pi with two USB SDR radios. It delivers a FlightWall-inspired, real-time aviation dashboard — but as a beautiful local web interface viewable on TVs, desktops, tablets, and phones instead of an LED matrix. Beyond ADS-B aircraft tracking, a second software-defined radio is intelligently time-shared across ATC airband audio, AIS vessel tracking, and NOAA/METEOR weather-satellite imagery.

**Product thesis:** the joy of FlightWall (ambient, glanceable, beautiful) + the power of a self-hosted SDR stack (open, extensible, private) — with none of the integration pain.

### What exists today / why now
| Option | Gap |
|---|---|
| FlightWall Mini (commercial) | Closed hardware, LED-only, no extensibility, cloud-tied |
| DIY (dump1090 + tar1090 + AIS-catcher + rtl_airband + satdump) | No unified UI, no SDR orchestration, hours of glue work, utilitarian visuals |
| FlightRadar24 / web trackers | Cloud data (not *your* antenna), no offline, no local pride-of-ownership |

---

## 2. User Personas

### P1 — "Wall-Display Wagner" (primary)
Aviation enthusiast, 35–65. Mounted a spare TV/tablet in office or living room. Wants an always-on, glanceable, *beautiful* display of what's flying overhead right now. Technical enough to flash an SD card and run `docker compose up`, not interested in maintaining services. **Cares about:** visual polish, zero-touch reliability, "what's that plane?" answers at a glance.

### P2 — "Spotter Sofia"
Plane spotter near an airport. Uses phone/tablet interactively. Wants alerts for interesting aircraft (military, rare types, emergencies), route context, and history of notable sightings. **Cares about:** interesting-aircraft detection, notifications surface, per-aircraft detail, photo/registration enrichment.

### P3 — "Tinkerer Tomás"
Ham/SDR hobbyist. Owns multiple radios, knows what a TLE is. Wants the orchestrator to be transparent and configurable, wants raw data access (APIs), wants to extend the system (feed aggregators, new decoders). **Cares about:** orchestration control, config files, API access, logs/observability, extensibility hooks.

### P4 — "Household Hannah" (secondary)
Non-technical household member. Glances at the wall display, occasionally taps a plane on her phone. **Cares about:** it just works, readable from the couch, nothing to learn.

---

## 3. Functional Requirements

Priorities: **P0** = MVP-blocking · **P1** = v1.0 · **P2** = post-1.0.

### FR-1 Aircraft Tracking (ADS-B, primary SDR)
- **FR-1.1 (P0)** Continuously decode 1090 MHz ADS-B via dedicated SDR #1; this pipeline must never be paused by any other subsystem.
- **FR-1.2 (P0)** Maintain live aircraft state table: ICAO hex, callsign, position, altitude, ground speed, vertical rate, squawk, heading, last-seen, message rate, RSSI.
- **FR-1.3 (P0)** Expire aircraft from the live set after configurable staleness (default 60 s no-position / 300 s no-message).
- **FR-1.4 (P0)** Compute distance/bearing from configured receiver location; sort/prioritize "nearby aircraft" by configurable rule (default: distance asc, weighted by descending altitude < 10,000 ft — approach/departure traffic surfaces first).
- **FR-1.5 (P1)** Persist position trails for the dashboard (in-memory ring per aircraft, last N positions, default 100).
- **FR-1.6 (P1)** Track receiver performance: message rate, aircraft count, max range, per-hour stats.

### FR-2 Aircraft Enrichment
- **FR-2.1 (P0)** Offline-first enrichment from bundled local DB: registration, type code, type name, operator, country — keyed by ICAO hex.
- **FR-2.2 (P1)** Optional online enrichment (route/origin/destination via adsbdb or equivalent) with local cache (SQLite, TTL 30 days); all lookups fail-soft.
- **FR-2.3 (P1)** Cache aircraft photos (thumbnail URL + attribution) when online; never block rendering on photo availability.
- **FR-2.4 (P2)** User-editable local overrides (custom labels, notes per airframe).

### FR-3 Interesting Aircraft Detection
- **FR-3.1 (P0)** Built-in rules: emergency squawks (7500/7600/7700) → CRITICAL; military hex ranges/operator flags → NOTABLE.
- **FR-3.2 (P1)** User-configurable watchlist (hex codes, registrations, callsign patterns, type codes) via config file + UI.
- **FR-3.3 (P1)** Rule hits publish an `aircraft.interesting` event → dashboard banner + sighting log entry.
- **FR-3.4 (P2)** Rarity scoring (type seldom seen at this receiver) from local history.

### FR-4 Secondary SDR Orchestration
- **FR-4.1 (P0)** Single owner process controls SDR #2; exactly one mode active at a time: `atc` | `ais` | `satellite` | `idle`.
- **FR-4.2 (P0)** Priority scheduler: satellite passes (predicted, elevation ≥ configurable min, default 30°) pre-empt ATC/AIS; manual user override pre-empts everything; on completion, return to previous mode.
- **FR-4.3 (P0)** Pass prediction from locally cached TLEs (CelesTrak), refreshed when online, valid offline for ~2 weeks with staleness warning.
- **FR-4.4 (P1)** Configurable schedule blocks (e.g., AIS 02:00–06:00, ATC otherwise) via config + UI.
- **FR-4.5 (P0)** Orchestrator state (current mode, next satellite pass, schedule) visible in UI and via API.
- **FR-4.6 (P1)** Graceful mode transitions ≤ 10 s including decoder restart; failed mode start retries with backoff, falls back to next scheduled mode, surfaces alert.

### FR-5 ATC Airband Audio
- **FR-5.1 (P0)** Monitor 1–N configured AM channels in 118–137 MHz (rtl_airband or equivalent), multi-channel within SDR bandwidth.
- **FR-5.2 (P0)** Live audio stream to the browser (HLS or WebSocket/Opus — decision in `/design-system`); play/pause + channel select in UI.
- **FR-5.3 (P1)** Squelch-gated activity events (`atc.activity`) so the dashboard can show "tower active" indicators.
- **FR-5.4 (P2)** Rolling audio buffer (last 30 min, RAM/tmpfs) for instant replay; no long-term recording by default.

### FR-6 AIS Vessel Tracking
- **FR-6.1 (P0)** Decode AIS (161.975/162.025 MHz) when orchestrator grants SDR #2; maintain vessel state table (MMSI, name, position, SOG, COG, type).
- **FR-6.2 (P1)** Vessels rendered on the same map as aircraft (distinct iconography, toggleable layer).
- **FR-6.3 (P1)** Vessel staleness handling mirrors aircraft (configurable, default 30 min — AIS is intermittent by nature here).

### FR-7 Weather Satellite Imagery
- **FR-7.1 (P0)** Capture + decode NOAA APT (137 MHz) during scheduled passes (satdump); produce PNG image products.
- **FR-7.2 (P1)** METEOR M2 LRPT decode (higher quality, same band).
- **FR-7.3 (P0)** Image gallery in UI: per-pass images, timestamp, satellite, pass quality (max elevation, SNR if available).
- **FR-7.4 (P1)** Retention: keep last N passes (default 50), prune oldest.

### FR-8 Real-Time Dashboard (the product's face)
- **FR-8.1 (P0)** FlightWall-inspired "hero" view: nearest/priority aircraft large (callsign, type, route, altitude, speed, distance, country/operator), with map context and smooth transitions when the priority aircraft changes.
- **FR-8.2 (P0)** Live map: aircraft with heading-oriented icons, trails, range rings; vessel layer; receiver location.
- **FR-8.3 (P0)** WebSocket push for all live data (aircraft delta ≤ 1 s cadence, orchestrator events, interesting alerts); auto-reconnect with backoff; UI never requires manual refresh.
- **FR-8.4 (P0)** Dashboard/TV mode: full-screen, cursor-hidden, 10-ft readable typography, no interactive chrome, auto-rotating panels (hero → map → satellite latest → stats), burn-in-conscious dark theme.
- **FR-8.5 (P0)** Responsive interactive mode for desktop/tablet/mobile: aircraft list, detail panes, ATC player, orchestrator panel, gallery, analytics.
- **FR-8.6 (P1)** Interesting-aircraft banner/toast with severity styling (CRITICAL = emergency, NOTABLE = military/watchlist).
- **FR-8.7 (P2)** Theming (dark default; accent presets).

### FR-9 Historical Analytics
- **FR-9.1 (P0)** Persist sighting summaries per aircraft per contact (first/last seen, min distance, max range, callsign, flags) — not full position firehose.
- **FR-9.2 (P1)** Analytics views: aircraft/day, unique types, range envelope (polar max-range plot), busiest hours, interesting-sighting log.
- **FR-9.3 (P0)** Retention policy: summaries 30 d default (configurable), hourly rollups ≥ 1 y; scheduled vacuum/prune respecting SD-card endurance.
- **FR-9.4 (P2)** CSV/JSON export of history.

### FR-10 System & Configuration
- **FR-10.1 (P0)** Single `config.yaml` (receiver lat/lon/alt, SDR serials→roles, ATC channels, schedules, watchlists, retention); validated at startup with actionable errors.
- **FR-10.2 (P0)** `docker compose up -d` on ARM64 Pi OS = fully working system; images published multi-arch (arm64 required, amd64 for dev).
- **FR-10.3 (P0)** Health endpoint per service + system status page in UI (SDR presence, decoder liveness, disk, CPU temp/throttle state).
- **FR-10.4 (P1)** REST API (documented, OpenAPI) for all read surfaces; WebSocket event schema documented — Tinkerer Tomás contract.
- **FR-10.5 (P1)** SDR hot-replug recovery: decoder containers detect device loss and recover without full-stack restart.
- **FR-10.6 (P2)** Config edit UI for safe subset (watchlist, schedules, channels) with file as source of truth.

---

## 4. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | **ADS-B latency** RF→dashboard | ≤ 2 s p95 |
| NFR-2 | **ADS-B availability** | Decoder pipeline uptime ≥ 99.5%/month; never paused by orchestrator |
| NFR-3 | **Resource ceiling** (Pi 4, 4 GB, steady state, ADS-B + 1 secondary mode) | CPU < 70% total, RAM < 3 GB, no sustained thermal throttling at 25 °C ambient |
| NFR-4 | **Satellite decode burst** | Allowed to spike CPU during pass; must not starve ADS-B (CPU pinning/nice/cgroup limits) |
| NFR-5 | **Offline operation** | All P0 features functional without internet indefinitely; enrichment fields show graceful fallbacks; TLE staleness warned after 14 d |
| NFR-6 | **SD-card endurance** | Steady-state writes < 1 GB/day; WAL mode; batch writes; tmpfs for transient artifacts |
| NFR-7 | **Cold start** | Power-on → live dashboard ≤ 3 min |
| NFR-8 | **WebSocket scale** | ≥ 5 concurrent clients (TV + phones) without degradation |
| NFR-9 | **UI performance** | 60 fps map pan on desktop; TV mode smooth on Pi-class browser/old smart-TV browsers (no exotic JS APIs) |
| NFR-10 | **Security posture** | LAN-only by default (bind LAN/localhost, no WAN exposure docs encourage); no secrets in images; enrichment API keys via env/config only |
| NFR-11 | **Maintainability** | Each bounded context independently restartable container; structured JSON logs; one-command update (`compose pull && up -d`) |
| NFR-12 | **Data integrity** | Crash-safe storage (SQLite WAL); unclean shutdown loses ≤ 60 s of summaries |
| NFR-13 | **Extensibility** | New decoder/mode addable by implementing a documented container contract (event topics + orchestrator registration) without touching core |

---

## 5. UX Principles

1. **Glanceable first.** The TV mode is the product. Every screen answers "what's overhead right now?" in < 1 second of looking. Hero data: callsign, type, route, altitude — huge.
2. **Calm motion.** Smooth, slow transitions (no flashing, no jitter) — it lives on a wall. Emergency states are the *only* loud thing.
3. **10-ft and 1-ft.** Same data, two grammars: TV mode = no interaction, giant type; mobile/desktop = dense, tappable, exploratory.
4. **Honest degradation.** Offline or enrichment-miss shows tasteful placeholders ("N/A · offline"), never spinners or broken layouts.
5. **Dark by default.** Wall displays run at night; OLED burn-in awareness (subtle pixel-shift in TV mode).
6. **The radio is a character.** Orchestrator state is first-class UI ("📡 Listening to Tower 118.1 · NOAA-19 pass in 22 min") — the system feels alive, not like a settings page.
7. **Zero-learning household use.** P4 never needs instructions: the wall display self-explains.

---

## 6. Success Metrics

| Metric | Target | How measured |
|--------|--------|--------------|
| RF→pixel latency (ADS-B) | ≤ 2 s p95 | Synthetic timestamp probe in dev; message timestamps in prod |
| ADS-B pipeline uptime | ≥ 99.5%/mo | Health-check history |
| Pi 4 steady-state CPU / RAM | < 70% / < 3 GB | Status page metrics, soak test |
| Fresh-install success | `compose up` → dashboard < 10 min, zero manual fixes | Release checklist on clean Pi |
| Offline parity | 100% of P0 features pass test suite with network disabled | CI scenario + manual gate |
| Mode-switch time (SDR #2) | ≤ 10 s p95 | Orchestrator event timestamps |
| Satellite pass capture rate | ≥ 90% of scheduled passes ≥ 30° produce an image | Pass log vs gallery |
| Wall-display longevity | 7-day continuous TV-mode run, no leak/crash/visual fault | Soak test per release |
| WebSocket stability | < 1 unintended disconnect/client/day | Client telemetry (local logs) |

---

## 7. Constraints & Assumptions

### Constraints (hard)
- Raspberry Pi 4 (4 GB) minimum target; Pi 5 is the comfort target; ARM64 only for release images
- Two RTL-SDR-class USB radios; SDR #1 exclusively 1090 MHz, never re-tasked
- Docker Compose only — no Kubernetes, no cloud services in the runtime path
- Single monorepo; local-only execution; LAN-scoped network exposure
- Frontend must run on smart-TV-grade browsers (conservative JS/CSS baseline)

### Assumptions (validate in /research)
- A1: Reusing mature decoders (readsb, AIS-catcher, rtl_airband, satdump) is viable on ARM64 — *high confidence, verify satdump CPU on Pi 4*
- A2: USB bus + power handles 2 SDRs (powered hub documented as recommended)
- A3: User can supply receiver coordinates at install (needed for distance, pass prediction)
- A4: 1090 MHz and secondary antennas are user-provided; docs cover basics only
- A5: SQLite suffices for write volume given summary-level persistence (NFR-6) — no time-series DB needed
- A6: Single household → no authN/multi-tenancy; trusted LAN
- A7: NOAA APT remains operational through the product horizon (NOAA-15/18/19 aging — see R-9)

---

## 8. Out of Scope (v1)
- Feeding FlightAware/FR24/ADS-B Exchange (hook documented, not implemented)
- MLAT, UAT 978 MHz, ACARS/VDL2, FLARM, radiosonde
- Cloud sync, remote/WAN access, VPN guidance beyond "use your own"
- User accounts, RBAC, multi-tenant
- Native mobile apps; LED/DMD hardware output
- ATC transcription / AI audio analysis
- Long-term raw audio or raw IQ recording
- Multi-receiver federation

---

## 9. Risk Register

| ID | Risk | Prob. | Impact | Mitigation |
|----|------|-------|--------|-----------|
| R-1 | Satellite decode (satdump) CPU starves ADS-B on Pi 4 | M | H | cgroup CPU limits + core pinning; decode-after-capture option (record SDR pass to tmpfs, decode at low priority); Pi 5 recommended docs |
| R-2 | USB bandwidth/power instability with 2 SDRs | M | H | Powered-hub requirement in docs; serial-based device pinning; hot-replug recovery (FR-10.5); soak test gate |
| R-3 | SD-card wear-out from chatty writes | M | M | NFR-6 write budget; WAL; tmpfs for transient; summary-not-firehose persistence; SSD-boot docs |
| R-4 | Orchestrator state-machine bugs (stuck mode, no return-from-pass) | M | M | Orchestrator as explicit FSM with watchdog + max-mode-duration timeout; chaos tests for kill/replug mid-switch |
| R-5 | Smart-TV browser can't handle map/WebSocket UI | M | M | Conservative baseline; TV mode = pre-composed panels (no interactive map); test on 2 real TV browsers + Pi kiosk |
| R-6 | Enrichment APIs change/rate-limit/disappear | H | L | Offline-first design (FR-2.1); adapter interface per provider; aggressive caching; fail-soft |
| R-7 | Audio streaming latency/compat (HLS vs WS/Opus) | M | M | Spike both in M1; pick one in /design-system; ATC tolerance for 2–5 s latency is acceptable |
| R-8 | Scope creep across 4 radio domains sinks the schedule | H | H | Strict P0 gating; milestone roadmap (§10) ships ADS-B-only value first; orchestrated modes land incrementally |
| R-9 | NOAA APT satellites decommissioned mid-life | M | M | METEOR LRPT path (FR-7.2); decoder behind adapter so new sats are additive |
| R-10 | Pi thermal throttling in enclosure degrades everything | M | M | Throttle-state on status page (FR-10.3); docs require heatsink/fan; soak test in enclosure |

---

## 10. Milestone Roadmap

### M0 — Foundation (scaffold)
Monorepo layout, Compose skeleton, CI (lint/test/build multi-arch), config schema + validation, event-bus choice ratified, health-check pattern. **Exit:** `compose up` runs stub services green on a Pi.

### M1 — ADS-B Core (first real value) 🎯
SDR #1 → readsb → state tracker → enrichment (offline DB) → WebSocket → minimal live map + aircraft list. Audio + orchestration spikes run in parallel (de-risk R-1/R-7). **Exit:** live aircraft on the dashboard ≤ 2 s, 48 h soak clean.

### M2 — The FlightWall Experience
Hero view, TV/kiosk mode, priority engine, interesting-aircraft rules + banner, trails, range rings, responsive interactive mode. **Exit:** 7-day wall-display soak; the "wow" demo exists.

### M3 — Second Radio: Orchestrator + ATC
Orchestrator FSM + schedule + manual override; ATC airband capture → browser audio; orchestrator UI panel. **Exit:** mode switching ≤ 10 s, ATC audible in browser, ADS-B untouched throughout.

### M4 — AIS + Satellites
AIS decode + vessel layer; TLE pass prediction; satellite pre-emption; APT capture/decode → gallery. **Exit:** ≥ 90% scheduled-pass capture; vessels on map; full priority chain proven.

### M5 — History + Analytics + Hardening
Sighting persistence, analytics views, retention/pruning, METEOR LRPT, offline test suite, SD-endurance audit, docs site, install guide, v1.0 release. **Exit:** all §6 metrics green on Pi 4 reference rig.

> Sizing intentionally deferred to `/plan` per-milestone; M1 is the schedule anchor.

---

## 11. Guardrails (engineering doctrine)

1. **Don't write DSP.** Wrap proven decoders (readsb, AIS-catcher, rtl_airband, satdump) as containers; our code is orchestration, state, and UI.
2. **Boring tech, small footprint.** FastAPI + SQLite + Redis-or-simpler + React/Vite. No Kafka, no Postgres, no microframework zoo. Every dependency must justify its RAM.
3. **Event bus ≠ enterprise bus.** Topic pub/sub with at-most-once is fine; this is a dashboard, not a bank.
4. **One container = one bounded context** (adsb, orchestrator, atc, ais, satellite, enrichment, api/ws, web). Restartable independently; ADS-B path has zero runtime dependencies on the others.
5. **Offline is the default test posture.** CI runs the suite with network disabled; online features are the add-on, not the baseline.
6. **Write budget is a feature.** Every persistence decision passes the "SD card in 2 years?" test.
7. **TV mode is sacred.** Any UI change re-validates 10-ft readability and the 7-day soak.
8. **Extensibility = contracts, not plugins-framework.** Documented event topics + container conventions; no premature plugin system.

---

## 12. Open Questions → /research & /design-system
1. Audio transport: HLS vs WebSocket/Opus (R-7 spike).
2. Event bus: Redis pub/sub vs NATS vs in-proc fan-out in the API service — measure RAM on Pi.
3. readsb vs dump1090-fa as ADS-B decoder (feature/maintenance comparison).
4. satdump headless CLI stability on ARM64; decode-after-capture feasibility (R-1).
5. Map stack: MapLibre GL vs Leaflet (TV-browser compatibility, NFR-9).
6. Bundled aircraft DB licensing (tar1090-db / Mictronics) for redistribution.
7. TV mode delivery: plain browser page vs Pi-kiosk-specific guidance.
