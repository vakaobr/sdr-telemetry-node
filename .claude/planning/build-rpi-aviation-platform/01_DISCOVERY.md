# Discovery: build-rpi-aviation-platform

## Summary
A self-hosted, Raspberry Pi-based aviation intelligence platform ("sdr-telemetry-node") inspired by FlightWall Mini, replacing the LED/DMD display with a modern, responsive local web interface. Two USB SDR radios feed the system: a dedicated 1090 MHz ADS-B receiver (always-on aircraft tracking) and a shared multi-role SDR orchestrated across ATC airband audio (118–137 MHz), AIS vessel tracking, and NOAA/METEOR weather-satellite reception. The product is local-first, Docker Compose-deployed, ARM64-native, and degrades gracefully when internet enrichment APIs are unavailable.

## Problem Statement
Aviation enthusiasts who want a FlightWall-class ambient display must buy closed commercial hardware with a fixed LED display, no extensibility, and cloud dependencies. Self-hosters today must manually glue together dump1090, rtl_airband, AIS-catcher, and satellite decoders with no unified UI, no orchestration of a shared SDR, and no cohesive "beautiful dashboard" experience. This project unifies those capabilities into a single deployable product with one beautiful web UI usable on TV, desktop, tablet, and phone.

## Success Criteria
- [ ] ADS-B aircraft visible on the live dashboard ≤ 2 s after RF reception, with zero ADS-B downtime caused by secondary-SDR activity
- [ ] Full stack (all containers) runs on a Raspberry Pi 4 (4 GB) with steady-state CPU < 70% and RAM < 3 GB while decoding ADS-B + one secondary mode
- [ ] Dashboard renders correctly on a 1080p TV (10 ft readable), desktop, and mobile; WebSocket-driven updates with no manual refresh
- [ ] Secondary SDR auto-switches between ATC / AIS / satellite per schedule + priority rules, with satellite passes pre-empting lower-priority modes and returning afterward
- [ ] System remains fully functional (tracking, dashboard, history) with internet disconnected; enrichment fields degrade gracefully
- [ ] Single-command bring-up: `docker compose up -d` on a fresh ARM64 Pi OS install completes to a working dashboard
- [ ] Historical analytics (daily counts, range, interesting sightings) queryable for ≥ 30 days of retained data

## Scope
### In Scope
- ADS-B decode (1090 MHz), aircraft state tracking, deduplication, prioritization by proximity
- Aircraft enrichment (registration, type, operator, route) via local DBs + optional online APIs with cache
- "Interesting aircraft" rules (military, emergency squawks 7500/7600/7700, rare types, watchlist)
- Secondary-SDR orchestrator: mode scheduling, priority pre-emption, satellite pass prediction (TLE-based)
- ATC airband audio streaming to browser; AIS vessel decode + display; NOAA APT / METEOR LRPT image decode
- Real-time WebSocket dashboard; wall-display ("kiosk/TV") mode; map-based route visualization
- Historical storage + analytics (SQLite), retention policy
- Monorepo, Docker Compose, ARM64 images, local-only operation
- PRD, personas, user stories, NFRs, risk register, roadmap (this phase's deliverables)

### Out of Scope
- Feeding external aggregators (FlightAware/FR24/ADSBx) — extensibility hook only, not built
- Cloud sync, remote access/VPN, multi-node federation
- MLAT (multilateration) — requires multiple receivers
- UAT 978 MHz, FLARM, ACARS/VDL2 decoding (future candidates)
- User accounts/multi-tenancy; the system is single-household, LAN-trusted
- Mobile native apps; Kubernetes; any cloud infrastructure
- Custom PCB/hardware design; antenna engineering guidance beyond docs
- ATC audio transcription/AI analysis (extensibility hook only)

## Stakeholders
- Users: aviation enthusiasts, plane spotters, households with wall-mounted displays, ham/SDR hobbyists
- Teams: single developer/maintainer (self-hosted OSS model)
- Systems: RTL-SDR USB radios ×2, Raspberry Pi 4/5, home LAN, optional internet enrichment APIs (adsbdb, hexdb, etc.), NOAA/METEOR satellites (TLE from CelesTrak)

## Risk Assessment
**Level:** Medium
**Justification:** No production users or existing system to break (greenfield). Highest risks are hardware/RF integration complexity (two SDRs, USB bandwidth, thermal), satellite decode quality, and Pi resource ceilings — all engineering risks, not safety/data risks. No PII beyond LAN-local data. Failure mode is a hobbyist dashboard going stale, not harm.

## Dependencies
- RTL-SDR drivers (librtlsdr) and proven decoders: readsb/dump1090-fa (ADS-B), AIS-catcher, rtl_airband / SDR++ server, satdump (NOAA/METEOR)
- TLE orbital data (CelesTrak) for pass prediction — cached locally, refresh when online
- Aircraft metadata DBs (e.g., tar1090-db, Mictronics DB) bundled for offline enrichment
- ARM64 base images for all services
- USB bandwidth/power budget on Pi (powered hub likely required for 2 SDRs)

## Estimated Complexity
**Size:** XL
**Reasoning:** Multiple bounded contexts (ADS-B ingest, orchestrator, ATC audio, AIS, satellite pipeline, enrichment, analytics, web UI), hardware integration, real-time streaming, audio transport, and image decode pipelines. Mitigated by reusing mature OSS decoders rather than writing DSP from scratch — the novel work is orchestration, the event bus, and the UI. Phased roadmap mandatory.

## Detected Tech Stack

### Languages & Frameworks
| Technology | Version | Expert Command |
|------------|---------|----------------|
| (greenfield — none detected) | — | `/language/software-engineer-pro` |

**Proposed stack (to be ratified in /design-system):**
| Technology | Role | Expert Command |
|------------|------|----------------|
| Python 3.12 (FastAPI) | Backend services, orchestrator | `/language/python-pro` |
| TypeScript + React (Vite) | Web dashboard | `/language/typescript-pro`, `/language/javascript-react-pro` |
| SQLite (WAL) | Storage/analytics | — |
| Redis or in-proc pub/sub | Event bus | — |
| Docker Compose | Deployment | (containerized) |

### Infrastructure
| Technology | Expert Command |
|------------|----------------|
| Docker Compose (ARM64, local-only) | `/language/cloud-engineer-pro` (fallback; no cloud) |

### Quality Tooling
| Tool | Status |
|------|--------|
| Linter | ✗ Missing |
| Formatter | ✗ Missing |
| Test Runner | ✗ Missing |
| CI/CD | ✗ Missing |
| Pre-commit Hooks | ✗ Missing |

### Missing Quality Tooling Recommendations
- Run `/quality/lint-setup` after the first scaffold (ruff + eslint + prettier)
- Run `/quality/test-strategy` to set pytest + vitest baseline before implementation
- Run `/quality/dependency-check` once package manifests exist
- `.pre-commit-config.yaml` with gitleaks per global security guidelines

## Repository Map

```
sdr-telemetry-node/
  LICENSE
```

**Files:** 0 source | 0 test | 1 config (LICENSE only)
**Primary language:** none yet (greenfield)
**Key entry points:** none — first scaffold will be created in /implement

> Generated automatically during discovery. Run `/repo-map` to refresh.

## Symbol Index

(empty — greenfield repository, no source files)

> Generated alongside repo map. Run `/repo-map` to refresh.
