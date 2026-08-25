# Hades post-overnight truth audit

Date: 2026-08-25  
Branch: `recovery/live-candidate-20260823`  
Final source under audit: `b4e362c1bd18`

## Current continuation update (2026-08-25)

- CMDB owner-boundary repair is now deployed in `9f86213a`: registered Hades
  asset operations require an authenticated owner and pass it through the
  existing CLI adapter. Legacy ownerless CLI compatibility remains outside the
  Hades binding; ownerless rows are fail-closed rather than guessed into an
  owner.
- Registered read executors now enforce declared collection/result shapes for
  Work, Household, OSINT, Communications, technical-asset, Network, and
  Security reads. Malformed success-shaped payloads become `RESULT_INVALID`.
- CardDAV contacts remain `NOT_PROJECTED` because the current provider path has
  no proven owner boundary. No global contacts data is presented as private
  canonical truth.
- Full regression at this checkpoint: **6259 passed, 3 skipped, 186
  warnings** in 126.64 seconds. Candidate `odysseus:candidate-20c6c0e84d69`
  is deployed with image `sha256:96519f4a5870d49bdcd5b7a5e8feef2414c157f46dc1ad6116cd6fcdd3dbd03c`.
  `/api/health`, `/api/version`, frontend static, browser-window, and
  realistic browser gates passed. Owner-live E6 remains pending.
- Follow-up `b5029dc7` repairs the chat-to-Run seam for explicit canonical
  Communications reads. Full regression is **6260 passed, 3 skipped, 186
  warnings** in 127.55 seconds. The source-matched candidate and browser gate
  evidence for that commit are recorded below; owner-live E6 remains pending.

## What changed

- Preserved and committed the handoff IntentFrame/domain-contract, canonical
  IT-asset read, bounded network service-enumeration, target-propagation, and
  action-exposure work as `be1435f8`.
- Audited original/recovered Odysseus versus newer Hades ownership in
  `docs/hades-architecture-convergence-audit.md`.
- Converged expanded workspace grouping onto the existing
  `WorkspaceDefinition`/`ModuleDefinition` registry. Virtual/contextual
  modules now have explicit metadata instead of silently missing registration.
  Commits: `5163533d`, `12494174`.
- Kept legacy routes/DOM bindings and mature provider implementations as
  compatibility/adaptation paths; no backend databases were merged.
- Added a first-class read-only `memory.read` Capability and `read_memory`
  ToolBinding over the existing canonical Brain store. This is an adapter, not
  a second memory engine; legacy mutations remain compatibility-only.
- Added a first-class read-only `work.read` Capability and `read_work`
  ToolBinding over the existing durable WorkEngine. Overview, review, context,
  and typed list reads remain owner-scoped structured projections; no second
  Work store or filesystem fallback was introduced.
- Added a first-class read-only `household.read` Capability and
  `read_household` ToolBinding over the existing owner-scoped InventoryService
  for household overview, listing, search, and item reads. Household Inventory
  remains distinct from technical CMDB/IT Assets.
- Added a first-class read-only `setup.read` Capability and `read_setup`
  ToolBinding over existing secret-free SetupCenterService projections for
  state, integrations, and permissions. Setup metadata remains distinct from
  authority and never resolves secrets.
- Preserved the mature `api_call` integration routing rule pack while adding
  Setup/Integration guidance; the full regression caught and verified this
  convergence detail.
- Added owner-scoped OSINT case reads (`list_cases`/`get_case`) through the
  existing public-source capability and durable research case store. Report
  prose remains tainted and does not promote itself into canonical claims.
- Built and deployed `odysseus:candidate-90cc66b0` with image
  `sha256:7434e78a8e375a8a37f09bdeb21e54d43c75f3612ca30da18fe0cad4f904ac18`.
  Runtime `/api/version`, container source hash, and browser/static checks are
  attributable to this commit; rollback `odysseus:rollback-0c18805fe1d0` is
  retained.

## Evidence

| Area | Evidence | Truth status |
|---|---|---|
| Python regression | 6120 passed, 3 skipped, 186 warnings | E3 |
| Focused contract/network/asset tests | green; workspace/theme focused tests green | E2/E3 |
| Frontend static verification | `npm run test:frontend` | E3 |
| Browser/window/realistic acceptance | all three repo commands pass against final candidate | E4 |
| Runtime provenance | `/api/version`, checkout/container hash, image digest agree | E4/E5 |
| Broker | socket present, `odysseus:odysseus`, mode 660 | E4/E5 |
| Ollama | bridge `/api/version` responds; model inference was verified at prior gate | E4/E5 |
| Owner-live dogfood | no owner-authenticated session available overnight | pending E6 |
| Memory read convergence | `memory.read`/`read_memory`, focused and full regression green | E3/E4 |
| Work read convergence | `work.read`/`read_work`, focused and full regression green | E3/E4 |
| Household read convergence | `household.read`/`read_household`, focused and full regression green | E3/E4 |
| Setup/Integration read convergence | `setup.read`/`read_setup`, focused tests green and deployed source-matched | E2/E4 |
| OSINT case read convergence | `research.public_sources` case reads, focused/full regression green | E3 pending deployment |

## Reuse and convergence decisions

New control-plane primitives remain canonical for consequential authority:
Capability → ActionSpec → Policy → Approval → ToolBinding/trusted executor,
Work Run/journal, CMDB identity, epistemic evidence, and workspace registry.
Original Email, Calendar, Telegram, Cookbook, Compare, document/media,
research, and operation implementations remain reused through adapters or
projections where their provider/product behavior is stronger.

Composed boundaries remain intentional: Household versus technical CMDB,
Deep Research versus OSINT cases, Calendar versus Work/Missions, semantic
memory versus vector index, and domain documents versus evidence references.

## Remaining truth gaps

- Intent contracts are implemented for technical assets, network, security
  findings, OSINT planning, explicit Memory reads, Work reads, Household
  reads, Setup/Integration state, and OSINT case reads. Richer domain reads still require
  canonical binding/result-contract adapters; they are not claimed complete.
- The legacy technical asset CLI storage is deployment-scoped rather than
  row-owner keyed. Hades entry is owner-aware, but multi-owner CMDB isolation
  remains a migration gap.
- Consequential legacy tool paths still need a bounded call-graph audit and
  strangler migration; no generic shell authority was added.
- Owner-live Memory, theme/sidebar visual acceptance, Telegram, and provider
  dogfood remain pending owner authentication/credentials.
- Vector/memory health and optional provider availability must continue to be
  reported honestly; no degraded subsystem is promoted by UI wording.

## Classification rule

Synthetic tests and source-matched browser tests are not owner dogfood. E6 is
reserved for the owner’s manual verification on the deployed candidate.

