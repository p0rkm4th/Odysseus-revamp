# Hades feature matrix

Checkpoint: V2 starts from accepted stabilization source
`120e4afa9d0cd60fff3f6225c42d131837c6c260`.

Status is intentionally conservative: `green` means the current acceptance
evidence is real, `partial` means useful backend capability exists but the
product workspace or dogfood gate is incomplete.

| Domain | Backend | Capabilities/routing | UI/windows/search | Tests | Live dogfood | Status / next gap |
|---|---|---|---|---|---|---|
| Self/continuity | present | present | partial | green | stabilization accepted; product dogfood pending | status, while-away, Episodes, Notifications, Monitors, Attention; unified self dossier and health explainability remain |
| Work/Life | present | partial | partial | green | partial | deterministic review provides focus/due/blocked/waiting projection; richer Life intake, reviews, habits, and timeline remain |
| Missions / Watches | present via WorkGoal projection and existing Monitor engine | `/api/work/missions` projection includes lifecycle, constraints, budget, allowed capabilities, checkpoints, and blockers; bounded Monitor routes expose response policy and tier-2 reviewable Run proposals | Control Center Mission dossier and Watch projection | focused Mission/Monitor/proposal tests plus synthetic cross-domain dogfood | synthetic projection and shared-Run dogfood complete; live restart/dedupe dogfood pending | Missions reuse Goals/Runs and Watches reuse Monitors; Mission projection derives WAITING/EXPIRED from durable state; linked Run validation enforces Mission `allowed_capabilities`; cooldown-aware trigger-event dedupe permits distinct later notifications; tier 3 requires an active owner-scoped delegated grant and downgrades to notification when unavailable; no Watch executes merely because it triggered |
| Execution nodes / fabric | present as owner-scoped registry around current broker boundary | register, heartbeat, list, deterministic requirements selection with rejection reasons and resource requirements; ActionSpec execution-requirement projection/validation; sandbox metadata lifecycle; sandbox creation requires a verified healthy, non-privileged node; no authority grant | Control Center Execution Nodes and Sandboxes inspection shows health, trust, heartbeat, runtime-adapter status, and unchanged broker authority | focused owner-scope/eligibility/sandbox/migration/UI tests | synthetic registry and sandbox lifecycle only; live broker/sandbox adapter pending | current broker remains canonical executor; ActionSpec requirements fail closed when no eligible node exists; actual sandbox runtime and scheduling migration remain |
| Delegated capability grants | present over WorkAction approval/digest state | exact Run/Action/capability/target/digest grants with expiry, revocation, atomic persisted call limits, and enforced parameter constraints | Control Center Delegated Grants inspection; trusted-caller binding narrowing | focused fail-closed scope/owner/replay/parameter/target/binding tests | synthetic grant dogfood only | grants are not credentials and cannot widen authority; full orchestrator grant issuance remains deliberate/future |
| Durable Runs / Action Contracts | present (src/work_engine.py, core/work_models.py, src/run_planner.py) | work.run.read, work.run.manage, preview/validate/replay/execution/verification projections | partial; full executor/compensation UI pending | focused Work/planner/execution/registry/binding/ambiguity/compensation/agent-bridge tests | synthetic lifecycle and same-Run continuity E2; owner-live consequential execution pending | additive structured RunPreview now projects targets/entities, effect classes, capability health, reversibility/compensation, reads/writes/resources, knowledge gaps, approvals, blast radius, declared prechecks, and verification; deterministic validation reports active resource-lock conflicts and blocks declared prechecks until successful evidence is recorded; completed Actions can now persist structured provenance-bearing WorkResults, with owner/Run-bound Action references; trusted Work binding adapter now reuses the registered ToolBinding executor map and normalizes structured results without adding a model-facing path; trusted binding orchestration validates the persisted Run, enforces cancellation/locks, invokes only a runtime callback, and durably records structured success/failure; actionable chat turns now create/reuse one owner/session Work Run and consequential bound results advance through ready/executing/verifying without claiming verification success; ambiguous binding outcomes now enter a durable execution-ambiguous state, retain locks, block blind retry, and require independent resolution through the Work API; persisted compensation contracts now dispatch through a trusted callback and transition successful restoration to mandatory verification, while failures remain explicit; cancellation before mutation is terminal, while cancellation during execution prevents new actions and requires minimum verification; explicit replay-safe contracts can create a new retry Action without copying exact approval, and Run Inspector exposes that bounded retry control; targeted invalidation now supports explicitly declared one-hop propagation through strong observed/confirmed World Model dependencies; legacy transition callers now share the verified lifecycle graph and fail-closed validation with rollback on rejected execution; every persisted Action now receives a canonical normalized-input digest, and validation exposes malformed input, unavailable/mismatched execution paths, missing scoped targets, and missing exact-approval digests as structured failures; explicit verified-execution transitions, prechecks, OTel execution spans, lock recovery, and temporal claim projection remain; richer compensation inspector remains | 
| Evaluation corpus / failure regression | present (core/evaluation_models.py, src/evaluation_service.py, benchmarks/jarvis/control_plane_v1.json) | existing benchmark scorer plus durable owner-scoped scenarios/runs/failures | UI pending; CLI/fixture foundation | focused service + corpus validation | deterministic fixture validation complete; live trajectory dogfood pending | supervised failure review and 15 historical regression seeds exist; trajectory scoring UI and production-failure ingestion remain |
| OTel-compatible observability | present (core/observability_models.py, src/observability.py) | trace projection foundation; request/Run adapters pending | Developer trace UI pending | focused redaction/span tests | deterministic span persistence pending live request wiring | redacted bounded spans, Run linkage, parent/child IDs, and low-cardinality metric projection; provider/exporter wiring remains |
| Loop / knowledge-gap safeguards | present (src/control_plane_safety.py, WorkEngine projections) | deterministic action fingerprints and epistemic requirement checks | diagnostics/UI pending | focused safety + Work tests | deterministic unit dogfood complete | repeated no-information calls can stop/replan; requirements classify known/stale/unknown; execution wiring and UI remain |
| World Model / epistemic relationships | present (core/work_models.py, src/world_model.py, WorkEngine claims) | owner-scoped relationships + bounded reconciliation, contradiction/lineage API; authenticated CMDB sync projection | visible World Model window and navigable Control Center Evidence Explorer, focus/search, Sync CMDB action, evidence/status badges, validity/freshness/evidence display, relation/status filters, bounded neighbors, blast-radius impact provenance and unknown-gap view | focused relationship/reconciliation/contradiction/lineage/planner/UI/CMDB-sync tests | synthetic dependency graph and visible projection dogfood complete | evidence-backed typed edges, explicit competing claims, stale-state projection, bounded neighbors, confidence/status filtering, temporal edge filtering, multi-hop RunPreview blast-radius projection, idempotent CMDB edge projection; derived activity_state separates active current impact from historical edges, while inferred/proposed edges remain likely with confidence/provenance and stale/contradicted/superseded/time-invalid edges remain unknown; broader domain ingestion remains |
| Memory | present | present; explicit owner-scoped Brain read projection via `summarize_owner_memory` / `search_memory` / `inspect_memory` | partial; Brain inspector now shows sanitized passive/explicit/provider projection diagnostics | green | live owner-memory dogfood pending | explicit wording now routes to canonical Memory, Qwen compact projection preserves zero/failure status, automatic Skills are suppressed for Brain reads, owner scope and retrieval-failure language remain authoritative; TTL/supersession and richer inspector UX remain |
| Notifications/monitors | present | partial | partial | green | partial | Attention and monitor primitives exist; cooldown-aware trigger-event dedupe permits distinct post-cooldown notifications while preserving owner dedupe; transport center and notification dogfood remain |
| Household | present via canonical InventoryService | inventory list/search, reviewable intake, recipes, stock projections | Household window now shows canonical overview, risk, intake, and activity; item dossier reused | green | projection dogfood pending | locations, recipe/shopping UX, and live intake dogfood remain |
| Smart Home / Home Assistant | present via generic integration boundary | existing authenticated `api_call` integration; read-only health/state projection; Setup Center safe-read validation reuses the existing adapter | visible Smart Home window plus Setup Center validation with configured/healthy/degraded state and authority boundary | focused projection/UI/setup tests | credentials-dependent | state-changing entity actions, rooms/presence, and richer entity dossiers remain policy-gated future work |
| Communications | present via canonical EmailAccount, CalendarCal/CalendarEvent, and Contacts stores | owner-scoped Email/Calendar projection; Contacts remains a linked canonical store; Setup Center contracts declare read/write/approval boundaries | visible Communications overview links the existing detailed Email/Calendar surfaces without copying records; Setup Center exposes bounded non-mutating readiness checks | focused projection/UI/setup tests | credentials/data-dependent | provider connectivity uses existing Email/Calendar operations; richer contact dossier and Email/Calendar/Business Work bridges remain |
| Setup Center / SetupContracts | present via `src/setup_center.py` and owner-scoped setup state | declarative module contracts, dependency readiness, profiles, permissions, secret references, skip/resume/reconfigure state; metadata-only existing-install detection | first-class Setup Center workspace with category/status projection, explicit profile selection, Permissions/Authority projection, safe non-mutating core/domain health checks for models, memory, OSINT, network, Homelab, communications, Home Assistant, Work/Business, Voice, and Automations; skip/resume, safe authority explanation, secret-free responses, and deterministic READY/MISSING_DEPENDENCY metadata; Integration Center API projection maps setup health to connected/degraded/not-configured states | focused declarative registry/state/privacy/dependency/profile/permissions/health/integration-projection tests; browser fixture pending | synthetic state and existing-install detection; provider/broker health tests remain credential/hardware-dependent | framework is additive and resumable; provider connectivity and module-specific configuration operations remain explicit rather than inferred from metadata |
| IT Assets/CMDB | present; InventoryService + canonical CMDB projection | inventory asset reads, CMDB map/observations, reconciliation boundary | IT Assets window now shows distinct Inventory/CMDB sources, canonical/unidentified metrics, dossiers, provenance, and empty/error states | green | projection dogfood pending | stronger reconciliation workflow, lifecycle/history, and live discovery dogfood remain |
| Network | present via canonical CMDB projection | bounded map/discovery, observations, identity boundary | Network window now shows canonical/unidentified/relationship metrics, provenance rule, dossiers, and empty/error states | green | projection dogfood pending | change detection/history and richer topology visualization remain |
| Homelab | present via manage_homelab and host broker | bounded host-discovery and distinct service/version-enumeration ActionSpecs with existing approval and broker policy | first-class Homelab window shows capability/broker health, bounded operation areas, CMDB observation, and authority explanation; recognizable weak-model network-discovery prose now receives one deterministic bounded plan repair before approval/execution; actionable chat turns now project bound actions/results into the canonical owner/session Work Run; broker discovery candidates now persist through the canonical CMDB observation writer and projection failure remains execution-ambiguous; service enumeration consumes the same Run's exact discovered private targets, persists service evidence through the same CMDB writer, verifies projection state, and emits inferred-only role hypotheses; service restart now requires recorded plan precheck evidence, uses a scoped service lock, invalidates targeted current service observations, and verifies the structured post-restart active state; diagnostic prerequisite installation now requires its plan, locks the package-manager resource, verifies broker executable availability, and invalidates affected capability health | focused intent/action, capability, broker, CMDB projection, precheck/invalidation/verifier, target-propagation, and durable agent-bridge tests | synthetic deep-dive continuity E2; owner-live Qwen/Luna/Sol retest pending | richer service/storage/container health, prerequisite-install continuation for missing broker dependencies, verifier coverage for remaining consequential actions, and live safe-operation dogfood remain |
| Security | present via SecurityAssessmentService | owner-scoped engagement, authorization, scope, target, evidence, finding, and report routes | Security panel now uses shared header/metrics/dossier states and exposes canonical grounded report output | green | assessment dogfood pending | richer timeline/remediation/verification UI and live authorized test remain |
| OSINT | present policy/research store | `research.public_sources` / `manage_osint`; visible intake uses existing `/api/research/start` and owner-scoped detail; existing upload/document/VL processors provide bounded attachment evidence; reviewed case claims project through Work `EpistemicClaim` with `osint:case:<session_id>` subject refs; explicit owner review uses the canonical claim ledger; open questions and delta checkpoints persist in the owner-scoped case projection | first-class OSINT window, structured overview, compact case cards, dedicated collapsible USER PROVIDED seed section, readable dossier prose, responsive scrollable tabs, bounded owner-checked file/image/document evidence intake, clickable evidence dossier with source counts, report/findings, canonical claim ledger with provenance/status/contradictions, explicit confirm/stale/retract correction controls, open-question capture/status, deterministic delta checkpoint/compare, fact/inference boundary, command/sidebar navigation; graph/timeline remain partial | focused surface + research/security/attachment/claim/review/question/delta/layout/overflow regression; reusable browser assertion helper | synthetic realistic-content acceptance; browser runner/owner-live visual acceptance pending | shared window/card/grid primitives now enforce intrinsic sizing, wrapping, containment, semantic action theme tokens, and responsive reflow; attachment text is capped, explicitly tainted, and never promoted automatically; owner review is required for claim recording/correction; corrections preserve prior evidence; unresolved questions remain explicit; delta is bounded to current evidence/checkpoints; canonical graph remains |
| Business/CRM | partial | partial | partial | partial | not accepted | canonical Work-linked CRM workspace |
| Telegram | present via owner-scoped TelegramStore/runtime | pairing, status, session binding, replay/approval boundaries | visible Telegram workspace plus Setup Center contract and bounded non-mutating health validation | focused transport + workspace + setup-contract tests | credentials-dependent | cross-channel continuity, media/voice delivery, and live pairing dogfood remain; setup health never invokes Telegram or handles bot credentials |
| Voice/multimodal | partial; existing STT/TTS providers and chat recorder | existing `/api/stt` and `/api/tts` providers, now authenticated before processing | voice remains integrated with Chat/settings; no duplicate voice workspace added | focused route-auth and service tests | credentials/browser/hardware-dependent | authenticated owner voice mode, Telegram voice mirroring, retention controls, and live PTT dogfood remain |
| PWA / offline shell | present via manifest and service worker | existing cache-first/static and network-first code strategies; APIs remain uncached | installable shell precaches current standardized workspaces; bounded Share-to-Hades GET target stages content for review | focused manifest/service-worker/share tests | browser/install dogfood pending | authenticated offline data UX, push notifications, and camera workflow remain |
| Email/calendar/contacts | present | partial | present | green | credentials-dependent | shared entity links and integration center |
| Documents | present | partial | visible canonical Document/Library module and existing upload/preview/editor paths | green | not accepted | reusable attachment/entity dossier links and broader document provenance remain |
| Models/routing | present (evaluation corpus + model competence projection) | present; owner-scoped empirical recommendation API plus evidence matrix with bounded evidence summary and route explanation; safety failures can disqualify a model/task pairing; deterministic local routing separates executable network intent from read-only homelab reads | Control Center Competence and Routing views | focused competence/evaluation/routing/matrix/local-intent tests | synthetic qualification dogfood complete; live multi-model qualification pending | recommendation is advisory and candidate-limited; deterministic recent-run ordering, measured latency/token/numeric-cost aggregation, and safety-disqualification guard are present; richer provider telemetry, optimization, and shadow review remain |
| Improvements | present | partial | partial | green | not accepted | registry workspace and promotion evidence |
| Developer/health/authority | present | partial | partial; Control Center with Runs/Evaluations/Inspector/Nodes/Grants is visible; Developer now shows source/image/frontend/UI-state/theme diagnostics; first-class Integration Center shows secret-free health/capabilities; Run Inspector visibly projects ambiguous execution and compensation trajectories | focused control-plane/UI/integration tests | deterministic Run Inspector and Integration Center dogfood; live provider/model evaluation pending | permissions, trace, backup projections, and richer health integrations remain; Action Contract and exact grant inspection are visible; Run Inspector exposes canonical preview targets, effects, capability health, reversibility, approvals, verification, ambiguity, and compensation state |
| Incidents / Changes | present (core/incident_models.py, src/incident_change.py) | Work/Run references; no second executor; Change preview includes planner validation/blast radius; hypothesis/evidence updates and guarded Change lifecycle | Control Center tabs with owner-scoped Incident/Change dossiers, linked verified Run state, evidence-linked diagnostic Runs, blast radius, and evidence counts | focused owner-scope, hypothesis/evidence loop, canonical evidence provenance, preview, lifecycle, reconciliation, dossier, and migration tests | synthetic incident/change records dogfood complete | completion of a Run-linked Change requires verified canonical Run state; Hades-owned run/action/result/artifact evidence references are owner- and Run-bound; opaque external/provider evidence remains supported; remediation execution and live safe-service dogfood remain |
| Shell/window/design system | present | partial | partial | focused theme/icon/nav regression green | owner browser review pending | semantic theme token contract, centralized icon registry, live accent binding, legacy-sidebar icon hydration, and persisted collapsible tool groups are implemented; full window/search/graph theme review and owner-live acceptance remain |

