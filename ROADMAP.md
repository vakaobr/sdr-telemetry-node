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
