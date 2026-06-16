# Roadmap

Post-v1 enhancements, ordered. Core build phases live in
`.claude/planning/build-rpi-aviation-platform/`.

## Near-term (after Node B is on air)

### R1 — Revised Node B bring-up: SoapyRemote capture-on-A / decode-on-B (ADR-009)
Both dongles stay on Node A; Node A runs SoapySDRServer for SDR #2; Node B
decoders open the remote device over the dedicated `10.55.0.x` link. Offloads
ATC/AIS/satellite decode onto Node B. Gated on the Node B PSU swap.

**Proven (2026-06-12 live spike):**
- Debian trixie packages: Node A `soapysdr-tools soapysdr-module-rtlsdr
  soapyremote-server`; Node B `soapysdr-tools soapysdr-module-remote`.
- `SoapySDRServer --bind=0.0.0.0:55132` on Node A serves SDR #2 **without
  disturbing readsb** (readsb keeps `stx:0:29`; server enumerates only on demand).
- Node B discovers the remote dongles over the link:
  `SoapySDRUtil --find="remote=tcp://10.55.0.1:55132"` → sees `stx:0:28` + `:29`.
  Open args: `dict(driver="remote", remote="tcp://10.55.0.1:55132", serial="stx:0:28")`.

**Gotchas found:**
- A bare host SoapySDR install loads all 12 device modules; opening a Device
  crashed with `Hash collision!!! Fatal error!!` (UHD/audio module conflict).
  **Fix:** the radio2 image ships ONLY `remote` + `rtlsdr` modules (set
  `SOAPY_SDR_PLUGIN_PATH` to a dir with just those) — avoids the conflict.
- rtl_airband must be built with `-DSOAPYSDR=ON` (current Dockerfile only has
  `-DNFM=ON`); device type `soapysdr`, device_string using the remote args above.
- Do the rtl_airband compile in the **Docker image built on Node A**, then
  `docker save | ssh node-b docker load` over the link — never compile on the
  throttled Node B, never compile heavy on Node A's host (protect ADS-B).

**Antenna — INADEQUATE for airband (verified by ear 2026-06-12):** the 978 MHz
spare does NOT yield intelligible ATC voice. Empirically, across 121.95/124.15/
118.1/119.1/120.35/122.877 MHz, demodulated audio was static; the only strong
FFT peaks (e.g. 122.877 @31 dB) are narrow spurs / unmodulated carriers with no
recoverable voice. A 978 MHz antenna is ~8× off-resonance at 122 MHz — it catches
spurs but can't pull AM voice from the noise. (Earlier "125.0 beep" = RTL-SDR
DC-spike; earlier "30 dB signals" = a transient/spurs, not reproducible.)
**Action: get an airband antenna** — a ~60 cm ¼-wave wire (300/125/4) on the
dongle center pin, or a cheap airband/scanner antenna. This is a hard blocker for
audible ATC, independent of software.

**Blocked on (both hardware):**
1. **Airband antenna** (978 MHz won't recover voice — see above).
2. **Node B PSU** (still `0x50005` after PSU swap — likely the USB power *cable*;
   decode results untrustworthy until `0x0`).
**Status:** dedicated link done + verified (94 Mbit/s); SoapyRemote discovery
proven; streaming/decode pending power fix.

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

## Backlog
- Multi-channel ATC selector in the UI (currently single primary mount)
- squelch → `atc/activity` event source from rtl_airband (UI pulse already wired)
- METEOR LRPT enablement once validated on the target hardware (ADR-006)
- Feeder hooks (FlightAware/FR24/ADSBx) — explicitly out of v1 scope
