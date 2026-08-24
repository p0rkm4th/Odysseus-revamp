# Hades productization roadmap

## Current checkpoint

- V2 baseline source: `120e4afa9d0cd60fff3f6225c42d131837c6c260`.
- Accepted baseline image: `sha256:b3f65991b7c59ed77118e15ed3e3faae2eea1d02d01169aa20b566ca19f06e97`.
- Accepted regression: `5890 passed, 3 skipped, 174 warnings, 0 failed`.
- Canonical network discovery: `homelab.manage` → `execute_network_discovery` → `manage_homelab` → `host_broker`.
- Fresh Luna and Qwen broker executions, exact approval continuation, CMDB
  observations, Network Map update, reconnect/model-switch/browser/container
  continuity, and immediate referent coverage are accepted stabilization
  evidence. Do not repeat that archaeology unless a regression appears.

## Dependency-ordered batches

1. **P0 baseline freeze:** preserve the accepted stabilization as rollback state and keep network/continuity invariants in regression.
2. **Tier 1 census and grammar:** make capability ownership, module states, authority, intake, dossiers, timelines, provenance, search, and window behavior inspectable and uniform.
3. **Tier 1 self/memory/Life:** unify identity, runtime health, Work state, capabilities, commitments, Attention, memory diagnostics, Episodes/Lessons, reviews, habits, and deterministic briefs on existing stores.
4. **Tier 2 communications:** productize Telegram continuity/voice and Email/Calendar/Contacts/Documents bridges.
5. **P2 local operations:** expand the existing bounded Homelab operation catalog and capability dependency health; then productize Household, IT/CMDB, Network history/change detection.
6. **P3 security/OSINT:** complete authorized assessment and public-source case workflows with evidence-linked reports.
7. **P4 communications/business:** expose Telegram cross-channel continuity, voice, Email/Calendar/Contacts links, and Work-based CRM.
8. **P5/P6 integrations and polish:** Home Assistant, PWA/share intake, multimodal/documents, Improvement/Model Lab/Developer surfaces, accessibility, and final uniformity.

Every batch must update the feature matrix, run focused tests, preserve policy
invariants, and leave a deployable commit. Schema changes require fresh,
rerun, and copied-database rehearsal before promotion. A partial backend or
sidebar entry is not a productized domain.

## V2 continuation checkpoint

The first active batch is the census/grammar boundary. Existing canonical
owners are sufficient for the initial Self, Attention, Work/Life, memory, and
window work; new tables are not justified until a focused gap is demonstrated.

## Completed V2 batches

- Updated the bounded existing-capability census and cross-cutting ownership map.
- Corrected the matrix/roadmap to the accepted `120e4afa…` baseline and made
  Tier 1 acceptance gates explicit.
- Added `PersistentAgent.operating_brief()` and `/api/hades/brief`, a
  deterministic daily/weekly projection over Self, Work review, Attention,
  capabilities, activity, and Episodes. It creates no new canonical state,
  model claims, or action claims.
- Added daily/weekly brief switching to the existing Hades window and focused
  tests for bounded horizon and grounding metadata.
- Extended the existing Ctrl+K conversation search surface with canonical
  module commands. Commands invoke existing module controls only; they do not
  create a UI-only execution path or bypass policy.
- Began the early UI standardization gate: added shared tokens and reusable
  header/state/badge/intake/provenance primitives, made OSINT explicit in the
  primary sidebar and command palette, and added an OSINT workspace with the
  required investigation tabs and review-oriented intake over the existing
  public-source research service.
- Made research intake seeds durable at start in the existing owner-scoped
  research store (`case_stage=intake`, `review_required=true`), so an OSINT
  investigation is recoverable before asynchronous results complete.

## Completed batches in this continuation

- Persisted `AssistantInstance.last_seen_at` and made `/api/hades/while-away`
  default to the persisted marker.
- Added `/api/hades/attention`, projecting unread notifications, blocked or
  awaiting Work runs, and open commitments without duplicating canonical state.
- Preserved notification source entity/run references for overdue commitments.
- Added a Hades workspace Attention Queue section.
- Added a deterministic Work Life Review projection for focus goals, due-soon
  and overdue commitments, due tasks, blocked tasks, and waiting runs.
- Extended the canonical Work Engine additively with durable Run intent/plan/
  assumption/cost/checkpoint/verification fields, explicit lifecycle phases,
  non-mutating Action contract previews, and persisted Action target/lock/risk/
  retry/rollback/postcondition/verification metadata. Existing owner isolation,
  approval sealing, and legacy statuses remain compatible.

## Phase 12+ control-plane sequence

