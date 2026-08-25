# Hades Codebase Truth Audit

Independent verification pass; evidence recorded 2026-08-24. This audit does not treat roadmap text, feature matrices, commit messages, or tests as proof without corroborating source/runtime evidence. No source or production data was changed. The only intentional repository change is this file.

## Executive result

The repository contains substantial Hades source, persistence, registry, route, UI, and focused-test work. The local Python suite is healthy (`6063 passed, 3 skipped, 186 warnings`), and the versioned migration layer rehearses cleanly. This is not equivalent to live product completion: the running container is built from a different source snapshot, the app has no source/build identifier, vector memory/RAG is degraded in the running process, Ollama is unreachable, and browser dogfood cannot run because Playwright is not installed. Most matrix rows are therefore source/test or partial, not live-verified.

## Repository truth

| Field | Evidence |
|---|---|
| PWD | `/home/scootz/Odysseus/odysseus` |
| Root | `/home/scootz/Odysseus/odysseus` |
| Branch | `recovery/live-candidate-20260823` |
| HEAD | `22982c29b6b716622a38f4abb91d046646836b38` (`Add synthetic cross-domain dogfood`) |
| Worktree before | clean according to `git status --short --untracked-files=all`; ignored `tmp_pytest_probe/` exists on disk |
| Baseline | tag `hades-baseline-20260823`; merge-base `4ded405973a605fc6b5303e41e447b0ef7b3703a` |
| Baseline delta | `170 files changed, 13776 insertions, 103 deletions`; includes 21 migration files/updates, 70+ source/model changes, frontend changes, and tests |
| fsck | integrity errors not reported; dangling blobs, 4 dangling commits, and 2 dangling tags were reported |

Recent commits sampled (`git show --stat --name-status`) contain the stated source/test changes for Run binding, action ownership, World Model CMDB projection, execution trajectories, and synthetic dogfood. They also update the feature matrix/roadmap in the same commits. That is documentation evidence, not live evidence.

## Runtime/deployment truth

| Check | Result |
|---|---|
| Running service | `odysseus-odysseus-1`, up approximately 4 hours at first inspection |
| Image | `sha256:c09af676703b70889207568076094e976c9a38256800a723ce7b2a0d35fc65d6`; created `2026-08-24T13:05:26-05:00` |
| Container source | `/app/app.py` SHA-256 `310e8ea4...`; checkout `app.py` SHA-256 `31c1b53d...`; no Git metadata/build ID in `/app` |
| API | `/api/health` returned `200 {"status":"healthy"}`; `/api/version` returned `1.0.2` with no commit identifier |
| Readiness/runtime | `/api/ready` and `/api/runtime` returned `401 Not authenticated` |
| Source match | `RUNNING_SOURCE_MATCHES_HEAD = NO/UNPROVABLE`; image/source hashes differ and no build ID exists |
| Compose security | `privileged=false`, ordinary bridge network, no Docker socket, no devices, no host-root mount; mounts include the checkout at `/home/...` and data/log/SSH/cache paths |
| Broker | host process `python -m src.privileged_broker --serve --allowed-pid 1 --allowed-uid 1000 --allowed-gid 1000`; expected `/run/odysseus-privd.sock` was absent during inspection, so live socket/status/ownership could not be verified |
| Ollama | `systemctl` says service active, but `127.0.0.1:11434/api/version` and `/api/tags` refused connection; no endpoint/model/inference verification |
| RAG/memory vectors | app import/runtime logs report HTTP embedding unavailable, FastEmbed permission failure at `/app`, `VectorRAG` unhealthy, and `MemoryVectorStore DEGRADED` |
| Frontend build | `npm run build` and `npm test` both fail because `package.json` defines no such scripts; JavaScript `node --check` over `static/js/*.js` passed |
| Browser | blocked: `require('playwright')` failed and no Playwright module was provided |

## Tests and migration rehearsal

