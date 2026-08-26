# Hades ACI V1 progress

## Authoritative current checkpoint — 2026-08-26 (updated)

This section supersedes older historical rows below for present-state claims.

- Source head: branch `hades-aci-v1`, commit `302ed03f`, remote
  `origin=git@github.com:p0rkm4th/Odysseus-revamp.git`; local commits after
  `f9661cda` await an authenticated SSH agent for push.
- Deployed runtime: `odysseus:candidate-7fe090cc8a23`, exact runtime source
  `7fe090cc8a23`, branch
  `hades-aci-v1`, migration
  `20260825_002_work_run_completion_v6`. This is a storage-constrained thin
  source overlay of the previously fully built candidate; `/api/version`
  reports `runtime_source_kind=image_source_marker` and `source_match=true`.
- Source evidence: last full regression is `6492 passed, 3 skipped, 186
  warnings` in 123s on the semantic-family checkpoint; later fallback/runtime
  changes have focused coverage of `210 passed` and security coverage of `198
  passed`. These later source changes are not represented in the deployed
  image.
- Current full regression at source tip: `6511 passed, 3 skipped, 186
  warnings` in 124s. This validates the infrastructure result-normalization,
  durable terminal-continuation, and live-canary telemetry changes; it does
  not change deployed-source or live-E5 claims.
- Current matched Qwen3:8b bridge probe (16-token cap, side-effect-free): raw
  `3.659s` vs Hades `5.462s`, total delta `1.803s`; framework preparation
  `0.218s`, residual non-preparation/model delta `1.585s`, one model call,
  zero tool calls and zero tool-index lookups. Diagnostic only.
- Current agent-loop/provider transport gate: `101 passed`, including ACI
  fallback, structured transport, reasoning-channel handling, and metrics
  compatibility.
- Live E5 evidence: real deployed qwen3:8b core matrix `25/25 answers` and
  `25/25` trajectory passes, zero transport errors, zero internal leaks, and
  zero assertion failures. It covered asset ordinal references, infrastructure
  reads, durable Continue, contamination isolation, fallback, and network
  safety through the authenticated production chat path.
- Current deployed targeted E5 is historical evidence for `c0a281f5`; the
  latest source changes have not received new live E5 because the owner-scoped
  cookie is invalid and the storage preflight is closed.
- Durable continuation fix: terminal/blocked durable Run state now transitions
  directly to answer-only completion instead of re-entering bounded Action
  selection; the continuation/intent/loop focused gate is `177 passed`.
- Latest focused control-plane gate: `186 passed` across infrastructure result
  normalization, terminal lifecycle continuation, semantic reads, bindings,
  Work runs, and planner projections. Host-operator reads now emit canonical
  `SUCCESS_WITH_DATA`/`FAILED` status and explicit observation location;
  lifecycle `succeeded` is terminal even if a stale Run status says `running`.
- Current deployed intentional-continuation E5: asset list → first physical
  asset and Review outstanding work → Continue both passed. The asset follow-up
  selected strong canonical `PHYSICAL-001`; Continue resumed with zero tool
  calls and no fallback. Both had zero index lookups and no leakage.
- Fresh-session core E5 on the deployed Qwen runtime: `22/22` trajectory
  passes, `22/22` answers, zero transport errors, zero internal leaks; the
  corrected canary sampler excludes continuation follow-ups from fresh mode.
- Live canaries now expose sanitized reference disposition telemetry (status,
  semantic concept, selection, count, and context source); asset ordinal cases
  assert `RESOLVED` / `TECHNICAL_ASSET` rather than relying only on prose.
- The live canary is model/endpoint-selectable and accepts an owner Netscape
  cookie export through `--cookie-file`; no credential is printed or
  committed.
- Follow-up live E5 evidence on the same source-matched image: seeded held-out
  slice `12/12` and rotating slice `16/16` trajectory passes, both with zero
  errors and zero internal leaks. Across all three runs: `53/53` trajectory
  passes, `23` canonical tool calls, and `3` tool-index lookups.
- Typed turn-disposition candidate live canary: `6/6` trajectory passes with
  zero transport errors or internal leaks; the thin overlay was built in about
  15 seconds and retained the same dependency layers.
- The seeded live canary sampler initially exposed a harness defect: sampling
  a continuation turn without its prerequisite made a valid asset reference
  appear to fail. The sampler now includes required preceding turns for a
  declared continuation group. The corrected seeded run executed
  `assets_list -> assets_reference` and passed `7/7` trajectories, including
  fallback, contamination, and continuation cases.
- Focused live follow-up on the deployed image passed infrastructure reads
  (`infra_running`, `infra_health`) and durable continuation
  (`continuation_start -> continuation_resume`) with completion on every turn;
  the resume turn used zero tool calls and no fallback.
