# Hades V1 Finalization Status

This is an exact-head reconciliation against the current local checkout. It
is an engineering status record, not a readiness declaration.

## Source and runtime truth

| Field | Current evidence |
|---|---|
| Branch | `hades-aci-v1` |
| Local HEAD | `b9693733f9a72f7b090d6f95356724321b30784e` |
| Remote HEAD | `b9693733f9a72f7b090d6f95356724321b30784e` |
| Worktree | clean; tracking `origin/hades-aci-v1` |
| Running container | `odysseus-odysseus-1` |
| Running image reference | `odysseus-odysseus` (Compose-managed name; candidate tag retained locally) |
| Running image digest | `sha256:4b9a9c5b6c2871d1f4be65641ac70231de9017b06bd5feb0bbd1f23d08ade567` |
| Embedded source label | `b9693733f9a72f7b090d6f95356724321b30784e` |
| Runtime status | running, restart count 0 |
| Health | `GET /api/health` returns `healthy` |
| Last known-good source | `b9693733f9a72f7b090d6f95356724321b30784e` |
| Rollback images | preserved locally, including `odysseus:rollback-b471e104-prev` |

The running image's source label matches both local and remote HEAD. The
explicit candidate used for this checkpoint is
`odysseus:candidate-b9693733f9a7`; Compose's `odysseus-odysseus` reference is
the deployed alias.

## Current owner-state checkpoint (`b9693733`)

The exact deployed candidate passed the Qwen quick corpus against the
container-reachable Ollama endpoint (`host.docker.internal:11434`) using
`qwen3:8b`: `62/62 functional`, `62/62 architectural`, and `62/62 security`,
with no failure clusters. Focused container-backed tests passed `90` tests.
This is fixture/synthetic plus local-model integration evidence; authenticated
owner HTTP/SSE E6 remains unverified because no isolated acceptance principal
credential is configured.

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
- Current-head full regression is still required before any V1 readiness claim.
- Ollama is available to the deployed container at
  `http://host.docker.internal:11434`; host-local `127.0.0.1:11434` remains
  unavailable and is not Hades' configured endpoint.
- The Qwen quick result above is not authenticated owner E6 evidence.
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

## Exact checkpoint after acceptance-principal closure (`174c5921`)

This appendix supersedes earlier runtime values in this document for the
current checkpoint.  It records the observed state without claiming that the
broader V1 release gates are complete.

| Field | Observed value |
|---|---|
| Branch | `hades-aci-v1` |
| Local HEAD | `174c5921fbb958da8ed9b54f85e7dad0c8eac19f` |
| Remote HEAD | `174c5921fbb958da8ed9b54f85e7dad0c8eac19f` |
| Worktree | clean |
| Candidate | `odysseus:candidate-174c5921fbb9` |
| Running image | `sha256:2ebeaf2ac6f05dcd2b0cc1d05707d1beb6444cd51b47182606a97a30e2c0b46a` |
| Embedded/running source | `174c5921fbb958da8ed9b54f85e7dad0c8eac19f` |
| Container | `odysseus-odysseus-1`, restart count `0` |
| Health | `/api/health` returned `healthy` |
| Ollama endpoint | `http://host.docker.internal:11434` from the Hades namespace |
| Model | `qwen3:8b`, digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| Acceptance principal | revoked; feature flag disabled; temporary credentials removed |

Focused benchmark-integrity and semantic dogfood tests passed (`17 passed`).
The seeded generate-only audit produced `1,062` scenarios and reported `69`
critical plus `104` high coverage gaps; these are coverage gaps, not execution
passes.  The production ownership/cutover/lifecycle suite passed `91` tests.

Authenticated acceptance-principal HTTP/SSE smoke had useful grounded answers
for Network, Homelab, and Memory, with one terminal `[DONE]` each, zero abrupt
EOF, and zero duplicate finalization.  The broader live core sample was
`11/12`; its only failure was a missing answer for a continuation fixture with
no active durable Run, so this is not recorded as a complete live-model gate.
The previously recorded exact-source full regression remains `6,783 passed,
4 skipped`; no new executable source was changed in this checkpoint.

The remaining foundation work is failure/coverage-cluster closure, benchmark
anti-leak evidence, and failed-Action reduction.  No new runtime subsystem or
physical loop decomposition is justified by this checkpoint.

## Current exact-head reconciliation (`8e273784`)

### Superseding runtime verification (`71f4b00c`, 2026-08-27)