## Durable canonical-read Run checkpoint

Commit `4bcce32cd85350b4d705c46cf6733a03739d0a78` extends the existing shared
Work bridge to canonical read domains. Memory, Work, Household, Setup, Career,
asset, security, and OSINT read Actions can now be attached to an owner/session
Run with semantic concept/operation metadata. A successful structured read
Result terminally completes a `single_verified_read` Run; a read failure
terminally records a blocked failure. Consequential Actions remain on the
existing exact-approval and verification lifecycle.

Focused bridge/contract/chat tests: 119 passed, 1 warning. Full pytest:
6131 passed, 3 skipped, 186 warnings, with one reproduced pre-existing failure
in `tests/test_agent_rounds_exhausted.py::test_emits_intent_nudge_exhausted_when_cap_is_exhausted`.
That failure is recorded as a remaining test-gate defect, not suppressed.

The source-matched deployed candidate is now `odysseus:candidate-4bcce32c`
with image `sha256:d60304610a4aaeb1239361627e767ddabbcad217158a2f8fd648b890eac00ad8`,
source `4bcce32cd85350b4d705c46cf6733a03739d0a78`, build ID
`4bcce32cd85350b4d705c46cf6733a03739d0a78-2026-08-25T05:00:00Z`, frontend
build ID `frontend-4bcce32cd85350b4d705c46cf6733a03739d0a78-6007cced95bca9218cf0721afb8c21f149683146706fd86f2b3fb3e09d64692d`,
and migration head `20260825_002_work_run_completion_v6`. Health, broker mode
and ownership, Qwen bridge inference, frontend static, browser-window, and
realistic browser checks passed. Rollback `odysseus:rollback-4bcce32c-prev`
is retained. Owner-live E6 remains pending.

## Read-intent boundary correction

Commit `2ec09bdf` adds bounded `IntentFrame.read_explicit` metadata. The shared
canonical-read projection now requires an explicit semantic read request, so an
imperative such as “do a long multi-step task” cannot be misrouted into a Work
overview read. Focused tests: 124 passed. Full pytest after this correction:
6133 passed, 3 skipped, 186 warnings, 127.22 seconds.
## Career foundation checkpoint

Career is implemented as a Work child module with owner-scoped durable
profile/search/opportunity/application/interview projections. It uses the
generic intent contract and canonical `career.read` binding. No provider is
configured in this environment, so external search is `NOT_CONFIGURED` and no
listings or application submissions are fabricated. Focused and full test
evidence is source-level; provider-backed and owner-live acceptance remain
pending external owner configuration.

## Universal Run checkpoint

`WorkRun.completion_criteria` is durable via migration
`20260825_002_work_run_completion_v6`. `WorkEngine.assess_deliverable_completion`
returns a model-independent `COMPLETE`, `IN_PROGRESS`, or `BLOCKED` projection
from persisted lifecycle/action/result state. Chat attaches IntentFrame and
deliverable metadata and emits the projection as `run_completion` for the GUI.
Canonical READ contract projection now covers the registered Memory, Work,
Household, Setup, Career, IT Asset, Network, Security, and OSINT read bindings;
the model is not required to name those bindings. The projection is focused
tested and committed in `723ca846`; it is pending rebuild/deployment
verification.

Final deployment verification supersedes that pending note: candidate
`odysseus:candidate-7d8b10dea3d1` is deployed with image
`sha256:42a4b85f9e98a657d327fb34994dc9b47719d889626cd4a5a6a98d3c9efc7772`,
source `7d8b10dea3d1e975ee62fba89f54f46f39ac5474`, build ID
`7d8b10dea3d1e975ee62fba89f54f46f39ac5474-2026-08-25T04:10:37Z`, and
migration head `20260825_002_work_run_completion_v6`. Health, broker, Qwen,
frontend static, browser-window, and realistic browser checks passed. Rollback
`odysseus:rollback-7d8b10de-prev` is retained.

## Setup health/configuration boundary checkpoint

Commit `dccc0acada8d7e268dd1cde6355e27f58a8d1546` keeps Setup Center's
resumable `status` as configuration state and adds separate `health_status`,
`health_reason`, and probe timestamp fields. `CONFIGURED` no longer implies a
successful provider or runtime health check. Integration projections retain
the compatibility `connection` field, but report unprobed configured modules
as `DEGRADED`/`UNKNOWN` rather than `CONNECTED`; absent, skipped, degraded,
and unavailable states remain distinct and secret-free.

Focused control-plane tests: 17 passed. Full regression after this change:
6134 passed, 3 skipped, 186 warnings in 128.00 seconds. Source-matched
deployment and runtime/browser gates are recorded below. Owner-live E6 remains
pending.

## Source-matched deployment verification

Commit `a423e87a24a04fe7d67b2be8b255b00b601a4ed3` is deployed as candidate
`odysseus:candidate-a423e87a24a0` with image
`sha256:c7e68dee91e3c5965d6eab3ab39fe25fa649431730fa2d7c2b6bca0d224e2219`.
Runtime `/api/health` is healthy and `/api/version` reports the same source,
build ID `a423e87a24a04fe7d67b2be8b255b00b601a4ed3-2026-08-25T06:25:00Z`,
frontend build ID, and migration head. Broker socket ownership/mode remain
`odysseus:odysseus`/`660`; Qwen `qwen3:8b` inference through the intended
`172.18.0.1:11434` bridge returned `OK`. Frontend static, browser-window, and
realistic browser acceptance all pass. Rollback is retained as
`odysseus:rollback-a423e87a-prev`.

## Consequential binding migration checkpoint

Commit `5b5c28fe` closes a concrete P0 control-plane gap: registered
Capability → ActionSpec → ToolBinding executors no longer dispatch around the
shared dispatcher gate. Focused binding/delegation/policy tests pass, and the
full regression at source level is `6136 passed, 3 skipped, 186 warnings` in
127.48 seconds. The change is source-tested and requires candidate rebuild and
runtime verification before deployment evidence is promoted. Owner-live E6
remains pending.

## Deterministic next-step projection checkpoint

Commit `761d3b58` adds a read-only `RunPlanner.next_step` projection over the
existing durable Work Run/action plan. It deterministically reports READY,
WAITING_APPROVAL, WAITING_INPUT, VERIFYING, BLOCKED, COMPLETE, or NO_PLAN;
selects the next incomplete action by sequence; surfaces validation failures;
and marks only validated read-only actions as safe for automatic continuation.
It never creates actions, executes them, grants authority, or bypasses exact
approval. The authenticated Work API exposes the same projection at
`GET /api/work/runs/{run_id}/next-step`, and the durable chat Work context
includes it when available. Focused coverage: 53 passed. Full regression:
6148 passed, 3 skipped, 186 warnings in 126.40 seconds. Source-matched
deployment and runtime verification are pending. Owner-live cross-model Run
continuation remains pending.