- Collection: `6066 tests collected in 2.85s`.
- Execution: first mandated run `6063 passed, 3 skipped, 186 warnings in 120.60s (0:02:00)`, exit 0. A subsequent `-rs` rerun reported `6064 passed, 3 skipped, 186 warnings in 118.79s`, exit 0. The one-test count difference is a reproducibility finding and was not normalized away.
- Warnings are predominantly SQLAlchemy/deprecated UTC usage; they are not silently treated as failures.
- Exact runtime skips from the `-rs` rerun: `tests/test_cookbook_helpers.py::...` Windows Ollama CLI startup guard; `tests/test_markitdown_runtime.py::...` missing `markitdown`; `tests/test_upload_content_detection_magic.py::...` missing libmagic/python-magic. Source also contains additional conditional skips for Node, SQLAlchemy stubs, and historical hardware fixtures; they were not selected in this run.
- Compilation: `venv/bin/python -m compileall -q app.py core routes src services mcp_servers` passed.
- Migrations: 21 registered versions, all current DB rows present; fresh DB applied all 21, rerun returned `()`, copied current DB applied `()`, rerun returned `()`. No exact duplicate revision IDs or missing predecessor mechanism exists in this registry. Two IDs share the `20260824_011_` prefix (`delegated_grants_v1`, `sandbox_v1`), which is a naming/order hazard even though full IDs differ.
- No production DB was mutated; rehearsal used temporary files under `/tmp` and a copied `data/app.db`.

## Registry and capability audit

The source registry (`src/capability_registry.py`) contains 28 capabilities and 66 ActionSpecs. `src/tool_bindings.py` contains 5 ToolBindings: `manage_assets`, `privileged_action`, `manage_homelab`, `manage_osint`, and `manage_security_assessment`. The ToolBinding map covers only the first-class transport projections; many ActionSpecs have no ToolBinding by design and are Work/API-only.

Each ActionSpec has a stable `action_id`, effects, approval mode, executor key where executable, execution location metadata, and (where declared) scopes, resources, locks, risk, idempotency, verification, and compensation fields. `security.recon.execute` is deliberately exact-approval metadata with no executor. `TOOL_CAPABILITY_IDS` has five entries and all five resolve to registered capabilities.

Findings:

- `ORPHAN_CAPABILITY`: no registry orphan was detected among the 28 registry entries, but capability-to-route exposure is not complete for every action.
- `ORPHAN_ACTION`: Work/API-only actions are not model-tool actions; this is expected but undocumented as a formal exposure matrix.
- `ORPHAN_BINDING`: none in the five binding map.
- `UNEXPOSED_ACTION`: several security/work/setup ActionSpecs are reachable through owner-authenticated API/service paths rather than LLM bindings; this is a deliberate boundary but means “registered” is not “model exposed.”
- `UNREGISTERED_TOOL_PATH`: legacy/general tool code exists outside the five first-class bindings; static searches show broad `src/tools` and `agent_loop` paths. A complete path-by-path proof that every legacy route is registry-governed is not present.

## Route/API and UI audit

The source app imports successfully and reports 77 top-level Starlette routes, but import-time enumeration only exposes shell/UI and health/version routes; feature routers are initialized through runtime setup rather than being visible in that import snapshot. The running API’s OpenAPI request did not return JSON (authentication/runtime response), so a complete live route enumeration was not possible.

Source route modules exist for Work, Memory, Research/OSINT, Security Assessment, Inventory, Telegram, Setup Center, Intelligence, and World Model projections. Representative API routes include `/api/work/...`, `/api/research/...`, `/api/security/...`, `/api/setup/...`, inventory/CMDB routes, and model/control-center projections. The source cannot prove that every claimed route is deployed in the running image.

Live navigation source in `static/index.html` and `static/app.js` contains entries and handlers for Hades, Memory, Work, OSINT, Security, Household, Communications, Telegram, Smart Home, IT Assets, Network, Homelab, World Model, Control Center, Setup Center, and Developer. Source-level labels/handlers are present and icons use `currentColor` for the sampled standardized legacy entries. Browser route availability, console errors, failed network calls, layout, and populated fixtures are `BLOCKED_EXTERNAL_AUTH`/blocked by missing Playwright.

Route/UI classifications:

| Claimed module | Source/UI classification | Evidence status |
|---|---|---|
| Hades, Memory, Work, OSINT, Security | FULL/PARTIAL source surfaces and nav handlers | VERIFIED_SOURCE_AND_TESTS; live UI not verified |
| Household, IT Assets, Network, Homelab, World Model | source projections, routes, nav handlers | VERIFIED_SOURCE_AND_TESTS; runtime/browser not verified |
| Control Center, Setup Center | source routes/UI modules and tests | VERIFIED_SOURCE_AND_TESTS; deployment not matched |
| Telegram, Communications, Smart Home | source integrations/projections/nav | PARTIAL; credentials/live state unavailable |
| Business/CRM | roadmap says partial; no equivalent first-class accepted workspace evidence found | PARTIAL |
| Permissions, Models, Improvements, Incidents, Changes, Missions, Watches | source/API/control-center projections exist in varying depth | PARTIAL or VERIFIED_SOURCE_AND_TESTS; not live |

