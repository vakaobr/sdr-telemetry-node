# ADR-003: All-Python Backend (FastAPI gateway, asyncio radio2)

## Status: Accepted
## Date: 2026-06-12

## Context
Guardrail allows FastAPI or Go. Two custom services exist: the gateway (Node A) and the radio2 supervisor (Node B). Satellite pass prediction requires orbital math from TLEs.

## Decision
Python 3.12 for both services: FastAPI/uvicorn for the gateway; plain asyncio (no web framework) for the radio2 supervisor. Go is documented as an **escape hatch** for the WS fan-out only, triggered by profiling evidence (>5 clients degrading NFR-8), not speculation.

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| **All Python** | Skyfield (pass prediction) is Python-native and excellent; one language/toolchain/test-stack; fastest iteration | WS fan-out heavier than Go (~fine at ≤5 clients); higher base RAM (~60–80 MB/service) |
| All Go | Lowest RAM/CPU; great concurrency | No Skyfield equivalent (would wrap C libs or port math); slower iteration; two custom services × harder hiring of contributors |
| Python gateway + Go radio2 | Right tool per service? | Two toolchains for ~3k LOC total — complexity not earned; radio2 is mostly process supervision + Skyfield, i.e., Python-shaped |

## Consequences
- Positive: single test/lint stack (pytest+ruff); shared pydantic models generated from `shared/schemas`; Skyfield used as designed.
- Negative: ~150 MB combined RAM for the two services — fits budgets (03_ARCHITECTURE §10).
- Risks: GIL irrelevant here (I/O-bound); if WS fan-out becomes the bottleneck the escape hatch swaps one module, not the architecture.

## References
- 02_CODE_RESEARCH §7.1
