# Hades ACI V1 progress

| Milestone | Commit | Focused evidence | Deployment | Evidence level |
|---|---|---|---|---|
| BASELINE_RECOVERY | `dbaddbda` | 130 existing focused tests; live candidate inspected | running candidate source `dbaddbda` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| ACI_CORE | local pending | `tests/test_aci_contracts.py` plus intent/context parity | not rebuilt | FOCUSED_TESTED |
| BENCHMARK_DRIVER_REPAIR | local pending | current `stream_agent_loop` executor seam; live 3-case Qwen subset | not rebuilt | PARTIAL |
| BUILD_CACHE_FIX | local pending | Dockerfile provenance moved after stable layers | not rebuilt | SOURCE |

## H0 evidence

The existing Jarvis suite is a 15-case synthetic suite. Its driver had drifted
from the current loop API; the current branch repairs that seam. A live Qwen
subset (3 cases, Ollama through the configured Docker gateway) produced:

`success_rate=0.3333`, `weighted_score=0.5`, with 2 provider errors and 1
successful continuity case. This is a partial H0, not a representative final
benchmark. The older 15-case suite is retained as a development fixture; a
100–200 case held-out corpus and Decision-JSON A/B remain required.

Runtime observation: Qwen `qwen3:8b`, Ollama native endpoint, reported tools and
thinking capability, 40960 model context, digest retained in local evidence.

## Build/cache observation

Previously mutable provenance arguments appeared before expensive system and
dependency layers. They now apply after source copy, preserving exact labels
while allowing source-only iterations to reuse the heavy layers. No candidate
was rebuilt for this documentation or Dockerfile-only checkpoint.
