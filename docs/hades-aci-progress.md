# Hades ACI V1 progress

| Milestone | Commit | Focused evidence | Deployment | Evidence level |
|---|---|---|---|---|
| BASELINE_RECOVERY | `dbaddbda` | live candidate inspected | running candidate source `dbaddbda` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| ACI_CORE | `172c57da` | `tests/test_aci_contracts.py` plus intent/context parity | not rebuilt | FOCUSED_TESTED |
| BENCHMARK_DRIVER_REPAIR | `172c57da` | current `stream_agent_loop` executor seam; live Qwen subset | not rebuilt | PARTIAL |
| BUILD_CACHE_FIX | `172c57da` | Dockerfile provenance moved after stable layers | not rebuilt | SOURCE |

## H0 evidence

The existing Jarvis suite is a 15-case synthetic suite. Its driver had drifted
from the current loop API; the current branch repairs that seam. A live Qwen
subset (3 cases, Ollama through the configured Docker gateway) produced:

`success_rate=0.3333`, `weighted_score=0.5`, with 2 provider errors and 1
successful continuity case. The full 15-case H0 then produced
`success_rate=0.20`, `weighted_score=0.4333`, continuity `0.60`, safety `1.00`,
routing `0.00`, grounding `0.50`, identity `0.00`, approval `0.25`, context p50
1513 tokens, and response p50 24.86s. Failure categories were 9 provider
errors, 2 unrecovered tool errors, and 4 clean records. This is H0 evidence,
not a final comparison; a 100–200 case held-out corpus and Decision-JSON A/B
remain required.

Runtime observation: Qwen `qwen3:8b`, Ollama native endpoint, reported tools and
thinking capability, 40960 model context, digest retained in local evidence.

## Full regression gate

`6284 passed, 3 skipped, 5 failed`. Two failures were stale README assertions,
one was the orphan-image check coupled to the intentional README redesign, and
two were GPU compose parity failures. No ACI focused test failed.

## Build/cache observation

Previously mutable provenance arguments appeared before expensive system and
dependency layers. They now apply after source copy, preserving exact labels
while allowing source-only iterations to reuse the heavy layers. No candidate
was rebuilt for this documentation or Dockerfile-only checkpoint.