- Provider-switch/recovery focused gate: `137 passed`, covering owner-scoped
  Run preservation, model-history recording, observed fallback provenance,
  continuation, and provider-failure routing. Live multi-provider switching
  remains unclaimed because only the local Qwen runtime was live-available in
  this environment.
- Developer/sandbox gate: `62 passed`, covering workspace-confined read/edit
  tools, explicit expiring YOLO leases, approval/admin boundaries, patch
  controls, and Docker hardening. V1 currently has a bounded generic developer
  path; a separate semantic `developer.read` registry is intentionally not
  claimed because it would require a canonical binding rather than another
  parallel tool registry.
- Full regression after the typed-disposition runtime change: `6416 passed,
  3 skipped, 186 warnings` in `125.55s`. The deployed implementation source
  is the same `0c07b542` source tested by this gate.
- Live security E5 slice: `1/1` trajectory pass for unauthorized network-scope
  handling, with zero tool calls, zero approvals, zero errors, and no internal
  leakage. Provider/runtime characterization and scheduler-focused gates pass
  `90` tests (four pre-existing async resource warnings).
- Matched synthetic local-latency rerun (same prompt/model/endpoint and
  explicit 128-token budget): raw Qwen `3.596s`; Hades `10.484s`; total delta
  `6.888s`. Hades context construction was `0.208s`, residual framework
  overhead approximately `0s` within timing resolution, and extra provider
  inference `6.684s`. This is diagnostic overhead evidence, not a claim that
  raw and Hades completed identical durable deliverables.
- Live root-cause evidence: asset ordinal references resolved to strong
  canonical identities; `Are my services alive?` used the SERVICE read fast
  path; direct MODEL_FALLBACK answers were emitted instead of remaining in
  the ACI prose buffer. New deployed variants `Is everything healthy?` and
  `Anything broken?` also completed through SERVICE reads; a general RAID
  question used authority-free MODEL_FALLBACK with no tools.
- Canonical read-only Developer ACI is source-complete for the bounded V1 read
  slice: semantic `DEVELOPER` intent resolves to `search_code`,
  `view_file_region`, or `show_repo_map` through one `developer_read`
  Capability → ActionSpec → ToolBinding, adapting existing workspace-confined
  handlers. Focused Developer/projection/security coverage is `175 passed`;
  full regression is `6421 passed, 3 skipped`. It is not deployed or live E5
  verified because production has no selected workspace mount.
- H0 remains frozen at 15 cases: success `0.20`, weighted `0.4333`.
  Historical ACI comparisons remain synthetic benchmark evidence and are not
  owner-live evidence.
- Storage: root `74%` used / `23 GiB` free after deployment and narrow
  retention cleanup. Docker build cache is zero. Current, rollback, live auth
  harness, pinned, and unrelated active images remain; six exact obsolete
  intermediate candidate tags were removed. No owner data, databases,
  volumes, backups, or model blobs were touched. Large builds remain blocked
  by the 30 GiB preflight headroom guard.
- Owner GUI evidence remains E6 pending. No owner data, databases, volumes,
  backups, or model blobs were removed.
- Source fix after the deployed candidate: resolved asset ordinal and pronoun
  references now select the canonical detail `get` ActionSpec instead of being
  consumed by the collection `list` fast path; ambiguous pronouns remain
  unresolved. The focused reference/control-plane gate is `291 passed`.
  Deployment is intentionally pending the storage preflight headroom guard.
- Follow-up contract-consistency gate: the shared canonical read-action helper
  now accepts the resolved entity reference, keeping `get` consistent across
  semantic resolution, projection, and execution; focused gate `271 passed`.
- Remote checkpoint: `origin/hades-aci-v1` is synchronized through source
  checkpoint `8038e227`; this documentation commit records that source/deploy
  distinction without requiring a rebuild.
- Live canary tooling now supports reproducible family/suite selection,
  seeded samples, and explicit fresh versus intentional-continuation session
  modes; selection tests pass without changing runtime authority or execution.
- Reference projection now prefers server-owned ordered/eligible result entities
  for ordinal language and uses a recent `last` reference only as a fallback;
  mixed-domain asset ordinal and durable-reference focused coverage is green
  (`150 passed`).
- The homelab binding now preserves structured executor failure status and
  non-zero exit semantics for broker/runtime failures such as unavailable host
  network context; binding/control-plane coverage is green (`45 passed`).
- The live canary now carries an explicit fixture-only core/held-out split;
  seeded rotating selection is restricted to held-out cases and the split
  tests are green (`7 passed`).
- Canary reports now retain split-level case, answer, and trajectory-pass
  totals alongside family totals; the combined reference/executor slice is
  green (`131 passed`, one existing SQLAlchemy deprecation warning).
- Storage preflight remains correctly blocked for a large build at 18 GiB free
  / 80% used against its 30 GiB / 80% guard. Six exact dangling intermediate
  image IDs with no container references were removed; current, rollback,
  harness, pinned images, volumes, and model data were preserved.