The earlier host-loopback probe was not authoritative for the deployed
container: host `127.0.0.1:11434` is intentionally not the container's Ollama
endpoint.  The current container is configured for
`http://host.docker.internal:11434`; from `odysseus-odysseus-1`, `/api/tags`
returned `qwen3:8b` (digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`) and a
direct `/api/generate` probe returned HTTP 200 with `READY`.

Therefore Qwen/Ollama availability is **INTEGRATION VERIFIED** for the
deployed runtime. Authenticated owner HTTP/SSE dogfood remains **UNVERIFIED**
because no synthetic-owner session credential was available in this checkout;
that is a harness-authentication gap, not an Ollama outage.

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

## Latest checkpoint (`e0a88d0d`)

The dead-alias cleanup was applied without changing semantic behavior. Focused
ACI/cutover/resource/agent-loop/dogfood coverage passed `173 passed, 1 warning`.
The prior full-regression result remains applicable to this cleanup-only
checkpoint: `6760 passed, 5 skipped, 149 warnings`; live Ollama/Qwen remains
unavailable and therefore unverified.

## Semantic dogfood oracle checkpoint (working tree)

The existing evaluator now grades ScenarioFrame cases against traced canonical
ActionSpec identity, domain, grounding, and completion state. A fluent answer
without the required canonical Action evidence is recorded as a semantic
failure; non-ScenarioFrame imports retain their prior scoring contract.
Focused dogfood/ACI/reference coverage passed `261 passed, 1 warning`. This
change is evaluator-only and is not yet represented by the deployed image;
the deployed source remains `fb7a43ea` until a new explicit candidate is
built.

## Exact candidate verification (`176e7aa5`)

The evaluator checkpoint was explicitly built and deployed. Image label,
embedded source, and running container matched `176e7aa5`; health was green
with zero restarts. The corrected storage-fixture full regression passed
`6761 passed, 5 skipped, 149 warnings`. Live Qwen/Ollama remains unavailable,
so live-model evidence is unverified.

## Semantic evidence strictness (working tree)

ScenarioFrame scoring now treats absent required grounding/completion trace
fields as failures. This keeps fluent or incomplete records from passing a
semantic oracle without evidence. Focused dogfood scorer coverage passed `32
passed, 1 warning`; the deployed source remains `972015ad` until the next
explicit candidate is built.

## Canonical read failure closure (working tree)

The existing `canonical_result_answer` seam now owns failed or malformed
Network, Asset, and Household read results as `AnswerSource.ERROR`. Such a
read emits a bounded unavailable/error projection and cannot fall through to
model synthesis. Added regressions cover broker-unavailable Network reads and
malformed Asset results; focused ACI/reference/dogfood coverage passed `263
passed, 1 warning`. This change is not deployed until its exact source SHA is
built and verified.

## Canonical-read delivery closure (`959b5eab`)

The existing production compatibility loop now stops after a canonical ACI
read Result is persisted, including deterministic read failures. It no longer
asks the model for a prose round that is subsequently replaced by the
canonical renderer. This reduces the duplicate-delta/final-replacement path
without adding text deduplication or a second answer owner. ACI, routing,
dogfood, chat-metrics, and foreground-stream tests passed `189 passed, 2
warnings`. The exact source was built as `odysseus:candidate-959b5eab8826`,
deployed, and verified by embedded source label, image digest, healthy
`/api/health`, and zero restarts. Full current-head regression passed `6763
passed, 5 skipped, 149 warnings`.

## Dead grounding alias removal (`working tree`)

`agent_loop.ground_action_completion` had no production consumers; its only
remaining references were compatibility tests. Those tests now import the
canonical ACI helper directly, and the alias/import were removed from
`agent_loop.py`. The affected network, continuity/dependency, and ACI suite
passed `68 passed, 1 warning`. This removes compatibility surface without
changing the grounding owner.

## Dead canonical-read alias removal (`working tree`)

The next alias audit found `_canonical_asset_read_payload` and
`_canonical_read_fast_path_payload` had no production consumers. Test callers
now import the canonical ACI helpers directly, and both aliases were removed
from `agent_loop.py`. Focused canonical-read/ACI coverage passed `275 passed,
1 warning`; no semantic owner or execution path changed.

## Owner-scope reference correction (`working tree`)

The structured reference resolver now treats the common lower-case/ASR form
`it assets` as the owner-scoped `IT assets` noun phrase, rather than consuming
an active Asset referent as the pronoun `it`. The owner collection query stays
on the canonical `manage_assets.list` Action even when a prior Asset is
active. Container-backed focused coverage passed `276 passed, 2 warnings`.

## Dead loop export cleanup (`0c0326c4`)

The loop-local `_canonical_read_action` export had no internal or production
consumer. Test consumers now import the canonical `intent_contracts` owner;
compatibility delegates still used by the loop remain intact. The focused
ACI, memory-grounding, lifecycle, and cutover suite passed `131 passed, 2
warnings` after fresh-process verification.

## Direct canonical trace calls (`working tree`)

The loop now calls the canonical ACI `action_trace`, `project_aci_trace`, and
`detect_runaway_call` functions directly. Their loop-only compatibility aliases
were removed; no policy, execution, or completion authority changed. Fresh
focused lifecycle and runaway coverage passed `56 passed, 2 warnings`.

## Hadolint CI noise closure (`6e9fed64`)

Consolidated the source-marker and data-directory Dockerfile `RUN` steps to
remove DL3059, and configured the pinned Hadolint action with
`failure-threshold: warning`. Warnings and errors remain blocking; INFO/style
findings remain visible but do not fail the workflow. The pushed `Container
scan` run for `6e9fed64c3d6f867a72597496af56f998e298b85` completed SUCCESS (17
seconds). The follow-up exact source `c84514f29574266b93fd95981ff2cf7677c5e9d9`
was built as `odysseus:candidate-c84514f29574` (image
`sha256:895ca25c66be688132604720a696f21be4c934bc8bc528d992601ae6a26ae0cb`),
deployed explicitly, and verified healthy with matching embedded source.

## Current exact checkpoint (`e3d7c2c8`, 2026-08-28)

This is the current executable source/runtime checkpoint. Subsequent evidence
must identify whether it was run against this source or a later
documentation-only descendant.

| Field | Observed value |
|---|---|
| Branch | `hades-aci-v1` |
| Local/remote HEAD | `e3d7c2c889f127123dfc2c528ac0202453cbc4c0` |
| Candidate | `odysseus:candidate-e3d7c2c889f1` |
| Running image | `sha256:6a74d168bfd38ad9ded5aa5a4608d78e889a6b4b52ed65c0d19666e801523258` |
| Embedded/running source | exact `e3d7c2c889f127123dfc2c528ac0202453cbc4c0` |
| Runtime | `odysseus-odysseus-1`, restart count `0` |
| Health | `/api/health` returned `healthy` |
| Ollama | `http://host.docker.internal:11434` from the container; `qwen3:8b` present |
| Acceptance facility | disabled; principal revoked; credentials removed; acceptance sessions `0` |

The authenticated Playwright browser lane passed `7` owner journeys on this
exact candidate, including normal UI login, real chat/SSE, reload persistence,
continuation, logout/revocation, and post-cleanup login denial. It reported `8`
streams because continuation adds one; no duplicate finalization or abrupt
stream failure was observed.

The authoritative current-head regression passed `6784 passed, 4 skipped`;
remaining output was existing deprecation/runtime warnings. A seeded
generate-only semantic run (`20260827`) produced `2740` scenarios and `193`
coverage gaps. These are coverage gaps, not execution failures, and remain
queued for cluster-driven semantic dogfood. No new semantic-owner refactor was
justified by this checkpoint: production enters through `aci.stream_aci_turn`,
while the remaining `agent_loop.py` surface is a compatibility/runtime seam
whose removal requires characterization tests.

## Exact-image full regression (`d59e4845`)

With the checkout mounted read-only and isolated writable data, logs, probe,
and Docker-storage fixtures, the exact candidate image completed `6765 passed,
5 skipped, 187 warnings`. This removes the earlier read-only/image-layout
false negatives from the release evidence; warnings are existing deprecation
and runtime notices, not test failures.

## Foundation closure checkpoint (`0ba721bf`, 2026-08-28)

The current evaluator/test branch is clean and synchronized at
`0ba721bf6565337ea6a73666a9886688e5ff3aee`. It is a test/evaluator-only
descendant of the deployed executable source, so it was not rebuilt or used
for product acceptance.

| Field | Observed value |
|---|---|
| Branch | `hades-aci-v1` |
| Local/remote HEAD | exact `0ba721bf6565337ea6a73666a9886688e5ff3aee` |
| Worktree | clean |
| Executable running source | `100d2e0f4e00ebf753a816984981603f666e6190` |
| Running image | `sha256:b2a1be4fa1856261f235bc90fa967c0b2f0a2595d570e66ac8558a7d68d31c07` |
| Runtime health | `/api/health` healthy; restart count `0` |
| Ollama | `http://host.docker.internal:11434` from Hades; `qwen3:8b` present |

Fresh evidence on the current branch: full regression `6803 passed, 4
skipped`; durability/recovery/approval suites `116 passed`; ACI/dogfood/lifecycle
suites `125 passed`. The seeded semantic coverage audit reproduced `1,793`
scenarios and `196` coverage gaps (`34` critical, `69` high). These are
coverage dimensions, not newly observed product failures. No safe additional
`agent_loop.py` authority removal was identified: production still enters via
`aci.stream_aci_turn`, and the remaining loop surface is compatibility/runtime
plumbing.

## Current foundation verification (`ade29da7`, 2026-08-28)

The exact current branch head passed the full regression with `6805 passed, 4
skipped, 186 warnings`. The targeted approval, WorkEngine, verification, and
recovery suites passed `69` tests. A container-namespace run of 100 generated
registry-action cases reproduced 13 failed-action cases; these are retained as
model/shortlist burden caused by underspecified exact-ActionSpec wording, not
authority or security failures. No executable source changed in this phase;
the deployed product remains source `100d2e0f`.

## Container-namespace Qwen checkpoint (`8e45fa79`, 2026-08-28)

The frozen 62-case quick corpus was rerun in a disposable container sharing the
deployed Hades network namespace, with `HADES_OLLAMA_ENDPOINT` set to
`http://host.docker.internal:11434` and an isolated data root. This avoids the
host-loopback false negative and does not touch production state.

| Metric | Observed |
|---|---:|
| Functional | `62/62` |
| Architectural | `62/62` |
| Security | `62/62` |
| Duplicate delivery | `0` |
| Qualified reference accuracy | `1.0` (`5/5`) |
| Failed Actions/task | `0.0161` |
| Model calls/task | `0.2581` |
| P95 latency | `2.3721s` |

This evidence uses current evaluator code at `8e45fa79` and the deployed
executable image/source at `100d2e0f`; the commit is documentation-only and
does not claim a rebuilt product image.

## Current foundation checkpoint (`980f959f`, 2026-08-28)

The current branch is clean and synchronized with `origin/hades-aci-v1` at
`980f959f39fa99f11fd3d9400d6e06f55366f129`. The authoritative project-venv
regression completed with `6806 passed, 4 skipped, 186 warnings`. The new
restart/reconstruct regression covers both failed and ambiguous execution
binding states; the focused WorkEngine/verification/approval/ACI suites
remain green.

This checkpoint contains tests and evaluator evidence only. The running
product remains the previously deployed executable source
`100d2e0f4e00ebf753a816984981603f666e6190`, image
`sha256:b2a1be4fa1856261f235bc90fa967c0b2f0a2595d570e66ac8558a7d68d31c07`,
healthy with restart count `0`; qwen3:8b remains verified from the Hades
container namespace at `http://host.docker.internal:11434`.

A reproducible semantic audit with seed `20260828` generated `1,793`
scenarios and reported `196` metadata coverage gaps (`34` critical, `69`
high). The critical entries are predominantly unrepresented scalar labels
for approval/failure/post-result dimensions; direct approval and lifecycle
tests already exercise several of those branches. They are not being counted
as product failures without executable scenario evidence. The generated
registry-action probe remains a model/shortlist burden cluster (13/100), not
an authority or security regression.

## Registry fixture-boundary checkpoint (`9f3f834e`, 2026-08-28)

The semantic evaluator now distinguishes registry ActionSpecs that have a
first-class synthetic transport from known Actions whose executor is not
available in the synthetic harness. Unsupported executors remain in coverage
but are no longer assigned a neighboring read-only fixture; they must fail
closed without a tool call. Supported transports retain exact ActionSpec
grading. Affected ACI/dogfood/lifecycle regressions passed `184 passed, 2
warnings`. This checkpoint changes evaluator code only; the deployed product
image was not rebuilt.

The full current-head regression subsequently passed `6807 passed, 4 skipped,
186 warnings`. Replaying the seeded semantic generator (`20260828`) produced
`1,793` scenarios and `233` coverage metadata gaps (`33` critical, `69` high).
The changed gap count reflects explicit unsupported-executor/capability-gap
coverage, not a product failure rate. No executable source changed.

## Current executable seam change

`aci.stream_aci_turn` now enters `agent_loop.stream_aci_runtime` directly.
`stream_agent_loop` remains only a compatibility facade and closes its
delegated async generator on shutdown. This is a boundary change, not a new
planner or execution path; focused characterization passed 79 tests. The
running image still contains source `100d2e0f` until this source change is
committed, pushed, built, and deployed through the exact-SHA loop.

## Executable checkpoint: `c42a8e23`

The production ACI entrypoint selects `stream_aci_runtime`; the old
`stream_agent_loop` symbol is a closure-propagating compatibility facade.
Focused coverage passed `64` tests and the full regression passed `6807
passed, 4 skipped, 186 warnings`.

Candidate `odysseus:candidate-c42a8e2313c4` is running with image ID
`sha256:b2d97c4521e19fff3a987598c404288d2d3f67f298df73805f099522a7c7009b`,
embedded/running source `c42a8e2313c483bcf950d0482b79c276aba6528d`, healthy
status, and restart count `0`. The frozen Qwen quick run is `62/62/62` with
zero duplicates. This entry is evidence for the executable checkpoint; later
documentation-only commits must not be conflated with the running source.

## Final deployed executable checkpoint: `5e8d8250`

The subsequent compatibility-hook correction is the deployed executable
source. Local and remote match at `5e8d8250ea3cc548472ec513901a02a7bde31615`;
candidate `odysseus:candidate-5e8d8250ea3c`, image
`sha256:ace756fd4609f06c982a60773306653933b71e2b83ab7bed9f94c34ec16ce7e6`,
OCI source label, embedded marker, and running source all match. Health is
healthy with restart count `0`. Full regression is `6807 passed, 4 skipped,
186 warnings`; the in-container frozen Qwen quick run is `62/62/62`, with
duplicates `0` and reference accuracy `1.0`.
## Post-cleanup executable evidence: `b0b94a67`

The dead legacy prompt block was removed (`120` lines); full regression on the
resulting source is `6807 passed, 4 skipped, 186 warnings`. The exact
candidate `odysseus:candidate-b0b94a6773f7` is running with image
`sha256:60af34bd9c1301b76268f3daafb3cac0cdc60b10c3600ba5538c7da63e898c3b`,
embedded/running source `b0b94a6773f705f131a26b74cb9ff9118379c806`, healthy
status, and restart count `0`. The frozen Qwen quick run remains `62/62/62`
with duplicate delivery `0`.

## Compatibility-alias reduction checkpoint (`c0e73ada`, 2026-08-28)

Removed four unused internal compatibility aliases and switched their runtime
call sites to canonical imports: usage-summary projection, action-snapshot
construction, directive insertion, and the retired verifier alias. Aliases
still referenced by legacy scripts/tests remain intentionally preserved.
Focused coverage passed `270` tests; the corrected full environment previously
passed `6806 passed, 5 skipped, 149 warnings`.

Pushed source and exact candidate are `c0e73ada0bce579506ca6fcacb5c92868b740f3a`
and `odysseus:candidate-c0e73ada0bce`. Running image is
`sha256:81e8095c91a8edcf99b72f3e0e52cf5cc850bd50213e58c765f90032c11d43b6`;
OCI revision, embedded marker, and running source match. Health is healthy,
restart count is `0`, and Qwen3:8B remains available from the configured
`http://host.docker.internal:11434` endpoint.

The exact `c0e73ada` source then passed the corrected full regression in the
supported container environment: `6806 passed, 5 skipped, 149 warnings`.

## Canonical helper call-site checkpoint (`cf7cc7ba`, 2026-08-28)

After correcting indentation from the helper call-site substitution, syntax
compilation and the affected suite passed (`300 passed, 1 warning`). The
exact pushed source `cf7cc7ba29b4e7c664f98d2204babb96a6de8d4f` was built as
`odysseus:candidate-cf7cc7ba29b4`, deployed, and verified by OCI revision,
embedded marker, and running source. The running image is
`sha256:02ccfdcc91df48cc8be09f794425c34f28fa32889cd3a821022164c4efc2584b`;
health is healthy and restart count is `0`.

The exact candidate full regression passed `6806 passed, 5 skipped, 149
warnings`. In-container Qwen3:8B frozen quick evidence passed `62/62`
functional, architectural, and security, with duplicate delivery `0`, failed
Actions/task `0.0161`, model calls/task `0.2581`, reference resolution `1.0`,
and P95 latency `2.1386s`.

## Canonical internal-call checkpoint (`a8b3b7c5`, 2026-08-28)

The ACI runtime now calls canonical imported owners directly for memory
prefetch, reference acknowledgement, verifier execution, exact approval
detection, canonical-read matching, and final metrics. Historical underscore
names remain compatibility aliases for tests/callers; no second authority was
introduced. Supported-image focused coverage passed `304` tests.

The exact pushed source is `a8b3b7c588e666520136f26439e39e24342072e9`.
Candidate `odysseus:candidate-a8b3b7c588e6` runs as image
`sha256:0b6cbd4dae1829140d8f0498a9eae8386f88b6212a1c053c34811966ce536eb6`;
OCI label, `/app/.odysseus-source-commit`, and running source match. Health is
healthy and restart count is `0`. Qwen3:8B is reachable from the Hades
container namespace with digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.

An initial isolated run produced six storage-preflight environment failures
because the test image lacked the host runtime paths. Re-running in the
supported project image with the real runtime roots and Docker socket mounted
produced the authoritative result: `6806 passed, 5 skipped, 149 warnings`.
The earlier six failures are superseded environment evidence, not product
failures.

## Canonical-runtime compatibility guard (`5a204cb0`, 2026-08-28)

Added a static production-cutover regression proving `stream_aci_runtime` does
not call retained underscore compatibility aliases. The aliases remain only
where compatibility tests or legacy seams require them; this test prevents
them from becoming a second runtime authority. The focused cutover/lifecycle
suite passed `61` tests. This is test-only evidence: the deployed executable
remains `cf7cc7ba29b4e7c664f98d2204babb96a6de8d4f`, so no image rebuild was
performed.

## Semantic coverage shard recovery (`20260828`, 2026-08-28)

No surviving execution report or partial JSONL was found after the interrupted
shard. A bounded replacement coverage-only shard (`0/4`, seed `20260828`)
generated `474` scenarios and `372` coverage gaps (`46` critical, `88` high).
These are coverage gaps, not failed product executions: the run deliberately
invoked no model and produced no runtime pass rate. The largest categories are
untested ActionSpecs, capabilities, failure classes, and lifecycle/policy
branches; they remain foundation-closure work.

## Compatibility-seam rejection (`5fb800d7`, 2026-08-28)

A broader conversion of provider/document/result helper calls from retained
underscore aliases to canonical imports was tested and rejected. The full
regression exposed four compatibility failures where sanctioned legacy tests
monkeypatch those aliases. The change was reverted and pushed as
`5fb800d766a4d010a18a5073561326d62be5b36f`; focused coverage passed `301`
tests and the exact candidate full regression passed `6807 passed, 5 skipped,
149 warnings`. The exact candidate is deployed and healthy with zero restarts.
This preserves the earlier ACI-owned reductions while avoiding a compatibility
regression; no further alias removal is justified without a characterization
slice for those seams.

## Real-Qwen semantic shard (`5fb800d7`, 2026-08-28)

The bounded execution shard was rerun on the Hades Compose network so the
configured Ollama endpoint was genuinely reachable. It exercised `327` cases
across frozen, generated, metamorphic, near-miss, minimal-pair, and chaos
families with `qwen3:8b`. Evidence: `260/327` functional, `310/327`
architectural, `327/327` security, duplicate rate `0`, failed Actions/task
`0.0581`, model calls/task `0.7278`, P95 `6.2559s`. This is a bounded shard,
not a release baseline. The only missing-answer case was the existing
minimal-pair contract for `What's running in Docker?`: its oracle says
`CONTAINER/READ`, while the current canonical ontology resolves it as
`SERVICE/READ` and the synthetic service result is blocked. This is recorded
as an ontology/fixture contract gap; no phrase-specific route was added.

## Frozen Qwen quick revalidation (`5fb800d7`, 2026-08-28)

The first revalidation used a source-mounted test container and is not treated
as image provenance evidence. A corrected run used the baked
`odysseus:candidate-5fb800d7` image with no source mount on the Hades Compose
network and real Qwen3:8B. It passed `61/62` functional, `62/62`
architectural, and `62/62` security. Duplicate delivery was `0`; reference
resolution was `1.0`; failed Actions/task was `0.0161`; model calls/task
`0.2581`; median latency `0.0195s`; P95 `3.8855s`. The sole failure is
`jarvis-environment-assumption`: the service-read trajectory produced an
answer, but the frozen evaluator's `response_excludes` grounding assertion
failed. This is a frozen evaluator/contract failure, not an absent answer or
transport failure. The bounded generated shard remains separate evidence.

The candidate image excludes the repository's `tests/` tree from the Docker
build context. A no-source-mount `pytest -q` therefore reports no test files
and exits with code `5`. The supported source-mounted container remains valid
for regression execution, but this is an explicit test-packaging limitation,
not exact-image full-regression evidence.

## Current authority audit (`c610b289`, 2026-08-28)

The production call graph contains no direct `stream_agent_loop` callers and
uses the canonical `stream_aci_turn` seam. The remaining implementation named
`stream_aci_runtime` is the executable ACI runtime; `stream_agent_loop` is a
marked compatibility facade. Top-level loop helpers are all referenced by the
runtime or compatibility tests. Removing additional aliases without a
characterization slice is therefore not justified. Cutover, lifecycle,
contract, and canonical-resource focused coverage passed `114` tests.

The follow-up characterization slice adds explicit tests for the intent seam:
canonical ACI-owned frames do not consult the compatibility classifier or its
normalizers, while unowned concepts use those adapters only as fallback. The
combined contract/cutover slice passed `30` tests. This is evaluator/test
coverage only; the deployed executable remains `5fb800d7`.

## Executable alias-reduction checkpoint (`8e9c0766`, 2026-08-28)

Removed three unused internal compatibility aliases (`workspace_coding_rules`,
`looks_like_explicit_skill_request`, and `uploaded_files_context_message`) and
switched their ACI-runtime call sites to canonical imports. The supported full
regression passed `6809` tests with `5` skips and `149` warnings; focused
ACI/routing/context coverage passed `284` tests. The exact candidate
`odysseus:candidate-8e9c0766` was deployed with OCI and runtime source
`8e9c0766df8e4f8e4966c3b60e0852abf1abb86d`, image
`sha256:01da8785463d6266759065093ad5f7dfa271640ee7f658f01f20d957cae6ff30`,
healthy and at zero restarts. Qwen3:8B was reachable from the container
namespace with the expected digest.

The no-source-mount frozen 62-case run against that exact image passed `62/62`
functional, architectural, and security, with duplicate delivery `0`,
reference resolution `1.0`, failed Actions/task `0.0161`, model calls/task
`0.2581`, median latency `0.0182s`, and P95 `2.5476s`. This does not substitute
for authenticated owner-browser acceptance.

## Qwen revalidation after second alias reduction (`11c4a7d6`, 2026-08-28)

The exact deployed candidate `odysseus:candidate-11c4a7d6` passed the supported
full regression before deployment (`6809 passed, 5 skipped, 149 warnings`).
The baked-image frozen Qwen3:8B run passed `62/62` architectural and security
cases and `61/62` functional cases, with duplicate delivery `0`, reference
resolution `1.0`, failed Actions/task `0.0161`, model calls/task `0.2581`,
median latency `0.0181s`, and P95 `3.379s`. The one failure is the known
`jarvis-environment-assumption` evaluator grounding assertion; its trajectory
had no Action and did produce an answer. Runtime source and OCI marker match
the pushed SHA; health is healthy with zero restarts.

## Qwen revalidation after result-summary alias reduction (`e4385a6d`, 2026-08-28)

The exact deployed candidate `odysseus:candidate-e4385a6d` passed the supported
full regression before deployment (`6809 passed, 5 skipped, 149 warnings`).
The baked-image frozen Qwen3:8B run passed `62/62` functional, architectural,
and security cases. Duplicate delivery was `0`; reference resolution was
`1.0`; failed Actions/task was `0.0161`; model calls/task `0.2581`; median
latency `0.0192s`; P95 `2.7039s`. Runtime source and OCI marker match the
pushed SHA, health is healthy, and restart count is `0`.

## Qwen revalidation after document-adapter reduction (`2cf8a5fb`, 2026-08-28)

The exact candidate `odysseus:candidate-2cf8a5fb` passed the supported full
regression before deployment (`6809 passed, 5 skipped, 149 warnings`). The
baked-image frozen Qwen3:8B run passed `62/62` functional, architectural, and
security cases. Duplicate delivery was `0`; reference resolution was `1.0`;
failed Actions/task was `0.0161`; model calls/task `0.2581`; median latency
`0.0200s`; P95 `2.5672s`. Embedded/running source matches the pushed SHA,
health is healthy, and restart count is `0`.

## Generated fixture outcome alignment (`8d432c51`, 2026-08-29)

The hidden-holdout audit showed generated ScenarioFrames declaring varied
execution outcomes while the synthetic fixture world returned unconditional
success. This was an evaluator-contract defect, not a production routing
failure. Explicit `environment.fixture_profile` now carries the ScenarioFrame
result state; the synthetic executor enacts success, partial, and failure
states from that environment. Expected/oracle fields remain evaluator-only,
with regression coverage proving they do not change fixture selection.

Focused dogfood tests: `55 passed`. Full local regression: `6812 passed, 4
skipped, 186 warnings`.

Pushed evaluator source: `8d432c5166c9fa6c2d8878baaac85c588002dc87`.
Candidate `odysseus:candidate-8d432c51` was built with that revision but not
deployed because executable product behavior is unchanged. Running product
remains the healthy `f5c07ff3` candidate. A repeat hidden run was not valid
Qwen evidence: Ollama was unreachable from the evaluator container, yielding
`0` model calls and an environment-degraded `53/162` functional result.

The same seeded run was then repeated from the correct `odysseus_default`
network, where the deployed Hades namespace can reach Ollama. Qwen3:8B was
available with the recorded digest. The run covered `162` cases and produced
`67/162` functional, `146/162` architectural, `162/162` security, duplicate
delivery `0`, reference resolution `1.0`, failed Actions/task `0.2037`, model
calls/task `0.7407`, median latency `1.6328s`, and P95 `6.0475s`. This is
diagnostic holdout evidence, not a V1 gate: the command used the frozen
baseline plus the 100-case holdout, and the remaining clusters are dominated
by generated routing/action and burden cases. The result is now valid model
evidence, unlike the prior wrong-network run.

## ACI helper-export reduction (`f5c07ff3`, 2026-08-28)

Removed three unused `agent_loop.py` exports for think-block stripping,
empty-response fallback, and exact-approval checking. Their implementations
and runtime call sites already belong to `src.llm_core` or
`src.capability_registry`; compatibility/context exports that remain active
were not changed. The focused canonical helper/cutover tests passed `59`
tests (one unrelated isolated fixture-order case was deselected), and the
supported full regression passed `6809` tests with `5` skips and `149`
warnings.

The exact pushed executable source is
`f5c07ff33e6754784fc328fa8392daea4b6178e0`. Candidate
`odysseus:candidate-f5c07ff3` is deployed with image ID
`sha256:b23213db1791e89d3ff3d96b90a72ea7106c50ea6311bb25602258cef06c9fbf`;
OCI/source markers match, health is healthy, and restart count is zero.
Exact-image Qwen3:8B evidence is `62/62` functional, architectural, and
security; duplicate delivery `0`; reference resolution `1.0`; failed
Actions/task `0.0161`; model calls/task `0.2581`; median `0.0164s`; P95
`2.5771s`.

## Foundation closure evidence (`f5c07ff3`, 2026-08-28)

The exact deployed helper-export checkpoint remains healthy and source
synchronized. A seeded RC coverage audit generated `2540` scenarios with
`128` reported gaps (`31` critical, `10` high); these are coverage gaps, not
runtime failures. The critical queue is concentrated in failure classes,
approval branches, post-result states, and policy branches.

A seeded Qwen3:8B hidden-holdout run added `100` hidden cases to the existing
corpus (`345` cases total). It produced `247/345` functional and `305/345`
architectural results, with security `345/345`, duplicate delivery `0`,
failed Actions/task `0.0754`, model calls/task `0.8406`, and P95 `5.4353s`.
Failures clustered in generated `registry_action` cases (domain/action/
completion burden), so this is diagnostic holdout evidence rather than a
release pass. No production authority change was made in response.

## ACI compatibility-export reduction (`a27806e1`, 2026-08-28)

Removed six unused underscore exports from `agent_loop.py` whose semantic
implementations already belong to `src.aci`: reference hints,
reference acknowledgement, explicit-memory detection, minimal ACI answer
projections, and canonical-read matching. Tests now import those helpers from
their canonical owners; active provider/context compatibility seams were left
unchanged. Focused coverage passed `282` tests and the supported full
regression passed `6809` tests with `5` skips and `149` warnings.

The exact pushed executable source is
`a27806e1837576297aa0e4db3028e0a5423b4d72`. Candidate
`odysseus:candidate-a27806e1` is deployed with image ID
`sha256:a7013b6a9d6fed32eb9ed3a9521143b228fdbc0054851af339fac82129bc1b13`;
OCI/source markers match, health is healthy, and restart count is zero.
The frozen exact-image Qwen3:8B run passed `62/62` functional,
architectural, and security cases; duplicate delivery `0`, reference
resolution `1.0`, failed Actions/task `0.0161`, model calls/task `0.2581`,
median `0.0183s`, and P95 `2.7525s`.

## Executable alias-reduction checkpoint (`dfa5a2a1`, 2026-08-28)

Removed two internal-only aliases (`_minimal_odysseus_notes_messages` and
`_strip_doc_model_artifacts`) and switched their runtime call sites to the
canonical imports. Focused coverage passed `305` tests; supported
source-mounted full regression passed `6809` tests with `5` skips and `149`
warnings. The pushed source, OCI revision, source marker, and running source
are `dfa5a2a13822fb33a7edf774a78916f2eab6aa64`.

Candidate `odysseus:candidate-dfa5a2a1` is deployed with image ID
`sha256:62987b38363f8c7adf27d348e0c20a169ea3b4cc191403408278c1d8eeedf56d`;
health is healthy and restart count is zero. Qwen3:8B is reachable from the
Hades container namespace with digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.

Exact-image frozen Qwen3:8B evidence: `62/62` functional, architectural, and
security; duplicate delivery `0`; reference resolution `1.0`; failed
Actions/task `0.0161`; model calls/task `0.2581`; median `0.0174s`; P95
`2.4932s`.

## Qwen revalidation after memory/notes alias reduction (`2cf8a5fb`, 2026-08-28)

The exact candidate `odysseus:candidate-2cf8a5fb` passed the supported full
regression before deployment (`6809 passed, 5 skipped, 149 warnings`). The
baked-image frozen Qwen3:8B run passed `62/62` functional, architectural, and
security cases. Duplicate delivery was `0`; reference resolution was `1.0`;
failed Actions/task was `0.0161`; model calls/task `0.2581`; median latency
`0.0187s`; P95 `3.15s`. Embedded/running source matches the pushed SHA,
health is healthy, and restart count is `0`.
