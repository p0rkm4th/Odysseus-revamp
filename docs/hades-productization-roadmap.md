# Hades productization roadmap

### Verified lifecycle compatibility checkpoint

The legacy `WorkEngine.transition_run` path now shares the verified-execution
state graph and execution validation gate. Invalid lifecycle jumps are rejected
and failed plan validation rolls back tentative transition data, so older
callers cannot bypass structured Run validation or leave a Run advertising a
state it did not successfully enter. The canonical Run, ActionSpec, policy,
approval, and journal architecture remains unchanged.

### Setup Center foundation checkpoint

The first Setup Center slice now uses a declarative `SetupContract` registry
and a resumable owner-scoped state projection. It covers module categories,
dependencies, permissions, secret references, safe status values, existing
integration detection, explicit skip/resume, and reconfiguration state. The
new workspace and API are projections only: setup does not resolve or expose
secret values and cannot grant runtime authority. Module-specific credential
flows, safe health operations, and owner-live browser acceptance remain
subsequent work.

The additive `/api/setup-center/integrations` projection gives the owner a safe
connection, permission, and capability summary derived from Setup Center state.

Setup dependency resolution now projects deterministic `READY` or
`MISSING_DEPENDENCY` metadata for every module, including the exact missing
contracts and whether an in-registry remediation path exists. This is
owner-facing setup guidance only: it does not change module status, resolve
secrets, or grant capability authority. Existing-install detection and live
integration health remain separate checks.
It reports no secret values and does not create a parallel integration store or
authority path.

Setup profiles now provide explicit PERSONAL, HOME_HOMELAB, BUSINESS,
SECURITY_RESEARCH, DEVELOPER, EVERYTHING, and custom selection paths. Applying
a profile changes only resumable module selection; it never changes policy,
permissions, secret bindings, or execution authority.

Telegram now has a module-specific Setup Center health operation. It reuses the
owner-scoped `TelegramStore.lifecycle_status` projection to validate pairing,
private-chat, replay-protection, and callback-approval prerequisites without
network calls, bot-token handling, re-pairing, or authority changes.

Email, Calendar, and Contacts now have the same Setup Center readiness boundary.
Checks are owner-scoped and non-mutating: they confirm canonical local
configuration and clearly report when provider connectivity was not probed.
Actual Email/Calendar provider tests continue through their existing routes and
credentials; Setup Center does not duplicate those operations.

Home Assistant Setup Center validation now reuses the existing read-only Smart
Home projection. An explicit owner-triggered check performs only the existing
`GET /api/` and `GET /api/states` adapter calls, reports configured/healthy/
degraded state, and never exposes credentials or invokes entity mutations.

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

### Home Assistant visibility slice

The first Home Assistant slice reuses the existing generic integration and
`api_call` boundary. An owner-authenticated Smart Home workspace now projects
configuration status, health, bounded entity-domain counts, and a small set of
entity references without copying state into a second store or exposing
credentials. No state-changing smart-home action is introduced by this slice;
future mutations must continue through canonical ActionSpec, policy, approval,
and integration authority.

Business/CRM remains a documented product gap because this audit found no
canonical CRM store or service to extend safely; no parallel business database
was introduced.

### Communications projection slice

Communications is now a visible owner-facing overview over the existing
`EmailAccount`, `CalendarCal`/`CalendarEvent`, and Contacts boundaries. It
reports masked account state and bounded upcoming events, while leaving detailed
Email and Calendar windows authoritative and keeping Contacts separate. Legacy
unowned email rows are included only when their mailbox matches the authenticated
owner. No CRM tables or duplicated contact/event stores were added.

### Telegram workspace slice

Telegram is now directly discoverable and exposes the existing owner-scoped
lifecycle boundary: connection status, short-lived pairing-code issuance,
disconnect, and bound Odysseus sessions. The UI does not store bot tokens or
implement a second transport. Private-chat pairing, replay protection,
approval/session binding, and runtime delivery remain owned by the existing
Telegram store/runtime; voice, media, and live cross-channel dogfood remain
future work.

### P0 OSINT UI quality checkpoint

