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
| Durable Runs / Action Contracts | present (src/work_engine.py, core/work_models.py, src/run_planner.py) | work.run.read, work.run.manage, preview/validate/replay/execution projections | partial; full executor/compensation UI pending | focused Work/planner/execution/registry tests | safe lifecycle/invalidation dogfood; live consequential execution pending | additive structured preview and validation, explicit verified-execution transitions, prechecks, cancellation request, targeted claim invalidation, OTel execution spans, lock recovery, and epistemic/temporal claim projection; external binding orchestration, compensation, and richer inspector remain |
| Evaluation corpus / failure regression | present (core/evaluation_models.py, src/evaluation_service.py, benchmarks/jarvis/control_plane_v1.json) | existing benchmark scorer plus durable owner-scoped scenarios/runs/failures | UI pending; CLI/fixture foundation | focused service + corpus validation | deterministic fixture validation complete; live trajectory dogfood pending | supervised failure review and 15 historical regression seeds exist; trajectory scoring UI and production-failure ingestion remain |
| OTel-compatible observability | present (core/observability_models.py, src/observability.py) | trace projection foundation; request/Run adapters pending | Developer trace UI pending | focused redaction/span tests | deterministic span persistence pending live request wiring | redacted bounded spans, Run linkage, parent/child IDs, and low-cardinality metric projection; provider/exporter wiring remains |
| Loop / knowledge-gap safeguards | present (src/control_plane_safety.py, WorkEngine projections) | deterministic action fingerprints and epistemic requirement checks | diagnostics/UI pending | focused safety + Work tests | deterministic unit dogfood complete | repeated no-information calls can stop/replan; requirements classify known/stale/unknown; execution wiring and UI remain |
| World Model / epistemic relationships | present (core/work_models.py, src/world_model.py, WorkEngine claims) | owner-scoped relationships + contradiction API | visible World Model window, focus/search, evidence/status badges, blast-radius view | focused relationship/contradiction/UI tests | synthetic dependency graph and visible projection dogfood complete | evidence-backed typed edges, explicit competing claims, stale-state projection, bounded neighbors, confidence/status filtering, and blast-radius projection; CMDB adapters and broader domain ingestion remain |
| Memory | present | present | partial | green | partial | retrieval/context diagnostics exist; explicit layer, TTL, supersession, and inspector UX remain |
| Notifications/monitors | present | partial | partial | green | partial | Attention and monitor primitives exist; transport center and notification dogfood remain |
| Household | present | partial | partial | green | not accepted | intake, dossier, history, provenance |
| IT Assets/CMDB | present | present | partial | green | partial | reconciliation and detail workspace |
| Network | present | green | partial | green | green | change detection, history, polished map |
| Homelab | present | green for discovery | partial | green | green discovery | operation catalog and health surface |
| Security | present | partial | partial | green | not accepted | end-to-end authorized assessment dogfood |
| OSINT | present policy/research store | `research.public_sources` / `manage_osint`; visible intake uses existing `/api/research/start` | first-class OSINT window, tabs, intake, cases list, command/sidebar navigation; dossier/graph/timeline remain partial | focused surface + research/security regression | browser gate passed for navigation/intake/mobile; live provider run pending | intake seed is persisted immediately in the canonical research JSON and replaced by sourced result; evidence dossier, corrections, and deep-dive projections remain |
| Business/CRM | partial | partial | partial | partial | not accepted | canonical Work-linked CRM workspace |
| Telegram | present | present | transport | green | partial | cross-channel continuity and voice |
| Voice/multimodal | partial | partial | partial | partial | not accepted | reviewable intake and PTT flow |
| Email/calendar/contacts | present | partial | present | green | credentials-dependent | shared entity links and integration center |
| Documents | present | partial | partial | green | not accepted | reusable attachments/dossiers |
| Models/routing | present (evaluation corpus + model competence projection) | present; empirical competence API | Control Center Competence view | focused competence/evaluation tests | synthetic qualification dogfood complete; live multi-model qualification pending | model lab, routing explanation, measured routing adoption, and shadow review remain |
| Improvements | present | partial | partial | green | not accepted | registry workspace and promotion evidence |
| Developer/health/authority | present | partial | partial; Control Center with Runs/Evaluations/Inspector is visible | focused control-plane/UI tests | deterministic Run Inspector dogfood; live provider/model evaluation pending | permissions, trace, backup projections, Action Contract inspection, and richer health integrations remain |
| Incidents / Changes | present (core/incident_models.py, src/incident_change.py) | Work/Run references; no second executor | Control Center tabs with incident/change status projections | focused owner-scope, hypothesis, preview, and migration tests | synthetic incident/change records dogfood complete | hypothesis/evidence history and Change preview reference canonical Runs; remediation execution, dedicated dossiers, and live safe-service dogfood remain |
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

## P0 memory grounding gate

The existing Brain/memory store now has a deterministic explicit-read
projection. Queries such as “what do you remember about me?” produce a
protected, owner-scoped canonical Memory Result; the existing
`manage_memory` capability is also exposed under a deterministic `memory`
intent. Retrieval failure is distinct from a genuine zero result, procedural
Skills are explicitly excluded from personal-memory answers, and explicit
results survive local-model context trimming. Synthetic owner-isolation,
failure, Qwen compact-projection, and trim tests are green. Live authenticated
dogfood and a persisted Memory Inspector/trace projection remain pending.
