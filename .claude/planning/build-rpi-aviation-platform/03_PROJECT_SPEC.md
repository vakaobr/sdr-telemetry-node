# Project Spec: build-rpi-aviation-platform

**Date:** 2026-06-12 · companion to 03_ARCHITECTURE.md + ADR-001…008

---

## 1. Technical Requirements (from Discovery success criteria)

| TR | Requirement | Verification |
|----|-------------|--------------|
| TR-1 | ADS-B RF→dashboard ≤ 2 s p95; pipeline never paused by Radio-2 activity (physically guaranteed, ADR-001) | latency probe test; 48 h soak with satellite passes occurring |
| TR-2 | Node A steady state: CPU < 55%, RAM < 600 MB (Pi 3B budget, 03_ARCHITECTURE §10) | `sys/node-a/health` metrics over soak |
| TR-3 | Dashboard correct on 1080p TV (10 ft), desktop, ≥360 px mobile; WS-only updates | manual matrix + Playwright viewport tests |
| TR-4 | Radio-2 mode switch ≤ 10 s p95; satellite pre-empts ATC/AIS at AOS−60 s; returns to prior mode post-LOS | FSM event-timestamp assertions in integration tests |
| TR-5 | Full P0 feature set functional with internet disconnected | CI offline scenario + manual gate |
| TR-6 | Per-node bring-up: `docker compose up -d` on fresh ARM64 Pi OS → working node ≤ 10 min | release checklist on clean SD images |
| TR-7 | History queryable ≥ 30 d; writes < 1 GB/day | retention test; iostat audit over 24 h |
| TR-8 | Node A fully functional with Node B offline; UI reflects Node-B loss ≤ 15 s (MQTT LWT) | chaos test: power-pull Node B mid-soak |

## 2. Non-Functional Requirements (measurable)

| NFR | Target |
|-----|--------|
| Availability (ADS-B path) | ≥ 99.5%/month (health-history computed) |
| WS clients | ≥ 5 concurrent, no degradation; reconnect storm of 5 ≤ 3 s to re-snapshot |
| Cold start | power-on → live dashboard ≤ 3 min (Node A); Node B modes ≤ 5 min |
| Satellite capture | ≥ 90% of scheduled ≥30°-elevation passes yield an image (APT) |
| Audio | stream start ≤ 5 s after tap; end-to-end latency ≤ 5 s |
| SD endurance | < 1 GB/day writes per node steady-state |
| Accessibility | interactive mode: keyboard navigable, WCAG AA contrast; TV mode: ≥ 24 px min font at 1080p |
| Security | zero WAN listeners; no privileged containers; image-upload endpoint rejects requests without `X-Node-Key` |

## 3. Interface Contracts

### 3.1 WebSocket messages (TS — generated from `shared/schemas`)

```typescript
type ServerMessage =
  | { type: "snapshot"; ts: number; aircraft: Aircraft[]; vessels: Vessel[];
      radio2: Radio2Status; latestPass: PassSummary | null; health: SystemHealth }
  | { type: "aircraft_delta"; ts: number; updated: Aircraft[]; removed: string[] /* icao */ }
  | { type: "vessel_delta"; ts: number; updated: Vessel[]; removed: number[] /* mmsi */ }
  | { type: "radio2_status"; ts: number; status: Radio2Status }
  | { type: "atc_activity"; ts: number; channelMhz: number; active: boolean }
  | { type: "interesting"; ts: number; icao: string; severity: "critical" | "notable";
      rule: string; callsign: string | null }
  | { type: "pass_update"; ts: number; pass: PassSummary }
  | { type: "system_health"; ts: number; health: SystemHealth };

type ClientMessage =
  | { type: "subscribe"; topics: ("aircraft" | "vessels" | "radio2" | "system")[] }
  | { type: "ping"; ts: number };

interface Aircraft {
  icao: string; callsign: string | null; lat: number | null; lon: number | null;
  altFt: number | null; gsKt: number | null; vrFpm: number | null; track: number | null;
  squawk: string | null; distanceKm: number | null; bearingDeg: number | null;
  priority: number;                       // 0 = hero candidate
  flags: ("military" | "emergency" | "watchlist")[];
  enrich: { registration: string | null; typeCode: string | null; typeName: string | null;
            operator: string | null; country: string | null; route: string | null;
            photoUrl: string | null } | null;   // null = pending/offline-miss
  trail: [number, number][];              // [lat,lon] ≤ 100, decimated for WS
  lastSeen: number; rssi: number | null;
}

interface Vessel { mmsi: number; name: string | null; lat: number; lon: number;
  sogKt: number | null; cogDeg: number | null; shipType: number | null; lastSeen: number; }

interface Radio2Status {
  mode: "atc" | "ais" | "satellite" | "idle" | "faulted" | "offline";
  since: number; reason: "schedule" | "preempt" | "manual" | "fault" | "lwt";
  nextPass: { satellite: string; aos: number; los: number; maxEl: number } | null;
  audioUrl: string | null;                // Icecast URL when mode==="atc"
  tleAgeDays: number;                     // staleness warning ≥ 14
}

interface PassSummary { id: number; satellite: string; aos: number; los: number;
  maxElevation: number; status: "scheduled" | "captured" | "decoded" | "failed";
  imageUrls: string[]; }

interface SystemHealth {
  nodeA: NodeHealth; nodeB: NodeHealth | null;   // null = LWT-offline
  adsb: { ok: boolean; msgRate: number; aircraftCount: number; maxRangeKm: number };
  dbOk: boolean;
}
interface NodeHealth { ok: boolean; cpuPct: number; memMb: number; tempC: number;
  throttled: boolean; diskFreePct: number; }
```