Shared workspace/window and product-grammar primitives now enforce intrinsic
min sizing, overflow wrapping, contained grid tracks, responsive summary grids,
scrollable tab navigation, semantic theme tokens for primary actions, and
accessible window-control tooltips. OSINT overview cards project compact case
metadata rather than raw seed queries. Original known information is rendered
only in a dedicated collapsible `USER PROVIDED` dossier section with safe
escaping and readable prose styling. Realistic adversarial fixtures and
framework-free overlap/containment assertions are included. Rendered browser
acceptance and owner-live visual acceptance remain explicitly pending because
no browser runner or owner session is available in this environment.

### CMDB-to-World-Model projection checkpoint

The existing authenticated Work surface now provides a bounded CMDB sync
projection into the existing owner-scoped WorldRelationship ledger. Canonical
CMDB asset IDs become explicit asset references, supported relationship types
are evidence-tagged with deterministic CMDB references, repeated syncs are
idempotent, and ended CMDB relationships remain stale historical edges.
Malformed or unsupported edges are skipped with structured reasons. CMDB
identity remains authoritative; no IP-only merge or alternate graph store was
introduced.

### Action-result ownership checkpoint

Structured WorkResults now require any supplied Action reference to resolve
through the same authenticated owner and Run. Cross-owner and cross-Run
references fail closed, preventing evidence/result provenance from being
attached to unrelated execution history.

The World Model workspace now exposes the authenticated Sync CMDB action
alongside focus and relationship filters. The action calls the canonical
projection endpoint and refreshes the same relationship view; it does not
create a client-side graph or bypass owner/policy boundaries.

### World Model activity-state checkpoint

World relationships now expose a derived `activity_state` projection. Current
valid edges may participate in bounded traversal, while stale, contradicted,
superseded, and out-of-valid-time edges remain visible as historical/unknown
evidence and cannot silently count as present dependencies. Blast-radius
entries preserve confidence, observation kind, source, and evidence references;
traversal remains depth-bounded and cycle-safe.

### PWA shell continuity slice

The existing service worker cache was updated and versioned to include the
current standardized workspace modules, shared UI components, and window
manager. API requests remain uncached, so authenticated canonical state is not
persisted into the offline cache. Share-target, push notification, camera
intake, and authenticated offline data workflows remain future work.

The manifest now also declares a bounded GET Share-to-Hades target. Shared
title/text/URL values are length-limited, staged in the existing Chat composer,
and removed from the address bar after import; nothing is auto-sent or promoted
into canonical state.

### Voice boundary hardening slice

The existing Web STT/TTS routes now require an authenticated owner before
reading audio uploads, synthesizing text, returning provider statistics, or
clearing the TTS cache. Provider implementations and the shared Chat recorder
remain canonical; this change does not create a second voice stack. Explicit
voice retention, Telegram voice mirroring, and live microphone dogfood remain
future work.

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

Model competence now has a durable owner-scoped projection derived from
EvaluationRun records. Qualification requires sample evidence, exposes sample
count/success rate/recent performance/failure classes, and distinguishes
unknown, experimental, qualified, degraded, and disqualified states. The
Control Center surfaces this evidence; it does not silently alter routing or
promote a model from a single successful run.

Incident/Change foundations are now additive and owner-scoped. Incidents keep
symptoms, affected references, timeline, hypotheses, evidence, root cause, and
outcome; Changes reference existing Runs and deterministic Run previews for
targets, actions, risk, resources, and verification. The Control Center shows
their status projections. Neither object executes Actions directly; Work and
the existing ActionSpec/ToolBinding/policy path remain authoritative.

Incident hypotheses now support owner-scoped updates with preserved supporting
and contradicting evidence, while evidence intake appends canonical references
and timeline events instead of rewriting history. Change lifecycle transitions
reuse the existing Run and verification projections; a Run-linked Change cannot
be marked completed until that canonical Run is completed and verified. These
are additive projections over Work/Run, not another incident executor or action
engine. Live safe-service remediation dogfood remains pending.
## P0 memory grounding gate (current continuation)

