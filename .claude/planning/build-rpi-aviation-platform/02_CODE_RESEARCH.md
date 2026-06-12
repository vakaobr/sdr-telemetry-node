# Code & Ecosystem Research: build-rpi-aviation-platform

> **Note on naming:** the `/research` invocation passed a long architecture brief (and an unrelated 1Password Slack paste) as the "issue name." This research belongs to the existing issue **`build-rpi-aviation-platform`** and is written here. The architecture *deliverables* requested (system diagram, monorepo layout, event-bus design, etc.) are produced in `/design-system`; this document does the **research that those decisions depend on** and resolves the PRD's 7 open questions.

---

## 1. Codebase Analysis

**Repository state:** greenfield. Only `LICENSE` exists. No source, no patterns, no tests yet.

Therefore "existing patterns to follow" = **conventions we adopt now and must hold to**, derived from the PRD guardrails:

- **One container = one bounded context** (adsb, orchestrator, atc, ais, satellite, enrichment, api/ws, web). Each independently restartable; ADS-B path has zero runtime dependency on the others.
- **Wrap, don't write DSP.** Our code orchestrates and presents; decoding is delegated to mature OSS (readsb, rtl_airband, AIS-catcher, SatDump).
- **Naming:** kebab-case services/dirs; `snake_case` Python, `camelCase` TS; events as `domain.noun.verb` (e.g., `aircraft.position.updated`, `sdr2.mode.changed`).
- **Error handling:** every decoder wrapper is a supervised child; failures emit a `*.health` event and self-heal; never crash the API/WS gateway.
- **Tests:** none yet → `/quality/test-strategy` must seed pytest (backend) + vitest (frontend) + a **network-disabled CI scenario** (offline-first is the default test posture, Guardrail #5).

**Verified:** `find … -maxdepth 4` for any manifest/source returned nothing; `ls` shows `LICENSE` + `.git` only.

---

## 2. Architecture Context

The system is a set of **producers (RF decoders)** feeding an **event backbone**, with a **read-model/API gateway** serving a **React dashboard** over WebSocket. Greenfield, so the "broader system" is what we define:

```
RF ──► [decoder containers] ──► EVENT BUS ──► [state/API gateway] ──► WS ──► [React dashboard]
                                    │
                                    └──► [persistence: SQLite] (summaries, gallery index, cache)
```

**Two device domains, fundamentally different control models:**

| | Radio #1 (ADS-B) | Radio #2 (shared) |
|---|---|---|
| Control | Static — one process owns it forever | **Dynamic — single-owner orchestrator** starts/stops exactly one decoder at a time |
| Failure tolerance | Must never pause (NFR-2) | May switch/restart freely |
| Decoder | readsb (+ tar1090) | rtl_airband \| AIS-catcher \| SatDump (mutually exclusive) |

**Key constraint discovered:** an RTL-SDR USB device can be opened by **exactly one process** (libusb claims the interface). There is no in-kernel multiplexing. This is the architectural pivot for Radio #2 — see §6 device-contention.

**Data flow (per domain):**
- **ADS-B:** RTL #1 → readsb (Beast/JSON on `:30005`/`aircraft.json`) → ingest adapter → `aircraft.*` events → state table → WS deltas. tar1090 can run alongside as a fallback/expert map reading the same readsb output.
- **ATC:** RTL #2 → rtl_airband → audio stream (Icecast/MP3 or raw) + squelch events → gateway proxies audio + `atc.activity` events.
- **AIS:** RTL #2 → AIS-catcher → NMEA/JSON (UDP/HTTP) → ingest → `vessel.*` events.
- **Satellite:** RTL #2 → SatDump (record + decode) → PNG products on disk → `satellite.pass.completed` event with image paths → gallery index.
- **Orchestrator:** owns RTL #2; computes passes from cached TLEs; publishes `sdr2.mode.*`; starts/stops the three decoders.

**API boundaries:** REST (read models + config) + WebSocket (live push) from one gateway. Decoder containers never talk to the browser directly except the **audio stream** (latency-sensitive — see §6 R-7) and **static image files** (served by gateway/static).

**DB schema relevant (to be finalized in design):** `sightings` (per-contact summary), `vessels_seen`, `satellite_passes` (gallery index + metadata), `enrichment_cache` (TTL), `hourly_rollups`. Summary-level only (SD-endurance, NFR-6).

---

## 3. Dependency Analysis

### Mandatory decoders (verified, ARM64 status)

| Tool | Role | Output interface | ARM64 / Pi | Maintenance | Notes / risk |
|------|------|------------------|------------|-------------|--------------|
| **readsb** (Mictronics fork) | ADS-B decode | Beast `:30005`, SBS `:30003`, `aircraft.json` (via run dir/HTTP) | ✅ native, NEON; the de-facto Pi standard | ✅ active | Successor to dump1090-fa; richer JSON, better resource use. **Recommend over dump1090-fa.** |
| **tar1090** | ADS-B web map | Reads readsb json; serves own web UI (lighttpd) | ✅ | ✅ active | Mandatory per brief. We run it as a **secondary/expert view**; our React dashboard is primary. Avoid double-serving the same port. |
| **rtl_airband** | ATC airband (AM multichannel) | Icecast/MP3/PCM/file; UDP PCM | ✅ NEON-optimized, built for Pi | ✅ active | Config-file driven; multi-channel within one tuner bandwidth (~2.4 MHz window). Audio transport choice (R-7). |
| **AIS-catcher** | AIS decode | NMEA over UDP/TCP, **HTTP JSON + built-in web**, MQTT output | ✅ excellent ARM support | ✅ very active | Has native MQTT output → clean event-bus fit. Low CPU. |
| **SatDump** | NOAA APT / METEOR LRPT | PNG/image products to disk; headless CLI | ✅ ARM64 builds; **CPU-heavy decode** | ✅ active | METEOR LRPT decode is the CPU spike (R-1). Supports **record-then-decode** (baseband → offline decode at low priority). |

### Platform/infra dependencies

| Dependency | Choice (proposed) | Health | Rationale |
|---|---|---|---|
| Container runtime | Docker + Compose v2 | stable, ARM64 | Mandated. |
| Event bus | **MQTT (Eclipse Mosquitto)** | mature, ~8–12 MB RAM | See §6 + §7 — best-justified bus for Pi/offline; AIS-catcher speaks it natively. |
| Backend | **FastAPI (Python 3.12)** primary; Go reserved for WS gateway if fan-out becomes hot | both excellent | Python wins for orchestrator (Skyfield TLE/pass math, no Go equivalent as clean). |
| Pass prediction | **Skyfield** (or `pyorbital`) + CelesTrak TLEs | active | Pure-Python, offline-capable with cached TLE. |
| Storage | **SQLite (WAL)** | rock-solid | No heavy DB (constraint). Postgres not justified at this scale. |
| Frontend | React + Vite + TypeScript | current | Mandated; MapLibre GL vs Leaflet open (R-5/NFR-9). |
| Map tiles | **self-hosted/offline raster or vector** | — | Offline-first (NFR-5) → bundle/cache tiles; no cloud tile dependency at runtime. |
| Aircraft DB | tar1090-db / Mictronics DB | active | Licensing check needed for redistribution (open Q6). |

### Version/compat concerns
- **librtlsdr vs rtl-sdr-blog v4 dongles:** v4 (R828D + improved) requires the **rtl-sdr-blog driver fork**, not stock Osmocom librtlsdr. Decoder images must bundle the correct driver or v4 dongles silently fail. **Verify which dongles the user owns.**
- Host kernel must **blacklist `dvb_usb_rtl28xxu`** or the DVB driver grabs the dongle before userland.
- SatDump version pinning matters — decode pipelines change between releases.

### Known vulnerabilities
- Low surface: all local, no auth, LAN-only. Main concern is **container privilege** for USB access (§7). No known critical CVEs in the decoder set as of cutoff; pin image digests and rebuild monthly.

---

## 4. Integration Points

- **Host ↔ containers (USB):** decoder containers need `/dev/bus/usb` access + udev rules; device→role pinning by **RTL-SDR serial number** (set via `rtl_eeprom`, e.g. `1090` and `MULTI`). This is the most fragile integration (R-2).
- **Orchestrator ↔ Radio-#2 decoders:** orchestrator does **not** share the device; it **controls lifecycle** of the three decoder containers (start/stop) so only one holds RTL #2. Two viable mechanisms (decide in design):
  1. **Compose profiles + Docker socket control** — orchestrator starts/stops sibling containers via Docker API. Powerful but gives orchestrator Docker-socket access (privilege/security cost).
  2. **Long-lived decoders gated by a "device token"** — all three run but only the token-holder opens the device; others idle. Simpler privilege model, slightly more RAM. **Leaning option 2** (no Docker socket, cleaner failure semantics).
- **Decoders → event bus:** AIS-catcher (native MQTT), readsb (JSON poll/Beast → small adapter publishes), rtl_airband (squelch/log → adapter), SatDump (exit-code + product dir → adapter). Adapters are tiny sidecars or in-gateway pollers.
- **Gateway → browser:** REST + WS (live). **Audio** path is separate (Icecast/HLS/WS-Opus). **Images** served as static files.
- **Async processes:** pass scheduler (cron-like, in orchestrator), retention/vacuum job (SQLite), TLE refresh job (online-opportunistic).

---

## 5. Risk Assessment (specific)

| ID | Risk | Sev | Evidence / detail | Mitigation |
|----|------|-----|-------------------|-----------|
| R-1 | **SatDump METEOR decode starves ADS-B** on Pi 4 | High | LRPT decode is multi-minute, CPU-bound; Pi 4 has 4 cores shared with readsb | cgroup `cpus`/`cpu-shares` caps on satellite container; pin readsb to a reserved core; **record-then-decode** (capture baseband to tmpfs during pass, decode at `nice 19` after). |
| R-2 | **Two RTL-SDRs on Pi USB: power/bandwidth/enumeration** | High | RTL dongles draw ~300 mA; brownouts cause silent decode death; same-serial dongles unaddressable | **Powered USB hub mandatory**; unique serials via `rtl_eeprom`; put dongles on Pi 4 **USB-3 ports** (dedicated controller bandwidth even though dongles are USB-2). |
| R-3 | **Device contention on Radio #2** (two processes grab one dongle) | High | libusb single-claim; race on mode switch | Single-owner orchestrator + device-token gate (§4 option 2); transition state machine with "released/acquired" confirmation before starting next decoder. |
| R-4 | **rtl-sdr-blog v4 dongle needs special driver** | Med | Stock librtlsdr can't init v4 | Detect dongle model; bundle blog-driver; document supported hardware. |
| R-5 | **Smart-TV browser can't run MapLibre GL/WebGL** | Med | Old TV browsers lack WebGL2/modern JS | TV mode = pre-composed panels, **Leaflet (canvas/raster)** fallback or static map render; test on 2 real TV browsers. |
| R-6 | **Audio transport latency/compat** (R-7 in PRD) | Med | HLS = 6–10 s latency but universal; WS/Opus = ~1 s but more code | Spike both in M1; ATC tolerates latency → **lean HLS via Icecast** for simplicity unless low-latency demanded. |
| R-7 | **SD-card write wear** from event/log volume | Med | MQTT retained + logs + SQLite WAL can be chatty | tmpfs for transient (audio buffer, baseband capture, logs→journald with limits); summary-only persistence; batch writes. |
| R-8 | **MQTT adds a moving part** vs guardrail "Redis only if justified" | Low | Any bus is operational surface | Justified in §7; Mosquitto is lighter than Redis and AIS-catcher speaks it natively — net simplification. |
| R-9 | **Orchestrator FSM bugs** (stuck mode, no hand-back after pass) | Med | State machines fail at edges (replug mid-switch) | Explicit FSM + watchdog + max-mode-duration timeout; chaos test: kill/replug during transition. |
| R-10 | **Pi 3B target gap** | Med | User's current Pi 3B = 1 GB RAM, USB-2 shared bus, 2.4 GHz Wi-Fi; below NFR-3 | Declare **Pi 4 (4 GB) minimum**; offer "ADS-B-only reduced profile" for 3B; recommend Pi 5 for full stack. |

---

## 6. Prior Art & Ecosystem Research

- **The "Pi SDR receiver" pattern is well-trodden:** readsb+tar1090 is the standard ADS-B stack (PiAware, ADSB.im, adsbexchange images all build on it). We are not innovating the decode — we're innovating the **unified UI + Radio-#2 orchestration**, which is the genuinely novel part with little prior art.
- **Multi-SDR orchestration is the thin-ice area.** Most projects dedicate one dongle per mode (4 dongles). Time-sharing one dongle across ATC/AIS/satellite with **satellite pre-emption** is uncommon — closest prior art is satellite-station automation (gpredict + hamlib doppler/scheduling) and SatNOGS (ground-station scheduling). **Borrow SatNOGS's scheduler concept**, not its complexity.
- **Event bus for Pi/IoT:** MQTT (Mosquitto) is the ecosystem-standard lightweight bus; Home Assistant, OpenMQTTGateway, etc. validate it on Pi. Retained messages give "last known state on reconnect" for free — valuable for WS clients and offline.
- **Best practices adopted:** device pinning by serial; blacklist DVB driver; powered hub; record-then-decode for satellites (SatNOGS does this); WAL + summary persistence for flash longevity.
- **Anti-patterns to avoid:**
  - ❌ Privileged containers / Docker-socket exposure unless unavoidable (prefer device-token gate).
  - ❌ Postgres/InfluxDB "just in case" — violates heavy-DB constraint; SQLite + rollups suffice.
  - ❌ Writing our own ADS-B/AIS/APT DSP.
  - ❌ Streaming raw IQ over the network between containers (bandwidth/latency) — decode at the edge, emit structured events.
  - ❌ Polling `aircraft.json` from the browser — gateway polls once, fans out over WS.
  - ❌ Two web servers fighting over port 80 (tar1090's lighttpd vs our gateway) — namespace them.

---

## 7. Recommendations

### Suggested technical approach (primary)
1. **Backend: FastAPI (Python 3.12)** for gateway + orchestrator + adapters. Rationale: Skyfield/pyorbital pass-prediction ecosystem is Python-native; async WS support is good; team cohesion. **Tradeoff:** Python WS fan-out is heavier than Go — acceptable at ≤5 clients (NFR-8); **escape hatch:** extract the WS gateway to Go only if profiling shows it's hot.
2. **Event bus: Mosquitto (MQTT).** Rationale: ~10 MB RAM, retained-message state, AIS-catcher native support, ecosystem-proven on Pi; lighter than Redis for pub/sub-only needs. **Tradeoff:** one more container vs in-proc fan-out — justified by decoupling decoders from gateway and surviving gateway restarts (restart-safe goal). *This is the "Redis only if justified" decision — we pick MQTT over Redis, justified.*
3. **Radio-#2 control: single-owner orchestrator + device-token gate** (decoders idle until granted the device). Avoids Docker-socket privilege. FSM with watchdog + max-duration + acquire/release confirmation.
4. **SatDump record-then-decode** with cgroup CPU caps + readsb core reservation — protects NFR-2/NFR-4.
5. **Persistence: SQLite (WAL), summary-level**, tmpfs for transient (baseband, audio buffer, logs).
6. **Audio: Icecast/HLS** as default (simplicity, universal playback); revisit WS/Opus only if latency complaints.
7. **Frontend: React + Vite**; **Leaflet for TV mode** (raster/canvas, max compatibility), MapLibre optional for interactive desktop only.
8. **Decoder containers** wrap upstream tools 1:1; tiny adapter sidecars normalize their output to MQTT topics.

### Key decisions needed (carry into `/design-system`)
- [ ] **Hardware floor:** Pi 4 (4 GB) min confirmed? Pi 3B as ADS-B-only reduced profile? (R-10)
- [ ] **Which RTL-SDR dongles** does the user own (blog v4 vs v3/generic)? Drives driver bundling (R-4).
- [ ] **Radio-#2 control mechanism:** device-token gate (recommended) vs Docker-socket lifecycle.
- [ ] **Audio transport:** confirm HLS default.
- [ ] **Map library** split (Leaflet TV / MapLibre interactive) vs single lib.
- [ ] **Backend language:** all-Python vs Python+Go-WS-gateway hybrid (default all-Python, escape hatch noted).
- [ ] **Aircraft DB licensing** for redistribution (tar1090-db / Mictronics) — open Q6.

### Unknowns to resolve before/within design
- SatDump METEOR LRPT wall-clock + peak CPU on a Pi 4 (needs a measured spike) — gates R-1 mitigation design.
- Real USB power behavior with the user's specific 2-dongle + hub setup (R-2) — empirical.
- TV-browser WebGL capability on the user's actual display (R-5).

---

## Summary

The decode layer is **low-risk and well-understood** (mature OSS, standard Pi pattern). The **novel, higher-risk work is Radio-#2 orchestration** (device contention + satellite pre-emption + CPU isolation) and the **unified offline-first UI**. Architecture should isolate the always-on ADS-B path completely, treat Radio #2 as a single-owner state machine with a device-token gate, use MQTT as a lightweight justified bus, and protect ADS-B from SatDump via cgroup CPU caps + record-then-decode. Hardware floor (Pi 4 min) and exact dongle models are the two facts most worth confirming before design.

---

## ADDENDUM (2026-06-12): Two-node Pi 3B topology — supersedes single-node assumptions

User confirmed **two Pi 3B units** available and elected to **distribute the load** rather than buy a Pi 4. This is adopted as the reference architecture and changes several conclusions above:

- **Node A** (existing `tattoine-watcher`): Radio #1 ADS-B (readsb + tar1090) always-on, MQTT broker, FastAPI gateway/WS, React dashboard, SQLite. Light load (~350–450 MB / ~20% CPU); **self-sufficient** if Node B is offline.
- **Node B** (second Pi 3B): Radio #2 orchestrator + rtl_airband / AIS-catcher / SatDump; **all CPU-heavy decode isolated here**.

**Effect on risk register:**
- **R-1 (SatDump starves ADS-B): eliminated** — decode is on a separate machine; cannot contend for Node A's CPU. The cgroup-cap/core-pin mitigation is no longer load-bearing (keep only as intra-Node-B hygiene).
- **R-2 (dual-SDR USB power/bandwidth): eliminated** — one dongle per Pi, separate USB controllers and PSUs.
- **R-3 (device contention): scope-reduced** — only Node B's single radio time-shares across three decoders; the single-owner FSM + device-token gate still applies *within Node B*. Cross-radio contention is gone.
- **R-10 (Pi 3B below targets): resolved** by splitting; residual watch item = METEOR LRPT decode RAM (~300–400 MB) on Node B's 1 GB — use record-then-decode + monitor.

**New risk introduced:**
- **R-11 cross-node network dependency** (Med→Low): Node A↔B over LAN MQTT. Mitigated by (a) Node A fully self-sufficient for ADS-B + dashboard, (b) MQTT reconnect + retained-state, (c) UI degrades gracefully when Node B's modes are unavailable. *Tradeoff vs "avoid distributed systems" guardrail:* two LAN nodes + one MQTT topic tree + per-node compose files is mild, justified distribution — not clustering/orchestration.

**Deployment implication:** two `docker-compose.yml` files (one per node) rather than one; broker reachable from both. Cross-node compose layout (two files vs Docker contexts) → decide in `/design-system`.

**Dongles (CONFIRMED via `lsusb -v`):** 2× **Stratux LowPowerV2** (manufacturer `Stratux`, serials `stx:0:28`/`stx:0:29`). RTL2832U + R820T2; **stock librtlsdr — R-4 closed**, no driver fork. Factory-unique serials (no rtl_eeprom step). Low-power design built for dual-dongle Pi operation. Notes: MCX antenna connectors (pigtails may be needed); aviation-band-optimized — assign to ADS-B on Node A preferentially; if 137 MHz satellite RX underperforms in M4, swap Node B's dongle for a generic/SDR-blog unit (~$30 upgrade path). Both currently enumerate on `tattoine-watcher`; one relocates to Node B at bring-up.