- The live corpus now includes additional asset ordinal, infrastructure health,
  and network-to-general-topic contamination trajectories; these remain
  fixture-only until the next source-matched deployment and live run.
- The current source head is deployed through a source-only overlay; no
  checkout is mounted over `/app` in the production container.
- Default production and GPU compose files no longer mount the host checkout at
  `/app`; `docker-compose.developer.yml` is now the explicit opt-in workspace
  override and requires `HADES_WORKSPACE`. This prevents silent image/checkout
  source mixing on future deployments. The current running service remains on
  the prior explicit developer-style mount until a source-matched image can be
  built safely.
- Compose/provenance/reference/executor/canary focused slice: `225 passed`.
- Continuation/reference and infrastructure executor slice: `234 passed`;
  source now carries ordered session-result references into explicit ordinal
  turns and uses runtime health for unqualified infrastructure status. These
  changes remain pending a source-matched image because storage preflight is
  still closed.
- Live canary now includes a negative asset-ordinal-without-context case, so
  reference resolution is tested both for correct continuation and for
  fail-closed absence of a canonical result. Canary/reference gate: `129
  passed`.
- Full regression after the reference, infrastructure, compose, and canary
  changes: `6414 passed, 4 skipped, 186 warnings` in 5:08. No deployment build
  was attempted because storage preflight remains below the 30 GiB headroom
  guard.
- A second exact audit removed six obsolete untagged Odysseus candidates
  labeled `a20ade61`, `7f0a8576`, `52cdfd5e`, `121cb6d7`, `8419fea9`, and
  `936fe437`; no active container referenced them. Security/control-plane
  regression coverage remains green (`181 passed`, 39 dependency warnings).
- A supported dangling-image prune subsequently reclaimed `9.067 GiB`; root
  is now approximately 74% used / 23 GiB free. Remaining Docker images are
  current, rollback, active auth harness, protected milestones, or unrelated
  active services. The 30 GiB build-headroom guard remains closed.
- `scripts/storage_preflight.sh` now reports running images, candidate tags,
  rollback tags, and positively identified unreferenced candidates, making
  retention decisions auditable without performing cleanup.
- Latest security/control-plane slice: `305 passed, 1 warning`, covering
  approvals, exact action scope, verified execution, external-context gating,
  control-plane safety, security regressions, and outbound URL safety.
- Storage maintenance removed only the exact unreferenced
  `nvidia/cuda:12.4.1-base-ubuntu22.04` image after verifying its layers
  were absent from all protected images. Docker usage fell from 21.89 GB to
  21.54 GB; preflight remains correctly blocked at 19 GiB free.