The existing Brain store remains canonical. Explicit owner questions now use a
deterministic read projection rather than relying only on vector relevance or
model-selected tools. The projection is protected through Qwen/local-model
shaping and context trimming, returns retrieval-failure/zero-result status
honestly, and keeps Skills separate from personal memory. Focused synthetic
tests are green. Live owner-authenticated dogfood and browser/restart
verification remain. Sanitized memory diagnostics now travel with the stream
and saved turn metrics, and Brain exposes an Inspector view without rendering
memory content in telemetry.

### Empirical model routing slice

The existing evaluation-derived competence projection now provides an
owner-scoped, candidate-limited recommendation endpoint and the deterministic
local route exposes task class plus sanitized recommendation reasons. A model
is never called qualified without sufficient evaluation evidence; degraded or
disqualified candidates are excluded, and no recommendation changes policy,
capability exposure, approval, or execution authority. High/critical risk
requests require qualified evidence, while privacy-local, latency, and cost
constraints filter candidates with explicit rejection reasons. Provider-level
live qualification, richer telemetry, routing explanation UI, and shadow plan
review remain future work.

The evidence matrix projection now groups measured competence by task class and
model, exposing sample counts, recent success, qualification, failure classes,
and evidence references in Control Center's Routing view. It remains
descriptive only: it does not select a model, alter policy, expose capabilities,
or grant authority. Live provider qualification, cost/latency optimization,
and shadow plan review remain future work.

### Mission projection slice

Missions now reuse canonical WorkGoals marked with an explicit operating-mode
constraint and project linked WorkRuns, success criteria, deadlines, lifecycle,
and stable goal references. The projection now also exposes mission budget,
allowed capabilities, linked checkpoints, blockers, and an explicit
authority-unchanged marker. Control Center exposes Mission inspection. This is
not a second scheduler or task engine; Watch behavior remains owned by the
existing bounded Monitor engine. Restart-persistent mission orchestration and
live dedupe dogfood remain future work.

The existing Watch/Monitor state is now also visible in Control Center with
condition, source domain, enabled state, consequence tier, and last-trigger
metadata, plus a deterministic response-policy label (`observe`, `notify`,
`create_work`, or `execute_pre_authorized_action`). The surface is read-only;
it does not grant authority or execute a response. Current evaluation remains
conservative and emits notifications only; higher response tiers require a
future explicit policy/delegation integration.

### Execution-node eligibility slice

The existing owner-scoped execution-node registry now projects deterministic
eligibility explanations for platform, architecture, runtime, capability,
privilege, trust, network, sandbox, memory, and GPU requirements. Selection
returns eligible nodes plus bounded rejection reasons, and explicitly marks
the result as a projection whose authority is unchanged. Control Center node
cards expose health, trust, heartbeat, and the fact that the current broker
remains authoritative. This does not migrate execution or grant a model node
selection authority; broker adaptation, live heartbeat dogfood, and sandbox
execution remain future work.

### World Model blast-radius integration

RunPreview now consumes the existing evidence-backed World Model for declared
Action resources. It preserves confirmed, likely/inferred, and unknown impact
classes and follows bounded multi-hop relationships, so a host plan can expose
downstream service dependencies without manufacturing topology. This remains a
projection; CMDB identity, ActionSpec scope, and execution policy remain
authoritative.

### World Model inspection checkpoint

The shared World Model window now exposes relationship validity and recorded
time, evidence-reference counts, confidence and observation class, relation and
status filters, bounded two-hop neighbors, and blast-radius impact entries with
provenance. Unknown dependency gaps remain visible instead of being converted
into asserted topology. The surface remains a read projection over canonical
CMDB/Work relationships; relationship mutation and authority stay owner-scoped
on the existing API.

### Execution-node registry foundation

An additive owner-scoped execution-node registry now records platform,
architecture, runtimes, capabilities, privilege classes, network reachability,
health, utilization, and heartbeat metadata. Deterministic selection can filter
eligible nodes for requirements, but node metadata does not grant authority or
replace the host broker. Existing execution remains unchanged; sandboxing,
delegated grants, and migration of scheduling are future phases.

### Delegated-grant scope hardening slice

The existing exact delegated-capability grant path now enforces persisted
parameter constraints at consumption, requires a target whenever the grant
declares target resources, and rejects constraints that disagree with the
sealed approved Action input. Owner, Run, Action, capability, digest,
expiration, revocation, and call-limit checks remain fail-closed. This is a
narrowing layer over existing approvals and the trusted binding boundary, not
a replacement authorization engine; grant issuance orchestration and live
worker delegation remain future work.

