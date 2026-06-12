# ADR-002: MQTT (Mosquitto) as the Event Bus

## Status: Accepted
## Date: 2026-06-12

## Context
Event-driven architecture is mandated; the guardrail says "Redis only if justified." With the two-node split (ADR-001), the bus must carry **cross-node** events (Node B → Node A) plus notifications, survive restarts, and cost almost nothing in RAM.

## Decision
Eclipse Mosquitto (MQTT 3.1.1/5) as the sole bus. **Scope-limited:** high-rate ADS-B positions do NOT transit the bus (gateway polls co-located readsb directly); the bus carries cross-node telemetry (AIS, satellite, radio2 state), notifications, and health.

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| **Mosquitto MQTT** | ~10 MB RAM; retained messages = free last-known-state; LWT = free liveness detection; AIS-catcher publishes MQTT natively; proven on Pi (Home Assistant ecosystem) | One more container |
| Redis pub/sub | Familiar; also K/V | ~3–5× RAM; no retained semantics (need extra K/V code); no LWT; AIS-catcher doesn't speak it |
| In-proc fan-out (no broker) | Zero containers | Impossible across two nodes; couples decoder lifecycle to gateway; not restart-safe |
| NATS | Fast, light | No native decoder support; younger ARM story; features unneeded |

## Consequences
- Positive: retained topics make the UI instantly correct after any restart; LWT gives Node-B-offline detection in ≤15 s with zero polling code; broker load trivial (<20 msg/s).
- Negative: QoS-1 is at-least-once → consumers must be idempotent (event payloads carry `ts`/ids).
- Risks: broker is a single point for Node-B freshness — acceptable; ADS-B path has zero bus dependency.

## References
- 02_CODE_RESEARCH §3/§7; 03_ARCHITECTURE §5
