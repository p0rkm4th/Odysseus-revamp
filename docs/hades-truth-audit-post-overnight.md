# Hades post-overnight truth audit

Date: 2026-08-25  
Branch: `recovery/live-candidate-20260823`  
Final source under audit: `38e3f984`

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
