# Hades architecture convergence audit

Status: **bounded archaeology recorded; migration queue active**  
Source basis: `be1435f8` plus prior truth-audit evidence in
`docs/hades-truth-audit.md`. Runtime provenance is not yet deployed from this
source, so live claims remain below E4/E5.

## Lineage

“Original” means the recovered/mature Odysseus implementation family, not
simply an older file. “New” means Hades additions built around durable domain,
capability, ActionSpec, ToolBinding, policy, approval, evidence, and workspace
projections. Compatibility adapters are neither a new truth owner nor a reason
to delete mature implementation logic.

## Decision vocabulary

`EXTEND_ORIGINAL`, `EXTEND_NEW`, `COMPOSE`, `MIGRATE_TO_NEW`,
`MIGRATE_TO_ORIGINAL`, `KEEP_BOTH_DISTINCT`, `DEPRECATE_ORIGINAL`,
`DEPRECATE_NEW`, and `REMOVE_DEAD_PATH` are architectural decisions, not
claims that migration is already complete.

## Subsystem convergence matrix

| Subsystem | Original implementation | New implementation | Current canonical owner / persistence | Strengths and duplication | Decision |
|---|---|---|---|---|---|
| Tool execution | `src/tools`, legacy registries, agent-loop dispatch | Capability Registry, ActionSpecs, ToolBindings, Work/API exposure | ActionSpec/policy/approval path; legacy logic may remain an executor adapter | Original tools contain provider behavior and normalization; legacy consequential bypass risk remains | **EXTEND_NEW**; wrap mature logic, migrate consequential callers |
| Brain / Memory / RAG | `static/js/memory.js`, memory file/manager, Brain UI, vector recall | memory grounding, epistemic claims, Episodes/Lessons, context projections | Domain stores and memory ledger; vector index is derived | RAG is useful retrieval but cannot own truth; overlapping “fact” concepts need boundaries | **COMPOSE** |
| Inventory / Household / CMDB | Inventory routes/models, Cookbook, stock, locations, intake | Household projections, CMDB/IT Assets, Network observations, World Model | Household inventory vs technical CMDB vs relationship projection | Existing inventory/intake is mature; technical identity must not be copied into household | **KEEP_BOTH_DISTINCT** |
| Cookbook / recipes | `static/js/cookbook*.js`, recipe/dependency services | Household recipe projection | Cookbook recipe behavior | New household UI must not duplicate recipe search/import | **EXTEND_ORIGINAL** |
| Work / Tasks / Life | `static/js/tasks.js`, notes/reminders, scheduler UI | Work Engine, Goals, Projects, Commitments, Runs, Missions | Work service for task truth; Run for execution | Legacy UI is useful; duplicate task stores are unsafe | **EXTEND_NEW** via UI adapters |
| Scheduling / monitors | scheduled tasks, TaskRuns, background jobs, reminders | Monitors/Watch direction, Missions | Separate calendar state, scheduled execution, condition monitoring | Similar trigger vocabulary but different semantics | **COMPOSE** |
| Deep Research / OSINT | research panel/jobs, search/fetch/extraction | durable OSINT cases, claims, evidence, reports | Research engine for bounded retrieval; OSINT case ledger | Rebuilding retrieval in OSINT would duplicate provider logic | **COMPOSE** |
| Security | security audit/recon/network tools | bounded Assessment/Engagement/Scope/Finding/Evidence | Security domain owns authorization/scope/finding lifecycle | Mature probes can be bound; no duplicate scanners | **EXTEND_NEW** |
| Network / Homelab | network/system/storage/container/remote operations | CMDB observations, Homelab workspace, verified execution | Canonical asset/observation stores and ActionSpecs | Operation implementations are reusable; UI and authority paths diverged | **COMPOSE** |
| Email / Calendar / Contacts | `emailInbox.js`, `emailLibrary.js`, `calendar.js`, contact/provider services | Setup, health, Work/Business/Commitment links | Existing provider stores/services | Mature provider behavior exceeds planned replacement | **EXTEND_ORIGINAL** with Hades projections |
| Telegram | pairing, callbacks, media, notifications, approvals | Setup/Integration/Permissions projections, voice direction | Existing secure pairing and transport behavior | Security behavior must not be replaced by setup UI | **EXTEND_ORIGINAL** |
| Documents / Library / Notes / Gallery | document editor/library, uploads, gallery/media, notes | shared artifact/evidence links, Share-to-Hades | Document/artifact metadata plus domain references | Similar file UI, distinct note/media semantics | **COMPOSE** |
| Compare / Model Lab | `static/js/compare/*`, provider comparison | competency/routing/evaluation projections | Compare engine for comparison; eval corpus for qualification | Do not create a second comparison engine | **EXTEND_ORIGINAL** |
| Theme / UI / navigation | mature sidebar, icon rail, modal/window behavior | semantic icons, shared Hades grammar, workspace registry | One frontend registry and shared components | Current expanded vs compact paths were parallel; now converging | **COMPOSE**, then converge |
| Window manager | routed/page state and legacy modal manager | `workspaceWindowManager.js`, snap/minimize persistence | One canonical view/entity identity; windows are projections | Separate implementations risk route/entity drift | **EXTEND_NEW** with compatibility adapters |
| Search | global/search-chat, email/library/CMDB/research search | OSINT/RAG/domain projections | Domain search remains specialized; federated result projection can be shared | One backend would erase domain semantics | **COMPOSE** |
| Notifications | legacy/UI/Telegram/reminder state | Attention and canonical notifications | Notification model; transports deliver | Transport-specific truth duplication | **EXTEND_NEW** |
| Settings / Setup | settings panels and config files | SetupContracts, Integration/Permissions projections | Existing canonical settings/config stores | Setup must configure, not duplicate | **COMPOSE** |
| Health | scattered configured/connected/status checks | shared health vocabulary and setup checks | Integration/domain health projection | “Configured” is not “healthy”; explicit gaps remain | **EXTEND_NEW** |
| Model providers | provider settings, Ollama/OpenAI-compatible paths | routing/competence/context projections | provider runtime abstraction plus domain routing | Embeddings/STT/TTS are separate provider classes | **COMPOSE** |
| Context assembly | chat, research, OSINT, memory-specific prompt paths | grounding/context projection direction | Shared context pipeline with domain projections | Independent prompt builders risk missing provenance/policy | **EXTEND_NEW** |
| Action results / errors | arbitrary tool dicts/strings | structured ActionResult and reason codes | ActionResult adapter boundary | Mature internals can survive normalized output | **EXTEND_NEW** |
| Multimodal intake | recovered upload/image/document flows | domain-specific review/intake | shared extraction/provenance pipeline with adapters | Rebuilding upload/extraction per domain would drift | **COMPOSE** |
| Economics | existing economic control plane | model/Run/budget projections | existing cost ledger | No evidence for a second ledger | **EXTEND_ORIGINAL** |
| Improvements | Improvement Registry and candidate lifecycle | supervised improvement plans | existing candidate/evaluation/promotion records | Promotion safety is stronger in existing registry | **EXTEND_ORIGINAL** |
| Execution profiles | broker/provider/runtime profiles | Execution Nodes/Fabric direction | profiles plus node projections | Same trust/privilege dimensions should not be duplicated | **COMPOSE** |
| MCP | existing adapters/schema conversion | ActionSpec/ToolBinding adapters | Odysseus identity/policy/evidence authority | MCP is an interface, not a capability owner | **EXTEND_ORIGINAL** |