- Host tmpfs hygiene removed `7,952` closed, transient `/tmp/tmp*.db`
  SQLite test fixtures (`14.53` GiB). Persistent repository/runtime stores
  were not touched; `/tmp` fell from 15 GiB used to 282 MiB. Root storage is
  a separate Btrfs filesystem and remains at 19 GiB free.

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
| RUNTIME_PROFILE_CACHE_REUSE | `fc87ea6d` | fresh endpoint/runtime/model profiles are reused before metadata calls; expiry and identity mismatch tested; 9 focused | not rebuilt | FOCUSED_TESTED |
| RUNTIME_PROFILE_DIAGNOSTICS | `85cb0ee4` | owner-scoped `/api/hades/runtime-profile`; sanitized runtime evidence projection; focused-tested | superseded by final candidate | FOCUSED_TESTED |
| TOKEN_ACCOUNTING | `ce626774` | nested native tool-schema serialization included in shared estimator; 52 focused tests | `odysseus:candidate-ce626774f5ac` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| FINAL_RUNTIME_CHECKPOINT | `ce626774` | `6298 passed, 3 skipped`; health/version, broker, Ollama verified; unauthenticated profile route returns 401 | `odysseus:candidate-ce626774f5ac` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| OLLAMA_CHARACTERIZATION | `4c43dfae` | metadata-only `/api/show` plus fallback `/api/tags`; qwen3:8b digest/context/capabilities recorded locally | `odysseus:candidate-4c43dfae28d8` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| PROTOCOL_PROBES | `49de2dc0` | synthetic strict Decision JSON PASS and verified native-tool PASS; no side effects | not rebuilt | FOCUSED_TESTED |
| MEMORY_COMPLETION_FIX | `d9d07bdc` | 75 focused; 6304 full; sanitized live Qwen trajectory reaches ANSWER without tool re-entry | `odysseus:candidate-d9d07bdc` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| HARNESS_OVERHEAD | `ab11579c` | matched synthetic raw-vs-Hades qwen3:8b timing; 70 focused | not rebuilt | FOCUSED_TESTED |
| MODEL_BURDEN_INSTRUMENTATION | `885ec24f` | sanitized per-turn framework/model labels; 76 focused; 6305 full | not rebuilt | FULL_REGRESSION |
| DEPLOYED_BURDEN_CHECKPOINT | `29cafccd` | source-matched health/provenance, broker/Ollama checks, six-case Qwen canary all scored 1.0 | `odysseus:candidate-29cafccde26a` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| BENCHMARK_BURDEN_RECORDS | `c425f020` | Jarvis collector retains sanitized model-burden totals/labels; 4 focused | not rebuilt | FOCUSED_TESTED |
| NATIVE_DECISION_TRANSPORT | `16748fe8` | native Ollama structured ACI transport disables thinking; 45 focused; 6307 full | `odysseus:candidate-16748fe8cccd` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| PACKET_CHOICE_SCHEMA | `2405ca79` | dynamic choice/context enums added; 6307 full; deployed probe confirms downstream rejection remains authoritative | `odysseus:candidate-2405ca79d117` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| INVENTORY_READ_FAST_PATH | `0147c77a` | inventory-state semantic contract, fixture correction, 6308 full; deployed case uses one deterministic read plus answer synthesis | `odysseus:candidate-0147c77a0803` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| CONTRACT_ACTION_RETENTION | `67106c5e` | resolved planning Action survives operation-class filter; 6308 full; deployed trace records `contract_action_retained` | `odysseus:candidate-67106c5e8e8a` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| DETERMINISTIC_CONTRACT_FALLBACK | `101910d2` | bounded one-use fallback for safe resolved planning Actions; 6308 full; deployed network probe one Action/no WHY_NO_ACTION | `odysseus:candidate-101910d2b37c` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| FINAL_QWEN_CANARY | `101910d2` | deployed six-case Qwen canary `6/6`, weighted `1.0`, zero retries/provider failures; network fallback one Action | `odysseus:candidate-101910d2b37c` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| SERVICE_CONTRACT_CONVERGENCE | `a61f06c5` | restart language resolves to canonical read-only `plan_service_restart` preflight; 152 focused; 6310 full | `odysseus:candidate-a61f06c5a2d9` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| SERVICE_TARGET_CLARIFICATION | `0cefba69` | unqualified restart is clarification-bound; qualified targets retain safe preflight; 154 focused; 6312 full; deployed Qwen synthetic canary 2/2, zero model/tool calls | `odysseus:candidate-0cefba69f3ac` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| DETERMINISTIC_SAFETY_BOUNDARIES | `0dc6ce15` | IP-only identity, public scope, changed approval, and replay boundaries are framework refusals; 157 focused; 6315 full; deployed four-case canary 4/4 | `odysseus:candidate-0dc6ce153ff5` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| CONTINUITY_HARNESS_RECOVERY | `05dd1e0d` | continuity cases now inject a loopback primary failure and verify configured-provider fallback; both recovered with one retry; 6316 full | no rebuild (benchmark-only) | FULL_REGRESSION |
| STRICT_DECISION_RUNTIME_PROBE | `c0ea2955` | safe qwen3:8b strict-schema probe PASS in 741ms; sanitized digest only; 31 focused | not rebuilt | FOCUSED_TESTED |
| PARAPHRASE_READ_CONVERGENCE | `ff14c3a0` | 21 metamorphic Memory/Work/Assets/Network utterances converge on canonical harmless reads; exact post-Result reads transition to answer; 67 checkpoint focused; 6366 full | not rebuilt | FULL_REGRESSION |
| MODEL_FALLBACK | `29427c1a` | one-repair invalid Decision falls to authority-free general answer; 70 focused; 6369 full, 3 skipped | superseded by `936fe437` | FULL_REGRESSION |
| TOOL_INDEX_BYPASS | `29427c1a` | unique canonical reads bypass generic tool ranking; sanitized live traces recorded | superseded by `936fe437` | PASSIVE_LIVE_VERIFIED |
| DIRECT_READ_COMPLETION_FIX | `936fe437` | direct fast-path reads remain terminal for Action selection even when low-signal normalization clears `read_explicit`; 109 focused | `odysseus:candidate-936fe43744a5` | DEPLOYED/PASSIVE_LIVE_VERIFIED |
| STORAGE_PREFLIGHT | `99b8787f` | conservative build guard reports disk/Docker/candidate/rollback state and blocks below configured headroom; continuity slice 63 focused | not rebuilt | FOCUSED_TESTED |
| ANSWER_SESSION_ISOLATION | `8419fea9` | successful direct reads rebuild answer route from ResultProjection; 6370 full, 3 skipped; 165 routing/continuity focused | `odysseus:candidate-8419fea9d94c` | FULL_REGRESSION |
| ANSWER_CHANNEL_PROTOCOL | `d77e0622` | answer/fallback calls omit Decision response schema; 56 focused; clean Work trace 111-token answer route | `odysseus:candidate-d77e06229504` | DEPLOYED/PASSIVE_LIVE_VERIFIED |

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

## Harness overhead evidence

