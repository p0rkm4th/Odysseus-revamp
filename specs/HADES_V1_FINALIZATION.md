# Hades V1 Finalization Status

This is an exact-head reconciliation against the current local checkout. It
is an engineering status record, not a readiness declaration.

## Source and runtime truth

| Field | Current evidence |
|---|---|
| Branch | `hades-aci-v1` |
| Local HEAD | `1dcd084e4f905875ae919210da54dcbf6663c019` |
| Remote HEAD | `1dcd084e4f905875ae919210da54dcbf6663c019` |
| Worktree | clean; tracking `origin/hades-aci-v1` |
| Running container | `odysseus-odysseus-1` |
| Running image reference | `odysseus-odysseus` (Compose-managed name; candidate tag retained locally) |
| Running image digest | `sha256:7a95786c681038159df7c51fca47eb4dec775a61964819e6c4028a10e4c4719e` |
| Embedded source label | `1dcd084e4f905875ae919210da54dcbf6663c019` |
| Runtime status | running, restart count 0 |
| Health | `GET /api/health` returns `healthy` |
| Last known-good source | `1dcd084e4f905875ae919210da54dcbf6663c019` |
| Rollback images | preserved locally, including `odysseus:rollback-b471e104-prev` |

The running image's source label matches both local and remote HEAD. The
runtime image reference is not itself an immutable candidate tag; a future
release checkpoint should deploy and verify an explicit SHA-tagged image.

## Sol review reconciliation

The independent review examined `c91a65bd2bcbd63598741b93b701452f6b736254`.
The current checkout is newer by six commits. Findings below are classified
against the current source rather than copied forward as assumptions.

| Review area | Prior grade | Current classification | Evidence / remaining work |
|---|---:|---|---|
| Control-plane architecture | A- | PARTIALLY FIXED | Production callers use `stream_aci_turn`; compatibility tests and the legacy implementation remain. Semantic ownership and physical strangling still need completion. |
| Security / authority | A | FIXED / MAINTAIN | Focused control-plane and security coverage remains green in the latest recorded runs. Continue treating any regression as release-blocking. |
| Grounding | A- | PARTIALLY FIXED | Asset, household, aggregation, and inventory mutation projections now use structured results/readback. A unified final `AnswerSource` and complete canonical-read audit remain. |
| Local-model architecture | B+ | AUDIT METRIC STALE | Profiles and ACI seams exist, but current-head live Qwen evidence is unavailable; no new portability claim is made. |
| Performance | C+ | STILL PRESENT | Deterministic paths were improved, but current-head latency phase timings and complete model-call/burden evidence are not yet recorded. |
| Maintainability | C+ | STILL PRESENT | `src/agent_loop.py` remains a large compatibility/implementation surface; no claim of a thin facade. |
| CI / release | C | PARTIALLY FIXED | CI workflows exist, but current branch push-gating/required checks and an exact immutable candidate deployment still need verification. |
| Provider portability | B- | STILL PRESENT | Provider/model contracts exist; a current-head conformance matrix and live second-provider evidence are absent. |
| Owner UX | B- | PARTIALLY FIXED | Canonical Asset/Household grounding and mutation verification improved owner paths. Repeated owner E6, exact stream completion, and unified failure language remain open. |
| Current-head readiness | B- | AUDIT METRIC STALE | The reviewed SHA is no longer current. Current HEAD is source-matched to the running container and healthy, but full current-head release evidence is incomplete. |

## Current measurable baseline

- Latest focused checkpoint: `252 passed, 1 skipped` across ACI lifecycle,
  first-class regressions, intent contracts, household projection, and tool
  binding projection tests.
- Latest recorded full regression on the writable test setup: `6720 passed,
  5 skipped, 6 failed`; all six failures were storage-preflight environment
  assumptions for `/home/.docker-data`, not a claimed clean release result.
- Current-head full regression and current-head Qwen evidence are still
  required before any V1 readiness claim.
- Local Ollama was previously unavailable at `127.0.0.1:11434`; live Qwen
  verification is therefore **UNVERIFIED**, not passed by fixture evidence.
- Chroma and SearXNG were previously healthy; that does not substitute for a
  complete current-head acceptance run.

## Priority finish gates

