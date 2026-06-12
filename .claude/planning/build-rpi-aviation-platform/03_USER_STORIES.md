# User Stories: build-rpi-aviation-platform

Companion to `02_PRD.md`. Stories map to FR-IDs and milestones. Format: As / I want / So that + acceptance criteria.

---

## Epic A — Live Aircraft Tracking (M1) — Wagner, Hannah

**A1 (P0, FR-1.1/1.2/8.3)** — As Wagner, I want aircraft overhead to appear on my dashboard within seconds of my antenna hearing them, so that the display reflects the sky in real time.
- AC: aircraft visible ≤ 2 s p95 after RF decode; no manual refresh ever needed; stale aircraft fade out per FR-1.3.

**A2 (P0, FR-1.4/8.1)** — As Hannah, I want the closest interesting plane shown big and obvious, so that I can glance from the couch and know what's flying over the house.
- AC: hero panel shows callsign, type name, route (if known), altitude, distance; readable at 10 ft on a 1080p TV; priority handoff animates smoothly.

**A3 (P0, FR-2.1, NFR-5)** — As Wagner, I want aircraft type/operator/registration shown even with internet down, so that the display is never a grid of bare hex codes.
- AC: bundled DB resolves ≥ 90% of received airframes to type+registration; missing fields render "—", never broken layout.

**A4 (P1, FR-2.2/2.3)** — As Sofia, I want origin→destination and a photo when online, so that I get full context for a sighting.
- AC: route appears when API resolves; cached for repeat sightings; offline shows local-only fields with no error states.

## Epic B — Interesting Aircraft (M2) — Sofia

**B1 (P0, FR-3.1/8.6)** — As Sofia, I want emergency squawks to take over the display, so that I never miss a 7700 overhead.
- AC: 7500/7600/7700 → CRITICAL banner ≤ 2 s, distinct styling/sound-free, persists until aircraft stale; logged to sighting history.

**B2 (P1, FR-3.2/3.3)** — As Sofia, I want a watchlist (hexes, callsign patterns, types), so that the system flags airframes I care about.
- AC: watchlist editable in config + UI; match → NOTABLE banner + log entry; patterns support glob (e.g., `RCH*`).

**B3 (P0, FR-3.1)** — As Sofia, I want military aircraft auto-flagged, so that rare traffic surfaces without my configuring anything.
- AC: military hex-range/operator detection on by default; flagged in list, hero, and history.

## Epic C — Wall Display (M2) — Wagner, Hannah

**C1 (P0, FR-8.4)** — As Wagner, I want a TV mode I can leave running 24/7, so that the display is furniture, not software.
- AC: full-screen, no cursor/chrome; auto-rotating panels; dark theme with burn-in mitigation; 7-day soak without crash/leak/visual fault.

**C2 (P0, FR-8.5)** — As Sofia, I want the same dashboard usable on my phone, so that I can explore details interactively.
- AC: responsive ≥ 360 px; aircraft list + tap-to-detail; map pannable; all P0 panels reachable.

**C3 (P1, FR-8.2)** — As Wagner, I want trails and range rings on the map, so that I can see approach paths and my receiver's reach.
- AC: per-aircraft trail (last ~100 pts); configurable rings (default 50/100/150 km); vessels layer toggle.

## Epic D — Second Radio Orchestration (M3) — Tomás

**D1 (P0, FR-4.1/4.2)** — As Tomás, I want one process to own SDR #2 with explicit modes, so that decoders never fight over the device.
- AC: exactly one mode active; mode transitions logged as events; conflict impossible by construction (single owner).

**D2 (P0, FR-4.2/4.3)** — As Tomás, I want satellite passes to pre-empt ATC/AIS automatically and hand back afterward, so that I never miss a pass while listening to tower.
- AC: pass ≥ min-elevation triggers pre-empt with countdown event; previous mode restored ≤ 10 s after pass end; behavior verified offline (cached TLEs).