No source-only filename was counted as a route. No broken-nav assertion was made without browser execution.

## Persistence and migration evidence

The ORM metadata has 92 tables. Relevant durable tables include `work_goals`, `work_runs`, `work_actions`, `work_results`, `work_artifacts`, `work_locks`, `work_events`, `epistemic_claims`, `world_relationships`, evaluation scenario/run/failure tables, `trace_spans`, inventory/CMDB tables, security engagement/scope/target/run/evidence/finding/report tables, persistent-agent tables, incidents/changes, execution nodes/sandboxes, delegated grants, and legacy `memories`.

This proves schema/model presence, not that production is using HEAD. The architecture contains a canonical Work/claim/world relationship store, but legacy Memory and vector stores remain parallel persistence paths; runtime evidence explicitly says vector memory is degraded. No second independent graph truth store was found in the audited Hades-specific models; World Model relationships are in `world_relationships` and CMDB projection code.

## Security invariant evidence

| Invariant | Source evidence | Test evidence | Audit result |
|---|---|---|---|
| owner isolation | `src/owner_identity.py`; owner filters in `src/work_engine.py`, `src/delegated_grants.py`, `routes/inventory_routes.py`, security services | owner-scope tests across Work, grants, inventory, security, memory | VERIFIED_SOURCE_AND_TESTS |
| exact approval/digest | `src/work_engine.py`; `src/delegated_grants.py:26`; approval routes | `tests/test_verified_execution.py`, `tests/test_delegated_grants.py`, Work engine tests | VERIFIED_SOURCE_AND_TESTS |
| replay protection | Work retry/replay code and action references | verified execution/replay tests | VERIFIED_SOURCE_AND_TESTS |
| broker peer auth | `src/privileged_broker.py:peercred`, `peer_is_allowed`, `SO_PEERCRED` | broker/security tests | SOURCE_AND_TESTS; live socket absent |
| package allowlist | `src/privileged_broker.py:ALLOWED_PACKAGES`, `validate_packages` | broker/privileged tests | VERIFIED_SOURCE_AND_TESTS |
| private network scope | `_private_discovery_cidr` requires private IPv4 <=256 addresses | URL/network/security tests and homelab tests | VERIFIED_SOURCE_AND_TESTS |
| no generic Hades sudo/Docker authority | `src/privileged_broker.py`, Compose lacks socket/privileged/device mounts | security regression and broker tests | SOURCE_AND_TESTS; runtime container config corroborates |
| no model self-enable YOLO | exact approval and developer authority code in `src/developer_mode.py`, `src/agent_loop.py` | control-plane/approval tests | VERIFIED_SOURCE_AND_TESTS |
| CMDB strong identity/IP merge boundary | inventory models/service and tool-binding contract | inventory/CMDB identity tests | VERIFIED_SOURCE_AND_TESTS |
| external-content taint | OSINT/research routes and attachment/claim projection | OSINT attachment/claim tests | VERIFIED_SOURCE_AND_TESTS |

Runtime broker socket ownership/mode and consequential broker path were not verified because the expected socket did not exist at inspection time.

## Feature claim → evidence ledger

