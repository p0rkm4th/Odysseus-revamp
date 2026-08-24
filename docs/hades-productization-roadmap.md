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
capability exposure, approval, or execution authority. Provider-level live
qualification, richer cost/latency telemetry, routing explanation UI, and
shadow plan review remain future work.

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
