# Hades V1 release ledger

Status: active engineering release ledger; not a release declaration.

## Latest branch checkpoint — `bb27c5c4`

The productization branch is synchronized with `origin/hades-v1-productization`
at `bb27c5c4601299461be76de2f9d8350ced305de9`; the worktree is clean. This
latest checkpoint is evaluator/documentation-only: it adds seeded sampling
coverage proving declared continuation groups retain their prerequisite turns
and fresh-session runs do not manufacture reference context. The deployed
executable remains the previously recorded exact product candidate, so this
checkpoint has not been rebuilt or presented as new runtime evidence.

The focused Recipe/owner/evaluator slice after the checkpoint passed `266`
tests. A bounded 100-seed selector audit found no orphaned declared
continuation. The current branch is `216` commits ahead of `origin/main` and
zero behind; no merge is implied by that divergence.

## Isolated fresh-start/restart rehearsal — `d1559078` (2026-08-29)

The exact retained executable candidate `odysseus:candidate-d1559078` was
started in a new Compose project with empty bind-mounted data, logs, and host
broker directories. The first attempt was stopped before service creation by
an environment-only Docker subnet collision (`172.30.0.0/16` was already in
use). A retry selected an explicit unused `172.40.0.0/16` network and passed:
the application reported healthy, `/app/.odysseus-source-commit` matched
`d1559078a414d7f2e7a8571ebf75028126121632`, normal first-run admin login
succeeded, and the authenticated session remained valid after an application
restart. Restart count was `0` before and after; post-restart health was
healthy. Only the disposable Compose project and temporary directories were
removed. This is fresh-start/bootstrap and restart durability evidence; it
does not claim empty-state suite journeys or owner-data behavior.

## Fresh empty-state browser Recipe journey — `d1559078` (2026-08-29)

Using a separate disposable Compose project and the exact retained candidate,
the normal first-run admin login registered the local Qwen endpoint, then the
existing gated non-admin acceptance principal authenticated through the real
login UI. The browser created a complete Recipe through natural-language chat,
read it back through chat, reloaded the conversation, and read it back again.
The result was `3` turns / `3` streams, `1` chat mutation, `2` canonical
readbacks, and `3` terminal `[DONE]` events. False success, raw final result,
duplicate delivery, and abrupt EOF counts were all `0`. The disposable
principal, credential, project, volumes, and temporary state were removed.
This proves the fresh empty-state Recipe mutation/readback lane on the
retained executable; it is not owner-data evidence and does not cover all
empty-state suites.

## Household browser fixture callback correction — `d1559078`

The isolated Household journey initially exposed a browser-harness setup
defect: `seedHouseholdAcceptanceState` destructured an argument its caller did
not provide, so the run failed before chat execution. The callback now accepts
no unused argument, and the static browser regression covers that invocation
shape. Replayed against the exact retained candidate, the four-turn
natural-language add/read/use/read journey passed with two canonical mutation
readbacks, four terminal `[DONE]` events, and zero false-success, raw-final-
result, duplicate-delivery, or abrupt-EOF failures. The earlier failure was
evaluator infrastructure, not product behavior; the disposable deployment
and all temporary credentials/state were removed.

The same exact retained candidate also passed the fresh realistic-messy Asset
browser journey `OWNER-ASSET-FILTER-NO-MATCH-001`. Its disposable canonical
fixture included incomplete and duplicate-like records; the natural-language
RTX 4090 filter completed with one human-readable answer and one `[DONE]`,
with zero raw final results, false success, duplicate delivery, or abrupt EOF.
The fixture database, acceptance principal, and disposable deployment were
removed. This is isolated Asset product evidence, not owner-inventory
evidence.

## Fresh empty-state Memory and Work browser reads — `d1559078` (2026-08-29)

Two additional fresh disposable Compose projects exercised the existing
authenticated browser harness after normal first-run admin setup and Qwen
endpoint registration. The empty Memory journey and empty Work journey each
completed one natural-language owner read with one human-readable final
answer and one terminal `[DONE]`. Both reported zero raw final results, false
success, duplicate delivery, and abrupt EOF. Acceptance credentials, volumes,
and projects were removed after each run. These are isolated empty-state
product checks, not evidence about the owner's accumulated data.

The current-tree supported full regression at this checkpoint completed
`6945 passed, 5 skipped` in `212.46s`. This run includes the evaluator
selection regressions above. The five skips remain documented test skips; no
product failure was observed. Because this checkpoint changes only tests and
documentation, the previously verified executable candidate was not rebuilt
or redeployed.

The existing non-mutating realistic browser acceptance lane also passed at
this checkpoint (`browser_realistic_acceptance: PASS`). It exercises shared
window/layout, Household/Recipe surfaces, long-content containment, and
responsive narrow/mobile behavior against the local healthy application. It
does not replace authenticated owner-journey evidence.