### Disposable-sandbox metadata foundation

The existing execution-node boundary now has an owner-scoped durable
`SandboxSession` projection linked to a canonical Work Run and eligible
non-privileged node. It validates bounded workload types, resource limits,
network-none/allowlist policy, lifecycle transitions, artifact references, and
cleanup timestamps. Control Center exposes the lifecycle and explicitly shows
that the runtime adapter is not configured. No commands, containers, host
secrets, Docker socket, host-root mount, or privileged execution are enabled;
the trusted runtime adapter remains a separately reviewed future phase.

### Delegated capability grant foundation

Short-lived owner-scoped grants now bind an existing approved WorkAction to its
Run, capability, target resources, sealed input digest, expiry, and bounded
call count. Grants can be revoked and consumed exactly within those bounds;
wrong owner, action, digest, target, expiry, replay, and call-limit cases fail
closed. They carry no secret or reusable credential and do not widen policy.
Integration with trusted ToolBindings and a dedicated grant inspector remain
future work. The current checkpoint adds both: a trusted-caller-only binding
boundary check that consumes an exact grant before the capability executor, and
read-only Control Center projections for execution nodes and grant scope. The
grant is optional and only narrows authority; existing policy, exact approval,
disabled-tools, owner, and broker checks remain authoritative.

### Verified execution continuation checkpoint

The execution-fabric slice now has an owner-scoped node registry and exact
delegated grants over existing approved WorkActions. The trusted binding
wrapper accepts a grant only through an orchestrator-supplied keyword (never
from model arguments), consumes it fail-closed against Run/action/capability/
digest/target scope, and then invokes the existing binding. No policy or
approval gate is bypassed and no secret is carried by the grant. Control Center
now exposes read-only Execution Nodes and Delegated Grants tabs. Focused tests,
including binding-boundary consumption and UI coverage, are green; live broker
node heartbeats and consequential grant-backed execution remain pending safe
owner-authenticated dogfood.

### Action Contract inspector slice

The existing Run Inspector now expands each canonical planner contract into
owner-visible reads, writes, target resources, preconditions, locks,
idempotency/retry semantics, state invalidations, verification, and honest
compensation/rollback metadata. Run-scoped delegated grants are shown with
scope and call/expiry state; sealed digests remain redacted. This is a
projection over ActionSpec/Run state and adds no execution authority. Focused
UI, grant-security, and JavaScript syntax checks are green.

### Evidence Explorer projection slice

The existing owner-scoped `EpistemicClaim` store is now available through a
read-only Work API and Control Center Evidence tab. The projection surfaces
claim class, subject/predicate, source, confidence, status, valid-time, and
counts of supporting evidence and contradictions. It does not merge claims,
resolve contradictions, expose private reasoning, or create a second evidence
store; existing WorkEngine claim and contradiction methods remain canonical.
Selecting a claim opens an owner-scoped Evidence Explorer lineage view showing
the claim, opaque evidence references, linked contradictions, derived claims,
and resolution status. Expanded epistemic classes remain additive to the
existing taxonomy and do not rewrite historical records.

### World Model reconciliation and routing evidence slice

World Model relationships now have an owner-scoped bounded update path for
status/provenance/evidence/valid-time reconciliation. Updates emit a durable
WorkEvent and never delete historical relationship records. The empirical
competence recommendation projection now includes selected sample count,
success and recent-success rates, failure classes, and evaluation references;
these are explanatory evidence only and cannot grant capability or change
policy. Focused owner-isolation, reconciliation, competence, and UI tests are
green.

### Incident/Change control-plane integration slice

The existing Change service now embeds deterministic RunPlanner validation and
World Model blast-radius projections when a Change references a canonical Run.
Change creation and transitions into validated/approval/scheduled/executing/
verifying states now refresh that validation and fail closed on invalid linked
Run plans; Change remains a projection and WorkEngine remains execution owner.

