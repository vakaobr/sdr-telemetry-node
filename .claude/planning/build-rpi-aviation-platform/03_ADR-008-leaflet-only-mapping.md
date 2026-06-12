# ADR-008: Leaflet-Only Mapping (no MapLibre dual-stack)

## Status: Accepted
## Date: 2026-06-12

## Context
Research suggested possibly splitting: Leaflet (canvas) for TV mode, MapLibre GL for interactive desktop. Smart-TV browsers may lack WebGL2; Pi-kiosk Chromium has weak GPU compositing. NFR-9 demands smooth TV rendering on conservative baselines.

## Decision
**Leaflet only**, canvas renderer, for both TV and interactive modes. Self-hosted raster tiles (offline-first). MapLibre is not included in v1.

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| **Leaflet everywhere** | One map stack to learn/test; canvas works on every target incl. TVs and Pi kiosk; raster tiles trivially self-hosted; plugin ecosystem (rotated markers, trails) mature | No vector-tile styling finesse; heavy marker counts (>500) slow — irrelevant at ~50–150 aircraft |
| MapLibre everywhere | Beautiful vector styling, smooth zoom | WebGL2 requirement fails exactly on the wall-display targets the product is for |
| Split (Leaflet TV + MapLibre desktop) | Best of both per surface | Two map stacks: double components, testing, tile pipelines (raster AND vector) — complexity not earned by a styling delta |

## Consequences
- Positive: one tile pipeline (raster, pre-bundled region pack + optional online cache); TV mode and interactive share map components; smallest bundle.
- Negative: less slick zooming/styling than vector GL — acceptable for v1 aesthetic goals (dark raster tiles exist).
- Risks: if v2 wants vector polish, MapLibre can be added behind the same component interface; not a one-way door.

## References
- PRD NFR-9, R-5; 02_CODE_RESEARCH R-5