The current branch also passed frontend static verification
(`npm run test:frontend`) and the existing windowed browser smoke
(`browser_window_dogfood: PASS`). These are UI/release checks only and do not
claim authenticated owner-state acceptance.

## Current productization checkpoint — `f60d9334`

- Branch `hades-v1-productization` is synchronized with its remote at docs
  head `f60d93341dec4212701a5c014bcd940c9aec2e4e`; the worktree is clean.
- The latest executable checkpoint is `8976228f1f5129db2cc9f2496dbb3d9b39bab7a0`.
  Its exact candidate `odysseus:candidate-8976228f` was verified in a
  disposable runtime as image
  `sha256:e92b27ffe5130f510666327881ca128d473183c4c3567065eebcf91ba1d03b40`.
  OCI marker, image label, and running source matched; health was healthy and
  restart count was zero. Qwen3:8B was reachable from the Hades container
  namespace.
- The executable change exposes explicit operation/result/store metadata for
  canonical Work reads while preserving WorkEngine status inference and empty
  results. Supported-container focused ACI/binding/intent coverage passed
  `241` tests. A later Tier 1 cross-suite source-mounted run passed `65`
  tests against the current checkout. The last authoritative full regression
  remains `6934 passed, 6 skipped`; it predates this small Work metadata
  change and is not relabeled as current-head evidence.
- A current-tree full regression run completed `6935 passed, 5 skipped` with
  one environment setup failure in `test_blocks_symlink_into_ssh`: the
  source-mounted checkout was intentionally read-only, so the test could not
  create its temporary `/app/.ssh` target. The same confinement file passed
  `25 passed` from a temporary writable checkout with isolated data/log/.ssh
  mounts. This remains an environment classification, not a hidden product
  pass or a changed security expectation.
- Owner deployment was not replaced. No owner data, credentials, or volumes
  were changed. The branch remains in productization stabilization; this is
  not a merge or release declaration.

## V1 blockers

None currently evidenced in the deployed core control plane. Security, owner
scope, exact approval, durable continuation, canonical reads, fallback
authority, and rollback invariants remain covered by the current focused/full
gates.

## Owner journey acceptance expansion

The legacy browser smoke lane remains unchanged. A supplemental data-driven
black-box lane is now defined in `benchmarks/hades_owner_journeys.json` and is
run by `test:browser:owner-journeys` against an isolated acceptance deployment.
It covers canonical Asset/RAM and filtered reads, Network, empty Recipe reads,
chat-driven Recipe mutation/readback, and chat-driven Household mutation/
readback. Expectations are evaluator-only; they are not supplied to routing or
model prompts. Mutation scenarios refuse to run without an external isolated
acceptance credential, preventing accidental writes to the owner instance.

The lane is prepared and contract-tested; live execution remains a separate
acceptance result and is not claimed by this documentation-only checkpoint.

To run the synthetic profiles, the operator must provide a disposable
isolated deployment and set `HADES_BROWSER_ISOLATED_ACCEPTANCE=true` together
with `HADES_BROWSER_EXTERNAL_CREDENTIAL_FILE`; the runner will not provision
or use the current owner Compose volumes for those cases. The
`actual_owner_read_only` profile remains a separate explicitly supplied
read-only smoke lane.

The lane now refuses synthetic scenarios unless the operator explicitly marks
the deployment as isolated (`HADES_BROWSER_ISOLATED_ACCEPTANCE=true`) and
supplies an external acceptance credential. Per-turn action/tool-binding
expectations are mandatory, semantic oracles support required-all facts, and
recipe/household mutations perform independent allowlisted canonical GET
readback before and after browser reload. The acceptance output reports
scenario/turn/read/mutation/readback/DONE/EOF counts. Checkpoint
`c1e9aa72` is evaluator/docs-only; the deployed executable remains `34ced247`.

## V1 RC fixes and evidence

### Browser acceptance synchronization — `78a79bde`

The empty-state Recipe browser regression passed on the disposable candidate
after the runner began waiting for the explicitly created session to be
selected and for application/history hydration to settle before submitting
the first turn. This is a generic startup synchronization fix; it preserves
the strict user-message, final-answer, persistence, and terminal-DONE
assertions. `OWNER-RECIPE-EMPTY-001` completed through normal login and
`/api/chat_stream` with one human-readable deterministic answer, one persisted
turn, one `[DONE]`, zero raw-final results, zero duplicate delivery, and zero
abrupt EOF. The owner deployment was not changed.