## Source-matched canonical read deployment

## Infrastructure Setup broker-health checkpoint

The authenticated Setup Center health probe for `technology.network` and
`technology.homelab` now checks the existing broker's read-only `status`
operation in addition to declared bindings. Network health requires the
private-scope host-broker binding and reported scanner availability; Homelab
health requires the bounded binding and broker availability. These probes do
not scan, mutate hosts, expose secrets, or alter authority. Results continue
through the existing persisted Setup health evidence path, with configuration
status kept separate from runtime health.

Focused Setup/workspace/binding tests: 34 passed, 1 warning. Full regression
after this change: 6245 passed, 3 skipped, 186 warnings in 125.71 seconds.
Candidate `odysseus:candidate-18db0e69` is source-matched and deployed with
image `sha256:c596d3bef9d812ca79e5be476db5a73d6f901b7efdb9a6b315a89133076a0b88`,
source `18db0e691f07e35bf59fd65acf63d875c9cdb816`, build ID
`18db0e691f07e35bf59fd65acf63d875c9cdb816-2026-08-25T10:08:20Z`, and the
existing migration head. Health, `/api/version`, Ollama bridge, frontend
static, browser-window, and realistic browser gates pass. Rollback
`odysseus:rollback-18db0e69-prev` is retained. Owner-live E6 remains pending.

## Model endpoint health checkpoint

Setup `core.models` now reuses the existing bounded provider reachability probe
against the configured Ollama/model endpoint. It records endpoint reachability
separately from capability metadata and never performs inference, downloads a
model, or changes authority. Focused tests: 108 passed, 1 warning. Full
regression: 6245 passed, 3 skipped, 186 warnings in 125.86 seconds.
Candidate `odysseus:candidate-7d061e77` is deployed with image
`sha256:f2891ced21433279f8437ce4e992f195c6a7bbced3734dba20ebed8a7518400b`,
source `7d061e77a8b04dcd9deea69c02145a4ecb1a7b60`, build ID
`7d061e77a8b04dcd9deea69c02145a4ecb1a7b60-2026-08-25T10:19:10Z`, and the
existing migration head. Health, `/api/version`, Ollama bridge, frontend
static, browser-window, and realistic browser gates pass. Rollback
`odysseus:rollback-7d061e77-prev` is retained. Owner-live E6 remains pending.

Commit `a9ab0e04d293b2bf606d6dbebd231077cee24054` is deployed as candidate
`odysseus:candidate-a9ab0e04d293` with image
`sha256:9b73c475186f5aec310e3668e7fc23099cdd7140e18c8ab0550f52fec5cbc0d3`.
Runtime health is healthy and `/api/version` reports the same source, build
ID `a9ab0e04d293b2bf606d6dbebd231077cee24054-2026-08-25T08:05:00Z`, frontend
build ID, and migration head. The broker socket remains
`odysseus:odysseus`/`660`; Qwen `qwen3:8b` inference through
`172.18.0.1:11434` returned `OK`. Frontend static, browser-window, and
realistic browser acceptance all pass. Rollback is retained as
`odysseus:rollback-a9ab0e04-prev`. Owner-live model parity remains pending.

## Canonical read exposure expansion checkpoint

The existing registered read bindings for Homelab hosts, service status,
Security engagements/evidence, and Research history are now exposed through
the semantic IntentFrame/DomainContract projection. Interrogative research
questions remain `READ` operations rather than being misclassified as new
research work. No executor or registry was duplicated. Full regression after
the change: 6143 passed, 3 skipped, 186 warnings. Owner-live model parity
remains pending.

## Source-matched consequential binding deployment

Commit `e7993fdb84c091b1a5a20f746829f8f322fc72f0` is deployed as candidate
`odysseus:candidate-e7993fdb84c0` with image
`sha256:45508b7b960d2612b62a6b26d95c443692b264d9276b2641dc9d7502b75acb6c`.
Runtime health is healthy and `/api/version` reports the same source, build ID
`e7993fdb84c091b1a5a20f746829f8f322fc72f0-2026-08-25T07:15:00Z`, frontend
build ID, and migration head. The broker socket remains
`odysseus:odysseus`/`660`; Qwen `qwen3:8b` inference through
`172.18.0.1:11434` returned `OK`. Frontend static, browser-window, and
realistic browser acceptance all pass. Rollback is retained as
`odysseus:rollback-e7993fdb-prev`. Owner-live E6 remains pending.

## Durable continuation pointer checkpoint

The shared continuation contract now projects the server-owned Run reference,
pending Action reference, and lifecycle phase into the durable Work context.
Registered binding preparation persists phases such as `PROPOSED` and
`AWAITING_APPROVAL`; structured results advance consequential work to
`VERIFYING` and terminal reads to `COMPLETE`. Ambiguous execution remains
blocked until independent verification. Focused coverage: 42 passed. Full
regression: 6138 passed, 3 skipped, 186 warnings. Owner-live cross-model
continuation remains pending.

## Source-matched durable continuation deployment

Commit `fab7c885407e7d7fc23de1166413271fe077cd4b` is deployed as candidate
`odysseus:candidate-fab7c885407e` with image
`sha256:444126dbf42b41afffb2e1a184737b93bc1b4d4932e9d60262c740292f05763e`.
Runtime health is healthy and `/api/version` reports the same source, build
ID `fab7c885407e7d7fc23de1166413271fe077cd4b-2026-08-25T07:40:00Z`, frontend
build ID, and migration head. The broker socket remains
`odysseus:odysseus`/`660`; Qwen `qwen3:8b` inference through
`172.18.0.1:11434` returned `OK`. Frontend static, browser-window, and
realistic browser acceptance all pass. Rollback is retained as
`odysseus:rollback-fab7c885-prev`. Owner-live cross-model continuation
remains pending.

## Synthetic cross-model contract parity checkpoint

Commit `8c1c6e58ac2d850640c74e93bcf9fab3b1c2d59f` adds a deterministic Qwen,
Luna, and Sol parity matrix over canonical IT asset, Memory, Work, Network,
Security, OSINT, Integration, and continuation requests. The matrix compares
IntentFrame, DomainContract, ActionSpec, binding, and durable Run phase—not
model prose—and passes for all three model identities. It also repaired plural
integration-health phrasing so “What integrations are degraded?” resolves to
the existing owner-scoped `read_setup`/`integrations` ActionSpec. Focused
matrix/contract coverage passes; full regression is 6159 passed, 3 skipped,
186 warnings. Owner-live provider swapping and E6 dogfood remain pending.

## Source-matched synthetic parity deployment