Mission-linked Run validation now also enforces the Mission's explicit
`allowed_capabilities` list. A Mission projection cannot widen capability
authority, and an omitted list remains an unrestricted-but-policy-bound Mission
for compatibility with existing Goals.
Tier-3 Watch response policy now requires a persisted owner-scoped delegated
grant reference. Evaluation rechecks that grant and falls back to notification
when it is unavailable; the Watch never executes the grant implicitly.
ActionSpecs can declare bounded execution requirements; RunPreview exposes them
and RunPlanner rejects the plan when no owner-scoped healthy node satisfies
them. Node selection remains a scheduling projection and does not alter
ToolBinding or broker authority.
Change dossiers expose current Run lifecycle, verification, result, and error
state. Incident dossiers expose linked Run state through their existing Change
references. No execution engine was added: WorkEngine remains responsible for
execution, approval, locking, invalidation, and verification.

### Incident/Change dossier slice

The existing Incident and Change projections now have owner-scoped detail
reads. Control Center cards open dossiers showing symptoms, affected systems,
hypotheses, evidence/timeline, linked Changes, deterministic previews,
approval/compensation metadata, verification, and canonical references. Work
Runs and ActionSpecs remain the only execution authority; this slice adds
inspection and cross-link visibility, not a second executor. Synthetic dossier
and owner-isolation tests are green; live safe-service remediation dogfood
remains pending.

### Verified outcome slice

WorkEngine now provides deterministic verification and compensation outcome
transitions over the existing Run lifecycle. A failed postcondition ends in a
distinct verification-failed outcome unless an explicit compensation
reference is supplied; successful compensation returns the Run to restoration
verification; final outcomes distinguish verified execution, compensated
restoration, verification failure, and compensation failure. These methods do
not execute bindings themselves, and exact approval/policy/broker authority is
unchanged. Focused lifecycle/replay tests are green; live safe-service
dogfood remains pending.
Watch evaluation now honors the existing bounded response tiers for the
reviewable middle tier: a tier-2 trigger creates a queued, owner-scoped Work
Run proposal with `review_required` and never executes an Action. Tier 0/1
remain observation/notification projections, and tier 3 remains explicitly
non-executing until a separate delegated-authority policy is implemented.
### OSINT dossier visibility slice

The existing owner-scoped research detail route is now used by the visible
OSINT workspace. Cases are actionable records rather than inert cards, and the
dossier renders escaped report/summary text, source references, per-source
findings, status, timing, and metadata with explicit tainted-content
provenance. It does not infer Facts or Inferences from external text and does
not create a second OSINT store. Relationship graph, corrections, and bounded
delta research remain future work.

### Household canonical projection slice

The existing owner-scoped InventoryService now exposes read-only Household
overview and append-only history projections over canonical items, lots,
movements, recipes, and intake drafts. The overview includes stock quantities,
reorder-point warnings, expiring lots, pending review drafts, recent activity,
freshness, and explicit canonical-store metadata. The Household workspace uses
the projection for its module header, summary metrics, needs-attention state,
reviewable intake state, and activity list while item dossiers continue to use
the existing owner-scoped item route. No Household database or duplicate stock
ledger was introduced; owner isolation and explicit review boundaries remain
unchanged.

### IT Assets source-boundary workspace slice

The IT Assets workspace now presents the existing InventoryService asset store
and canonical CMDB map as two explicit sources, with metrics for user-entered
assets, canonical CMDB assets, unidentified observations, and total observed
nodes. Existing dossiers remain owner-authenticated and provenance-visible.
The UI explains that IP-only observations are not canonical identities and
does not silently merge Inventory assets with CMDB records. This is a product
projection only; reconciliation, discovery, and broker authority remain in
their existing canonical services.

### Network canonical map workspace slice

The existing owner-authenticated Network window now consumes the canonical CMDB
map projection with visible counts for nodes, canonical identities,
unidentified observations, and active relationships. It presents the existing
IP-only identity rule and provenance boundary directly, keeps unidentified
observations non-canonical, and reuses CMDB dossiers for node inspection.
No alternate topology store or identity merge path was introduced; discovery,
observation persistence, and reconciliation remain owned by the existing CMDB
and Network services.

### OSINT evidence presentation slice

