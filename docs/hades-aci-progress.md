# Hades ACI V1 progress

| Milestone | Commit | Focused evidence | Deployment | Evidence level |
|---|---|---|---|---|
| BASELINE_RECOVERY | `dbaddbda` | live candidate inspected | running candidate source `dbaddbda` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| ACI_CORE | `172c57da` | `tests/test_aci_contracts.py` plus intent/context parity | not rebuilt | FOCUSED_TESTED |
| BENCHMARK_DRIVER_REPAIR | `172c57da` | current `stream_agent_loop` executor seam; live Qwen subset | not rebuilt | PARTIAL |
| BUILD_CACHE_FIX | `172c57da` | Dockerfile provenance moved after stable layers | not rebuilt | SOURCE |
| DECISION_INTERFACE | working tree after `818f0bcf` | 63 focused tests; strict Decision JSON, opaque choices, one repair, chat setting seam | not rebuilt | FOCUSED_TESTED |
| FROZEN_CORPUS | working tree | 120 synthetic owner-free cases: 96 development, 24 held-out, 12 canary | not rebuilt | SOURCE |
| FULL_REGRESSION | `a1abb6e1` + README checkpoint | `6292 passed, 3 skipped` | not rebuilt | FULL_REGRESSION |
| FINAL_DEPLOYED_CHECKPOINT | `1ce7ec34` image | health/version, broker, Ollama, Chroma/SearXNG verified | `odysseus:candidate-1ce7ec34b9f7` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| RUNTIME_PROFILE_CONTEXT | `3d106a6a` | runtime-keyed evidence cache, TTL, protocol/runtime separation, ACI context-envelope metrics; focused-tested | superseded by final candidate | FOCUSED_TESTED |
| RUNTIME_PROFILE_DIAGNOSTICS | `85cb0ee4` | owner-scoped `/api/hades/runtime-profile`; sanitized runtime evidence projection; focused-tested | superseded by final candidate | FOCUSED_TESTED |
| TOKEN_ACCOUNTING | `ce626774` | nested native tool-schema serialization included in shared estimator; 52 focused tests | `odysseus:candidate-ce626774f5ac` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| FINAL_RUNTIME_CHECKPOINT | `ce626774` | `6298 passed, 3 skipped`; health/version, broker, Ollama verified; unauthenticated profile route returns 401 | `odysseus:candidate-ce626774f5ac` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| OLLAMA_CHARACTERIZATION | `4c43dfae` | metadata-only `/api/show` plus fallback `/api/tags`; qwen3:8b digest/context/capabilities recorded locally | `odysseus:candidate-4c43dfae28d8` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| PROTOCOL_PROBES | `49de2dc0` | synthetic strict Decision JSON PASS and verified native-tool PASS; no side effects | not rebuilt | FOCUSED_TESTED |
| MEMORY_COMPLETION_FIX | `d9d07bdc` | 75 focused; 6304 full; sanitized live Qwen trajectory reaches ANSWER without tool re-entry | `odysseus:candidate-d9d07bdc` | DEPLOYED/PASSIVE_LIVE_VERIFIED |

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

## ACI evidence

The final six-case ACI canary used the same Ollama/qwen3:8b route and synthetic
executor as the H0 harness. All six records were clean and scoreable:
canonical grounding, network semantic routing, shell-fallback safety, action
narration grounding, referent selection, and duplicate-read-loop control. The
subset score was `6/6` (`1.00`); this is a canary, not a replacement for the
full-suite comparison. Median request context was 1248 tokens and median
response time was 27.42s. The network case emitted one canonical
`manage_homelab` action; no raw shell command or arbitrary action identifier was
accepted. Raw artifact: `/tmp/hades-aci-final-canary.json` (local only).

The earlier full 15-case ACI run is retained as pre-fast-path evidence
(`success_rate=0.3333`, `weighted_score=0.4667`, routing `1.00`, grounding
`0.75`) but is not called final because deterministic reads and malformed
decision handling landed afterward.

The final H0-equivalent 15-case ACI run completed after those fixes with
`success_rate=0.4667`, `weighted_score=0.6667`, 11 clean records, and 4
timeouts. Compared with H0 (`0.20` / `0.4333`, 4 clean records), the weighted
delta is `+0.2334` and success delta is `+0.2667`. Category deltas were routing
`0→0.50`, prerequisite `0.50→1.00`, efficiency `0.50→1.00`, grounding
`0.50→0.75`, approval `0.25→0.50`, security `0→0.50`, continuity
`0.60→0.70`; identity remained `0`. Final ACI median request context was 1248
tokens across 11 measured records. Raw artifact: `/tmp/hades-aci-final-15.json`
(local only).