| Item | Status | Evidence |
|---|---|---|
| Deterministic Memory/Work/Assets/Network/Service reads | green | source tests; deployed Qwen E5 matrices |
| Asset ordinal continuation | focused and authenticated live green | route no longer materializes asset `get` without strong identity; source `dcb57621`; live core `assets_list` and ordinal continuation green |
| Durable Continue terminal-state handling | green | `177` focused tests; live Continue resumed with zero tool calls |
| General MODEL_FALLBACK | green | focused security/fallback gates; live ordinary-question cases |
| Conceptual explanation routing | focused green, deployment pending | `17cbbb97`; RAID/backup explanations no longer enter `storage_ops`; direct fallback diagnostics are initialized safely |
| Infrastructure failure normalization | green | executor/projection focused gates preserve unavailable/invalid status; host-operator reads now expose canonical success/failure status |
| Exact approvals and policy boundaries | green | security/control-plane suites; live unauthorized-scan case |
| Deployment provenance and rollback | green | runtime source match `074d240f`; rollback `odysseus:rollback-b471e104-prev` |
| Automated live Qwen canary | E5A core slice green | fresh isolated normal-auth acceptance runtime, synthetic `hades-acceptance`, real qwen3:8b; core `8/8`, no internal leaks |
| Authenticated automated fuzzing | E5A partial/current | `scripts/hades_live_fuzz.py`; disposable Chroma/state, real login/chat/control plane; core `8/8`, held-out sample `20/22`, full regression `6535 passed, 3 skipped`; remaining failures are Work paraphrase direct-routing and network deep-dive disposition |
| Developer ACI read path | source-complete, E5 pending | focused developer/sandbox gates; production workspace mount intentionally absent |
| Provider switching/recovery | focused green, live E5 pending | `137` focused tests; only local Qwen endpoint live-available |

## V1.1+ deferred

- resource-scoped scheduler replacing the safe single-GPU global lock
- full negotiated provider protocol wiring and prefix-cache evidence
- broad agent-loop decomposition
- stronger developer sandbox resource/egress isolation
- large semantic corpus expansion beyond the current frozen/held-out suites
- additional provider live matrix
- cosmetic UI/accessibility and non-core integrations

## Owner E6 pending

Owner GUI use remains required for E6. Suggested spot checks are the natural
Memory, Work, asset-reference, current-network, ordinary fallback, ambiguous
restart, and durable Continue prompts. Automated E5 does not promote these to
E6.

## Current release state

### Productization owner-journey checkpoint — 2026-08-28

- Branch `hades-v1-productization` is pushed at `171e61af0738`; worktree is
  clean. The executable candidate `odysseus:candidate-e140a0accc52` embeds
  `e140a0accc525646c42eb674027cbac436e9a4c7` and runs only in the disposable
  owner-journey Compose project; the owner deployment remains on `34ced247`.
- Exact isolated browser evidence: empty Recipe read passed; complete recipe
  CREATE executed `manage_recipes.add`, persisted/read back the recipe, and
  rendered one deterministic human answer plus one `[DONE]`. The prior false
  success is closed on this candidate.
- The browser harness now records nested tool completion outcomes and does not
  mistake a tool card for a successful effect. Household `add_item` currently
  fails closed because the existing canonical action has no initial-stock
  semantics; this is a product capability gap, not a green acceptance result.
- The isolated Network/Asset lanes still require their declared fixture
  profiles. No owner data was modified. Full browser owner-journey acceptance,
  current owner deployment, and merge readiness remain pending.

- Branch: `hades-aci-v1`, synchronized with `origin` at `dcb57621` after the
  bounded upstream harvest and asset-reference fix.
- Source head: `dcb57621`; deployed runtime implementation is source-matched
  at `dcb576219516`, with the peak-aware build guard retained.
- Running image: `odysseus:candidate-dcb576219516`, source-matched and healthy.
- Last full regression before the latest fallback/runtime source slice:
  `6492 passed, 3 skipped, 186 warnings` in 123 seconds. Later focused gates:
  `210 passed` for fallback/control-plane behavior and `198 passed` for
  security/authority coverage.
- Current source-tip full regression: `6535 passed, 3 skipped, 186 warnings`
  in 230.81 seconds. Authenticated core live evidence is E5A; owner E6 remains
  supplemental.
- Current matched Qwen3:8b probe: raw `3.659s` vs Hades `5.462s` at a
  16-token cap; delta `1.803s`, including `0.218s` framework preparation and
  one Hades model call with zero tools/index lookups. Diagnostic only.
- Current agent-loop/provider transport gate: `101 passed`.
- Current telemetry/reference gate: `97 passed`.
- Storage: 77% used / 22 GiB free after removing superseded candidates and
  disposable acceptance containers/volumes.
  The peak-aware preflight reports CAUTION but permits only when projected
  growth preserves a 12 GiB emergency reserve; no further build is currently
  planned.
  Current, rollback, and live-auth images remain retained; no owner data,
  databases, volumes, backups, or model blobs were removed.