The visible OSINT dossier now reports recorded source counts from the canonical
research library and separates Summary/Report, Sources, Findings/Evidence, and
Facts/Inferences sections. The latter explicitly states when no separate
canonical claim ledger is attached; report text is never silently promoted into
facts or inferences. External content remains escaped, tainted, and
provenance-labelled. Canonical graph, corrections, and delta research remain
future work.

### OSINT attachment evidence slice

The existing OSINT intake now accepts up to five owner-uploaded attachment
references through the canonical upload handler. Files remain owner-scoped and
confined to the upload store; existing document and vision processors are
reused to produce bounded evidence labelled as untrusted external content.
Extraction is capped per attachment and in aggregate, and the start response
does not echo extracted content. The research session retains the evidence for
the existing bounded research path, while canonical facts/inferences still
require the existing review and provenance boundaries. Live provider research
and richer correction/delta workflows remain pending.

### OSINT canonical claim ledger slice

The OSINT dossier now projects owner-scoped, case-bound claims from the
existing Work `EpistemicClaim` ledger using the subject reference
`osint:case:<session_id>`. Claims retain class, source, confidence, evidence,
status, and contradiction references, and a lineage endpoint is available for
Evidence Explorer integration. An explicit owner action is required to record
a claim; crawler report text and tainted findings are never auto-promoted.
Case-specific delta research, richer correction controls, and live provider
dogfood remain pending.

### Documents shell visibility slice

The existing canonical Document module and Library modal are now reachable from
the rendered primary sidebar through the actual `tool-library-btn` binding. The
visible label is Documents, while the existing library/research/archive tabs,
editor, upload, and preview paths remain the implementation owner. The command
palette also exposes Open Documents. A second document store or editor was not
introduced; entity dossier linking and broader document provenance remain
future product work.

### P0 memory grounding gate

The existing Brain store is canonical; no second memory engine was introduced.
The repaired path recognizes explicit owner-memory wording including “all the
information you have about me,” classifies it into the existing memory domain,
and projects the existing structured owner-scoped Memory Result. Qwen/compact
routes now preserve explicit `OK`, `ZERO_RESULT`, and `RETRIEVAL_FAILED` status
instead of reducing the result to optional bullet facts. Automatic procedural
Skills are suppressed for explicit Brain reads, so a Skill such as
`obsidian-rag-maintenance` cannot substitute for personal memory. Sanitized
context/provider traces record counts, roles, section location, token size, and
presence without recording memory content. Synthetic regression coverage is
green; authenticated live owner-memory dogfood remains the next acceptance
step.

### OSINT claim correction checkpoint

The existing Work epistemic ledger is now projected into OSINT cases through
owner- and case-scoped `osint:case:<session_id>` references. Reviewed claims
retain provenance, evidence, confidence, time, status, and contradiction
links. A case-scoped contradiction endpoint rejects claims from another case
or owner, while preserving competing history. The owner can now explicitly
confirm, mark stale, retract, or supersede a claim through a canonical review
endpoint; prior evidence remains available through inactive-claim inspection.
Report prose and tainted research findings are not auto-promoted. Open
questions, delta research, and owner-live provider dogfood remain future work.

### OSINT open-question checkpoint

Research cases now persist owner-scoped open questions in the existing case
projection with status, reason, relevant entity, required/current evidence,
resolution, and status history. The dossier can add questions and mark them
answered; unanswered and blocked questions remain visible rather than being
closed by generated report prose. Updates use atomic replacement of the
existing owner-checked case JSON and do not create a second research store.

### OSINT delta checkpoint

Cases can now record a bounded delta checkpoint containing source references
and fingerprints of the case-scoped canonical claims. A deterministic compare
projection reports new/removed sources, new or changed claims, stale or
retracted claims, and contradiction changes. It does not launch external
research or assert an external change without current evidence; full bounded
delta retrieval remains future work.

### Theme-aware icon and semantic token checkpoint

The shared theme system now derives a complete semantic token layer for each
registered palette, including surfaces, text, borders, accent, icon states,
status, and epistemic states. Shared module headers use the centralized icon
registry, and legacy sidebar destinations missing inline icons are hydrated
from that same registry. Themeable icons inherit `currentColor`, so selected,
hover, disabled, and normal states follow live theme changes without per-module
color hacks. Base-theme validation falls back safely for incomplete custom
palettes. Synthetic contract/syntax tests and the full regression are green;
owner-authenticated browser theme acceptance remains pending.