### 3.2 MQTT payloads — JSON Schema source of truth in `shared/schemas/mqtt/*.json`; identical field names as above (`Radio2Status` ⊂ `radio2/mode` + `radio2/pass/next` + `radio2/health` retained merge). All payloads carry `ts` (unix s) and are idempotent on consumer side (QoS 1).

### 3.3 Node B → gateway upload
`POST /api/v1/passes/{id}/images` · headers: `X-Node-Key: <shared secret>` · multipart `image/png` (≤ 8 MB each, ≤ 6 files) → `201 {urls: string[]}` · `401` bad key · `404` unknown pass id · `413` too large.

### 3.4 config.yaml (validated by pydantic at startup; same file schema both nodes, node-relevant sections read per role)

```yaml
receiver: { lat: 38.7169, lon: -9.1399, alt_m: 45 }
nodes: { gateway_url: "http://nodea.local:8080", mqtt_host: "nodea.local" }
adsb: { staleness_pos_s: 60, staleness_msg_s: 300, trail_len: 100 }
radio2:
  schedule: [ { mode: atc, from: "07:00", to: "23:00" }, { mode: ais, from: "23:00", to: "07:00" } ]
  satellite:
    min_elevation_deg: 30
    apt: { enabled: true }
    lrpt: { enabled: false }     # experimental on 1 GB (ADR-006)
  atc: { channels_mhz: [118.1, 121.5], icecast_mount: "/atc" }
watchlist: [ { match: "hex", value: "3e8413" }, { match: "callsign_glob", value: "RCH*" } ]
retention: { sightings_days: 30, passes_keep: 50 }
```

## 4. Testing Requirements

| Layer | Tooling | Must cover |
|---|---|---|
| Unit (gateway) | pytest | state-table diffing, staleness expiry, priority ranking, interesting rules, enrichment fallback chain, RFC-7807 errors |
| Unit (radio2) | pytest | **FSM exhaustive transition table** (incl. preempt during STARTING, fault during STOPPING), pass-window math vs known TLE fixtures, watchdog/timeout firing |
| Unit (web) | vitest | ws-client reconnect/snapshot merge, store reducers, hero-priority selection |
| Contract | CI job | pydantic models + TS types both regenerated from `shared/schemas` → diff must be empty |
| Integration | docker compose + pytest | fake-decoder harness (scripted stdout/exit codes) driving real FSM; MQTT round-trip; image upload path; **offline scenario: all tests pass with network namespace disconnected** |
| Chaos (pre-release) | scripted | kill -9 each container mid-soak; power-pull Node B; SDR replug; assert TR-8 + restart-safety invariant |
| Soak (release gate) | 7 days TV mode | zero crash/leak (RSS slope ~0), TR-1/TR-2 sustained |

## 5. Migration Plan
Greenfield — no existing data. Schema versioning from day 1: `schema_version` table + ordered `migrations/NNN_*.sql` applied by gateway at boot (forward-only). Pre-migration automatic copy `app.db → app.db.pre-NNN` (rollback artifact). Config migrations: pydantic accepts N-1 schema with deprecation warnings for one minor version.

## 6. Feature Flag Strategy
Flags are **config keys, not code branches sprinkled ad hoc** — each maps to a module enable:
- `radio2.satellite.apt.enabled` / `lrpt.enabled` (ADR-006 gate)
- `radio2.schedule` empty ⇒ ATC-only static mode (M3 ships before AIS/satellite exist)
- `enrichment.online.enabled` (default true, auto-degrades offline)
- `ui.tv_rotation` panel list (lets M2 ship without satellite panel)
Rollout = milestone-gated: each milestone's features land disabled-by-default in config.example until its exit tests pass, then flipped to default-on in the next tag.

## 7. Rollback Plan
- **Images:** every release tags all images `vX.Y.Z` + digest-pins in committed compose files. Rollback = `git checkout vPrev -- docker/ && docker compose up -d` per node (≤ 2 min, no data touched).
- **Database:** restore `app.db.pre-NNN` copy if a migration misbehaves (gateway refuses to start on schema mismatch rather than corrupting).
- **Config:** `config.yaml` is user-owned and versioned in their git or backed by `config.yaml.bak` written before any UI-driven change.
- **Node B independence:** a bad Node B release cannot take down tracking — Node A keeps full ADS-B + dashboard (TR-8). Roll nodes independently, Node A last.
- **Abort criteria:** failed healthz 3× post-deploy → operator instruction: rollback, file issue with `docker logs` bundle (script `scripts/support-bundle.sh`).

## 8. Definition of Done (per milestone)
Code + tests green (incl. offline CI) · contract-codegen clean · resource budgets verified on real Pi 3B · docs updated · CHANGELOG entry · rollback tested once on hardware.