The chat route now passes the explicit `hades_aci_mode` setting to the canonical
agent loop. `aci` is the default, with `shadow` and `legacy` available as
operator rollback modes; this is a setting, not model-name capability logic.

Runtime characterization is now represented by a persisted, sanitized cache
keyed by endpoint identity, protocol, serving runtime, model identity/digest,
and server fingerprint. Evidence precedence is explicit administrator override,
capability probe, provider report, endpoint configuration, registry, heuristic,
then unknown. The cache is observational and cannot grant an Action. ACI final
metrics include the effective context projection with runtime allocation,
profile target, requested input, and reserved output separated.

Live local characterization evidence for the configured Ollama bridge recorded
protocol `ollama-chat`, runtime `ollama`, model `qwen3:8b`, digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`, architecture
context `40960`, and provider-reported capabilities `completion`, `tools`, and
`thinking`. No discovery or inference probe was performed.

The later synthetic protocol probes recorded strict Decision JSON as schema-valid
(`ACTION`, choice `A`) and native tool calling as a verified alternate
(`inspect_services(target=synthetic-host)`), with execution disabled. The
sanitized fixture is `benchmarks/hades_aci_protocol_probe.json`; canonical
ActionSpec, policy, approval, and executor authority remain downstream.

## Owner Memory completion defect

The exact utterance `What do you remember about me?` is now a frozen trajectory
case: `DETERMINISTIC_READ -> CANONICAL_RESULT -> RESULT_PROJECTION -> ANSWER ->
COMPLETE`. A protected explicit Memory pre-read is recognized as the unique
owner-scoped read, so ACI does not duplicate it or parse a second Action
decision. A standalone deterministic read also clears its packet and
transitions to answer-only mode after a successful Result; failed reads retain
bounded recovery behavior.

The model/UI receive a bounded L1 projection with retrieved count, compact
records, epistemic labels, current runtime provider/model, contradictions, and
canonical references. Full evidence remains behind the Memory/Action boundary.
The sanitized live Qwen trajectory produced no `tool_start`, no
`WHY_NO_ACTION`, and metrics `aci_completion_transition=ANSWER` with the
CompletionContract satisfied. Owner GUI confirmation remains pending.

## Deployment provenance

The application candidate was built and deployed from source commit
`1ce7ec34b9f70d846e6b41d3f7632a16a2c0bb8b` as
`odysseus:candidate-1ce7ec34b9f7`. Runtime `/api/version` matched that source,
build ID `1ce7ec34b9f70d846e6b41d3f7632a16a2c0bb8b-2026-08-25T22:08:46Z`,
frontend ID `frontend-1ce7ec34b9f70d846e6b41d3f7632a16a2c0bb8b-ed62c6f38298daf5f815194c51b60b485beb10ecbfd02ca287ab6978c80ba0fe`, and
migration head `20260825_002_work_run_completion_v6`. The documentation commit
that records this evidence is intentionally later than the deployed image.

The current implementation candidate is source commit
`d9d07bdc4a5c5c22a319ed724076c8335b500519`, image
`odysseus:candidate-d9d07bdc`, image ID
`sha256:bec0b1db31a30a3a0819668741b20f141a2eeda21dc372ba4cd8fce4ac1afae8`,
build ID `d9d07bdc4a5c5c22a319ed724076c8335b500519-2026-08-25T23:12:44Z`,
and frontend ID
`frontend-d9d07bdc4a5c5c22a319ed724076c8335b500519-ed62c6f38298daf5f815194c51b60b485beb10ecbfd02ca287ab6978c80ba0fe`.

## Full regression gate

The exact deployed source gate is `6304 passed, 3 skipped, 186 warnings` in
123.36 seconds. The touched Memory/ACI focused gate is `75 passed`.

## Build/cache observation

Previously mutable provenance arguments appeared before expensive system and
dependency layers. They now apply after source copy, preserving exact labels
while allowing source-only iterations to reuse the heavy layers. No candidate
was rebuilt for this documentation or Dockerfile-only checkpoint.