### Sidebar grouping checkpoint

The existing Tools destinations are now grouped in-place into Personal,
Communications, Technology, Investigation, Work, Knowledge, Agent, and System
sections. Groups are collapsible, keyboard-operable, and persist their open /
closed state under a versioned frontend key. Existing destination IDs and
route bindings remain intact, including legacy Compare, Cookbook, Theme,
Gallery, Notes, and Tasks compatibility entries. This is a navigation
projection; backend functionality was not removed or duplicated.

### Frontend/runtime diagnostics checkpoint

`GET /api/version` now exposes non-secret source commit, image identifier,
frontend build identifier, and UI-state schema version fields with explicit
`unknown` fallbacks. Developer Mode projects these alongside the active local
theme. This supports diagnosing stale browser/container generations without
exposing credentials or private content.

### Structured RunPreview checkpoint

The existing `RunPlanner` projection now exposes canonical target/entity
resources, effect classes, capability availability, and per-action
reversibility/compensation metadata alongside its existing reads, writes,
locks, approvals, knowledge gaps, blast radius, and verification fields. This
remains an additive projection over Work Runs and registered ActionSpecs; it
does not create a second planner or grant execution authority. Focused planner,
verified-execution, and Work tests pass. Full consequential execution,
compensation orchestration, and owner-live dogfood remain pending.

The canonical WorkEngine now provides a narrow trusted-binding orchestration
seam. It revalidates the persisted Run before dispatch, honors cancellation and
resource locks, accepts only a structured result from runtime binding code,
persists provenance-bearing output, and records binding failure with lock
release. It does not accept model-supplied commands or tool names. Concrete
binding adapters, ambiguity handling, compensation dispatch, and live
consequential dogfood remain pending.

The adapter boundary now reuses the registered ToolBinding executor map for
validated Work actions. It normalizes the existing executor tuple into a
structured result and rejects unknown bindings, while preserving the existing
policy, approval, owner, disabled-tool, and broker checks in the executor path.

Ambiguous binding outcomes now enter a durable `execution_ambiguous` Run state.
The originating Action is marked with an ambiguity error, resource locks are
retained, blind retry is rejected, and an owner-scoped resolution endpoint
requires independent evidence that the mutation occurred or did not occur.

Plan validation now also checks the existing owner-scoped active lock
projection and returns a structured `lock_conflict` failure before a plan can
be treated as ready. Lock acquisition and authority remain owned by
WorkEngine; this is an additive validation guard rather than a second locking
system.

The durable Run transition to `executing` now invokes the same canonical
validation projection for Runs that carry a plan or persisted Action. Invalid
scope, approval, knowledge-gap, compensation, verification, or lock state
therefore fails closed before the lifecycle advertises execution. Empty
projection-only Runs remain available for non-consequential orchestration.

Cancellation semantics now distinguish pre-mutation cancellation from an
in-flight Action. Before mutation, the Run becomes terminal and releases its
locks. During execution, cancellation is durable, blocks new Actions, and
requires the bounded Action to reach verification before cancellation can be
finalized, avoiding an unverified unknown state.

Retry behavior now fails closed for unknown or non-idempotent contracts. Only
an explicitly replay-safe/idempotent ActionSpec may create a bounded retry;
the retry is a new persisted Action and exact approval references are never
copied across attempts. Ambiguous or unsafe mutations therefore require fresh
verification rather than blind repetition.
The Run Inspector exposes this path only for failed/expired Actions; the UI is
still a projection and the Work route enforces owner scope and replay-safe
ActionSpec semantics.

### Run Preview inspector checkpoint

The existing Work and Control Center views now visibly consume the structured
preview fields rather than only rendering action prose: canonical targets,
effect classes, capability health, reversibility/compensation, approvals,
knowledge gaps, and verification are available in the Run detail surface.
This is page/window-compatible projection work over the existing Run and
ActionSpec paths. Owner-authenticated live acceptance of consequential work
remains pending.

### Bounded invalidation propagation checkpoint

