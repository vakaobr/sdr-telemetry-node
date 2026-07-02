# ADR-005: SQLite (WAL) with Summary-Level Persistence, Single Writer

## Status: Accepted
## Date: 2026-06-12

## Context
Pi boots from SD cards with finite write endurance (NFR-6: <1 GB/day). ADS-B produces hundreds of messages/sec; persisting the firehose would kill the card and is unneeded for the product's analytics (FR-9). Heavy databases are prohibited.

## Decision
One SQLite database (WAL, `synchronous=NORMAL`), owned exclusively by the gateway process on Node A. Persist **summaries only**: per-contact sightings (upserted on contact close / 60 s batch), hourly rollups, pass index, enrichment cache. Live positions/trails are RAM-only. Node B never touches the DB (ships data via HTTP/MQTT).

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| **SQLite summaries, single writer** | Zero server RAM; crash-safe WAL; write volume ~MBs/day; trivially backed up (one file) | ≤60 s data-loss window on crash (accepted); analytics limited to summarized grain |
| PostgreSQL | Rich SQL, concurrent writers | ~100–200 MB RAM on a 1 GB node for no concurrent-writer need; "heavy database" violation |
| InfluxDB/Timescale (full position history) | Replay/deep analytics | Firehose writes destroy SD card; RAM-hungry; product doesn't need replay (out of scope) |
| Flat JSONL logs | Simplest | No queryability for FR-9 analytics; retention/rollup logic reinvented badly |

## Consequences
- Positive: SD endurance preserved; restore/backup = copy one file; analytics queries are simple indexed SQL.
- Negative: no flight-path replay feature possible later without schema addition (accepted — out of scope).
- Risks: cross-process write temptation later (e.g., a new service) — guard via code review rule: *all* writes through gateway's persist module.

## References
- PRD NFR-6/FR-9; 03_ARCHITECTURE §3/§8
