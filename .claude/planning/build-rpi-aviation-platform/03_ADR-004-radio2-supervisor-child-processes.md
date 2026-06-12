# ADR-004: Radio-2 Decoders as Supervised Child Processes (one container)

## Status: Accepted
## Date: 2026-06-12

## Context
SDR #2 time-shares three mutually-exclusive decoders; an RTL-SDR can be claimed by exactly one process. Research (pre two-node split) proposed cross-container coordination: either Docker-socket lifecycle control or a "device token" gate — both add a distributed-coordination protocol around a single USB device.

## Decision
With orchestrator and decoders co-located on Node B (ADR-001), run **rtl_airband, AIS-catcher, and SatDump as child processes of the radio2 supervisor, inside one container**. Mode switch = `SIGTERM child → waitpid → spawn next`. The FSM's single-owner invariant is enforced by ordinary process lifecycle — no token, no Docker socket, no cross-container handshake.

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| **Supervisor + child procs (1 container)** | Device handoff is `waitpid` — race-free by construction; zero coordination protocol; one image to build; SIGKILL escalation trivial | One container hosts 4 binaries (fatter image ~300 MB); "one container = one bounded context" guardrail bends — justified: the bounded context is *radio-2 as a resource*, decoders are its modes, not independent services |
| Device-token gate across 3 containers | Containers stay 1:1 with tools | Invents a distributed mutex for a local resource; 3 idle containers burn RAM on a 1 GB node; failure modes (token holder dies mid-switch) need protocol care |
| Orchestrator drives Docker socket | Standard images unmodified | Docker-socket access ≈ root on host — security cost; restart races; violates least-privilege |

## Consequences
- Positive: R-3 reduced to single-process discipline; simplest possible recovery (child dies → FSM respawns); RAM only for the active decoder.
- Negative: decoder upgrades rebuild the radio2 image (acceptable: monthly pinned rebuilds anyway); container restart kills active mode (~10 s gap, within FR-4.6).
- Risks: zombie child on supervisor bug — mitigated by PID-1 init (`tini`) + watchdog SIGKILL escalation (10 s).

## References
- 03_ARCHITECTURE §2/§6 FSM; 02_CODE_RESEARCH §4 (superseded options)
