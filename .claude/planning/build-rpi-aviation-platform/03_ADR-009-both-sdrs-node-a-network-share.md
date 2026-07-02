# ADR-009: Both SDRs on Node A; share SDR #2 to Node B over a dedicated Ethernet link

## Status: Accepted
## Date: 2026-06-12
## Supersedes: the "SDR #2 physically on Node B" assumption in ADR-001

## Context
ADR-001 split the work by putting SDR #2 physically on Node B. Two hardware
realities make that impossible/undesirable here:
1. **The dongle cannot move to Node B** — the enclosure doesn't support it;
   relocating risks damaging the SDR/antenna (user constraint).
2. **Neither Pi can reach the router by cable** — both are on 2.4 GHz Wi-Fi.
   Cross-node MQTT/audio over congested Wi-Fi is unreliable.

The user ran a **direct Ethernet cable between the two Pis** to give them a
private, low-latency channel independent of Wi-Fi.

## Decision
- **Both RTL-SDR dongles stay on Node A** (`stx:0:29` ADS-B, `stx:0:28` shared).
- A **dedicated point-to-point Ethernet link** carries all inter-node traffic:
  `10.55.0.1` (Node A) ↔ `10.55.0.2` (Node B), static, `never-default` so
  internet keeps routing over Wi-Fi. Measured **94 Mbit/s, 0.9 ms, 0% loss**.
- **Node A captures, Node B decodes.** Node A runs a **SoapySDRServer** for
  SDR #2; Node B's decoders (rtl_airband / AIS-catcher / satdump) open the
  remote device (`driver=remote`) over the link. This offloads the CPU/RAM-heavy
  decode — especially satdump (R-1) — onto Node B while Node A only captures +
  runs ADS-B + gateway.
- MQTT (`nodes.mqtt_host = 10.55.0.1`) and the SDR sample stream both traverse
  the dedicated link. The browser still pulls ATC audio from Node B's Icecast
  over Wi-Fi (`192.168.31.71:8000`); clients are on Wi-Fi, not the private link.

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| **SoapyRemote over dedicated Ethernet** (chosen) | Tool-agnostic (all 3 decoders speak SoapySDR); one sample stream; offloads heavy decode to B; private link unaffected by Wi-Fi | Node A's USB-2 bus now carries both dongles + Ethernet (≈120 Mbit aggregate — within practical limits); SoapyRemote setup on both nodes |
| rtl_tcp | Dead simple, single-client (matches single-owner FSM) | rtl_airband has no native rtl_tcp input — would force SoapySDR anyway for ATC |
| Run all SDR-2 decoders on Node A | No network SDR at all | satdump starves ADS-B on a 1 GB Pi 3B (R-1 returns); defeats the load-share goal |
| Stream over Wi-Fi instead of the cable | No cabling | 40 Mbit IQ over congested 2.4 GHz = drops/jitter; the reason the cable was added |

## Consequences
- Positive: respects the immovable-dongle constraint; private link removes Wi-Fi
  as a failure path for control + samples; heavy decode lives on Node B; **Node B
  no longer needs a dongle, so it's no longer blocked on the case constraint** —
  only on its PSU (for decode CPU headroom).
- Negative: Node A's shared USB-2 bus now carries both dongles' capture + the
  outbound sample stream (the R-2 contention ADR-001 had eliminated partially
  returns — watch `dmesg` for USB resets; the Stratux LowPower dongles are
  designed for dual operation, which helps).
- Risk: SoapyRemote sample drops if the link saturates — mitigated by the
  dedicated cable (94 Mbit vs 40 Mbit need) and single-owner decoding (one
  stream at a time).

## Implementation status
Dedicated link: **done + verified**. SoapyRemote capture/decode wiring is the
revised Node B bring-up (see flash-node-b.md) — hardware-validated, gated only
on the Node B PSU now (not the dongle).

## References
- ADR-001 (superseded topology); 02_CODE_RESEARCH R-1/R-2; scripts/flash-node-b.md