The local-only benchmark compares the same harmless synthetic prompt through
Ollama directly and through Hades ACI. It executes no Actions, performs no
network scan, and writes only a local report. Two matched samples measured raw
completion at `3.48–3.66s`, Hades completion at `14.48–14.54s`, and an
end-to-end delta of `10.82–11.05s`. Hades context construction accounted for
`1.38–1.48s`; both samples made zero tool calls. This is measured harness cost,
not a claim that all operational workloads have the same overhead.

The same benchmark now records responsibility accounting. A synthetic ACI turn
measured two framework steps (`intent_resolution`, `action_hard_filter`) and
one model-required step (`bounded_action_decision`); the counters are
observational and cannot grant authority.

## Deployment provenance

The application candidate was built and deployed from source commit
`1ce7ec34b9f70d846e6b41d3f7632a16a2c0bb8b` as
`odysseus:candidate-1ce7ec34b9f7`. Runtime `/api/version` matched that source,
build ID `1ce7ec34b9f70d846e6b41d3f7632a16a2c0bb8b-2026-08-25T22:08:46Z`,
frontend ID `frontend-1ce7ec34b9f70d846e6b41d3f7632a16a2c0bb8b-ed62c6f38298daf5f815194c51b60b485beb10ecbfd02ca287ab6978c80ba0fe`, and
migration head `20260825_002_work_run_completion_v6`. The documentation commit
that records this evidence is intentionally later than the deployed image.

The current implementation candidate is source commit
`a61f06c5a2d935ab2116252c01c3ac180e36551d`, image
`odysseus:candidate-a61f06c5a2d9`, image ID
`sha256:3aaad07faca7cbaf84f33972ff854770bc68d600fc2079d88ffc79de55071a6a`,
build ID `a61f06c5a2d935ab2116252c01c3ac180e36551d-2026-08-26T00:23:54Z`,
and frontend ID
`frontend-a61f06c5a2d935ab2116252c01c3ac180e36551d-ed62c6f38298daf5f815194c51b60b485beb10ecbfd02ca287ab6978c80ba0fe`.

## Full regression gate

The exact source gate before deployment is `6310 passed, 3 skipped, 186
warnings` in 123.58 seconds. The touched Memory/ACI focused gate is `90
passed`. The six-case deployed Qwen canary scored `6/6` with no runtime
failures; its detailed records contain only synthetic fixtures. The replacement
deployed three-case native-transport probe had zero provider failures and no
empty bounded-decision payloads. It still exposed an invalid model choice on
the broad synthetic inventory prompt and one `MODEL_PROSE_ONLY` network
diagnostic; those remain action-exposure/routing evidence rather than
transport failures.

The deployed network probe now shows the framework retention label, but Qwen
still returned prose for that operational branch. The Action was not executed
from prose; the downstream control plane remained fail-closed.

The current deployed fallback probe supersedes that intermediate observation:
the same prose-only branch produced one framework-owned safe plan Action, no
repetition, and no `WHY_NO_ACTION` event. Consequential execution and scope
authorization remain downstream requirements.

The current six-case deployed canary scored `6/6` with weighted score `1.0`:
canonical grounding, network routing, shell-fallback safety, action-narration
grounding, referent selection, and duplicate-read-loop control. It made zero
retries and had no provider failures. Two broad service-operation cases still
emit `WHY_NO_ACTION=MODEL_PROSE_ONLY` and remain explicit follow-up evidence;
they produced no unsafe tool calls.

## Service operation contract convergence

Owner-style prompts `Restart the registered service` and `Restart the service`
were classified as `EXECUTE` but previously had no `SERVICE` contract, causing
the ACI path to fall through to model prose/`WHY_NO_ACTION`. The canonical
contract now maps this semantic operation to the read-only
`plan_service_restart` preflight Action. The exact restart Action remains
separate, exact-approval protected, and is not selected by this resolution
change. Focused coverage: `152 passed`; full regression after the change:
`6310 passed, 3 skipped, 186 warnings` in 122.43 seconds. A host-side live
Qwen rerun was unavailable because the deployed Ollama bridge is not exposed
in the host namespace; no provider result is claimed from that attempt.

## Build/cache observation

Previously mutable provenance arguments appeared before expensive system and
dependency layers. They now apply after source copy, preserving exact labels
while allowing source-only iterations to reuse the heavy layers. No candidate
was rebuilt for this documentation or Dockerfile-only checkpoint.

The deployed service-target clarification canary (`generic-shell-fallback` and
`action-narration`) scored `2/2` against Qwen3:8b with zero provider failures,
zero model calls, zero tool calls, and the framework response
`Which service or systemd unit should I restart?`.

## Final deployed Qwen checkpoint

The pre-correction 15-case synthetic Qwen3:8b ACI run scored `0.8667` case
success and `0.9333` weighted score, versus H0 `0.20` success and `0.4333`
weighted. The two misses were benchmark-driver recovery flags, not runtime
failures. After correcting the harness, the authoritative rerun scored `1.0`
case success and `1.0` weighted across all 15 cases and categories, with no
runtime failures. This remains synthetic evidence, not owner-live GUI
evidence.

