# Single-Node Deployment (Pi 4 / Pi 5 / other adopters)

Run the entire platform on **one** host instead of the two-Pi split. Recommended
for Pi 4 (4 GB) / Pi 5, where USB-3 + a separate USB controller + adequate power
make running both SDRs on one board a non-issue (the constraints that forced the
two-node split were specific to the Pi 3B — see ADR-009).

All services run in one Docker Compose project on one network: `mosquitto`,
`readsb`/`tar1090`, `gateway`, `radio2`, `icecast`. They resolve each other by
name, so **no dedicated link and no SoapyRemote** — both SDRs are local.

## 1. Provision
```bash
sudo ./scripts/install-node.sh --role single
# docker, DVB blacklist, udev SDR rules, health timer
```

## 2. config.yaml (single-host values)
```yaml
receiver: { lat: <you>, lon: <you>, alt_m: <you> }
nodes:
  mqtt_host: "mosquitto"        # the broker container (same network)
timezone: "Europe/Lisbon"
adsb:
  readsb_url: "http://readsb:80"
radio2:
  sdr_serial: "<ADS-B-second-dongle-serial>"
  sdr_remote: null              # local SDR (NOT SoapyRemote)
  atc:
    channels_mhz: [118.1, 119.1]
    icecast_url: "http://<host>.local:8000/atc"   # browser pull (host IP/name)
    icecast_host: "icecast"     # rtl_airband push target (container)
```

## 3. Secrets / env — `docker/node-a/.env`
```
RECEIVER_LAT=...   RECEIVER_LON=...   RECEIVER_ALT_M=...
ADSB_DONGLE_SERIAL=<adsb dongle serial>
ICECAST_SOURCE_PASSWORD=<random>
TZ=Europe/Lisbon
OPENAIP_API_KEY=...        # optional (airspace overlay)
AISSTREAM_API_KEY=...      # optional (AIS)
```

## 4. Launch
```bash
./scripts/up-single.sh        # builds + runs all services, one project "sdrnode"
```
This merges `docker/node-a` + `docker/node-b` + `docker/single/compose.override.yml`.
The override **pins CPUs** so the heavy SDR-2 decode (satdump) can't starve the
always-on ADS-B path on one host (re-instates the R-1 mitigation the two-node
split made moot): readsb + gateway on cores 0,1; radio2 on 2,3 (assumes a 4-core
Pi). Satellite decode also runs record-then-decode at low priority (ADR-006).

## 5. Verify
```bash
docker compose -p sdrnode ps
curl -s localhost:8080/healthz
open http://<host>.local:8080
```

## Stop / rollback
```bash
docker compose -p sdrnode down
```

## Notes
- Both dongles on one host → make sure the PSU is adequate (Pi 4/5 official
  supply) and ideally use a powered USB hub; watch `vcgencmd get_throttled`.
- Satellite still needs its own 137 MHz antenna (deferred, ADR-010); AIS uses the
  AISStream feed by default (no marine antenna needed).
