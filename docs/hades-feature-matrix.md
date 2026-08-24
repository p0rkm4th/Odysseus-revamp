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
| Missions / Watches | present via WorkGoal projection and existing Monitor engine | `/api/work/missions` projection includes lifecycle, constraints, budget, allowed capabilities, checkpoints, and blockers; bounded Monitor routes expose response policy and tier-2 reviewable Run proposals | Control Center Mission dossier and Watch projection | focused Mission/Monitor/proposal tests | synthetic projection only; live restart/dedupe dogfood pending | Missions reuse Goals/Runs and Watches reuse Monitors; tier 3 remains non-executing projection; richer lifecycle persistence remains; projections do not grant authority |
| Execution nodes / fabric | present as owner-scoped registry around current broker boundary | register, heartbeat, list, deterministic requirements selection with rejection reasons and resource requirements; sandbox metadata lifecycle; no authority grant | Control Center Execution Nodes and Sandboxes inspection shows health, trust, heartbeat, runtime-adapter status, and unchanged broker authority | focused owner-scope/eligibility/sandbox/migration/UI tests | synthetic registry and sandbox lifecycle only; live broker/sandbox adapter pending | current broker remains canonical executor; actual sandbox runtime and scheduling migration remain |
| Delegated capability grants | present over WorkAction approval/digest state | exact Run/Action/capability/target/digest grants with expiry, revocation, call limits, and enforced parameter constraints | Control Center Delegated Grants inspection; trusted-caller binding narrowing | focused fail-closed scope/owner/replay/parameter/target/binding tests | synthetic grant dogfood only | grants are not credentials and cannot widen authority; full orchestrator grant issuance remains deliberate/future |
| Durable Runs / Action Contracts | present (src/work_engine.py, core/work_models.py, src/run_planner.py) | work.run.read, work.run.manage, preview/validate/replay/execution/verification projections | partial; full executor/compensation UI pending | focused Work/planner/execution/registry tests | safe lifecycle/invalidation dogfood; live consequential execution pending | additive structured preview and validation, explicit verified-execution transitions, prechecks, cancellation request, targeted claim invalidation, OTel execution spans, lock recovery, explicit verification/compensation outcome transitions, and epistemic/temporal claim projection; external binding orchestration and richer inspector remain |
| Evaluation corpus / failure regression | present (core/evaluation_models.py, src/evaluation_service.py, benchmarks/jarvis/control_plane_v1.json) | existing benchmark scorer plus durable owner-scoped scenarios/runs/failures | UI pending; CLI/fixture foundation | focused service + corpus validation | deterministic fixture validation complete; live trajectory dogfood pending | supervised failure review and 15 historical regression seeds exist; trajectory scoring UI and production-failure ingestion remain |
| OTel-compatible observability | present (core/observability_models.py, src/observability.py) | trace projection foundation; request/Run adapters pending | Developer trace UI pending | focused redaction/span tests | deterministic span persistence pending live request wiring | redacted bounded spans, Run linkage, parent/child IDs, and low-cardinality metric projection; provider/exporter wiring remains |
| Loop / knowledge-gap safeguards | present (src/control_plane_safety.py, WorkEngine projections) | deterministic action fingerprints and epistemic requirement checks | diagnostics/UI pending | focused safety + Work tests | deterministic unit dogfood complete | repeated no-information calls can stop/replan; requirements classify known/stale/unknown; execution wiring and UI remain |
| World Model / epistemic relationships | present (core/work_models.py, src/world_model.py, WorkEngine claims) | owner-scoped relationships + bounded reconciliation, contradiction/lineage API | visible World Model window and navigable Control Center Evidence Explorer, focus/search, evidence/status badges, blast-radius view | focused relationship/reconciliation/contradiction/lineage/planner/UI tests | synthetic dependency graph and visible projection dogfood complete | evidence-backed typed edges, explicit competing claims, stale-state projection, bounded neighbors, confidence/status filtering, and multi-hop RunPreview blast-radius projection; CMDB adapters and broader domain ingestion remain |
| Memory | present | present | partial | green | partial | retrieval/context diagnostics exist; explicit layer, TTL, supersession, and inspector UX remain |
| Notifications/monitors | present | partial | partial | green | partial | Attention and monitor primitives exist; transport center and notification dogfood remain |
| Household | present via canonical InventoryService | inventory list/search, reviewable intake, recipes, stock projections | Household window now shows canonical overview, risk, intake, and activity; item dossier reused | green | projection dogfood pending | locations, recipe/shopping UX, and live intake dogfood remain |
| Smart Home / Home Assistant | present via generic integration boundary | existing authenticated `api_call` integration; read-only health/state projection | visible Smart Home window with configured/health/entity-domain summary and authority boundary | focused projection/UI tests | credentials-dependent | state-changing entity actions, rooms/presence, and richer entity dossiers remain policy-gated future work |
| Communications | present via canonical EmailAccount, CalendarCal/CalendarEvent, and Contacts stores | owner-scoped Email/Calendar projection; Contacts remains a linked canonical store | visible Communications overview links the existing detailed Email/Calendar surfaces without copying records | focused projection/UI test | credentials/data-dependent | richer contact dossier and Email/Calendar/Business Work bridges remain |
| IT Assets/CMDB | present; InventoryService + canonical CMDB projection | inventory asset reads, CMDB map/observations, reconciliation boundary | IT Assets window now shows distinct Inventory/CMDB sources, canonical/unidentified metrics, dossiers, provenance, and empty/error states | green | projection dogfood pending | stronger reconciliation workflow, lifecycle/history, and live discovery dogfood remain |
| Network | present via canonical CMDB projection | bounded map/discovery, observations, identity boundary | Network window now shows canonical/unidentified/relationship metrics, provenance rule, dossiers, and empty/error states | green | projection dogfood pending | change detection/history and richer topology visualization remain |
| Homelab | present via manage_homelab and host broker | bounded host/service/discovery ActionSpecs with existing approval and broker policy | first-class Homelab window shows capability/broker health, bounded operation areas, CMDB observation, and authority explanation | green | discovery accepted; workspace projection pending | richer service/storage/container health and live safe-operation dogfood remain |
| Security | present via SecurityAssessmentService | owner-scoped engagement, authorization, scope, target, evidence, finding, and report routes | Security panel now uses shared header/metrics/dossier states and exposes canonical grounded report output | green | assessment dogfood pending | richer timeline/remediation/verification UI and live authorized test remain |
| OSINT | present policy/research store | `research.public_sources` / `manage_osint`; visible intake uses existing `/api/research/start` and owner-scoped detail | first-class OSINT window, tabs, intake, clickable evidence dossier with source counts, report/findings, explicit fact/inference boundary, command/sidebar navigation; graph/timeline remain partial | focused surface + research/security regression | browser gate passed for navigation/intake/mobile; live provider run pending | external content remains tainted and escaped; corrections, canonical fact/inference ledger, and bounded delta research remain |
| Business/CRM | partial | partial | partial | partial | not accepted | canonical Work-linked CRM workspace |
| Telegram | present via owner-scoped TelegramStore/runtime | pairing, status, session binding, replay/approval boundaries | visible Telegram workspace with connection, pairing, session, and continuity projection | focused transport + workspace tests | credentials-dependent | cross-channel continuity, media/voice delivery, and live pairing dogfood remain |
| Voice/multimodal | partial; existing STT/TTS providers and chat recorder | existing `/api/stt` and `/api/tts` providers, now authenticated before processing | voice remains integrated with Chat/settings; no duplicate voice workspace added | focused route-auth and service tests | credentials/browser/hardware-dependent | authenticated owner voice mode, Telegram voice mirroring, retention controls, and live PTT dogfood remain |
| Email/calendar/contacts | present | partial | present | green | credentials-dependent | shared entity links and integration center |
| Documents | present | partial | partial | green | not accepted | reusable attachments/dossiers |
| Models/routing | present (evaluation corpus + model competence projection) | present; owner-scoped empirical recommendation API plus evidence matrix with bounded evidence summary and route explanation | Control Center Competence and Routing views | focused competence/evaluation/routing/matrix tests | synthetic qualification dogfood complete; live multi-model qualification pending | recommendation is advisory and candidate-limited; richer provider telemetry, cost/latency optimization, and shadow review remain |
| Improvements | present | partial | partial | green | not accepted | registry workspace and promotion evidence |
| Developer/health/authority | present | partial | partial; Control Center with Runs/Evaluations/Inspector/Nodes/Grants is visible | focused control-plane/UI tests | deterministic Run Inspector dogfood; live provider/model evaluation pending | permissions, trace, backup projections, and richer health integrations remain; Action Contract and exact grant inspection are now visible |
| Incidents / Changes | present (core/incident_models.py, src/incident_change.py) | Work/Run references; no second executor; Change preview includes planner validation/blast radius; hypothesis/evidence updates and guarded Change lifecycle | Control Center tabs with owner-scoped Incident/Change dossiers, linked verified Run state, blast radius, and evidence counts | focused owner-scope, hypothesis/evidence loop, preview, lifecycle, reconciliation, dossier, and migration tests | synthetic incident/change records dogfood complete | completion of a Run-linked Change requires verified canonical Run state; remediation execution and live safe-service dogfood remain |
| Shell/window/design system | present | partial | partial | partial | browser review pending | shared tokens/primitives and OSINT module header/intake now exist; existing screens still need incremental migration |

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
granted or widened by competence data. Synthetic owner-scope and qualification
tests are green; live multi-model qualification remains pending.

## P0 memory grounding gate

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