1. Run current-head full regression with storage fixtures isolated and report
   the remaining failures honestly.
2. Prove one final answer owner and exactly-once stream/finalization behavior.
3. Audit and remove remaining production semantic authority from
   `agent_loop.py`; retain only tested compatibility delegation where needed.
4. Record latency/model-burden and reference-resolution evidence at this SHA.
5. Verify CI push gating, build one explicit SHA-tagged candidate, and verify
   running image/source/digest together.
6. Run owner-failure regressions and live Qwen only when the provider is
   actually available.

## Verification labels

- **LIVE VERIFIED:** source/runtime health and embedded source-label match for
  the running container.
- **INTEGRATION VERIFIED:** focused ACI and projection tests listed above.
- **FIXTURE VERIFIED:** prior broad regression and dogfood evidence recorded in
  the reuse ledger; not proof of live Qwen behavior.
- **UNCONFIGURED / UNVERIFIED:** live Ollama/Qwen and any external provider or
  credential-dependent path not exercised in this environment.

This document must be updated whenever the source, deployment, or release
evidence changes.

## Current exact-head reconciliation (`8e273784`)

The historical entries above describe earlier checkpoints. Current source and
runtime truth is:

- Branch: `hades-aci-v1`
- Local HEAD = remote HEAD: `8e2737847812a3f21aff8d798ede7beff7bd2b9e`
- Worktree: clean
- Candidate image: `odysseus:candidate-8e2737847812`
- Image ID: `sha256:0ea35c34923346bc3268c740442318283227fd4a667d5be9a01d3d26c2a0714d`
- Image revision label and `/app/.odysseus-source-commit`: exact current SHA
- Running container: `odysseus-odysseus-1`, running, restart count `0`
- Health: `GET /api/health` returned `healthy`
- Focused cutover/resource/ACI/dogfood validation: `136 passed, 1 warning`
- Production direct legacy stream callers and imports: `0`
- Live Ollama/Qwen: unavailable; live owner-model acceptance remains **UNVERIFIED**.

## Model-decision projection checkpoint (`76c64ce0e593f2d4a626fcf9384e5e6542629487`)

The existing ACI seam now owns model-decision parsing, bounded invalid-decision
recovery, and action/answer selection projection via `project_model_decision`.
`agent_loop.py` retains only the transport-side retry/fallback and execution
handoff behavior. Focused ACI/cutover/resource-contract tests passed `264
passed, 1 warning`. The exact source was pushed and deployed as
`odysseus:candidate-76c64ce0e593`; the running image digest is
`sha256:5d5feaa95fd1405b566b4dd39711c7ae87b1227916434df113aad2a806e80e64`,
the embedded source label matches the commit, restart count is `0`, and
`/api/health` is healthy. Live Ollama/Qwen remains unavailable and therefore
unverified.

## Owner-state closure checkpoint (working tree after `299ef9ee`)

The exact reconciled baseline before this closure slice was:

- Local/remote source: `299ef9ee72b666c1a796d79436576dead1196166`
- Running container: `odysseus-odysseus-1`
- Running image ID: `sha256:77bd2346f2278e564757142ac68a14250f60aa62d74ac38d463d0895920fa226`
- Embedded source label: `299ef9ee72b666c1a796d79436576dead1196166`
- Container state: running; `/api/health` returned `healthy` after startup
- Worktree: clean at reconciliation; closure checkpoint is deployed below

The closure slice adds active Asset property/reference projections (`specs`,
GPU, RAM, and “other one”), suppresses intermediate deterministic-read
replacement events when a canonical Result exists, and ignores duplicate
provider terminal markers within one HTTP stream. The affected suites passed
`401 passed, 1 skipped` before the final documentation/commit step. This is
integration/fixture evidence; live Qwen owner verification remains
**UNVERIFIED**.

The prior isolated full regression remains honestly recorded as `6729 passed,
5 skipped, 7 failed`: the semantic near-miss failure was fixed in the closure
slice; six storage-preflight failures were environment failures caused by the
minimal test container lacking `/home/.docker-data` and are not converted to
passes. A current-head full regression and explicit redeployment are still
required.

## Deployed closure checkpoint

