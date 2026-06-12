# Node B Bring-Up Runbook (M3 — ATC audio)

Node B (`tattoine-watcher-beacon`, 192.168.31.71) is base-provisioned (Docker,
DVB blacklist, udev, health publisher → Node A broker). This is the remaining
hardware bring-up to get ATC audio on air.

## ⚠️ Prerequisites (hardware — do these first)

1. **Swap the PSU.** Node B reports `vcgencmd get_throttled = 0x50005`
   (under-voltage active) *at idle*. Adding an SDR (~300 mA) will make it worse
   → silent decode death (R-2). Fit a genuine **5 V / 2.5 A+** supply and
   confirm `vcgencmd get_throttled` reads `0x0` before continuing.
2. **Move the SDR-2 dongle.** Unplug Stratux dongle **`stx:0:28`** from Node A
   and plug it into Node B. (Node A keeps `stx:0:29` for ADS-B.) Verify:
   ```bash
   ssh root@192.168.31.71 'lsusb | grep 0bda:2838'   # expect 1 dongle
   ssh root@192.168.31.218 'lsusb | grep 0bda:2838'  # expect 1 (stx:0:29)
   ```
3. **Antenna.** Connect a 118–137 MHz airband antenna to the Node B dongle
   (MCX connector — pigtail may be needed). A simple quarter-wave or the stock
   telescopic tuned to ~125 MHz works to start.

## 1. Configure ATC channels + secrets

Lisbon (LPPT) airband frequencies: https://skyvector.com/airport/LPPT
Pick channels **within ~2.3 MHz of each other** (single-tuner limit), e.g.
Tower/Approach. Edit `/opt/sdr-telemetry-node/config.yaml` on **both** nodes
(it's shared; keep them identical):

```yaml
timezone: "Europe/Lisbon"
radio2:
  sdr_serial: "stx:0:28"
  atc:
    channels_mhz: [118.1, 119.1, 120.35]   # within one 2.56 MHz window
    icecast_url: "http://192.168.31.71:8000/atc"
    icecast_host: "icecast"
    icecast_port: 8000
    icecast_mount: "atc"
  schedule:
    - { mode: atc, from: "07:00", to: "23:00" }
```

Set the Icecast source secret in Node B's env (gitignored, not in config.yaml):
```bash
ssh root@192.168.31.71 'cat >> /opt/sdr-telemetry-node/docker/node-b/.env <<EOF
ICECAST_SOURCE_PASSWORD=$(openssl rand -hex 16)
TZ=Europe/Lisbon
EOF'
```

## 2. Deploy

From your dev machine:
```bash
rsync -az --exclude .venv --exclude __pycache__ --exclude tests \
  docker scripts shared services root@192.168.31.71:/opt/sdr-telemetry-node/
```
On Node B (the rtl_airband image compiles from source — **~15–20 min on a Pi 3B**,
one-time):
```bash
ssh root@192.168.31.71 'cd /opt/sdr-telemetry-node/docker/node-b && docker compose up -d --build'
```

## 3. Verify

```bash
# radio2 + icecast up
ssh root@192.168.31.71 'docker ps --format "{{.Names}}: {{.Status}}"'

# radio2 state reaches Node A's broker (mode follows the schedule)
ssh root@192.168.31.218 'mosquitto_sub -h 127.0.0.1 -t "radio2/#" -v -W 3'

# dashboard shows radio2 ATC + the audio player appears
open http://192.168.31.218:8080         # ▶ ATC button in the top bar
curl -sI http://192.168.31.71:8000/atc  # icecast mount serving audio/mpeg
```
Tap ▶ in the dashboard — tower audio should play within ~5 s.

## 4. Cross-node resilience check (TR-8, story D3)

```bash
# pull Node B power → Node A dashboard must stay fully functional,
# radio2 panel flips to "offline" within ~15 s (MQTT Last-Will)
# restore power → radio2 auto-resumes its scheduled mode unattended
```

## Dry-run without RF (optional, before the antenna/PSU work)
Copy the fake decoder and uncomment `RADIO2_FAKE` in `docker/node-b/compose.yml`
to validate the cross-node FSM/MQTT/LWT wiring using a scripted fake decoder
(no SDR, negligible power):
```bash
scp services/radio2/tests/fakes/fake_decoder.py root@192.168.31.71:/opt/fake_decoder.py
# set RADIO2_FAKE=/opt/fake_decoder.py in the radio2 service env, then up -d
```

## Rollback
```bash
ssh root@192.168.31.71 'cd /opt/sdr-telemetry-node/docker/node-b && docker compose down'
```
Node A is unaffected at all times — ADS-B + dashboard keep running.