## Tier 1 acceptance gates

- Self/runtime/Work/commitment/Attention state is sourced from canonical APIs,
  not model narration.
- Recent conversation and active Work state outrank supplemental memory.
- Module windows reuse the existing manager and owner persistence.
- UI actions remain projections of canonical routes and ActionSpecs.
- A domain is not complete until intake/detail/activity/provenance and
  restart/local-model evidence are recorded.

This matrix is a continuation artifact, not a claim that partial domains are
complete.

## Empirical routing continuation

Model competence is now consumable by a bounded recommendation projection. The
authenticated Work API can recommend among caller-supplied candidates for a
task class, requiring qualification when requested and otherwise clearly
marking unknown/experimental fallback evidence. The local-intelligence route
also reports task class and a sanitized competence recommendation. This is
advisory routing evidence only: explicit model preferences, capabilities,
approval policy, and execution authority remain authoritative and are not
granted or widened by competence data. High/critical risk requests require
qualification; privacy-local, latency, and cost constraints are represented as
bounded candidate filters with rejection reasons. Synthetic owner-scope and
qualification tests are green; live multi-model qualification remains pending.

## P0 memory grounding gate

Intent contract checkpoint: a bounded IntentFrame/domain-contract resolver now
maps semantic concepts to existing ActionSpecs and ToolBindings, with explicit
result-status and exposure metadata. Technical-asset paraphrases resolve to
the canonical `inventory.manage/list` read without approval or filesystem
fallback. Contract validation is green; broader Memory/Work/Setup/Household
read contracts remain explicitly partial until canonical owner services are
bound.