- Live canary accepts `--model`, `--endpoint-id`, and `--cookie-file`; cookie
  files support the existing Netscape export format without printing
  credentials.
- Real bridge overhead probe (Qwen3:8b, 172.18.0.1:11434, 64-token cap):
  cold raw `0.275s` vs Hades `12.850s`; warm raw `3.352s` vs Hades `12.600s`.
  Hades preparation was `0.235s`/`0.208s`, with one model call and zero tool
  calls. This is diagnostic only: raw stopped at 3 output tokens while Hades
  consumed 64, so it is not an equivalent-deliverable quality comparison.
- Tight-cap diagnostic rerun at 3 tokens measured raw `3.486s` vs Hades
  `5.955s` (`2.468s` total delta; `0.222s` preparation; `2.244s` extra
  provider span; one model call; zero tools). Both providers reported 3 output
  tokens, but Hades streamed 144 characters, so usage/stream accounting still
  needs correction before declaring an equivalent benchmark.
- The overhead harness now emits `output_accounting.consistent=false` for this
  mismatch (`hades_text_token_ratio implausible`) instead of allowing the run
  to be mistaken for an equivalent benchmark. Latest real-bridge run: raw
  `3.769s`, Hades `5.860s`, delta `2.091s`, prep `0.211s`, one model call,
  zero tools.
- The latest run classifies the discrepancy as
  `hades_framework_generated_fallback` (not provider token accounting): Qwen
  reported 3 provider tokens, while Hades emitted 99 characters of its
  domain-neutral fallback. Equivalent-deliverable latency remains unclaimed.
- Deployed fallback hardening at `c0a281f5`: empty model/synthesis responses no
  longer emit a search-specific false claim; the real-Qwen probe returned a
  domain-neutral fallback, one model call, zero tools, and
  `aci_empty_answer_fallback=true`.
- A matched normal-question probe after `17cbbb97` still produced a framework
  fallback from Qwen despite one authority-free model call and zero tools;
  this remains an attribution/ provider-output issue, not equivalent benchmark
  evidence. The harness now accepts `--prompt` so future matched probes do not
  depend on the old arithmetic wording.
- Direct bridge evidence then isolated the provider cause: this Ollama runtime
  ignored `think:false` on ordinary Qwen chat, while honoring
  `reasoning_effort:none`. After `16d42ccc`, the same probe produced normal
  content with consistent accounting: raw `4.695s` / Hades `7.319s`, total
  delta `2.624s`, preparation `0.245s`, extra provider span `2.375s`, one
  model call, and zero tools. This is source/live-bridge evidence; deployment
  E4/E5 for this newest adapter commit is still pending storage-approved build
  and authenticated live canary.

## Productization checkpoint — `65d61e9a` (2026-08-29)

- Added deterministic projection/rendering for successful canonical Homelab
  `service_status` reads, closing the observed gap where non-empty service
  health could fall through to unconstrained synthesis.
- Focused supported-container tests: `99 passed`, one SQLAlchemy deprecation
  warning.
- Exact candidate: `odysseus:candidate-65d61e9a1b65`, image
  `sha256:2aca24361b21f5e9876b25f89c7b4cace7803728e67b0a115a74893b14a1dd0b`;
  OCI marker and running source match the pushed SHA; health healthy; restart
  count `0`.