Commit `8c1c6e58ac2d850640c74e93bcf9fab3b1c2d59f` is deployed as candidate
`odysseus:candidate-8c1c6e58` with image
`sha256:ed1c6b3eeefd85af7bb710b9181cbbdbf3160c0aed2ace8cef8891d0112d444f`.
Runtime `/api/version` reports the same source/build/frontend provenance;
health, broker socket, Qwen inference, frontend static, browser-window, and
realistic browser gates pass. Rollback is retained as
`odysseus:rollback-8c1c6e58-prev`.
## Complete discovered target propagation checkpoint

- Status: `VERIFIED_TESTED` / `OWNER_DOGFOOD_PENDING`
- Evidence: the canonical Work bridge now propagates every discovered private
  address from each CMDB draft candidate, including multi-homed candidates,
  into the durable service-enumeration Plan and Action in stable order.
- Bound: propagation remains owner/run scoped and capped at 256 targets; the
  existing private-scope validation, exact approval, broker, and verification
  gates remain authoritative.
- Tests: focused Network/Run gates `20 passed, 1 warning`; full regression
  `6159 passed, 3 skipped, 186 warnings`.
- Live status: owner-live network dogfood remains pending; no live scan was run.

## Complete-target propagation deployment checkpoint

- Source: `d831d84b7bb84d180ecc35978195bc2ed6a15398`
- Candidate: `odysseus:candidate-d831d84b7bb8`
- Image: `sha256:6c0ea2acf5409b6990bf97aff41369f663cb46736c5da63a709a2439036672cd`
- Runtime `/api/version`, health, broker socket, Qwen bridge/model discovery,
  frontend static verification, browser-window acceptance, and realistic
  browser acceptance passed.
- Rollback: `odysseus:rollback-d831d84b-prev` →
  `sha256:f141fa985de7b71e26588bdff1ed086f4e5fa2d0c8b8b553d7cca873540dfac8`.
- Evidence level: `E4 VERIFIED_DEPLOYED`; owner-live Network and cross-model
  dogfood remain `E6 OWNER_DOGFOOD_PENDING`.

## Qualified continuation resolution checkpoint

- Source change: `0fc294e0` adds generic anchored recognition for qualified
  continuation turns such as “continue until…”, “resume that task”, and “keep
  going with the current Run”. This only produces `CONTINUE` intent metadata;
  durable Run state, ActionSpec policy, approval, and trusted execution remain
  authoritative.
- Evidence: focused intent/parity/network coverage `42 passed, 1 warning`;
  full regression `6163 passed, 3 skipped, 186 warnings`.
- Status: `VERIFIED_TESTED`; deployment of the final docs-inclusive checkpoint
  is pending. Owner-live cross-model Run dogfood remains pending.

## Canonical attention read checkpoint

- Source change: `59f1aa8c` promotes the existing owner-scoped
  `PersistentAgent.attention()` projection through the Work `read_work`
  binding as `work.read / attention`. “What needs attention?”, “What is Hades
  waiting on?”, and pending-approval phrasing now resolve semantically without
  model knowledge of internal tools or routes.
- The projection remains read-only and aggregates existing notifications,
  blocked/waiting Runs, and commitments; no second attention engine was added.
- Evidence: focused contract/parity/binding coverage `91 passed, 1 warning`;
  full regression `6168 passed, 3 skipped, 186 warnings`.
- Status: `VERIFIED_TESTED`; owner-live cross-model attention dogfood remains
  pending.

## Conversational reference intent checkpoint

- Source change: `af82c82e` aligns the semantic compiler and agent classifier
  for “do that”, “all of them”, “do all of the above”, and qualified
  continuation language. These turns now preserve structured continuation /
  reference intent for resolution against recent durable context or an active
  Run; they do not select, approve, or execute Actions.
- Evidence: focused continuation, reference, and regex-safety coverage
  `78 passed, 1 warning`; full regression `6171 passed, 3 skipped, 186
  warnings`.
- Status: `VERIFIED_TESTED`; owner-live multi-step reference dogfood remains
  pending.

## Live durable continuation projection checkpoint

- Source change: `07d86113` wires the existing pure
  `resolve_continuation()` decision into the agent loop using a minimal,
  owner-scoped durable Run/Action projection. The projection is read-only and
  omits result payloads; it cannot advance lifecycle, grant approval, or
  execute Actions.
- Evidence: focused bridge/intent/reference coverage `60 passed, 1 warning`;
  full regression `6172 passed, 3 skipped, 186 warnings`.
- Status: `VERIFIED_TESTED`; owner-live continuation and model-swap dogfood
  remain pending.

## Setup/Integration canonical read projection checkpoint

- Source change: `6efde1cb` centralizes canonical read Action projection and
  preserves the resolved `INTEGRATION` `view=integrations` filter. Integration
  health requests therefore use `read_setup / integrations`; ordinary Setup
  state requests continue using `read_setup / state`.
- Evidence: focused Setup/contract/parity/projection coverage `93 passed, 1
  warning`; full regression `6173 passed, 3 skipped, 186 warnings`.
- Status: `VERIFIED_TESTED`; provider credential/live health remains distinct
  from configuration metadata and owner-live dogfood remains pending.

## Career opportunity semantic-read checkpoint

- Source change: the bounded Career intent compiler now treats opportunity and
  role nouns, plus ordinary save/search inflections such as “did I save?”, as
  `JOB_OPPORTUNITY` semantics. These requests project to the existing
  owner-scoped `read_career / saved_opportunities` Action; profile,
  application, and interview reads remain distinct.
- Evidence: Career, intent-contract, and cross-model parity coverage `51
  passed, 1 warning`; full regression `6174 passed, 3 skipped, 186 warnings`.
- Status: `VERIFIED_TESTED`; external job-provider configuration and owner-live
  dogfood remain pending. No fake listings or autonomous applications were
  introduced.

## Career cross-model parity checkpoint

- The deterministic Qwen/Luna/Sol synthetic matrix now includes saved
  opportunities, applications, and interviews in addition to the Hades,
  Infrastructure, Research, and Integration requests.
- Evidence: model parity plus Career foundation coverage `19 passed, 1
  warning`; provider calls and owner-live model swapping remain pending.

## Durable next-step continuation checkpoint

- Source change: the owner-scoped continuation projection now reuses the
  existing `RunPlanner.next_step()` decision. It exposes the next valid,
  waiting-approval, blocked, or complete state without materializing an
  Action, granting authority, or executing anything.
- Evidence: continuation/bridge/planner coverage `64 passed, 1 warning`.
- Status: `VERIFIED_TESTED`; live multi-step provider continuation and
  owner-live model swapping remain pending.

## Safe automatic continuation checkpoint