The existing Brain/memory store now has a deterministic explicit-read
projection. Queries such as “what do you remember about me?” produce a
protected, owner-scoped canonical Memory Result; the existing
`manage_memory` capability is also exposed under a deterministic `memory`
intent. Retrieval failure is distinct from a genuine zero result, procedural
Skills are explicitly excluded from personal-memory answers, and explicit
results survive local-model context trimming. Synthetic owner-isolation,
failure, Qwen compact-projection, and trim tests are green. Live authenticated
dogfood remains credential-gated. A sanitized Memory Inspector now receives
request diagnostics and saved turn metrics without memory content.

The follow-on convergence batch now projects those explicit reads through a
first-class `memory.read` Capability, `read_memory` ToolBinding, and structured
Result adapter. Legacy memory mutations remain compatibility-only; Work,
Household, and Setup/Integration reads remain unregistered until real
owner-scoped executors exist. Full regression after this batch: 6116 passed,
3 skipped, 186 warnings.

Theme/icon checkpoint: the existing semantic token system and centralized
icon registry now cover the previously plain-text legacy sidebar destinations
Household, IT Assets, Network, Developer, and Hades. Their navigation SVGs
inherit currentColor, so selected/hover/theme changes follow shared shell
tokens. Owner-live browser acceptance remains separate from synthetic tests.

