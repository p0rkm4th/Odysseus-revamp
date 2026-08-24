# Hades existing capability inventory

Inventory checkpoint: V2 start, accepted stabilization source
`120e4afa9d0cd60fff3f6225c42d131837c6c260`.

This is a bounded productization inventory of the recovered platform. “Present”
means a canonical implementation exists; it does not imply that the workspace,
intake, dossier, provenance, or live dogfood gates are complete.

| Subsystem | Canonical owner/store | Capability/action surface | UI/integration surface | Tests/live state | Main gap |
|---|---|---|---|---|---|
| Chat/context | `core/session_manager.py`, `src/context_compactor.py`, `src/agent_loop.py` | routed agent loop, context diagnostics, approval continuation | Web chat, streaming | P0 tests; Luna/Qwen network dogfood | live weak-model referent handling still needs stronger deterministic resolution |
| Work | `src/work_engine.py`, `core/persistent_agent_models.py` | Goals/Projects/Tasks/Runs and durable continuation | Work/task panels | broad regression | unified Life overview and review UX |
| Persistent Hades | `core/persistent_agent_models.py`, `routes/intelligence_routes.py` | self/health/while-away projections | intelligence/self surfaces | persistent-agent tests | unified identity/runtime/work/attention dossier |
| Memory/RAG | `routes/memory`, `src/memory*`, Chroma projection | memory retrieval and durable records | memory/settings views | memory and context tests | explicit layer/TTL/supersession inspector |
| Skills | `routes/skills_routes.py`, skill stores | bounded skill lifecycle and execution | skills UI | skills route tests | capability/skill catalog unification |
| Scheduler/jobs | scheduler, `src/bg_jobs.py`, task routes | scheduled tasks, background jobs, monitors | task/settings surfaces | scheduler regression | unified Automation projection |
| Household inventory | `src/inventory*`, inventory routes/store | items, lots, recipes, stock movements | inventory UI | inventory tests | complete intake/dossier/history UX |
| IT assets/CMDB | `src/asset_inventory.py`, `data/assets/assets.db` | assets, identifiers, observations, relationships | inventory/intelligence UI | CMDB tests | complete reconciliation and provenance UX |
| Network | `src/network_projection.py`, asset observations | map projection and discovery | intelligence/network UI | network tests; live broker scans | change detection, history, filters |
| Homelab operations | `src/homelab_operations.py`, capability registry | `homelab.manage / execute_network_discovery` and related actions | chat/tool surfaces | security + work tests; live host broker | broader first-class operation catalog |
| System/network/storage/container/remote ops | `src/*operations.py`, brokers | bounded diagnostics and selected mutations | mostly chat/developer surfaces | focused policy tests | surface catalog and health in UI |
| Security assessment | security services/routes | engagement, authorization, scope, evidence, findings | security workspace | security domain tests | polished dossier/report and live dogfood |
| OSINT/research | `routes/research/*`, `src/research_handler.py`, `src/osint_policy.py`, owner-stamped research JSON | `research.public_sources` → `manage_osint`; bounded public-source plan/search/fetch; research start/report | OSINT workspace, New Investigation intake, Cases and research tabs; legacy Deep Research panel remains | research policy/route/path tests; browser OSINT visibility gate | dossier/detail, graph/timeline, correction/review, provider-backed OSINT dogfood |
| Telegram | Telegram poller/store/routes | pairing, owner binding, callbacks, approvals | Telegram transport | Telegram tests | shared cross-channel context, voice/notifications |
| Voice/multimodal | voice recorder/TTS/media routes | browser voice and media intake primitives | voice UI/components | focused media tests | reviewable extraction and transport parity |
| Email/calendar/contacts | email, calendar, contacts routes | provider reads, drafts, events, contacts | existing specialized views | provider tests | unified integration/entity linking |
| Documents/files | document/upload routes | upload, preview, extraction, attachments | document/gallery UI | upload/document tests | reusable entity dossier attachments |
| Models/routing | provider/model routes, endpoint resolver | route selection, profiles, metrics | provider/developer UI | routing tests | model lab and qualification evidence |
| Improvements | improvement registry routes/store | candidate/evaluation/promotion controls | limited developer surfaces | improvement tests | full registry workspace |
| Developer/YOLO/health | developer routes, readiness, profiles | leases, health, diagnostics, audits | settings/developer surfaces | readiness/policy tests | unified authority, trace, backup projections |

## Cross-cutting ownership map

| Concern | Canonical owner | Current projection | Productization gap |
|---|---|---|---|
| Durable orchestration | Work Engine and persistent Work models | Goals, Projects, Tasks, Runs, Commitments, WorkEvents | Life/review/navigation should remain projections over these records |
| Authority | capability registry, ActionSpecs, ToolBindings, approvals, execution profiles | chat/tool routing and broker validation | unified owner-facing Authority Center |
| Canonical evidence | domain stores plus Results, observations, and WorkEvents | domain routes and selected dossiers | reusable activity/provenance components |
| Conversation continuity | session manager, context compaction, agent loop | Web chat/provider reconstruction | context inspector and transport parity |
| Memory indexes | semantic memory services and vector projection | memory UI and retrieval | explicit layer/TTL/supersession diagnostics |
| UI shell | workspace window manager, app shell, module JS | routed panels and floating windows | uniform module grammar, search, palette, responsive states |
| Integrations | provider-specific stores/routes | Telegram/email/calendar/document views | common health and permission projection |

For each row, implementation batches must verify canonical store/model, service/API,
Capability → ActionSpec → ToolBinding, policy/approval, execution profile, Work
linkage, UI/window, search, activity/history, provenance, correction/review,
restart persistence, focused tests, and strong/local dogfood. Missing fields
remain gaps even when the backend is substantial.

## Architectural invariants

- Domain → Capability → ActionSpec → ToolBinding remains the execution path.
- Work Engine remains durable orchestration truth; domain stores remain domain truth.
- Network discovery uses the authenticated host broker, private bounded scope, and exact approval.
- IP-only observations never become strong identity merges.
- External content remains tainted and cannot grant authority.
- No Docker socket, privileged Hades container, generic root shell, or unrestricted YOLO is introduced.