- Source change: the shared agent loop may now project a planner-approved
  `safe_auto_continue` read-only Action from the durable Run into the normal
  ToolBinding loop. Consequential Actions, approval-required Actions, blocked
  Runs, and unavailable projections remain fail-closed.
- Evidence: agent-loop/planner/bridge coverage `82 passed, 1 warning` plus the
  explicit binding projection assertion.
- Status: `VERIFIED_TESTED`; owner-live multi-step and cross-model continuation
  remain pending.

- The continuation projection is refreshed after each successful bridged
  Action before the next agent round, preserving current Run state across
  chained read-only steps.

## Cross-model Run continuity checkpoint

- Active owner/session Runs now record bounded model history and the current
  model when a continuation arrives through a different provider. The same
  Run, plan, pending authority, and Results remain authoritative; model swap
  is an auditable cognition change, not a new Run or an authority change.
- Evidence: owner-scoped bridge, intent, and model-parity coverage `64 passed,
  1 warning`.
- Status: `VERIFIED_TESTED`; live provider swapping remains pending.

## Canonical Work/Mission/Watch read sweep checkpoint

- The semantic compiler now distinguishes first-class Work concepts for goals,
  projects, tasks, Runs, commitments, missions, and watches. Each resolves to
  an explicit read-only `work.read` Action through the existing `read_work`
  binding; missions reuse `MissionService` over canonical Work goals and
  watches reuse the owner-scoped `Monitor` store.
- Read-explicit phrasing such as “What runs are active?” is normalized to
  `READ`, while imperative execution requests remain distinct. Empty results
  retain `EMPTY_RESULT` rather than being represented as a successful data
  response.
- Evidence: semantic contract and binding coverage `93 passed, 1 warning`;
  full regression `6188 passed, 3 skipped, 186 warnings`; frontend static,
  browser-window, and realistic-browser gates all passed. Candidate
  `odysseus:candidate-d91d08930be1` is source-matched and live-verified with
  image `sha256:1d518a617e50...`; the broker socket and Ollama `qwen3:8b`
  were present at runtime.
- Status: `VERIFIED_LIVE`; owner-live cross-model dogfood remains pending.

## Cross-model Work read parity checkpoint

- The deterministic Qwen/Luna/Sol corpus now includes goals, projects, tasks,
  Runs, commitments, missions, and watches. Each model identity produces the
  same IntentFrame and canonical `work.read` ActionSpec projection; provider
  choice cannot add or remove authority.
- Evidence: model parity, contract, and binding coverage `79 passed, 1
  warning`; full regression `6195 passed, 3 skipped, 186 warnings`; frontend
  static, browser-window, and realistic-browser gates passed on the exact
  candidate. Runtime source is `b4e362c1bd18e5e1a1a26c0a35ba4e00feeb0580`
  with image `sha256:945da2e8fddf...`; live provider competence and
  owner-authenticated model swapping remain pending.
- Status: `VERIFIED_LIVE`; owner-live parity remains `OWNER_DOGFOOD_PENDING`.

## Durable conversational reference checkpoint

- `resolve_structured_reference` now resolves “it”, “that one”, ordinals, and
  plural references only against a bounded server-owned opaque reference set
  from the durable Run/result projection. Ambiguous singular references,
  missing context, and out-of-range ordinals fail closed. The resolved refs are
  carried by `IntentFrame`; they do not select Actions, widen scope, or grant
  authority.
- Evidence: focused intent/parity/bridge coverage `81 passed, 1 warning`; full
  regression `6198 passed, 3 skipped, 186 warnings in 127s`; frontend static,
  browser-window, and realistic-browser gates passed. Candidate
  `odysseus:candidate-0975fcf6` is deployed with image
  `sha256:6d17ca70d6f7...`; `/api/version` reports source
  `0975fcf67637ee32ad86ffffe993cb31978a3237` and migration
  `20260825_002_work_run_completion_v6`.
- Status: `VERIFIED_LIVE`; owner-live cross-model reference dogfood remains
  `OWNER_DOGFOOD_PENDING`.

## Canonical read failure grounding checkpoint

- Source change: durable single-read Runs now preserve explicit
  `DEGRADED`, `UNAVAILABLE`, `FAILED`, and `INVALID_RESULT` statuses in the
  persisted Result while transitioning the Run to failed/blocked. Only
  successful data or successful-empty canonical Results may complete the
  read deliverable.
- This closes the distinction between “the binding returned” and “canonical
  truth was retrieved.” No provider failure is converted to an empty list or
  a succeeded Run.
- Evidence: focused bridge/contract/planner coverage `125 passed, 1 warning`;
  full regression `6271 passed, 3 skipped, 186 warnings in 127.86s`. Status:
  `VERIFIED_TESTED`; source-matched deployment follows this checkpoint.

## Communications canonical-read checkpoint

- The existing owner-scoped EmailAccount and Calendar projection is now
  exposed through `communications.read/overview` and the shared
  `read_communications` ToolBinding. The contract is read-only and
  secret-free; it reports configured accounts and upcoming canonical calendar
  events. Contact/CardDAV records remain explicitly `NOT_PROJECTED` because
  the current provider cache is not yet a sufficient owner-scoped canonical
  binding.
- Evidence: registry, capability-gate, parity, and binding coverage `230
  passed, 1 warning`; full regression `6201 passed, 3 skipped, 186 warnings
  in 124.58s`. Candidate `odysseus:candidate-4433f2ad` is deployed and matched
  by source commit `4433f2ad1d7cd113099b3eaba2534ccad609d0c2`; health and all
  frontend/browser gates passed. Status: `VERIFIED_DEPLOYED` / `VERIFIED_LIVE`.

## Communications durable-Run bridge checkpoint

- The shared chat-to-Work bridge now persists `read_communications` alongside
  the other first-class canonical reads. A successful or empty Communications
  overview therefore remains inspectable in the owner/session Run and uses the
  existing structured read completion path; no Communications-specific loop or
  executor was added.
- Evidence: focused bridge/intent/parity/binding coverage `100 passed, 1
  warning`; full regression `6202 passed, 3 skipped, 186 warnings in
  126.15s`. Candidate `odysseus:candidate-fcf3daae` is deployed and matched
  by source commit `fcf3daaee63814340a8ebbf7f2d203eb0c37844d`; health and
  frontend/browser gates are source-matched. Status: `VERIFIED_DEPLOYED` /
  `VERIFIED_LIVE`.

## Network CMDB owner-scope checkpoint

- The standalone SQLite CMDB now has additive `owner` columns for assets and
  observations. New brokered network discovery writes the authenticated owner;
  projections filter assets, observations, and relationships by that owner,
  and same-MAC observations from another owner remain unattached rather than
  merging identity. Legacy ownerless rows are preserved but hidden from
  authenticated reads until an explicit `migrate-owner --owner <owner>` action
  binds them.