**D3 (P0, FR-4.5)** — As Wagner, I want to see what the second radio is doing right now, so that the system feels alive and trustworthy.
- AC: UI shows current mode, channel/satellite, next pass countdown; updates via WebSocket.

**D4 (P1, FR-4.4)** — As Tomás, I want schedule blocks per mode, so that AIS runs overnight and ATC during the day without my touching anything.
- AC: schedule in config + UI; orchestrator follows it; manual override wins until released.

## Epic E — ATC Audio (M3) — Sofia, Wagner

**E1 (P0, FR-5.1/5.2)** — As Sofia, I want to listen to tower frequency in my browser, so that I hear the traffic I'm watching.
- AC: configured channels selectable; audio starts ≤ 5 s after play; latency ≤ 5 s; works on mobile Safari + Chrome.

**E2 (P1, FR-5.3)** — As Wagner, I want a "tower active" pulse on the dashboard, so that the wall display hints when something's being said.
- AC: squelch-open events drive an activity indicator ≤ 1 s after audio starts.

## Epic F — AIS Vessels (M4) — Wagner

**F1 (P0, FR-6.1)** — As Wagner near the coast, I want ships decoded when the second radio is on AIS duty, so that the map shows the harbor too.
- AC: vessels appear with MMSI/name/type; positions update while mode active; staleness per FR-6.3.

**F2 (P1, FR-6.2)** — As Hannah, I want ships visually distinct from planes, so that the map reads instantly.
- AC: distinct icon set + color; layer toggle persists per device.

## Epic G — Weather Satellites (M4) — Tomás, Wagner

**G1 (P0, FR-7.1/7.3)** — As Tomás, I want NOAA APT passes captured and decoded automatically, so that fresh weather imagery appears with zero effort.
- AC: scheduled pass → image in gallery ≤ 10 min after pass end; pass metadata shown; ≥ 90% capture rate over a week.

**G2 (P0, FR-8.4)** — As Wagner, I want the latest satellite image in the TV rotation, so that the wall display includes my own weather photo from space.
- AC: latest image panel in rotation with satellite name + age.

**G3 (P1, FR-7.2)** — As Tomás, I want METEOR LRPT decode, so that I get higher-resolution imagery.
- AC: LRPT passes produce images alongside APT in the same gallery.

## Epic H — History & Analytics (M5) — Sofia, Tomás

**H1 (P0, FR-9.1/9.3)** — As Sofia, I want a log of past sightings, so that I can check what flew over while I was out.
- AC: per-contact summaries retained 30 d; interesting sightings flagged; queryable by date/type/flag.

**H2 (P1, FR-9.2)** — As Tomás, I want range/traffic analytics, so that I can tune my antenna and brag about max range.
- AC: polar range plot, aircraft/day, busiest hours, unique types — all rendered from local data, offline.

## Epic I — Operations (M0–M5) — Tomás, Wagner

**I1 (P0, FR-10.2)** — As Wagner, I want `docker compose up -d` to be the whole install, so that I never debug a service mesh.
- AC: fresh ARM64 Pi OS + Docker → working dashboard ≤ 10 min, no manual steps beyond config.yaml (location + SDR serials).

**I2 (P0, FR-10.3)** — As Wagner, I want a status page that says what's wrong in plain language, so that I can fix it or file an issue.
- AC: SDR detected? decoder alive? disk? CPU temp/throttling? each green/red with hint text.

**I3 (P1, FR-10.4)** — As Tomás, I want documented REST + WebSocket APIs, so that I can build my own consumers.
- AC: OpenAPI served by the API container; WS event schema doc in repo; stability noted per endpoint.

**I4 (P1, FR-10.5)** — As Tomás, I want the system to survive me yanking and re-plugging an SDR, so that a flaky hub doesn't mean SSH-and-restart.
- AC: device loss detected, decoder recovers ≤ 60 s after replug, event logged, no other container restarts.

---

**Story count:** 24 (P0: 14 · P1: 9 · P2 deferred to backlog) — traceable to FR/NFR matrix in `02_PRD.md`.
