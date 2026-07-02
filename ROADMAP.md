# Roadmap

Post-v1 enhancements, ordered. Core build phases live in
`.claude/planning/build-rpi-aviation-platform/`.

## Near-term (after Node B is on air)

### R1 — ATC audio — ✅ DONE (deployed + verified live 2026-06-30)
**ADR-009 reversed: ATC decode runs on Node A directly, not Node B/SoapyRemote.**
The two-node split existed to offload heavy satellite + AIS + ATC decode onto
Node B. That rationale is gone — AIS is an internet feed (AISStream, ADR-010),
satellite is deferred, so SDR #2's only job is one light ATC decode, and the
dongle + airband antenna are physically on Node A. Running `rtl_airband` on Node A
is simplest and lowest-latency; it avoids SoapyRemote and Node B's throttling
risk. Node B is now a spare (ready for satellite later, when that antenna exists).

**Pipeline (live-verified on Node A):** radio2 supervisor → rtl_airband (local
`type=rtlsdr`, serial `stx:0:28`) → Icecast `/atc` mount → gateway publishes
`mode=atc` + `audioUrl` → browser AtcPlayer. Channels **119.1 / 118.1 / 118.95**
(LPPT Approach/Tower/Clearance) on one 2.56 MHz tuner; 119.1 first = primary mount.
radio2 stable, 0 faults; `/atc` streams continuously (MP3 8 kHz mono).

**Deploy mechanics:** radio2 + icecast images cross-built on an Apple-Silicon Mac
(`docker buildx --platform linux/arm64`), shipped to Node A and `docker load`ed,
then run in the **node-a** compose project (`-f node-a -f node-b up -d icecast
radio2`) so they share the network (radio2→mosquitto, rtl_airband→icecast). Config
in `config.yaml`: `radio2.sdr_remote=null`, all-day `atc` schedule block, and
`satellite.min_elevation_deg=90` so no predicted pass can preempt ATC. Added
`ICECAST_SOURCE_PASSWORD` to `docker/node-a/.env`; disabled the host
`soapyremote-server` unit (it auto-grabbed the dongle on boot).

**Bugs fixed during bring-up (this commit):**
- `rtl_airband.py`: `sample_rate` was written in kHz; v5 wants **Hz** (min 16000).
- `proc.py`: heartbeat read whole lines, but rtl_airband's `-f` display redraws
  with ANSI codes and **no newlines** → watchdog killed a healthy decoder. Now
  reads in chunks (any bytes = heartbeat).
- `decoders.py`: rtl_airband **block-buffers stdout when piped** → no heartbeat
  reached the supervisor. Wrapped in `stdbuf -o0 -e0`.
- `Dockerfile`: `-DPLATFORM=native` cross-built on the Mac baked in Apple-Silicon
  instructions → **SIGILL** on the Pi 3B Cortex-A53. Changed to `PLATFORM=generic`
  (portable aarch64). `-DSOAPYSDR=ON` retained (kept for a future Node B path).
- `fsm.py`: log the specific fault reason (made the above diagnosable).

**Antenna:** the 978 MHz spare was inadequate (verified by ear 2026-06-12). The
replacement **108–136 MHz airband antenna works** — real ATC voice confirmed by
ear on Approach 119.1 (2026-06-30), though SNR is modest (an airband bandpass
filter/LNA would help, since strong 150–300 MHz signals desensitize the unfiltered
front end). The Stratux LowPowerV2 dongles have **no airband-blocking SAW filter**
(wideband sweep: most sensitive 100–400 MHz, least at 1090) — they decode airband fine.

**⚠️ Remaining: connectivity, not software.** Node A's good-RF spot (balcony) is at
the edge of WiFi range (−69 to −81 dBm, drops out); the in-WiFi-range indoor spot
is RF-dead (ADS-B 0 msg/s, airband silent). To actually *use* ATC audio + the
dashboard, Node A needs one location with **both** — a WiFi extender/mesh near the
balcony, a windowsill with both, or the antenna on coax with the Pi indoors. The
dedicated A↔B Ethernet link (`10.55.0.x`) is a reliable out-of-band path to manage
Node A when its WiFi is down (jump via Node B, or `ssh root@10.55.0.1`).

### R2 — OpenAIP airspace overlay — ✅ DONE (deployed + verified live 2026-06-12)
Verified on Node A: real OpenAIP tiles fetch through the gateway (z8/z10 Lisbon
→ 200 PNG, cached); OpenAIP accepts the `?apiKey=` query param (we send header +
query); config flag flips true; key stays server-side. (Empty tiles 404 → render
transparent, expected.)