- `/api/network/map`, Security CMDB resolution, Work world-model sync, and the
  shared Homelab read path now pass authenticated owner context. Missing owner
  metadata returns `UNAVAILABLE / OWNER_SCOPE_NOT_CONFIGURED`, not an empty
  success or another owner's data.
- Evidence: owner-scope, legacy migration, cross-owner MAC, Security, network,
  and first-class binding coverage passed; full regression `6206 passed, 3
  skipped, 186 warnings in 126.22s`. The explicit migration was executed for
  the sole configured owner `scotty`; the database retained 8 assets and 59
  observations, and the owner-scoped projection returned `SUCCESS` with 19
  nodes and 1 relationship edge. The pre-migration database copy is retained
  at `/tmp/odysseus-assets-pre-owner-745e3936.db` for this deployment check.
- Candidate `odysseus:candidate-745e3936` is deployed with image
  `sha256:b6465f6078822cac9d6be41eeb4cccac971f836ded5fe37c0bbc99a9e35f38fd`;
  `/api/health`, `/api/version`, frontend static verification, browser-window
  dogfood, and realistic browser acceptance passed. Status:
  `VERIFIED_DEPLOYED` / `VERIFIED_LIVE`; owner-live network dogfood and
  cross-model provider swapping remain `OWNER_DOGFOOD_PENDING`.

## Safe durable read continuation checkpoint

- Source change: `4957b0af` promotes the existing `RunPlanner` projection into
  a server-owned safe continuation seam. After a successful bound read, the
  agent may chain the next declared read-only Action without another user
  message, but only when the planner reports `READY` and
  `safe_auto_continue`, the binding is currently exposed, the tool is not
  disabled, and the per-turn continuation budget remains healthy. Approval,
  policy, owner, and executor checks still run for the appended binding.
- The planner now merges persisted authoritative Actions with later
  unmaterialized declared plan steps. This prevents a completed first Action
  from falsely terminating a multi-step Run, while preserving sequence and
  compiled target scope.
- Evidence: focused continuation/planner/contract coverage `80 passed, 1
  warning`; full regression `6209 passed, 3 skipped, 186 warnings in 126.76s`.
  The source-matched candidate passed `/api/health`, `/api/version`, frontend
  static verification, browser-window dogfood, and realistic browser
  acceptance. This checkpoint is `VERIFIED_TESTED`; owner-live model swapping
  and consequential network dogfood remain `OWNER_DOGFOOD_PENDING`.

## Verified deliverable progression checkpoint

- Source change: `081908b1` fixes a shared lifecycle defect in which every
  successful postcondition verification transitioned the Run directly to
  terminal `succeeded`, even when later declared or persisted Actions still
  belonged to the deliverable. Successful verification now advances the Run
  to `ready` when remaining work exists; the existing planner then determines
  whether the next step is safe to continue, requires exact authority, or is
  blocked. Single-step verified Runs remain terminally successful.
- The transition is model-independent and does not create approvals, execute
  Actions, or weaken owner/policy checks. The regression proves a verified
  network Action exposes the next declared read Action with `safe_auto_continue`
  while retaining the structured verification result.
- Evidence: focused WorkEngine/planner/bridge coverage `94 passed, 1 warning`;
  full regression `6210 passed, 3 skipped, 186 warnings in 126.82s`;
  `py_compile` and diff checks passed. Candidate `odysseus:candidate-b7e57f81b7e5`
  is deployed with image `sha256:b7e4370d203fa18e4521d07b748038f4254dcac3f654e27d17e7567b506582d7`;
  `/api/health`, `/api/version`, owner-scoped CMDB continuity, frontend static
  verification, browser-window dogfood, and realistic browser acceptance
  passed. Status: `VERIFIED_DEPLOYED` / `VERIFIED_LIVE`; owner-live model
  swapping and consequential network dogfood remain `OWNER_DOGFOOD_PENDING`.

## Terminal Run and staged execution validation checkpoint

- Source change: `a06fd71b` closes the shared lifecycle gap that allowed new
  Actions to be appended to terminal Runs. `WorkEngine.create_action` now
  rejects completed, failed, cancelled, and succeeded Runs while preserving
  the existing cancellation boundary. Trusted execution validates the current
  Action as a focused step, so a later declared step's not-yet-due approval or
  precheck does not block the present step; unknown and structurally invalid
  future Actions still invalidate the plan before effects occur.
- The network service-enumeration regression now declares discovery,
  enumeration planning, and enumeration execution as one durable deliverable
  Run. This prevents verified discovery from falsely terminating the Run
  before the remaining work is assessed.
- Evidence: focused lifecycle/planner/bridge/verification coverage `70 passed,
  2 warnings`; full regression `6212 passed, 3 skipped, 186 warnings in
  125.25s`; `git diff --check` passed. Candidate
  `odysseus:candidate-a06fd71b` is source-matched and deployed as image
  `sha256:03e7a04817eed4d4ead358d419a32f6c2478c285fb480998d1152babe4c2d60c`.
  Runtime provenance, health, Ollama bridge, persistent CMDB continuity,
  frontend static verification, browser-window dogfood, and realistic browser
  acceptance passed. Status: `VERIFIED_DEPLOYED` / `VERIFIED_LIVE`; owner-live
  model swapping and consequential network dogfood remain
  `OWNER_DOGFOOD_PENDING`.

## Contract-driven canonical-read projection checkpoint

- Source change: `f134baa9` removes the agent loop's duplicate semantic
  concept-to-read-action table. Generic canonical-read repair now obtains the
  Action ID from the authoritative `DomainContract.actions` metadata, while
  preserving the existing specialized Work-attention and Integration-health
  view selectors. Security engagement/evidence and Research reads therefore
  resolve and project through the same contract path as Memory, Work, CMDB,
  Network, Household, Setup, Communications, and Career.
- Evidence: contract and memory-grounding coverage `80 passed, 1 warning`;
  agent-loop/bridge/capability coverage `114 passed, 1 warning`; full
  regression `6239 passed, 3 skipped, 186 warnings in 126.04s`; `git diff
  --check` passed. Source-matched deployment and browser gates are pending
  this checkpoint. Status: `VERIFIED_TESTED`; owner-live cross-model and
  consequential network dogfood remain `OWNER_DOGFOOD_PENDING`.

## Canonical read status normalization checkpoint

- Source change: `de13ed11` adds a shared status projection at the existing
  read-binding boundary. Status-less structured reads now explicitly report
  `SUCCESS_WITH_DATA` or `SUCCESS_EMPTY`; existing `DEGRADED`, `UNAVAILABLE`,
  and failure-shaped payloads remain authoritative and are not converted into
  empty collections. Domain payloads and owner scopes are unchanged.