| Feature claim | Commit/source | Tests | Runtime/UI | Actual status |
|---|---|---|---|---|
| Durable Runs / Action Contracts | `core/work_models.py`, `src/work_engine.py`, `src/run_planner.py` | Work/planner/verified execution/compensation tests | source UI; running image mismatch | VERIFIED_SOURCE_AND_TESTS |
| Resource locks | `core/work_models.py:WorkLock`, WorkEngine lock paths | `tests/test_work_engine.py`, verified execution tests | not live verified | VERIFIED_SOURCE_AND_TESTS |
| Epistemic ledger | `EpistemicClaim`, WorkEngine claim APIs | contradiction/claim/world-model tests | source projections | VERIFIED_SOURCE_AND_TESTS |
| Evaluation corpus | `core/evaluation_models.py`, `src/evaluation_service.py`, benchmark JSON | evaluation service/corpus tests | UI partial; no live trajectory | VERIFIED_SOURCE_AND_TESTS |
| OTel | `TraceSpan`, `src/observability.py` | `tests/test_observability.py` | roadmap itself says wiring pending | SOURCE_ONLY/PARTIAL |
| Memory repair/grounding | `core/database.py:Memory`, `src/memory_grounding.py`, memory routes | memory grounding/owner/trim tests | live vector provider degraded; owner dogfood absent | PARTIAL |
| OSINT | research routes, `src/osint_policy.py`, claim projection | OSINT surface/layout/attachment/claim tests | source nav; browser/live auth absent | VERIFIED_SOURCE_AND_TESTS |
| World Model | `src/world_model.py`, `world_relationships`, CMDB sync routes | world model/UI/CMDB tests | source UI; live projection absent | VERIFIED_SOURCE_AND_TESTS |
| Blast radius | planner/world-model projections | planner/world model tests | source Control Center | VERIFIED_SOURCE_AND_TESTS |
| UI standardization | `static/js/theme.js`, icon/nav source, CSS | theme/icon/layout tests; JS syntax | browser blocked | VERIFIED_SOURCE_AND_TESTS |
| Setup Center | `src/setup_center.py`, `routes/setup_center_routes.py` | setup/projection tests | source UI; live deployment mismatch | VERIFIED_SOURCE_AND_TESTS |
| Synthetic cross-domain dogfood | `tests/test_cross_domain_dogfood.py`, HEAD `22982c29` | executed in full suite | synthetic only | VERIFIED_SOURCE_AND_TESTS, NOT LIVE |

## Stubs, placeholders, and false-data audit

The marker search found many legitimate test/compatibility/empty-state matches. Meaningful findings are:

- `routes/setup_center_routes.py:55` explicitly raises “safe health check is not implemented for this module”; this is a real unfinished capability behind a setup surface, not a false completion.
- `src/sandbox.py:90` reports `runtime_adapter: not_configured`; the roadmap correctly describes sandbox runtime migration as pending.
- `src/privileged_broker.py` is narrow and allowlisted; it is not a generic root shell.
- `static/js/slashCommands.js` has an explicit `/demo` feature; this is user-visible demo functionality and must not be treated as canonical operational data.
- The source contains synthetic fixtures and realistic OSINT fixture content under `tests/`; these are test-only and not evidence of live data.
- No verified production route was found that unconditionally emits fabricated canonical counts/findings/hosts. However, a browser run was unavailable, so user-facing false-data display is not live-verified.
- Broad `except Exception`/empty-list matches exist in legacy/provider/degraded paths. They are not individually classified as defects; the high-impact runtime example is the embedding failure being downgraded to degraded state and logged.

## Documentation drift and inflation

The matrix is unusually explicit that `green` is not necessarily complete and repeatedly records pending dogfood. That reduces, but does not eliminate, inflation risk. Drift/high-risk claims:

- The matrix’s “green” rows can be read as implementation status while their own Live dogfood column says pending/credentials-dependent; this audit preserves the distinction.
- Matrix checkpoint names a prior accepted source SHA `120e4afa...`, while the audited baseline/HEAD lineage is later; this is historical context, not current build identity.
- Roadmap statements that tests are green are corroborated by this run, but statements implying production/live acceptance are not corroborated by deployment or browser evidence.
- Deployment docs do not provide a current source commit/build ID for the running image; `/api/version` only exposes `1.0.2`.
- The feature matrix and roadmap describe a broker boundary, while the inspected host broker process had no expected socket at `/run/odysseus-privd.sock`; this is runtime/deployment drift requiring investigation.

## Call-path evidence

- Network discovery: `manage_homelab` binding → `homelab.manage` ActionSpecs → host-broker execution metadata → `_private_discovery_cidr`/broker allowlist → intended XML nmap result → inventory/CMDB projection code. Source and focused tests exist; live broker socket and CMDB mutation were not exercised.
- Explicit memory read: chat intent/model context → `src/memory_grounding.py` canonical owner-scoped read → memory result/projection → model context. Tests cover owner/failure/trim behavior; running vector provider is degraded and no owner-live auth acceptance was performed.
- OSINT case: research API/UI → owner-checked research/session paths → tainted attachment/public-source evidence → epistemic claim projection/correction. Tests cover surface/layout/claim paths; browser/live owner route was unavailable.
- World Model: CMDB/inventory relationship projection → `world_relationships` → bounded `src/world_model.py` traversal/activity-state filtering → source UI/Control Center. Tests cover projection/idempotence/temporal behavior; live UI not verified.

## Required return summary