After benchmark-driver correction `05dd1e0d`, both continuity cases exercise a
deliberate loopback provider failure followed by the configured Ollama endpoint
and report `recovered=true`, one fallback retry, and no provider failure. This
changes evaluation validity only; the deployed application candidate remains
`0dc6ce153ff5d7e1bb359fe8fd7a94e89de95dbf`.

The authoritative post-fix artifact is `/tmp/hades-final-15-harness-fixed.jsonl`.

## Sol root-cause checkpoint

Owner dogfood showed that `Tell me about me` diverged before model reasoning:
the chat-prefetch phrase recognizer did not classify it as Memory, while the
canonical intent compiler classified both that phrase and the previously
successful `What do you know about me?` as `UNKNOWN`. The latter succeeded only
through a compatibility rescue. Commit `ff14c3a0` replaces that split behavior
with a shared compositional deterministic-read resolver used by intent
contracts and Memory grounding.

The same commit repairs two control-flow defects. Protected ACI packet messages
now survive provider-route rebuilding, and an exact successful resolved
canonical read is classified as `COMPLETE_AFTER_ANSWER` independently of which
execution branch produced the Result. Answer synthesis receives a minimal
semantic Objective/Result packet with no provider schemas or ToolBinding names.

The separate frozen metamorphic corpus contains 9 Memory, 4 Work, 4 Assets, and
4 current-Network paraphrases. All 21 source/focused cases resolve to their
canonical read contract with no approval; the unambiguous Memory cases require
zero bounded Action-selection calls and no post-Result Action decision. This is
E2/E3 evidence, not a replacement for owner dogfood.

Current latency instrumentation attributes one local sample as follows: raw
Qwen completion `0.238s`; Hades completion `8.723s`; context preparation
`1.432s` (including `1.288s` tool selection/retrieval fallback); provider/model
wait `4.524s`; remaining structured generation/validation/buffering about
`2.77s`. Hades sent 1406 prompt tokens versus 31 raw and made one model call,
so this sample did not contain an unnecessary second inference. The synthetic
raw and Hades requests are not equivalent deliverables and are retained as
diagnostic overhead evidence, not a release-quality harness-tax comparison.

The current implementation head is `ff14c3a0`; the deployed implementation
remains `0dc6ce153ff5d7e1bb359fe8fd7a94e89de95dbf`. No image was rebuilt for this
source/root-cause checkpoint.

## Automated live E5 and V1 fast-track checkpoint

## Control-plane failure-class checkpoint — 2026-08-26

## Direct fallback subtraction checkpoint — 2026-08-26

## Semantic precision checkpoint — 2026-08-26

- `44c5537d` centralizes a negative near-miss corpus: 21 positive
  deterministic-read variants and 14 adversarial Memory/Work/Asset/Network
  variants. Static semantic evaluation is `21/21` positive contracts
  available and `0/14` negatives incorrectly available as READ contracts.
  Focused near-miss/domain gate: `166 passed`.
- Retention metadata was corrected without changing image content: the
  previous known-good b9 image now has the explicit
  `odysseus:rollback-b9d500f2e567-prev` tag with the same digest. Preflight
  now reports two candidate images and one rollback image; the build remains
  blocked at 19 GiB free.

- `fbe5cd66` adds negative near-miss guards to the shared semantic resolver.
  Definitions, explanations, advice, mutations, and imperative work requests
  no longer collapse into owner-state reads merely because they contain
  Memory/Network/Work nouns. Valid owner/current-state reads remain on their
  existing contracts. Focused gate: `159 passed`; full regression:
  `6390 passed, 3 skipped, 186 warnings`.
- The candidate is pushed but not deployed. Storage preflight is correctly
  fail-closed: root is 78% used with 19 GiB reported free versus the
  configured 30 GiB large-build minimum. Protected current/rollback/harness/
  pinned images remain; no further safe Odysseus candidate cleanup was
  identified without removing protected or unrelated images.

- `a51e9297` makes the sanitized live canary assert trajectory classes rather
  than only transport success: read families require completion, general
  fallback requires fallback/no tools, and clarification/security families
  require safe answer/no execution without pretending they are read
  CompletionContracts. The focused harness/control-plane gate is
  `92 passed`. No authenticated live cookie was present in this execution
  environment for a new canary run; prior b471 live evidence remains the
  deployed runtime evidence.
- `48ff97db` exposes the existing semantic route as
  `aci_turn_disposition` telemetry without changing authority or execution:
  `EXECUTE_DIRECT`, `ANSWER`, `DECIDE`, `CLARIFY`, or
  `MODEL_FALLBACK`. Focused continuation/intent/corpus/projection suites
  passed `123` tests; the runtime metric is source-present and not yet
  deployed.