- The projection covers the first-class Security, Work, Household, Setup,
  Career, and Communications read adapters while preserving explicit legacy
  statuses.
- Evidence: focused binding/bridge/contract coverage `109 passed, 1 warning`;
  full regression `6240 passed, 3 skipped, 186 warnings in 124.25s`; `git diff
  --check` passed. Source-matched deployment and browser gates are pending
this checkpoint. Status: `VERIFIED_TESTED`; owner-live provider swapping and
consequential network dogfood remain `OWNER_DOGFOOD_PENDING`.

## Specialized owner-scoped Network read checkpoint

- Source change: the existing `homelab.manage` ActionSpec family now exposes
  `list_unidentified_hosts` and `infer_role_hypotheses` as read-only canonical
  projections. Network intent contracts select these actions from structured
  views (`unidentified` and `roles`); no model-facing sentence or tool-name
  branch is required.
- Both projections reuse `network_projection.map_projection(owner=...)`.
  Unidentified devices remain non-canonical observations. Role output is
  explicitly `INFERRED`, includes canonical reference/freshness when present,
  and declares that canonical identity was not updated.
- Evidence: focused intent/binding/network coverage `103 passed, 1 warning`;
  full regression `6244 passed, 3 skipped, 186 warnings in 126.92s`.
  Source-matched deployment and browser gates are pending this checkpoint.
  Status: `VERIFIED_TESTED`; owner-live model swapping and consequential
  network dogfood remain `OWNER_DOGFOOD_PENDING`.

## Persisted Setup health evidence checkpoint

- Source change: bounded Setup Center module health probes now persist their
  secret-free health status, reason, and probe timestamp through the existing
  owner-scoped Setup state. Persisted setup/configuration status remains
  separate, so a probe cannot silently configure a module or grant authority.
- All existing supported health branches use the same persistence path; no
  provider credential, mutation, or alternate policy path was introduced.
- Evidence: focused Setup/binding coverage `31 passed, 1 warning`; full
  regression `6245 passed, 3 skipped, 186 warnings in 124.67s`.
  Source-matched deployment and browser gates are pending this checkpoint.
  Status: `VERIFIED_TESTED`; owner-live provider health remains
  `OWNER_DOGFOOD_PENDING`.

## Durable Run observed-provider provenance checkpoint

- Source change: `1ab830fe` records the model and endpoint that actually
  served each durable agent round, including foreground fallback, in the
  existing owner-scoped Run continuation state and audit events. This is
  metadata-only: the compiled plan, ActionSpec policy, approvals, and trusted
  executor authority are unchanged.
- Cross-owner observation is fail-closed. Existing explicit model swaps remain
  durable, and fallback observations now become truthful active-model context
  for later continuation.
- Evidence: focused bridge/chat/parity coverage `81 passed, 1 warning`; full
  regression `6261 passed, 3 skipped, 186 warnings in 126.65s`. Candidate
  `odysseus:candidate-1ab830fe172a` is deployed with image
  `sha256:f20c1ed914b8a7221104755d54435ebb49207fb811159ca23caa8abbbd063905`;
  `/api/health`, `/api/version`, frontend static verification, browser-window,
  and realistic browser acceptance passed. Status: `VERIFIED_DEPLOYED` /
  `VERIFIED_LIVE`; owner-live Qwen-to-Luna-to-Sol dogfood remains
  `OWNER_DOGFOOD_PENDING`.

## Nested canonical read degradation checkpoint

- The shared read-status normalizer now detects explicit `NOT_PROJECTED`,
  `UNAVAILABLE`, `FAILED`, or `DEGRADED` nested in an otherwise structured
  overview. Such a result is surfaced as top-level `DEGRADED`, including when
  a legacy adapter supplied `SUCCESS_EMPTY`; nested evidence is preserved.
- This keeps the current CardDAV contact limitation honest without exposing
  global contacts as private canonical data. No owner, provider, or authority
  boundary was weakened.
- Evidence: focused Result/contract/Run coverage `121 passed, 1 warning`; full
  regression `6262 passed, 3 skipped, 186 warnings in 126.75s`. Status:
  `VERIFIED_TESTED`; source-matched deployment follows this checkpoint.

## Exact approval preview/execution convergence checkpoint

- Source change: Run validation now reports an exact approval reference that
  has not resumed the Action, while approved Actions lacking the required
  reference or sealed input remain non-continuable. The trusted binding
  executor independently enforces `approved + approval_reference +
  sealed_input_digest` immediately before effects, so lifecycle staging cannot
  become authority.
- The existing planner, Run lifecycle, and WorkEngine remain the sole stores;
  the compatibility lifecycle projection is retained for pre-execution
  staging and does not invoke a binding. No approval digest, replay, owner, or
  policy invariant was weakened.
- Evidence: focused planner/verified-execution/approval coverage `39 passed,
  1 warning`; broader control-plane coverage `188 passed, 2 warnings`; full
  regression `6270 passed, 3 skipped, 186 warnings in 126.89s`. Candidate
  `odysseus:candidate-21644edc` is deployed as image
  `sha256:ac1cfc5442b3d87ae46e065eba244e649a79d591c77b6e9e8a579a32ef3b8c03`;
  `/api/health`, `/api/version`, broker-socket, Ollama-bridge, frontend
  static, browser-window, and realistic browser acceptance passed. Status:
  `VERIFIED_DEPLOYED` / `VERIFIED_LIVE`; owner-live model swapping and
  consequential network dogfood remain `OWNER_DOGFOOD_PENDING`.

## Owner-bounded Contacts canonical read checkpoint

- `CONTACT` is now a semantic IntentFrame concept mapped onto the existing
  `communications.read` Capability and `read_communications` ToolBinding.
  `Show my contacts` therefore follows the shared contract/Run path rather
  than relying on model-specific `manage_contact` wording.
- The existing CardDAV admin/single-user boundary is enforced at execution.
  Permitted owners receive typed `contacts` data; other owners receive
  structured `UNAVAILABLE / OWNER_BOUNDARY_UNAVAILABLE`. No CardDAV global
  data is exposed to a non-permitted owner, and no mutation is added.
- Explicit `UNAVAILABLE` and `DEGRADED` Result statuses now survive the shared
  Result validator instead of becoming `RESULT_INVALID`. Evidence: focused
  contract/security coverage `115 passed, 1 warning`; full regression `6268
  passed, 3 skipped, 186 warnings in 125.65s`. Status:
  `VERIFIED_TESTED`; source-matched deployment follows this checkpoint.

## Canonical read completion invariant checkpoint

