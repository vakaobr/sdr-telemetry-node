# ADR-001: Two-Node Pi 3B Topology

## Status: Accepted
## Date: 2026-06-12

## Context
Target hardware is two existing Raspberry Pi 3Bs (1 GB RAM, USB-2 shared bus each). A single Pi 3B cannot meet NFR-3 with the full stack: SatDump decode is CPU/RAM-heavy and two SDRs on one Pi 3B's shared USB-2 bus risk power/bandwidth instability. Buying a Pi 4/5 was the alternative.

## Decision
Split the system across both Pi 3Bs:
- **Node A** (`tattoine-watcher`): SDR #1 + readsb/tar1090, Mosquitto, gateway (API/WS/UI/SQLite). Always-on, self-sufficient.
- **Node B**: SDR #2 + radio2 supervisor (rtl_airband/AIS-catcher/SatDump) + Icecast. All heavy decode isolated here.

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| Single Pi 4 (4 GB) | One node, no network coupling | Requires purchase; R-1/R-2/R-3 remain and need software mitigations (cgroups, token gate, powered hub) |
| Single Pi 3B | Zero new anything | Cannot meet NFR-3; satellite decode likely OOMs alongside full stack |
| **Two Pi 3Bs** | Uses owned hardware; eliminates R-1/R-2/R-3 physically; ADS-B isolation by machine boundary | Mild distribution: two compose files, LAN dependency for Radio-2 features |

## Consequences
- Positive: R-1 (CPU starvation), R-2 (USB power/bandwidth), R-3 (cross-radio contention) eliminated by separation; same-serial dongle problem moot (one per host); Node A survives Node B loss with full ADS-B + dashboard.
- Negative: new cross-node dependency (R-11) — mitigated by MQTT LWT/retained state + Node A self-sufficiency; two devices to power/maintain.
- Risks: METEOR LRPT decode RAM (~300–400 MB) on Node B's 1 GB — APT default, LRPT config-gated (ADR-006).

## References
- 02_CODE_RESEARCH.md addendum; PRD NFR-2/3/4