## Scoring summary

The newer control-plane primitives score strongest on architectural fit,
security, provenance, and restart-safe orchestration. Original modules score
strongest on mature provider behavior, interaction details, and real-world edge
cases. The convergence pattern is therefore adapters and projections, not a
rewrite: preserve original operation logic where it is strong, but route
consequential authority through the newer canonical contracts.

## High-confidence convergence queue

### P0 — security and policy

- Inventory every consequential path in `src/tools` and `agent_loop`; either
  bind it to Capability → ActionSpec → Policy → Approval → ToolBinding or mark
  it read-only/compatibility.
- Centralize owner resolution, approval digest/replay validation, SSRF/CIDR
  validation, secret redaction, and structured result normalization where
  duplicate security-sensitive copies diverge.

### P1 — canonical truth and execution

- Keep Work task truth, Run execution truth, Calendar event truth, Watch
  condition truth, and Mission objective truth distinct but linked.
- Use domain stores as canonical truth; project semantic/episodic memory and
  vector retrieval without copying facts into multiple stores.
- Wrap mature network, security, communications, research, and intake logic in
  ActionSpec/ToolBinding adapters.

### P2 — product and provider convergence

- Finish WorkspaceDefinition → ModuleDefinition navigation and migrate
  expanded, compact, mobile, search, Setup, Permissions, and window launchers
  to it.
- Reuse original Email, Calendar, Telegram, Cookbook, Compare, document, and
  multimodal behavior beneath Hades projections.

### P3 — internal helpers

- Consolidate only after call-graph evidence proves semantic equivalence:
  pagination, retries, JSON normalization, and generic UI primitives.

## Migration discipline

Every migration requires a source/target owner, data and caller plan, route
compatibility, UI/test coverage, rollback, and a deprecation period. The
preferred strangler shape is `old caller → compatibility adapter → canonical
service`; no legacy subsystem is removable from this audit alone.

## Current convergence evidence

The existing workspace registry was audited rather than replaced. Before this
batch, `static/app.js` maintained a second hard-coded workspace grouping list
while `static/js/workspaceRegistry.js` owned the compact rail. That was a
parallel UI identity path. The expanded grouping now projects workspace member
IDs through `MODULE_BY_ID`; virtual/contextual modules are declared explicitly
with a null legacy DOM binding instead of being silently omitted. Structural
tests assert that every workspace member has label/icon metadata and an
intentional legacy-or-virtual navigation binding.

This is source/focused evidence only. It does not establish deployed browser
acceptance or owner dogfood.

## Reuse metrics (baseline)

- Original subsystems deliberately retained/reused: provider integrations,
  Telegram security, Calendar/Email behavior, Cookbook, Compare, document and
  multimodal intake, mature operation implementations.
- New subsystems promoted: ActionSpec execution authority, Work/Run
  orchestration, exact approvals, CMDB identity, epistemic claims, World Model
  relationships, evaluation corpus, tracing, semantic workspace registry.
- Composed subsystems: Memory/RAG, Household/CMDB, Research/OSINT,
  Calendar/Work, Documents/domain evidence, Execution Profiles/Nodes, Search.
- Deletion is intentionally deferred. No dead path is removed without parity,
  migration, compatibility, and rollback evidence.