- Source change: `WorkEngine.complete_read_deliverable` now enforces the same
  Result-status boundary as the agent bridge. Explicit `DEGRADED`,
  `UNAVAILABLE`, `FAILED`, and `INVALID_RESULT` outcomes persist a failed Run
  rather than allowing a direct caller to mark the deliverable succeeded.
- Evidence: focused agent-bridge/contract/planner coverage `126 passed, 1
  warning`; full regression `6272 passed, 3 skipped, 186 warnings in 127.31s`.
  Candidate `odysseus:candidate-5c335a0a` is deployed as image
  `sha256:46efbd17770ad2b8d7030490d2b862cfa9f56593006a396e777f5a8e62e10467`;
  `/api/health`, `/api/version`, broker-socket, Ollama-bridge, frontend
  static, browser-window, and realistic browser acceptance passed. Status:
  `VERIFIED_DEPLOYED` / `VERIFIED_LIVE`.

## Recursive canonical Result envelope checkpoint

- Source change: the shared `WorkEngine` completion boundary now walks nested
  Result envelopes, including `domain_reference` projections, when checking
  for `DEGRADED`, `UNAVAILABLE`, `FAILED`, or `INVALID_RESULT`. A nested
  provider failure therefore cannot be promoted to a succeeded single-read
  Run by a direct caller.
- Evidence: focused bridge/contract/projection coverage `130 passed, 1
  warning`; full regression `6273 passed, 3 skipped, 186 warnings in 315.73s`.
  Source-matched deployment follows this checkpoint. Status:
  `VERIFIED_TESTED`.

## Registry-derived durable action projection checkpoint

- Source change: the streaming agent loop now derives durable Work-action
  attachment eligibility from the canonical ToolBinding registry. The former
  duplicated tool-name allowlist is gone; `prepare_action` still resolves the
  exact ActionSpec and rejects unknown actions, so this changes projection
  coverage without changing authority.
- Evidence: focused bridge/registry/contract coverage `114 passed, 1 warning`;
  full regression `6273 passed, 3 skipped, 186 warnings in 177.44s`.
  Source-matched deployment and end-to-end acceptance follow this checkpoint.
  Status: `VERIFIED_TESTED`.

## Morning convergence acceptance checkpoint

- The final candidate is source-matched at commit `a3d84c0d12190d10170424246ed25c07b7757db8`, image
  `sha256:abcf8e0480a696b49f6bdc4d6ba8ee66bdf8c724f8d09d10ba0d773c9024de17`,
  build `a3d84c0d12190d10170424246ed25c07b7757db8-2026-08-25T13:15:53Z`,
  frontend build `frontend-a3d84c0d12190d10170424246ed25c07b7757db8-6007cced95bca9218cf0721afb8c21f149683146706fd86f2b3fb3e09d64692d`.
- `/api/health`, `/api/version`, broker socket ownership/mode, and Ollama
  bridge health passed. Direct Qwen3:8b inference returned the acceptance
  sentinel. Frontend static, browser-window, and realistic populated/narrow
  browser acceptance passed against this deployed candidate.
- The synthetic golden-flow matrix covering Hades, Infrastructure, Research,
  continuation, owner scope, and Qwen/Luna/Sol contract parity passed `136
  tests, 3 warnings`. Full regression remains `6273 passed, 3 skipped, 186
  warnings`. Status: `VERIFIED_DEPLOYED` / `VERIFIED_LIVE` for the local
  runtime and synthetic architecture; owner-live Luna/Sol swapping and
  consequential network dogfood remain `OWNER_DOGFOOD_PENDING`.

## Source-matched deployment reliability and final candidate checkpoint

- The candidate image-generation wheel stage now preinstalls its small build
  toolchain and uses `--no-build-isolation`, preventing an unnecessary torch
  bootstrap for the non-CUDA patched Real-ESRGAN dependencies. The isolated
  wheel target built all three patched wheels successfully.
- Exact current HEAD `f491d6a1b6204c7f846b365680a8127708210f58` built as
  `odysseus:candidate-f491d6a1` with image
  `sha256:fc4731a67d33733c1727286d4c4300e214947d7c6a0b3876af562c8e77703537`,
  source/build/frontend provenance, and migration head
  `20260825_002_work_run_completion_v6`.
- The candidate is deployed and `/api/health`, `/api/version`, broker socket,
  Ollama bridge, Qwen sentinel, frontend static, browser-window, and realistic
  browser acceptance all pass. Status: `VERIFIED_DEPLOYED` / `VERIFIED_LIVE`;
  owner-live Luna/Sol swapping, consequential network dogfood, and external
  credential flows remain `OWNER_DOGFOOD_PENDING`.

## Final convergence UI repair checkpoint

- The authenticated product pass found a real P1 in Control Center: its Run
  cards inherited the global fixed-height button rule, so multi-line Run rows
  overlapped. The shared `.control-run-card` layout now grows with content,
  wraps long identifiers, and remains fully clickable. This is a generic UI
  contract repair, not a fixture-specific adjustment.
- Exact HEAD `0d20eddb139b9c1f12785129c087239ce762822f` is deployed as
  `odysseus:candidate-0d20eddb139b` with image
  `sha256:c649536b01371c77c28cda7e83323b6c078c560e140479a27631d8d974809448`.
  `/api/health`, `/api/version`, frontend static verification,
  browser-window, realistic browser, authenticated Setup/Integration/Control
  Center loading, and Control Center non-overlap acceptance pass.
- Full regression is `6273 passed, 3 skipped, 186 warnings in 155.78s`.
  Owner-authenticated cross-model swapping, owner-live network dogfood, and
  external credential flows remain `OWNER_DOGFOOD_PENDING`; no owner authority
  was bypassed.
# P0 owner-dogfood correction checkpoint — 2026-08-25

Evidence level: E3 VERIFIED_TESTED (deployment pending for this checkpoint).

The owner-live retest exposed four generic seams, repaired in commit
`0056bc0c`:

- `read_network_context` now reads host interfaces/routes through the existing
  broker, classifies VPN, host-local, and application-runtime interfaces, and
  emits a context identity plus ownership classification. Docker bridge state
  is not a current user-network target.
- Omitted network discovery scope remains unresolved. Historical observations
  are returned as `HISTORICAL_DISCOVERY` evidence and cannot become current
  scan scope. VPN/corporate/unknown private ranges are not implicitly
  authorized.
- Domain contracts expose default overview reads and read Actions remain
  approval-free; consequential Actions retain exact approval.
- Grounding recognizes durable canonical read/observation evidence, while
  model-only claims and unsupported shell suggestions remain rejected.

Focused control-plane suite: 192 passed. Full regression: 6277 passed, 3
skipped, 186 warnings. Deployment, browser provenance, and owner-live Qwen
retest remain pending for this checkpoint.