```text
AUDITED_HEAD: 22982c29b6b716622a38f4abb91d046646836b38
BRANCH: recovery/live-candidate-20260823
WORKTREE_BEFORE: clean (ignored tmp_pytest_probe present)
WORKTREE_AFTER: audit artifact only; verify with git status below
GIT_FSCK: no integrity errors; dangling blobs/commits/tags reported

RUNNING_IMAGE: sha256:c09af676703b70889207568076094e976c9a38256800a723ce7b2a0d35fc65d6
RUNNING_BUILD: API 1.0.2; no source/build ID
RUNNING_SOURCE_MATCHES_HEAD: NO/UNPROVABLE

PYTEST_COLLECTED: 6066
PYTEST_RESULTS: first run 6063 passed, 3 skipped, 186 warnings, 120.60s; -rs rerun 6064 passed, 3 skipped, 186 warnings, 118.79s
SKIPPED_TESTS: cookbook_helpers Windows Ollama guard; markitdown unavailable; libmagic/python-magic unavailable
WARNINGS: 186
WEAK_TEST_FINDINGS: many contract/static tests; source/test pass does not establish deployed/live behavior; browser and provider dogfood absent

MIGRATION_HEAD: 21 registered/current rows; last full version 20260824_011_sandbox_v1
FRESH_DB_MIGRATION: PASS; 21 applied, rerun empty
COPIED_DB_MIGRATION: PASS; none pending, rerun empty

CAPABILITIES: 28
ACTIONSPECS: 66
TOOL_BINDINGS: 5
ORPHAN_CAPABILITIES: none detected
ORPHAN_ACTIONS: no registry orphan; exposure is split API/Work vs model bindings
ORPHAN_BINDINGS: none detected

SECURITY_INVARIANTS: source/tests strong for owner, approval, digest, replay, scope, taint, identity, broker policy; live broker socket unavailable
ROUTE_COUNT: 77 import-time top-level; complete live OpenAPI enumeration blocked by auth/runtime response
DEAD_ROUTES: not proven without authenticated route/browser crawl
UNEXPOSED_ROUTES: source has API-only and UI-only projections; complete pairing not established
BROKEN_NAV: not live-verified; browser blocked

THEME_FINDINGS: semantic/currentColor system present; browser acceptance pending
ICON_FINDINGS: sampled standardized legacy icons use currentColor
UI_LAYOUT_FINDINGS: static/layout tests pass; browser unavailable
FRONTEND_ERRORS: no browser capture; runtime source mismatch and no build script

MEMORY_STATUS: PARTIAL; canonical/source/tests present, vector provider degraded, owner-live pending
OSINT_STATUS: VERIFIED_SOURCE_AND_TESTS; live/browser pending
WORLD_MODEL_STATUS: VERIFIED_SOURCE_AND_TESTS; live/browser pending
BLAST_RADIUS_STATUS: VERIFIED_SOURCE_AND_TESTS; not live
RUN_ENGINE_STATUS: VERIFIED_SOURCE_AND_TESTS; consequential live execution pending
EVAL_STATUS: VERIFIED_SOURCE_AND_TESTS; live trajectory ingestion/UI pending
OTEL_STATUS: SOURCE_ONLY/PARTIAL; wiring pending

DOCUMENTATION_DRIFT: build ID/runtime broker/matrix interpretation gaps
FEATURE_MATRIX_INFLATION: live claims exceed evidence in places; pending gates are documented but not independently accepted
STUBS: setup health module explicitly not implemented; sandbox runtime adapter not configured
PLACEHOLDERS: demo/empty-state/test fixtures classified separately
FALSE_DATA_PATHS: no confirmed canonical production fake-data path; browser not verified
TODO_DISCREPANCIES: setup/sandbox/runtime/live dogfood gaps

AUDIT_REPORT: docs/hades-truth-audit.md
AUDIT_COMMIT_IF_ANY: none
```

## Overall trust assessment

Source and test claims are generally credible for the narrow behaviors covered. Live/deployed claims are not credible without a source-matched image, authenticated route enumeration, broker socket verification, working Ollama endpoint, and browser smoke evidence. The repository should be treated as a substantial tested candidate, not as live-verified Hades completion.

## Next recommended remediation

First reconcile deployment provenance: build and expose the HEAD commit/build ID, restart from that image, restore/verify the broker socket boundary, and make `/api/runtime` produce authenticated source/provider diagnostics. Then run authenticated Playwright against the built candidate with realistic fixtures and capture console/network failures. Only after those gates should pending live dogfood rows be promoted.