- Source SHA: `c77563e82c543d0f8901164ee261638fb1afa20e`
- Remote HEAD: `c77563e82c543d0f8901164ee261638fb1afa20e`
- Running image ID: `sha256:b98de538b4dcb8800645395445c4800d8fc1f2768caa66690ba634f1f9bba01e`
- Running source label and `/app/.odysseus-source-commit`: `c77563e82c543d0f8901164ee261638fb1afa20e`
- Runtime: `odysseus-odysseus-1`, running, restart count `0`
- Health: `GET /api/health` returned `{"status":"healthy"}`
- Rollback: `odysseus:rollback-299ef9ee72b6-prev`, source `299ef9ee72b666c1a796d79436576dead1196166`
- Host Ollama: unreachable at `127.0.0.1:11434`; live Qwen evidence is **UNVERIFIED**.

The documentation-only follow-up that records this deployment must itself be
included in the next source/image match if the tree changes again.

## Final-answer owner migration

The next source checkpoint moves final answer projection into the existing ACI
module. It selects a canonical structured Result before transport-level
grounding and emits at most one replacement event; the compatibility loop no
longer owns separate grounding and tool-summary replacement decisions. The
same change retains provider fallback behavior and existing persistence.
Focused ACI/cutover/resource-contract tests passed `263 passed, 1 warning`.

## Semantic dogfood expansion (working tree)

The existing evaluator now generates explicit conceptual/operational minimal
pairs from `ScenarioFrame` oracles and records state-mutation boundaries in
generated chaos journeys. The existing CLI tiers expose the pair count without
introducing a second evaluator. A reproducible core-tier generation smoke with
seed `20260827` expanded `1,793` cases, including `100` minimal-pair cases;
the dogfood test suite passed `29 passed, 1 warning` after the mutation
coverage assertion. Push-triggered CI, CodeQL, container scans, secret scan,
and workflow security now include `hades-aci-v1`.

The existing dogfood runner also supports seeded hidden holdouts through
`--hidden-holdout-count`. Holdout prompts are generated from semantic cases
with deterministic transform chains and are not serialized into coverage
reports; only digests and semantic metadata remain. A seed `20260827` smoke
produced `500/500` unique held-out cases.

The dogfood transport projection now records response-replacement count,
duplicate finalization, stale deltas after replacement, and a delivery identity
derived from event IDs. The live runner uses these lifecycle signals without
answer-text deduplication. Focused dogfood/live-selection coverage passed `51
passed, 1 warning`.

## Current-head cutover checkpoint (`e4e80c03`)

- Local HEAD and `origin/hades-aci-v1`: `e4e80c03ae0acb380fa44b8272dc0d7f98df7fb5`
- Worktree: clean after checkpoint commit
- Candidate image ID: `sha256:f292defb418c7d935601e93a295e9ac3eeec3bab0df2deb7c4c52a8d0bcb5780`
- Running source label and `/app/.odysseus-source-commit`: exact `e4e80c03ae0acb380fa44b8272dc0d7f98df7fb5`
- Running container: `odysseus-odysseus-1`, running; `/api/health`: healthy
- Focused cutover/ACI/dogfood/live protocol suite: `102 passed, 1 warning`
- Full regression with intentionally read-only `/home` fixture: `6751 passed, 5 skipped, 5 failed, 2 errors`; failures/errors were writable-fixture failures except one stale CI assertion.
- Writable rerun of the seven affected tests, including the corrected CI assertion: `8 passed, 2 warnings`.
- Live Ollama/Qwen remains unavailable; live owner-model verification is **UNVERIFIED**.

## Foreground route authority closure

The foreground chat route no longer exposes a mutable `stream_agent_loop`
compatibility hook. `_chat_stream_entrypoint` now always enters the existing
ACI seam with `aci_mode="aci"`; tests replace that canonical seam directly.
The cutover, lifecycle, foreground routing, dogfood, and live-protocol suites
passed `204 passed, 2 warnings`. No production direct legacy stream callers
were found by the AST audit.

## Full regression evidence (`8ea00f81`)

The complete suite ran with the project fixture writable and only the host
Docker storage path mounted read-only: `6760 passed, 5 skipped, 149 warnings`.
The storage-preflight tests passed `6/6` under the corrected fixture; the six
prior failures were mount artifacts. No current-head full-regression failure
was observed in this run.