- `b471e104` removes the empty bounded-decision round for benign unknown
  read-style questions. When no specialized contract exists and the semantic
  frame is `UNKNOWN`/`READ`, Hades now enters authority-free
  `MODEL_FALLBACK` directly instead of constructing an empty Action packet,
  invoking Decision repair, and falling back afterward.
- Focused ACI/fallback gate: `67 passed`; the earlier full gate at
  `b9d500f2` was `6384 passed, 3 skipped, 186 warnings`.
- Real deployed qwen3:8b evidence for “Explain why RAID is not a backup.”:
  one model call, zero tool calls, zero tool-index lookups, `312` input tokens,
  no internal error/tool leakage. The prior path made three model calls and
  consumed `8423` input tokens. General fallback has no durable read
  CompletionContract; answer presence and authority-free completion are the
  acceptance criteria for this category.
- Current deployed candidate is `odysseus:candidate-b471e10455ba`, source
  `b471e10455ba846373ca89449fc021cea21ace2e`, build
  `b471e104-20260826T080000Z`, digest
  `sha256:5dfda0f9517c8ccdac1a0f66e8bc27d695289fb6cc5204d2829749bd41d7ecd0`.
- Retention cleanup removed nine exact untagged build leftovers and the
  redundant non-running `rollback-d77e0622-prev` tag. Current, one prior
  rollback (`candidate-b9d500f2e567`), the live auth harness, and the pinned
  bundle remain. No owner data, databases, volumes, or model blobs were
  touched; storage remains caution-level and is not a build authorization.

- `a0ccc895` fixed the three traced failure classes: completed canonical asset
  results now retain ordered strong IDs; qualified ordinal references inherit
  only the current session's server-owned result context and preserve the
  resolved ID; broad infrastructure status reads no longer send a unit-less
  `service_status` request into the strict named-unit validator.
- `7f0a8576` generalized empty continuation handling. `Review outstanding
  work.` resolves to the existing Work overview read; `Continue.` with no
  active durable Run is answer-only/authority-free rather than bounded Action
  selection. No Action is invented or executed.
- Focused gates: `182 passed`, then `211 passed`, then `152 passed` for the
  touched control-plane suites. Full regression at `a0ccc895`: `6382 passed,
  3 skipped`; final full regression at `7f0a8576`: `6384 passed, 3 skipped`.
- Final deployed candidate is `odysseus:candidate-7f0a857687b4`, source
  `7f0a857687b43777194f3210ce0045011e449a27`, build
  `7f0a8576-20260826T060000Z`, image digest
  `sha256:c0b3c9f41b854a2c3d9f76fe51698849fb6b7639c7dda08a2502e9a385e53a98`.
  Health, migration head, broker, Ollama bridge, and Chroma were verified.
- Automated real qwen3:8b E5 targeted matrix: asset list → “first physical
  one” completed with one Action and zero index lookup; both infrastructure
  reads completed with one Action; Work review → Continue produced two
  answer-bearing, complete turns with no second Action or internal leakage.
  This is E5 automated, not E6 owner GUI evidence.
- Storage after bounded retention: 76% root usage / 22 GiB free, 14 images,
  zero build cache. Retained current candidate, one rollback candidate, the
  active authenticated harness image, and the pinned bundle; obsolete
  non-running Odysseus candidate tags were removed.
- `dd7c3117` expands the permanent sanitized live harness with qualified
  ordinal pairs, infrastructure positive/near-miss families, empty
  continuation, and cross-domain contamination cases. Harness-only changes do
  not require a production image rebuild. The next broad live rotation should
  use fresh sessions plus the explicit continuation groups.

- `121cb6d7` broadened compositional Work/infrastructure-read routing and
  added negative near-miss coverage so general VM/container explanations do
  not become host inspection. Focused routing: `149 passed`; full regression:
  `6379 passed, 3 skipped, 186 warnings`.
- `scripts/hades_live_dogfood.py` is the reusable sanitized production-path
  runner. It uses owner-scoped temporary sessions, fresh sessions for unrelated
  cases, and explicit continuation sessions for references/Continue.
- Candidate `odysseus:candidate-121cb6d7b74b` is source-matched to
  `121cb6d7b74b3160fe4e6fe05edd981036966926`; build
  `121cb6d7-20260826T033209Z`; image digest
  `sha256:bdc4aab4cfef9f8e4fd6a1cad9073dcbf2ce96af1b9025b7a11944343891dbb9`.
- Real authenticated HTTP chat with real qwen3:8b produced answers for all
  `23/23` live cases, with zero transport errors and zero internal tool/error
  leakage. Memory was `5/5` direct/complete; Work was `3/3` direct/complete;
  current Network was `3/3` direct/complete. Remaining live failures are the
  asset ordinal continuation, infrastructure executor failures, and durable
  Continue completion. This is E5 automated evidence, not E6 owner GUI
  evidence.