Toggleable Leaflet overlay (CTR/TMA/airways/navaids), served through the gateway
tile proxy with the API key server-side (key in the Pi `.env`), region-cached
into `/tiles/openaip/` for offline use.
- gateway: `/tiles/openaip/{z}/{x}/{y}.png` proxy (key via header+query, fetch-
  once-cache-forever); `/api/v1/config` exposes only an `airspaceOverlay` bool
  (key never reaches the browser); compose passes `OPENAIP_API_KEY`
- web: persisted toggle (localStorage) + Leaflet overlay layer (opacity 0.85,
  tile pane so it's above base map / below aircraft); toggle shown only if keyed
- tests: tile proxy cache/key/offline (gateway), toggle persistence (web)
- **Deploy pending:** rebuild gateway + redeploy bundle when Pis power on.
  **Verify at deploy:** confirm OpenAIP's current auth (header `x-openaip-api-key`
  vs `?apiKey=` query — we send both) and tile URL against a live request.

### R3 — Single-node profile (Pi 4 / Pi 5 / other adopters) — ✅ DONE (compose-validated)
One-host deployment is now first-class:
- `install-node.sh --role single` provisions one host
- `scripts/up-single.sh` merges node-a + node-b + `docker/single/compose.override.yml`
  into one project/network (`sdrnode`) — services resolve by name, both SDRs local,
  no SoapyRemote
- **CPU pinning re-instates the R-1 mitigation** the split made moot: readsb +
  gateway on cores 0,1; radio2 (heavy satdump) confined to 2,3 — ADS-B can't be
  starved (satdump also record-then-decode at low priority, ADR-006)
- config: `nodes.mqtt_host=mosquitto`, `radio2.sdr_remote=null`, `atc.icecast_host=icecast`
- runbook: `scripts/single-node.md`
- Validated via `docker compose config` (merge parses, pinning applied). Not
  deployed — no Pi 4/5 on hand; turnkey for adopters / a future upgrade.

## Not yet implemented

Outstanding work, grouped by theme. Nothing here blocks the core ADS-B + ATC
build (R1/R2/R3 done); these are the next things to pick up.

### Hardware / deployment (needed to actually *use* the system)
- **Connectivity fix for the balcony.** The good-RF spot is at the edge of WiFi
  range (Node A drops off-LAN), and the in-WiFi indoor spot is RF-dead. Options:
  a WiFi extender/mesh node near the balcony, reposition to a windowsill with
  both, or run the antenna on coax with the Pi indoors. Until one is in place the
  dashboard/ATC audio are only reachable when Node A happens to be on WiFi.
- **Airband bandpass filter or LNA** to lift ATC SNR (strong 150 to 300 MHz
  signals desensitize the unfiltered RTL-SDR front end). Optional, improves voice
  clarity; not required for R1.
- **Deploy + soak on real hardware for R3** (single-node Pi 4/5). Validated only
  via `docker compose config`; never run on a physical Pi 4/5.

### Satellite (deferred feature, ADR-006 / ADR-010)
- **APT weather-image reception** (SatDump, NOAA 137 MHz). Needs a dedicated
  137 MHz antenna, which does not exist yet. radio2 has the scheduler/pass-
  prediction plumbing; the decoder command is still a placeholder.
- **METEOR LRPT enablement** once validated on the target hardware.
- Node B is now a spare and is the intended home for this when the antenna exists.

### ATC enhancements
- **Multi-channel selector in the UI.** rtl_airband already streams per-channel
  Icecast mounts (`atc_118100`, `atc_118950`, `atc_119100`); the UI plays only the
  primary `atc` mount. Expose a channel picker.
- **Ground (121.75) and other channels outside the 2.56 MHz tuner window.** Would
  need a second tuner or a scanning mode.
- **`atc/activity` squelch event source** from rtl_airband, so the UI activity
  pulse reflects real transmissions (the UI wiring already exists).

### AIS
- **Local AIS radio** as an alternative to the AISStream internet feed (needs a
  marine-band antenna). Currently internet-only by design (ADR-010).

### Platform / ops
- **CI on GitHub** (the codegen drift check and tests run locally; wire them into
  Actions).
- **Automatic out-of-band management** over the A-to-B Ethernet link (currently a
  manual ProxyJump / `ssh root@10.55.0.1` when Node A's WiFi is down).

### Explicitly out of v1 scope
- Feeder hooks (FlightAware / FR24 / ADSBx).
- Public exposure / TLS / auth (local-first, LAN-trusted by design).
