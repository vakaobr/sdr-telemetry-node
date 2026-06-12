# ADR-007: ATC Audio via Icecast MP3 Stream (direct to browser)

## Status: Accepted
## Date: 2026-06-12

## Context
ATC airband audio must reach browsers (TV/mobile/desktop) with acceptable latency and minimal moving parts. rtl_airband natively outputs to Icecast. PRD R-7 left HLS vs WebSocket/Opus open.

## Decision
rtl_airband → **Icecast (Node B) → browser `<audio>` element playing the MP3 stream directly**. The gateway only hands clients the stream URL (`GET /api/v1/radio2` includes `audio_url`). No HLS packaging, no WS audio transport, no transcoding hop.

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| **Icecast MP3 direct** | rtl_airband native output — zero extra components; `<audio src>` works on every target browser incl. smart TVs; 2–5 s latency (Icecast buffer) acceptable for ATC | Cross-origin to a second host:port (fine for media elements); per-listener MP3 stream ~24–64 kbps × ≤5 clients — trivial |
| HLS (ffmpeg/nginx packaging) | CDN-style semantics | Adds ffmpeg + packager container for nothing; 6–12 s latency; more disk churn (segments) |
| WebSocket + Opus | ~1 s latency; single origin | Custom audio pipeline both ends (encoder, WS framing, MSE/WebAudio playback); smart-TV browser support risky; most code for least benefit |

## Consequences
- Positive: zero custom audio code; squelch-activity events (`atc/activity`) stay on MQTT independent of transport.
- Negative: audio unavailable when Node B is down (inherent — the radio is there); latency ~2–5 s (within tolerance, story E1).
- Risks: some TV browsers autoplay-block audio — UI requires a tap-to-play affordance (also better UX).

## References
- PRD FR-5, R-7; story E1/E2