State invalidation remains history-preserving and owner-scoped. An explicit
invalidation rule may now propagate one hop through an observed or
owner-confirmed, high-confidence World Model dependency; proposed or inferred
edges do not propagate stale state. This keeps dependent service observations
honestly stale without invalidating unrelated claims or inventing topology.
Focused verified-execution coverage is green; broader executor integration and
live safe-operation dogfood remain pending.

### Competence measurement checkpoint

Empirical model competence recomputation now orders evaluation runs
deterministically and aggregates available latency, token, and numeric cost
measurements into the existing owner-scoped competence projection. Qualification
still requires the existing evidence threshold and remains advisory: it cannot
grant capability or bypass policy. Shadow review and broader measured routing
optimization remain future work.

Safety-sensitive evaluation failures now disqualify the affected model/task
pairing during recomputation, even when aggregate success is otherwise high.
This qualification state remains advisory and cannot grant or remove runtime
authority; policy and capability exposure remain authoritative.

### Incident evidence/Run integration checkpoint

Incident evidence may now reference only an owner-scoped existing Work Run.
Incident dossiers aggregate Runs linked through Changes and evidence timeline
events, preserving lifecycle, verification, and result state without creating a
second executor. Cross-owner or nonexistent evidence Run references fail
closed; diagnostic evidence history remains intact.

### Mission/Watch lifecycle checkpoint

Mission projections now derive `WAITING` from durable approval/input Runs and
`EXPIRED` from an active mission deadline without rewriting canonical Goal
status. Watch notification dedupe keys now include the durable trigger event,
so cooldown permits distinct later notifications while the same event remains
deduplicated. Response tiers remain bounded and do not grant authority.

### Execution-fabric safety checkpoint

Delegated capability consumption now uses an atomic persisted call-limit guard,
so concurrent trusted callers cannot both consume the final call of a scoped
grant. Disposable sandbox metadata creation requires a verified healthy,
non-privileged execution node rather than treating an unknown-health node as
ready. No runtime sandbox adapter, Docker socket, or new execution authority
was introduced; the current broker remains the canonical executor.

### Homelab visible authority slice

Homelab is now directly discoverable in the primary application navigation. Its
workspace projects the existing `homelab.manage` capability health, broker
health, execution environment, bounded operation areas, and current CMDB
observation counts. The surface explicitly states that ActionSpec, policy,
approval, and the existing privileged host broker remain authoritative; it
does not add a shell, Docker socket, or alternate executor. Service/storage/
container health detail and live safe-operation dogfood remain future work.

### Security assessment dossier slice

The existing Security panel now exposes the canonical assessment lifecycle in
the shared product grammar: authorization, scope, targets, runs/activity,
evidence, finding candidates, confirmed findings, and a grounded report
projection. Report output is generated through the existing owner-scoped
SecurityAssessmentService and rendered as escaped canonical data; the UI does
not create findings, widen scope, or execute assessment actions. Timeline,
remediation/verification UX, and live authorized dogfood remain future work.

### Theme-aware legacy navigation checkpoint

The shared icon registry and semantic theme tokens were already present, but
five legacy sidebar rows were still plain text. Household, IT Assets, Network,
Developer, and Hades now use theme-inheriting currentColor SVG icons in the
legacy compatibility navigation. This closes the concrete missing-icon slice
without creating a second navigation implementation. Synthetic theme/browser
coverage is distinct from owner-authenticated live acceptance.

### Canonical ActionResult checkpoint

The existing WorkEngine completion path now persists an optional structured
Action result as a durable WorkResult tied to the owner-scoped Run and
RunAction. References, metadata, provenance, and content digests remain
structured and inspectable; action completion still does not imply desired
state verification. No second executor or result store was introduced.

### OSINT epistemic projection checkpoint

OSINT case claim reads continue to use the existing owner-scoped Work
EpistemicClaim ledger. The case projection now returns structured counts by
claim class and lifecycle status, including claims carrying contradiction
references. The dossier surfaces this summary alongside the existing
provenance/taint boundary, so Facts, Retrieved Claims, Inferences, stale
records, and contradictions remain visibly grounded in canonical state. Report
prose and external findings remain tainted artifacts and are not promoted into
claims. Broader graph/timeline integration and live provider dogfood remain
future work.