- `06e29f18` is the current pushed source checkpoint. It repairs the resolved
  asset-detail contract so an ordered canonical result plus an ordinal
  reference projects to `manage_assets/get` with the strong asset identity;
  focused reference/projection coverage is `160 passed`, the broader ACI/domain
  gate is `81 passed`, and the last full regression is `6478 passed, 3 skipped`.
  The deployed candidate remains `c0a281f5` because the storage preflight is
  closed at 23 GiB free; no safe obsolete candidate was identified.

- The follow-on semantic-family slice adds bounded typo normalization and
  colloquial owner-self/infrastructure status recognition. `tell me abotu me`,
  `give me my lore`, `whats running`, `hows Hades doing`, and `anything dead`
  now project to existing safe canonical reads without broadening deletion,
  advice, recommendation, or active-scan near-misses. Focused semantic gate:
  `142 passed`. This source slice is not yet deployed or live-qwen verified.

- The subsequent breadth audit corrected three additional semantic-family
  boundaries: physical-host inventory is no longer shadowed by network-host
  language, current network-context questions survive the definition guard,
  and casual stack-health phrases (`are we good`, `how is the stack`) use the
  existing safe service-status read. Capability questions are kept out of the
  Work fallback when no SelfState contract applies. The affected control-plane
  gate is `214 passed`; source is pushed as `0c4d9ff3` plus this follow-on
  slice, while deployment remains blocked by storage preflight.

- Full regression after the semantic-family corrections: `6492 passed, 3
  skipped, 186 warnings` in 123 seconds. This confirms the shared resolver
  changes do not regress the broader repository suite; deployment and live E5
  for this source remain pending the storage preflight and a valid owner-scoped
  session cookie.

- A follow-up Memory-family correction recognizes compositional stored-memory
  wording such as `what do you actually have saved` while excluding file,
  document, and secret targets. The affected gate is `215 passed`; this
  source-only checkpoint remains awaiting deployment and automated live E5.

- The continuation-language family now includes natural `go on` phrasing in
  both the IntentFrame compiler and the agent-loop recognizer. This changes
  classification only; durable Objective/Run state remains authoritative for
  resolution and execution. Continuation/control-plane gate: `202 passed`.
  The source checkpoint is not yet deployed because storage preflight remains
  closed.

- The next semantic-family slice routes default-route, interface, subnet, and
  current-context wording through the existing host-network-context read, and
  recognizes recorded/known-for-me asset inventory language. Focused gate:
  `161 passed`. No new authority or discovery path was introduced; deployment
  remains pending the storage preflight.

- Work-status language now recognizes `where did we leave off` and its natural
  variants as the existing safe Work overview read. Explicit `Continue` remains
  durable Run continuation rather than a lexical Work read. Focused gate:
  `203 passed`; no deployment was attempted while storage preflight was closed.

- Explicit host-inspection language now resolves to the existing safe
  `HOMELAB_HOST/inspect_host` contract instead of being shadowed by generic
  Network routing. The focused host/ACI gate is `166 passed`; no new executor,
  authority, or discovery capability was introduced.

- General MODEL_FALLBACK now accepts an optional compact derived SelfState
  projection containing only active model, provider, and branch. It excludes
  endpoint/credential material and retains `Execution authority: NONE`; the
  fallback/control-plane gate is `210 passed`. This is source-tested but not
  yet deployed or live-qwen verified.

- Security/authority regression gate after the fallback SelfState changes:
  `198 passed, 1 warning`. Coverage includes fallback authority isolation,
  prompt injection, owner isolation, exact approvals, network scope,
  Workspace-YOLO boundaries, and chat/tool policy. No security invariant was
  relaxed.

- Runtime characterization, context-budget, fallback attribution, and harness
  overhead focused gate: `110 passed, 1 warning`. This covers the existing
  provider/runtime profile and token/context instrumentation without claiming
  equivalent live latency until the corrected source is deployed.

- Core agent-loop and provider-transport regression gate: `107 passed, 1
  warning`. This covers streaming, sanitization, Ollama thinking/structured
  transport, fallback attribution, and the main loop after the recent
  continuation/runtime-context changes.

- Current-source side-effect-free Qwen bridge probe (`qwen3:8b`, 16-token cap,
  equivalent 3-token accounting): raw `2.760s` versus Hades `5.436s`, total
  delta `2.676s`. Hades used one model call, zero tools, and zero tool-index
  lookups. Attribution was `2.420s` extra provider/model time, `0.255s`
  context preparation, and `0.001s` remaining framework span. This is
  diagnostic latency evidence, not deployed quality or owner-live E5 evidence.

- Developer ACI, workspace confinement, ActionBinding, verified execution, and
  action-intent gate: `94 passed, 1 warning`. This confirms the read/patch
  authority boundary remains covered while the newer semantic/fallback source
  is awaiting deployment.
