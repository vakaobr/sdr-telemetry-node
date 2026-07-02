# ADR-010: AIS via AISStream (internet); satellite deferred

## Status: Accepted
## Date: 2026-06-12

## Context
The shared radio (SDR #2) has ONE antenna port but the design time-shares three
bands: ATC airband (118–137 MHz), AIS (162 MHz), and NOAA/METEOR satellite
(137 MHz). No single practical antenna serves all three well, and the user's
hardware reality is one airband antenna (108–136 MHz) on the shared dongle. AIS
at 162 MHz and satellite at 137 MHz would both be marginal-to-unusable on it,
and a wideband discone is bulky/compromised.

## Decision
- **AIS: consume from AISStream.io** (free real-time WebSocket feed), decoded in
  the gateway on Node A — no radio, no antenna, no orchestration. Gated on
  `AISSTREAM_API_KEY` (env, gitignored). The local `ais` decoder mode in the
  radio2 orchestrator remains for anyone with a marine antenna (future
  `ais.source: local`), but the internet feed is the default.
- **Satellite: deferred.** NOAA/METEOR's value is capturing *your own* image from
  *your own* antenna; an internet weather image is a different, lesser feature.
  It needs a dedicated 137 MHz up-pointing antenna (QFH/turnstile) anyway. Keep
  it roadmapped as an optional hardware add-on; do NOT fake it via the internet.
- Net effect: the shared radio (SDR #2) is effectively **ATC-only** for local RF,
  so the single airband antenna suffices. The orchestrator (Phase 7) still runs
  (ATC-only now) and is ready for satellite if a 137 MHz antenna is added.

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| **AIS via AISStream (chosen)** | No hardware; reliable global real-time; runs on Node A now | Not local-first for AIS (degrades offline); external dependency |
| Local AIS on shared radio | Local-first | 162 MHz needs a marine/wideband antenna we don't have; time-sharing complexity for marginal results |
| Satellite via internet | "works" offline-less | Not the same feature — defeats the point of own-capture; rejected |
| Wideband discone for all bands | One antenna, all modes | Bulky; compromised gain; still poor satellite (wants circular polarization) |

## Consequences
- Positive: AIS ships on the map **today**, no hardware wait; antenna decision
  simplifies to "airband only"; offline-first preserved for the core (ADS-B) —
  AIS just goes stale when offline.
- Negative: AIS depends on an internet service + third-party key; satellite
  feature delayed.
- Risk: AISStream availability/rate limits — fail-soft (vessels go stale, ADS-B
  and the rest are unaffected).

## References
- ADR-009 (shared-radio topology); PRD FR-6 (AIS), FR-7 (satellite); ROADMAP R-sat