The existing Work Engine remains canonical; no second Run/task engine is being
introduced. Next bounded batches are resource-lock enforcement, epistemic and
temporal evidence, event reconstruction/compensation, evaluation and
OpenTelemetry traces, empirical routing/budgets, then incidents/changes and
the eventual control-center projection.

Resource-lock enforcement is now additive in Work migration v3: Action
contracts can declare shared/exclusive resources, owner-scoped conflicts are
inspectable before execution, and held locks are released on completion. The
epistemic batch is now additive in Work migration v4: typed owner-scoped claims
retain evidence, contradiction references, confidence, Run provenance, valid
time, recorded time, expiry, and stale/current projections. It does not replace
CMDB, Security Evidence, or Network observations.

The Work journal now also supports read-only Run lifecycle reconstruction plus
bounded checkpoints and verification records. The ORM row remains the fast
current projection; replay is diagnostic and does not silently mutate state.

V3 Tier 1 has begun with durable owner-scoped evaluation scenarios, sanitized
trajectory records, supervised failure candidates, review admission, and a
15-case control-plane regression corpus covering grounding, routing, approval,
continuity, scope, identity, and duplicate-read failures. The existing Jarvis
fixture scorer remains the deterministic benchmark projection; no second
benchmark engine was added.

The next observability slice adds an OTel-shaped durable trace projection with
Run linkage, parent/child spans, bounded attributes, automatic sensitive-value
redaction, and low-cardinality metric dimensions. It intentionally does not
archive prompts, raw documents, or secrets and still needs request/Run wiring
and the Developer trace explorer.

Deterministic safeguards now provide canonical action fingerprints, repeated
no-information loop detection, and targeted knowledge-gap classification over
the epistemic ledger. These are advisory projections until execution paths wire
their STOP/replan behavior; they do not grant or change authority.

Resource locking hardening now releases locks on terminal Run states and offers
owner-scoped abandoned/expired lock recovery. Multi-resource requests already
use sorted acquisition order; arbitrary lock deletion remains unavailable.

## Verified execution continuation

The first verified-execution slice is now implemented as an additive
projection over Work: `src/run_planner.py` compiles owner-scoped structured
Run previews from persisted plans/actions and the canonical ActionSpec
registry. It exposes targets/resources, reads/writes, risk, approvals,
verification, compensation metadata, and stale/unknown epistemic gaps without
executing or mutating a Run. Deterministic validation rejects unknown action
contracts, private-network scope violations, missing approval, missing
high-risk verification, invalid compensation claims, and unresolved required
state. `/api/work/runs/{id}/preview`, `/validate`, and `/replay` expose the
projection to the existing Work UI, whose Run dossier now presents the preview
and validation result. This is the preview/validation boundary; execution,
targeted invalidation, compensation, and full lifecycle orchestration remain
the next batches.

Epistemic ledger refinement now preserves competing claims through an explicit
contradiction link and resolution marker in provenance; it never silently
deletes either claim. Targeted execution invalidation marks current claims
stale, and epistemic context/knowledge-gap projections exclude those stale
claims until refreshed while retaining their historical record.

The next epistemic/world-model slice adds `WorldRelationship` to the existing
Work/CMDB boundary. It is owner-scoped and evidence-backed, supports typed
relations such as `RUNS_ON`, `DEPENDS_ON`, `USES`, and `CONNECTED_TO`, preserves
proposed/inferred edges separately from observed or user-confirmed edges, and
provides bounded neighbor and blast-radius projections. It does not replace
the asset inventory database or manufacture topology; existing CMDB adapters
remain the canonical source for technical assets and observations.

The next execution slice adds explicit Work lifecycle transitions for planning,
ready, executing, verifying, compensating, succeeded, failed, and cancelled.
Transitions are fail-closed, journaled, replayable, and emit redacted local
OTel-shaped execution spans. Prechecks are persisted as bounded checkpoints;
operator cancellation is durable; targeted invalidation marks matching current
epistemic claims stale while retaining their historical evidence. This is a
control-plane lifecycle foundation, not an executor: broker/tool bindings and
approval policy remain the authority for real-world mutation.

The World Model now has a visible first-class window using the shared Hades
module grammar. It is discoverable from application navigation and the command
palette, supports entity focus, displays provenance/status distinctions, and
shows bounded blast-radius projections. It remains a read/projection surface;
relationship mutation continues through the authenticated canonical Work API.

The Control Center now exposes the existing durable Run, evaluation, and trace
projections through a focused workspace. Its Run Inspector presents canonical
intent/plan state, preview and validation, knowledge gaps, locks, replay
state, execution spans, and verification. Evaluations remain supervised and
owner-scoped; the surface does not create a second benchmark or execution
engine.
