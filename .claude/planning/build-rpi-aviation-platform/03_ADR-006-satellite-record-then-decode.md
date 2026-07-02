# ADR-006: Satellite Record-Then-Decode; APT Default, LRPT Experimental

## Status: Accepted
## Date: 2026-06-12

## Context
SatDump live decode during a pass is CPU-bound for the whole 10–15 min window. On Node B's Pi 3B (4×A53, 1 GB), live METEOR LRPT decode risks dropped samples and OOM. A pass is unrepeatable — capture must be protected; decode timing is flexible.

## Decision
During a pass, SatDump (or rtl_sdr) only **records baseband to tmpfs** (cheap, I/O-bound). After LOS, decode runs at `nice 19` with a 512 MB cgroup cap. **NOAA APT is the default enabled pipeline; METEOR LRPT ships config-gated (`satellite.lrpt.enabled: false`)** until empirically validated on 1 GB (M4 exit test).

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| **Record → decode after LOS** | Capture (the unrepeatable part) needs minimal CPU; decode can take 5 min without harming anything; OOM kills decode, not capture | Image arrives ~5–10 min after pass (fine vs FR-7/G1's ≤10 min); tmpfs holds ~400 MB during pass |
| Live decode during pass | Image ready at LOS | CPU saturation during capture → sample drops → degraded image; OOM mid-pass loses everything |
| Decode on Node A | Node B stays idle post-pass | Ships ~400 MB baseband over Wi-Fi (minutes); loads the node whose job is staying light — backwards |

## Consequences
- Positive: pass capture success decoupled from decode resources; aligns with SatNOGS practice.
- Negative: tmpfs sizing constrains max pass length (400 MB ≈ 15 min @ ~1.024 Msps APT profile — sufficient; LRPT needs care).
- Risks: LRPT may prove infeasible on 1 GB → feature stays gated; documented Pi 4/5 upgrade path for LRPT users.

## References
- 02_CODE_RESEARCH R-1 (historical), addendum; PRD FR-7, NFR-4
