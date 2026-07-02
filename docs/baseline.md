# Performance Baseline

## Node A — tattoine-watcher (Pi 3B, 192.168.31.218) · 2026-06-12, Phase 2

Hardware: repurposed FR24 beacon — proven 1090 MHz antenna chain. Dongle: Stratux LowPowerV2
serial `stx:0:29` (pinned via `ADSB_DONGLE_SERIAL`). Second dongle `stx:0:28` parked here until
Phase 8 relocates it to Node B.

### First-decode snapshot (≈3 min after cold start, midday)
| Metric | Value |
|---|---|
| Messages decoded | 438 → 6,357 (10 min) |
| Aircraft tracked | 4–8 concurrent |
| With position | 3+ (incl. AFR37EQ @400 ft on LIS final, VLG6LF @20,200 ft) |
| RSSI range observed | −21.7 … −25.6 dBFS |
| Node CPU steady | 4–5% |
| Node RAM used | 280–370 MB (of 905) |
| SoC temp | 48–53 °C, throttled=0x0 |

### Restart-safety (reboot test)
Power-cycle → SSH back ≈40 s → containers auto-started healthy → decode resumed unattended.
Memory cgroup enabled (`cgroup_enable=memory cgroup_memory=1`); compose mem limits now enforced.

### Cross-node bus
`sys/node-a/health` and `sys/node-b/health` both retained on broker; Node B publishes over LAN.

## Node B — tattoine-watcher-beacon (Pi 3B, 192.168.31.71) · provisioned, idle

Docker + blacklist + udev + health timer installed. No SDR attached yet (Phase 8).

> **⚠️ ACTION REQUIRED before Phase 8:** `vcgencmd get_throttled = 0x50005` — under-voltage
> **active** and throttling **now**, at only 55 °C idle. The PSU is inadequate. Replace with a
> proper 5 V/2.5 A supply before attaching the SDR; under-voltage causes silent decode death (R-2).

## TODO next phases
- 24 h passive soak (P2 AC): check `dmesg` for USB resets, message-rate stability
- TR-1 latency probe once gateway lands (P3)
- METEOR LRPT RAM test on Node B (P10, ADR-006 watch item)