- Qwen3:8B was verified from the candidate container namespace at the
  configured host-gateway endpoint; digest
  `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- The prior authoritative full-regression result remains `6935 passed, 5
  skipped, 1 environment setup failure`; the isolated affected confinement
  suite passed `25`. This checkpoint did not rerun the full suite.
- Owner deployment remains unchanged; browser/live owner acceptance against
  this candidate remains separate evidence.

## Productization checkpoint — `fe7b6b74` (2026-08-29)

- Extended the existing canonical Homelab service renderer to target-qualified
  `service_status` reads, preserving bounded subprocess evidence instead of
  falling through to model synthesis.
- Focused supported-container tests: `100 passed`, one SQLAlchemy deprecation
  warning.
- Exact candidate image: `odysseus:candidate-fe7b6b74`,
  `sha256:1e20b8d3136cc4ea43b978f428ad115351f8bd12886b902fb19bb0a1b63c955f`;
  marker/OCI label/running source matched the pushed SHA; health healthy;
  restart count `0`.
- Qwen3:8B remained reachable from the candidate container namespace with
  digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- The prior full-regression evidence remains `6935 passed, 5 skipped, 1
  environment setup failure`; this checkpoint did not rerun the full suite.
- Owner deployment remains unchanged.

## Productization checkpoint — `d41c67fc` (2026-08-29)

- Closed the demonstrated Asset RAM owner-journey defect. `how much` is now
  included in the shared explicit-read predicate, so collection property reads
  cannot silently fall through to model-only prose.
- Focused owner/core suite: `535 passed, 2 skipped`.
- Full current-source suite: `6931 passed, 6 skipped`, with six
  storage-preflight environment failures because the source-mounted container
  did not contain `/home/.docker-data`; no product test failures were observed.
- Pushed source and candidate: `d41c67fcbc5e04dd932712beaf049389a5e1d4d5`,
  `odysseus:candidate-d41c67fc`, image
  `sha256:310bdcb9c37e6f1aa0533593ff2160f60e09a3b92a06319b7a9f90b97784f32c`.
  OCI marker/source matched; candidate health was healthy; restart count `0`.
- Browser acceptance against the exact disposable candidate passed the RAM
  property journey with canonical `manage_assets/list`, deterministic answer,
  correct Atlas/Erebus values, one persisted answer, and one `[DONE]`.
  Qwen3:8B was reachable from the candidate namespace. Disposable acceptance
  principal/container were removed; owner deployment was unchanged.

## Productization live Recipe checkpoint — `d41c67fc` (2026-08-29)

- Exact candidate browser acceptance passed the empty Recipe read with one
  deterministic human answer, one persisted answer, and one `[DONE]`.
- Chat-driven Recipe mutation/readback passed `3/3` turns: creation entered
  through natural-language chat, canonical readback found the recipe, and the
  recipe remained after reload. The run had `2` readback checks, `0` false
  successes, `0` raw final results, `0` duplicate delivery, and `0` abrupt EOF.
- Candidate source was `d41c67fcbc5e04dd932712beaf049389a5e1d4d5`, image
  `sha256:310bdcb9c37e6f1aa0533593ff2160f60e09a3b92a06319b7a9f90b97784f32c`;
  OCI/source marker matched, health was healthy, and restart count was `0`.
  Qwen3:8B was reachable from the candidate namespace. The disposable
  acceptance principal and credential were revoked/removed; owner deployment
remained unchanged.

## Productization Asset filter checkpoint — `d41c67fc` (2026-08-29)

- The exact disposable browser/chat journey for `Which of my servers has an
  RTX 4090?` passed against incomplete/duplicate-like synthetic canonical
  assets with no 4090. It used `manage_assets/list` and returned a bounded
  deterministic no-match answer with no invented server or raw JSON final.
- The run had one persisted answer, one `[DONE]`, zero raw final results,
  zero duplicate delivery, and zero abrupt EOF. No executable source changed;
owner deployment remained unchanged.

## Productization Recipe coverage checkpoint — `d41c67fc` (2026-08-29)

- Stateful browser/chat acceptance passed Recipe list followed by the
  pronoun/reference continuation `Can I make that recipe?`.
- The second turn used canonical `read_recipes/can_make` pantry coverage and
  deterministic rendering. Two streams produced two final answers and two
  `[DONE]` events, with zero raw final results, duplicate delivery, or abrupt
  EOF. No executable source or owner deployment changed.
- Meal-plan mutation remains explicitly deferred until Recipe read/composition
  coverage is broader and green.

## Productization Household checkpoint — `d41c67fc` (2026-08-29)

- Chat-driven Household mutation/readback passed `4/4` turns on the exact
  candidate: add three synthetic cans, read quantity, consume one, and read
  the remaining quantity after reload.
- The run had `2` canonical mutations and `2` readback checks, one persisted
  answer and one `[DONE]` per turn, zero false successes, zero raw final
  results, zero duplicate delivery, and zero abrupt EOF.
- This was isolated synthetic state using the existing Inventory Service; the
  acceptance principal was revoked/removed and the owner deployment remained
  unchanged.

## Productization URL import checkpoint — `d41c67fc` (2026-08-29)

- The live URL Recipe journey reached `manage_recipes/commit_import` through
  normal authenticated browser/chat execution and approval handling.
- The source contained an unquantified `salt and pepper` ingredient, so the
  canonical importer correctly returned review-required failure and explicitly
  said no recipe was saved. It emitted one `[DONE]` with no false success,
  invented quantity, or persistence claim.
- This confirms incomplete imported drafts fail closed. Complete URL import
  acceptance remains pending; no executable source or owner deployment changed.

## Productization Work projection checkpoint — `7c54a485` (2026-08-29)

- Fixed the demonstrated Work owner-answer disappearance: a successful
  `read_work` result could exceed the display envelope and leave the
  deterministic renderer with truncated JSON. The canonical projection now
  preserves bounded collection counts before display/history truncation.
- Focused supported-container tests: `77 passed`.
- Pushed source: `7c54a4859c9503dd264bd2e1459354f16321ef98`.
- Exact candidate: `odysseus:candidate-7c54a485`, image
  `sha256:4c1c70ed79502e482378310c27e6c680182c1a52a8624b579bc063cebac3f78e`;
  OCI marker/source matched, health was healthy, and restart count was `0`.
- Exact disposable browser acceptance for the previously failing empty Work
  journey passed: one deterministic human answer, one persisted answer, one
  `[DONE]`, zero abrupt EOF, and zero duplicate delivery. Qwen3:8B was
reachable from the candidate namespace. Disposable acceptance resources
were removed; owner deployment was unchanged.

- The authoritative supported-container full regression completed `6938
  passed, 5 skipped, 149 warnings` in `293.80s`, with exit status `0`.

## Productization Work/Recipe checkpoint — `7ea39f04` (2026-08-29)

- Exact disposable authenticated browser acceptance passed the non-empty Work
  overview against executable source `5c9e1be3465e352463479b698619663cf250be52`:
  one human-readable deterministic answer, one persisted turn, one `[DONE]`,
  zero abrupt EOF, and zero duplicate delivery.
- The browser harness now waits for asynchronous normal-login initialization
  before submitting the real login form. This is acceptance infrastructure;
  no auth semantics or owner deployment changed.
- Exact Recipe URL argument projection was rechecked with mixed read/manage
  capability visibility. The request resolves to `manage_recipes/commit_import`
  and carries the explicit requested name plus source URL. Recipe/import
  focused coverage: `46 passed`; the original `{"action":"add"}` loss was
  not reproducible on current source.
- Executable candidate remains `odysseus:candidate-5c9e1be`, image
  `sha256:96d8f900e19f0f43e2df15d07fe48da147a7d12498740cc50683643cf4cf42b`;
  OCI/source marker matched, health was healthy, restarts were `0`, and
  Qwen3:8B was reachable from the candidate namespace. Current branch/docs
  HEAD is `7ea39f044e0cde88d6d089c7ed020cd10122b2de`; this test-only descendant
  did not require a rebuild. Owner deployment remains unchanged.
- Full executable regression: `6932 passed, 5 skipped, 6 known
  storage-preflight environment failures`; the environment failures remain
  explicitly isolated.

## Recipe complete-URL mutation acceptance — `d1559078` (2026-08-29)

- Executable candidate: `odysseus:candidate-d1559078`, source
  `d1559078a414d7f2e7a8571ebf75028126121632`, image
  `sha256:3ec804a8a516deb0c9bb7e801598c70b1f7191e7a41a4cec9ab052521c38fce8`;
  OCI revision matched. This was an isolated disposable deployment; the
  owner deployment was not changed.
- Browser acceptance passed the complete URL journey through normal login,
  approval, chat-driven `commit_import`, list, and show. Requested name and
  source URL survived projection; canonical readback verified persistence
  before the deterministic success answer. Two readbacks (including reload),
  three terminal `[DONE]` events, `falseSuccess=0`, `rawFinalResults=0`,
  `duplicateDelivery=0`, and `abruptEOF=0`.
- The live SSE envelope now exposes only bounded `success`, `verified`, and
  `status` outcome scalars. Acceptance aggregates proposal and continuation
  streams for one logical turn; model prose and hidden raw Results remain
  non-authoritative.

## Current productization candidate regression — `d1559078` (2026-08-29)

- Full supported-container regression against the exact executable candidate,
  with the real storage roots mounted for the storage-preflight tests:
  `6940 passed, 6 skipped, 149 warnings` in `301.27s`.
- The same suite without those mounts produced six explicitly classified
  storage-preflight environment failures (`/home/.docker-data` absent); the
  six tests pass when the supported fixture paths are present. No product
  failure was hidden or converted into a pass.
- The current branch tip is a test/documentation-only descendant of this
  executable candidate; no owner deployment was changed.

## Household chat mutation acceptance — `d1559078` (2026-08-29)

- The isolated authenticated browser journey added three synthetic
  `Acceptance Tomatoes`, consumed one, and read the quantity back after each
  mutation through the normal chat route. No mutation was performed by a
  direct setup API.
- Result: `4` turns, `2` mutations, `2` canonical readbacks, `4` `[DONE]`,
  `falseSuccess=0`, `rawFinalResults=0`, `duplicateDelivery=0`, and
  `abruptEOF=0`, against the exact candidate image and source recorded above.
- This validates the existing Inventory Service owner for the seeded
  Household journey; fresh-install and broader Recipe/Household composition
  remain distinct release work.

## Frozen Qwen3:8B quick revalidation — `d1559078` (2026-08-29)

- The exact executable candidate ran the bounded `quick` tier from the Hades
  container namespace against `qwen3:8b`: `62/62` functional, `62/62`
  architectural, `62/62` security, duplicate rate `0`, and reference
  resolution `1.0`.
- Measured `model_calls/task=0.2581`, `decision_calls/task=0`,
  `failed_actions/task=0.0161`, median latency `0.0271s`, and P95 latency
  `3.9145s`. All 62 cases completed with incremental evidence; no timeout or
  provider-unavailability classification occurred.
- The report was generated against executable source
  `d1559078a414d7f2e7a8571ebf75028126121632`; subsequent branch commits are
  documentation/test-only and did not change the product image.

## Productization branch reconciliation — `38f2d048` (2026-08-29)

- `origin/main` is `364380ed3f46c1d14d3229e5b7530698cfa22e65`, the merge base
  of the productization branch, with no main-only commits. The branch is
  `190` commits ahead and `0` behind; no reconciliation conflict is pending.
- Current branch HEAD is `38f2d048`; worktree is clean and the branch matches
  `origin/hades-v1-productization`. The deployed owner runtime remains a
  separate older source and was not changed during productization acceptance.
- Merge/release is not declared: fresh-install, broader cross-suite, and
  release-candidate gates remain outstanding.

## Isolated fresh-start smoke — `d1559078` (2026-08-29)

- A disposable container was started from the exact candidate with empty
  data, logs, and broker volumes. The documented entrypoint created the first
  `admin` account and emitted a temporary credential; no owner state or
  credential was reused.
- Headless Chromium reached the real login page, authenticated through the
  normal form, and landed at `/`. After a container restart, the authenticated
  session remained valid and `/api/health` was healthy. The isolated instance
  was removed after the check.
- This is first-run/bootstrap and session-restart evidence only. Empty-state
  suite journeys, backup/restore, and a second clean fresh-fresh run remain
  release work.

## Recipe URL import acceptance checkpoint — `1c8c22a7` (2026-08-29)

- The exact isolated authenticated browser request for the named Sunday
  Supper recipe reached `manage_recipes/commit_import` and completed normal
  approval continuation.
- The source had an unquantified `salt and pepper` ingredient. Review-required
  fail-closed behavior was correct: no recipe persisted and the answer said no
  recipe was saved.
- Browser result: `PASS`, one terminal `[DONE]`, `falseSuccess=0`, zero raw
  final results, zero duplicate delivery, and zero abrupt EOF.
- Requested name and source URL remain preserved by the canonical mixed-
  capability projection regression. Complete-source persistence is still
  pending. Executable candidate remains `odysseus:candidate-5c9e1be` with image
  `sha256:96d8f900e19f0f43e2df15d07fe48da147a7d12498740cc50683643cf4cf42b`;
  test-only HEAD is `1c8c22a7`, and owner deployment was unchanged.

## Recipe complete-text mutation checkpoint — `359e518e` (2026-08-29)

- The exact isolated authenticated browser journey for a complete pasted
  recipe passed through normal chat mutation and readback: 3 turns, 2
  readbacks, and 3 `[DONE]` events.
- It reported zero false-success claims, raw final results, duplicate
  delivery, or abrupt EOF. This validates ordinary canonical `add` persistence
  independently of the URL import review case.

## Recipe import action-contract checkpoint — `3af8b2f8` (2026-08-29)

- The `manage_recipes` native schema now permits the staged `commit_import`
  payload (`action`, source metadata, and later validated `draft`) without
  incorrectly requiring primitive `add` fields. `requested_name` is explicitly
  represented in the contract. This prevents URL imports from being projected
  as an under-specified `add` action.
- Focused contract evidence: `357 passed, 1 warning`. Exact candidate image
  `odysseus:candidate-3af8b2f8` has OCI revision and
  `/app/.odysseus-source-commit` equal to
  `3af8b2f8b3c3845ff537233197ee38ac8df05e60`; isolated runtime health was
  healthy with zero restarts and Qwen3:8B visible from the container namespace.
- Browser replay was not graded: the isolated fresh data volume had no
  registered chat model endpoint, so normal session creation failed closed
  before the Recipe turn (`no usable endpoint for qwen3:8b`). This is an
  acceptance-environment readiness failure, not a product PASS. The temporary
  acceptance principal was removed and the disposable deployment was stopped.

## Full regression revalidation — `3af8b2f8` (2026-08-29)

- The complete repository suite ran in the supported project `venv` after the
  Recipe contract change: `6942 passed, 5 skipped, 186 warnings` in `215.25s`.
- The current branch tip is documentation-only relative to the executable
  candidate; no additional image build was required. Browser acceptance remains
  unverified on this candidate until the isolated deployment has a registered
  Qwen3:8B chat endpoint.

## Recipe URL browser revalidation — `3af8b2f8` (2026-08-29)

- A fresh disposable deployment registered its Qwen3:8B endpoint through the
  normal admin endpoint flow, then authenticated the gated acceptance principal
  through the normal login UI. The complete URL-import journey passed: `3`
  turns, `1` chat mutation, `2` canonical readbacks including reload, and `3`
  terminal `[DONE]` events. False-success, raw-final-result,
  duplicate-delivery, and abrupt-EOF counts were all `0`.
- The exact named Sunday Supper request also passed its review-required lane:
  `1` turn, `1` bounded failure, `1` `[DONE]`, no persisted recipe, and zero
  false-success/raw-result/duplicate/abrupt-EOF failures. The explicit name and
  source URL were retained through the projected import contract.
- Candidate image `odysseus:candidate-3af8b2f8` had OCI revision and source
  marker `3af8b2f8b3c3845ff537233197ee38ac8df05e60`, healthy runtime, and zero
  restarts. The principal, credentials, disposable volumes, and containers were
  removed after both runs; the owner deployment was untouched.

## Fresh Recipe onboarding acceptance — `3af8b2f8` (2026-08-29)

- A clean disposable Compose project was bootstrapped with no application
  state. A normal first-run admin login registered the Qwen3:8B endpoint through
  the existing admin endpoint route; the separate gated acceptance principal
  then authenticated through the normal login UI.
- The empty Recipe read plus natural-language Recipe mutation/readback journey
  passed: `2` scenarios, `4` turns, `1` chat mutation, `2` canonical readbacks
  including reload, and `4` terminal `[DONE]` events. False-success,
  raw-final-result, duplicate-delivery, and abrupt-EOF counts were all `0`.
- The acceptance principal, credential, database, volumes, containers, and
  network were removed after the run. This is isolated fresh-install evidence;
  it does not substitute for real-owner data validation.

## Backup/recovery focused validation — `69dc51af` (2026-08-29)

- Existing backup CLI security and recovery ownership tests passed in the
  supported project environment: `16 passed, 3 warnings`. Coverage includes
  safe snapshot output placement, symlink/hardlink/path traversal rejection,
  restore staging of the previous data directory, backup-import owner scope,
  and setup/readiness behavior.
- The documented Docker caveat remains: application `data/` is covered by the
  host snapshot, while Compose-managed Chroma vectors require a separate
  volume backup. A full live backup/restore rehearsal remains release work and
  was not represented as passed by this focused result.

## Isolated backup/restore rehearsal — `9d08d75d` (2026-08-29)

- The existing `scripts/odysseus-backup` CLI was exercised against a stand-alone
  temporary data tree. Snapshot creation and read-only archive verification
  both succeeded (`2` archive members).
- After deliberate SQLite/JSON drift and an extra file, `restore --yes`
  restored the original database row and JSON state, removed the drift file,
  and retained one `data.before-restore-*` rollback stash. No owner data or
  live application directory was involved.
- This validates the application-data backup/restore path. Docker Chroma
  volume backup remains a separate documented operational step.

## Bounded live Qwen candidate shard — `3af8b2f8` (2026-08-29)

- The exact candidate completed all `10/10` selected cases through the real
  authenticated HTTP/SSE path with incremental JSON evidence. Qwen3:8B was
  reached through `http://host.docker.internal:11434` from the Hades namespace;
  the candidate source marker matched and the runtime had zero restarts.
- Transport/security invariants held for every case: `answers=10`,
  `internal_leaks=0`, no abrupt EOF, no duplicate delivery, and one terminal
  event per stream. The trajectory score was `8/10`.
- `network_1` is an environment fixture classification: the disposable run
  had no host-network broker observation, so the canonical read correctly
  produced a bounded failure outcome rather than fabricated state. The
  `assets_reference` failure is an evaluator/session-selection classification:
  a continuation was sampled without its prerequisite context and therefore
  resolved no referent. Neither result supports a production semantic fix.

# Dogfood sampled-trajectory integrity checkpoint — `603b80dc`

The live dogfood selector now preserves the prerequisite turns for a declared
continuation group when a seeded bounded sample selects a follow-up. Fresh
session mode continues to strip continuation context deliberately, so it tests
the no-context behavior instead of manufacturing a reference. This closes an
evaluator integrity gap exposed by the interrupted bounded Qwen shard: an
`assets_reference` follow-up must not be scored as a product reference failure
when its `assets_list` setup turn was omitted by sampling. Focused coverage is
11 passed. This is evaluator-only; the deployed executable candidate remains
the previously recorded exact product SHA.