OSINT claim projection checkpoint: owner/case-scoped claim reads now include a
structured epistemic summary (claim classes, lifecycle statuses, and claims
with contradiction references). The dossier displays this summary while
keeping external report/findings tainted and non-authoritative.

### Overnight convergence checkpoint — 2026-08-25

The expanded sidebar now projects workspace groups from the existing canonical
`WorkspaceDefinition`/`ModuleDefinition` registry; virtual modules have
explicit metadata and legacy DOM IDs remain compatibility bindings. Source and
focused evidence is E2/E3; the final candidate is E4/E5 source-matched, while
owner-live UI and memory dogfood remain pending. See
`docs/hades-truth-audit-post-overnight.md`.

The Work read convergence batch adds the read-only `work.read` capability and
`read_work` ToolBinding over the existing durable WorkEngine. Overview, review,
context, and typed list reads are owner-scoped structured results with no
generic approval or filesystem fallback. “What am I working on?” now compiles
through the generic Work contract; mutation lifecycle convergence remains
separate. Focused and full regression evidence is green, and the exact
source-matched candidate is deployed. Owner-live Work dogfood remains separate.

Household read convergence now projects the existing owner-scoped
`InventoryService` through `household.read`/`read_household` for overview,
listing, search, and item reads. Household Inventory remains distinct from
technical CMDB/IT Assets; no second store or filesystem fallback was added.
Focused/full regression evidence is green, and the exact source-matched
candidate is deployed. Owner-live Household dogfood remains separate.

Setup/Integration read convergence now projects the existing secret-free
`SetupCenterService` through `setup.read`/`read_setup` for configuration state,
integration projection, and permissions projection. It adds no settings store,
secret resolution, or authority grant. Focused tests and exact source-matched
deployment are green; owner-live provider health remains separate.
