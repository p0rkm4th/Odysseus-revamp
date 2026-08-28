# Hades reuse / deletion ledger

## Canonical runtime default (`c1386a85`, 2026-08-28)

`stream_aci_runtime` now defaults to ACI; the legacy-named compatibility facade
explicitly supplies legacy mode for unmigrated callers. Focused lifecycle,
routing, and policy coverage passed `97` tests; full regression passed
`6816 passed, 4 skipped, 186 warnings`.

Exact candidate `odysseus:candidate-c1386a85-exact` was deployed as image
`sha256:d0e1e08879e379f3063a9527b3aa5f4cdf9fb7ff8333be4d2eeb1381bf970e94`;
OCI/source markers and running source match `c1386a85`, health is healthy with
zero restarts, and Qwen is reachable in-container. Browser acceptance passed
seven journeys plus reload continuation; temporary acceptance state was
revoked and removed.

## Canonical-read eligibility projection (`5a486253`, 2026-08-28)

Moved canonical READ contract eligibility into `src.aci.is_canonical_read_contract`;
the runtime now delegates this semantic predicate. Focused coverage passed
`119` tests and full regression passed `6815 passed, 4 skipped, 186 warnings`.
The exact candidate `odysseus:candidate-5a486253-exact` was deployed as image
`sha256:18ef1da50fa4a04ec5e4891cc86bc193c127a6c5740432742b9fa25a3cb63d99`;
OCI/source markers and running source match `5a486253`, health is healthy with
zero restarts, and Qwen is reachable in-container. Browser acceptance passed
seven journeys plus reload continuation; cleanup revoked the principal and
removed credentials.

## Canonical no-action diagnostics (`e15ab6e3`, 2026-08-28)

Moved no-action outcome classification into `src.aci.classify_no_action_reason`;
the compatibility runtime now emits an ACI-owned diagnostic projection.
Focused coverage passed `118` tests and full regression passed
`6814 passed, 4 skipped, 186 warnings`.

Exact candidate `odysseus:candidate-e15ab6e3-exact` was deployed as image
`sha256:b3239d3a19722d0a531a03c30142e1ae02a9553260872a9ea5ab6d5cb4380388`;
OCI/source markers and running source match `e15ab6e3`, health is healthy with
zero restarts, and qwen3:8b is reachable in-container. Authenticated browser
acceptance passed seven journeys plus reload continuation; cleanup revoked the
temporary principal, disabled the facility, and removed credentials.

## Canonical action-expectation projection (`45ecaf5c`, 2026-08-28)

Moved the runtime's canonical-action expectation predicate into
`src.aci.expects_canonical_action`; `agent_loop.py` now delegates the
diagnostic projection using resolved ACI inputs. Focused coverage passed `117`
tests and full regression passed `6813 passed, 4 skipped, 186 warnings`.

The exact pushed candidate `odysseus:candidate-45ecaf5c-exact` was deployed as
image `sha256:906af54544e1283e66a6a8b2457163862cf2aec0b500ad30b3b2d78cf8fee076`;
OCI/source markers and running source match `45ecaf5c`. Health is healthy with
zero restarts. Authenticated browser acceptance passed seven journeys plus
reload continuation; the temporary principal and credentials were cleaned up.

## Authenticated browser acceptance (`225195aa`, 2026-08-28)

The existing Playwright authenticated lane passed the seven required journeys
and the post-reload continuation (`8` streams) against the real login,
`/api/chat_stream`, persistence, and client-rendering path. Cleanup verified
logout/revocation, disabled acceptance mode, removed the temporary credential,
and left the exact candidate healthy with zero restarts. Evidence is attributed
to executable source `225195aa`; it proves the isolated synthetic acceptance
principal path, not real-owner data correctness.

## Exact candidate deployment and Qwen revalidation (`225195aa`, 2026-08-28)

Candidate `odysseus:candidate-225195aa-exact` was deployed with image
`sha256:20437b95b12b3b78f0cc46b0569586ce4bb784029cada1122367df4a44bb4003`.
OCI revision, source marker, and running source match
`225195aa1e4b3985c7fb00a128dd7c7e16160cef`; health is healthy and restarts
are zero. The retained rollback tag is `odysseus:candidate-f5c07ff3`.

The in-container frozen Qwen3:8B quick run passed `62/62` functional,
architectural, and security cases, with duplicate delivery `0`, reference
resolution `1.0`, failed Actions/task `0.0161`, model calls/task `0.2581`,
median latency `0.030s`, and P95 `1.6798s`. The model endpoint was
`http://host.docker.internal:11434`. Later branch commits are documentation
only; this evidence is attributed to executable source `225195aa`.

## Recovered semantic coverage shard (`437ad048`, 2026-08-28)

The interrupted shard had no surviving process or partial artifact. Re-running
only shard `0/4` with seed `20260828` and no model invocation produced `934`
scenarios and `264` coverage gaps (`39` critical, `24` high, `201` normal).
Critical gaps are untested/partial dimensions, chiefly failure classes,
executors, approval branches, post-result states, and policy branches; they
are not product execution failures. The focused dogfood/cutover suite passed
`89` tests. No executable source changed and the healthy `f5c07ff3` runtime was
left untouched.

The matching unsharded seeded coverage-only audit (`seed=20260828`, RC
generation) produced `3733` scenarios and `128` gaps (`31` critical, `10` high,
`87` normal). Critical gaps remain coverage dimensions rather than product
execution failures; the focused dogfood/cutover suite remained `89 passed`.

This ledger records semantic ownership before new work is added.  “Reuse” is
not counted as consolidation until the superseded authoritative path is
removed or reduced to a delegating compatibility boundary.

| Concept | Current owner | Target owner | Action | Legacy LOC before | Legacy LOC after | Runtime delta | Test evidence | Dogfood delta |
|---|---|---|---|---:|---:|---:|---|---|
| Turn orchestration | `src/agent_loop.py` + ACI seam | canonical ACI lifecycle | EXTEND / STRANGLE | 10296 | 9532 | -764 LOC vs measured pre-slice worktree; LOC reduction is not treated as authority removal by itself | focused + 6,658-test full regression green after chat Work-run pre-routing moved to ACI; pure post-result/message projections remain covered by focused suites | latest historical 62-case local qwen: 62/62 functional, 62/62 architectural, 62/62 security |
| Action/capability metadata | `src/capability_registry.py`, `src/tool_bindings.py`, `src/tool_capabilities.py` | existing registry + bindings | EXTEND | existing | existing | 0 | capability/ACI suites green | pending rerun |
| Dependency truth | `src/capability_dependencies.py` + broker allowlist | `src/capability_dependencies.py` | EXTEND / MERGE | 147 | 842 | +695 contract/adapter LOC; duplicate manager not added | dependency contract suite + 6,647-test full regression | coverage metadata exposes dependency gaps; runtime identity/platform preflight is now shared with Cookbook |
| Legacy dependency/package map | hand-maintained `REGISTRY` literal | typed `DEPENDENCY_REGISTRY` plus derived compatibility projection | DELETE / DELEGATE | 22 data LOC | 0 duplicated data LOC | removes second package truth; compatibility operation names remain import-stable | 19 focused dependency/resource tests | legacy network/DNS/package resolution remains green while canonical specs own binaries/packages |
| Legacy dependency health callers | free-standing `capability_health`/operation projections | `DependencyManager.inspect_operation` compatibility projection | DELEGATE | 1 public wrapper path | manager-owned projection; response shape preserved | health consumers share the canonical backend without a new dependency authority | 32 focused dependency/homelab/Cookbook/MCP tests + 6,641-test full regression | no behavior or authority change; canonical source is reported as `DEPENDENCY_REGISTRY` |
| Canonical read payload/action projection | loop-local helpers + DomainContract table | `src/aci.py` + `src/intent_contracts.py` | MOVE / DELEGATE | 68 | 0 authoritative LOC in loop | -68 loop LOC; aliases only for imports | 336 ACI/intent tests + full regression | fixture-backed run: 61/62 architectural |
| ACI result/evidence/context projections | loop-local completion grounding, result identity, evidence recognition, answer projection, and fallback context | `src/aci.py` pure projections with compatibility aliases | MOVE / DELEGATE | 307 | 0 semantic implementation LOC in loop | -307 loop LOC; no execution, policy, approval, or persistence authority moved | 272 focused ACI/read/loop tests + 6,641-test full regression | canonical completion/evidence boundaries remain unchanged; fallback context continues to exclude internal authority and untrusted results |
| Cookbook artifact/runtime mechanics | Cookbook routes/helpers/UI | existing `ArtifactManager` contracts with Cookbook adapters | EXTEND / DEMOTE | 22154 across audited paths | runtime preflight delegated; mature download/launch adapters retained | removes a second runtime identity/platform decision without moving execution authority | 130 focused Cookbook/resource tests green | known runtimes now validate through the shared artifact/runtime contract; unknown commands remain compatibility input |
| Durable composition substrate | `src/run_planner.py`, `src/work_engine.py`, `src/agent_runs.py` | existing WorkRun/WorkAction path | REUSE | existing | existing | 0 | planner/work suites | not started |
| Health/verification | `src/service_health.py`, `src/readiness.py`, `src/cookbook_serve_lifecycle.py` | existing health/probe owners | REUSE | existing | existing | 0 | readiness/lifecycle suites | not started |
| Background work | `src/bg_jobs.py`, `src/bg_monitor.py`, `src/task_scheduler.py`, `src/event_bus.py` | existing durable Run wakeups | REUSE / EXTEND | existing | existing | 0 | 33 continuation/scheduler/background tests; 6,620-test full regression green after explicit mode selection | bg monitor and task scheduler now invoke ACI explicitly; no second continuation engine |
| Dogfood evaluation | existing `benchmarks/hades_dogfood.py` | same evaluator, generative extension | EXTEND | existing | 1260 | test-only | 31 focused dogfood/resource tests + 6,668-test full regression; generated CLI coverage green | same authoritative evaluator now includes frame-backed semantic coverage, metamorphic, negative-near-miss, chaos-journey, cross-domain, failure-injection, coverage-audit, clustering, and provenance-envelope layers; full generation produced 6,540 reproducible cases with 86 raw coverage gaps, classified as 71 critical, 0 high, and 15 normal in the current generated mix |
| Semantic scenario frames | none | `benchmarks.hades_dogfood.ScenarioFrame` in the existing evaluator | NEW (test-only) | 0 | 180 | test-only | reproducibility, constrained-universe, frame round-trip, coverage, and cluster tests; 6,668-test full regression green | 1,000 frame sampler covers 17 entity types, 24 compatible intent classes, 27 properties, 10 relations, 4 graph depths, 10 temporal scopes, 9 epistemic states, and 17 reference strategies; final full generate-only run emits 6,540 cases and 84 raw gaps classified 33 critical, 11 high, 40 normal; no runtime authority |
| Canonical concept routing | legacy classifier + ACI compile | `src/intent_contracts.compile_intent` for supported concepts | STRANGLE / EXTEND | 44 duplicated call-site lines | compatibility fallback only | reduced duplicate domain decision for ACI-owned concepts | 314 focused + 6,603 full regression; Qwen quick unchanged at 53/62 | unsupported document/email/UI concepts remain explicitly legacy until their contracts are migrated |
| Canonical capability projection | ACI contract + legacy RAG/always-available/domain/skill expansion | ACI-resolved binding via existing registry | STRANGLE / DELETE duplicate projection | route-wide set plus expansion branches | one binding for unforced ACI-owned turns | removes legacy capability arbitration from canonical turns; no executor or policy change | 12 ACI lifecycle + 178 affected routing/background tests | local qwen quick: prompt 1779.5645 -> 1480.5323 tokens/task; functional 53/62, architectural 61/62, security 62/62 |
| ACI domain visibility projection | `src/agent_loop.py` legacy `_DOMAIN_TOOL_MAP` plus canonical `ToolBinding` registry | `src/tool_bindings.py.tools_for_domains` for ACI turns; legacy map retained only for compatibility callers | EXTEND / DEMOTE | 5 ACI call sites | canonical ACI projection helper; compatibility map remains non-authoritative for ACI | prevents legacy transport visibility from reintroducing a second capability palette while preserving import-stable legacy tests/callers | 106 affected routing/ACI/network tests + 6,670-test full regression | current generate-only semantic run: 6,540 cases, 84 frame-aware coverage gaps; source dirty and provenance recorded |
| ACI projection failure boundary | packet construction exception disabled ACI in `src/agent_loop.py` | existing ACI authority-free `MODEL_FALLBACK` path for production mode | HARDEN / DELETE AUTHORITY ESCAPE | 1 fallback branch | compatibility-only disable branch remains outside production ACI | prevents a projection failure from silently selecting legacy routing or execution semantics | 75 focused ACI/fallback/dogfood tests + 6,672-test full regression | no model/authority expansion; failure mode is now explicitly traceable as `aci_projection_failure` |
| Caller-independent canonical selection | ACI action projection depended on route-side `relevant_tools` even when the resolved contract already named a binding | `src/aci.py.project_action_selection` resolved binding candidate set | EXTEND / DELETE HIDDEN PRECONDITION | 1 selection guard | 0 dependency on route retrieval for resolved binding | deterministic ACI reads remain selectable after a cold/failed tool-index projection without widening the candidate set | 69 focused ACI/network tests + 6,673-test full regression | no new model call or tool lookup; canonical network read fast path remains available with `relevant_tools=None` |
| Canonical read payload shaping | loop-local memory/developer payload branches | `src/aci.py.canonical_read_fast_path_payload` | MOVE / DELEGATE | 15 | 0 authoritative LOC in loop | -15 loop LOC; shared ACI builder now serves fast and repair paths | 271 focused ACI/intent/developer/security tests | no new model work; payload semantics preserved |
| Safe contract fallback selection | duplicated loop-local fallback checks | `src/aci.py.safe_contract_fallback_selection` | MOVE / MERGE | 44 | 0 authoritative LOC in loop | removes duplicate fallback authority; loop now delegates both recovery sites | 128 focused ACI/fallback/security tests | no new model work; only resolved approval-free private reads remain eligible |
| Legacy canonical-read repair | loop-local generic/asset repair branches | legacy adapter only; ACI fast path is authoritative | DEMOTE | 57 | retained only outside ACI mode | ACI turns cannot reselect a canonical read after projection | 293 focused ACI/read/network tests; prior full regression green | no measured burden regression; compatibility behavior remains available to legacy callers |
| Failed ACI Action retry | loop could reselect a failed canonical Action in the same turn | ACI post-result transition to `BLOCKED`/answer-only | DELETE / EXTEND | repeated retry loop | one bounded attempt | prevents duplicate failed Actions without weakening policy or approval | 15 ACI lifecycle tests; focused dogfood journey regression | journey failure fixed; architectural 61/62 -> 62/62; failed Actions/task 0.4839 -> 0.4355 |
| ACI lifecycle trace | runtime metrics + dogfood normalization | existing ACI metrics and same dogfood record | EXTEND | 0 | 0 net control-plane authority | 0 | trace field regression + focused/full regression | required lifecycle fields are projected without prompt/secret retention |
| Unscoped discovery expectations | stale dogfood contracts required a tool for unauthorized scans | safety contract over canonical scope gate | EXTEND / DELETE stale expectation | 3 cases | 3 corrected cases | no runtime authority change; removes false retrieval failures | dogfood contract tests + local qwen rerun | all unscoped cases refuse with zero tool calls; security 62/62 |
| Synthetic journey execution | isolated synthetic turns despite journey labels | existing dogfood runner with transient conversation context | EXTEND | 0 | small test-runner delta | no production control-plane authority; prior turns now reach the same runtime call | dogfood tests + local qwen rerun | action-result journey domain/reference failure removed; 62/62 functional |
| Synthetic provider recovery | recovery expectations lacked fault injection in authoritative runner | existing provider fallback seam | EXTEND / REUSE | 0 | small test-runner delta | no new provider authority; primary endpoint fault is fixture-only | local qwen rerun | model-switch/provider-reconnect cases recover through configured fallback |
| Conversational reference continuity | loop-local semantic predicate | `src/aci.py.is_contextual_reference_followup` | MOVE / DELEGATE | 33 | 0 authoritative LOC in loop | net runtime LOC 0; ACI owns the predicate and loop is a caller | 134 focused ACI/intent/dogfood tests; 6,610 full regression green | latest journey run remains 62/62; no historical-domain stickiness on unrelated turns |
| Explicit continuation classification | loop-local regex/function | `src/intent_contracts.is_explicit_continuation` with compatibility aliases | MOVE / DELEGATE | 52 | 0 semantic implementation LOC in loop | removes pure continuation-language ownership from the orchestration engine; durable Run resolution remains canonical | continuation/intent/ACI regression suite green | terse approvals, ordinals, qualifiers, and negative near-misses preserve prior classification; no Action authority is granted by the classifier |
| Scheduled remote serve cleanup | `src/cookbook_serve_lifecycle.py` remote shell command | existing cleanup seam with fail-closed SSH verification | HARDEN / REUSE | 1 command path | same path, strict host-key policy | no new transport; unknown/changed keys now fail closed | 11 focused lifecycle/SSH tests green | compatibility cleanup remains bounded and reports failure instead of accepting an untrusted host |
| Action prerequisite projection | `ActionSpec.dependencies` plus capability-name compatibility declarations | `ActionSpec.dependencies` consumed by `DependencyManager` | EXTEND / DEMOTE | 1 exact action declaration + compatibility map | 1 authoritative action declaration; compatibility map explicitly non-authoritative | ACI no longer inspects a parallel per-capability declaration for selected actions | 38 focused resource/ACI tests green | exact `manage_homelab.execute_network_discovery` projection reports `binary.nmap`; no-dependency reads remain empty |
| Action dependency remediation plan | `DependencyManager.inspect_action` plus capability-level compatibility planner | existing `DependencyManager.ensure_action` | EXTEND / MERGE | 0 | 48 | +48 shared backend LOC; no installer or execution path added | 147 focused resource/ACI/intent tests + 6,647-test full regression; unknown actions fail closed | missing `binary.nmap` yields an approval-bound host/remote package plan that preserves the same Action for resume; available prerequisites produce no install action |
| Canonical intent normalizers | `agent_loop.py` keyword normalizers after frame compilation | `IntentFrame`/`DomainContract` for supported ACI concepts; normalizers only for compatibility concepts | DEMOTE | 3 post-frame normalizer calls | 0 on supported ACI turns; legacy calls retained only when no canonical frame exists | removes a second domain/operational evidence pass from ACI | 251 focused tests + 6,641-test full regression green | canonical ACI provisional ownership now skips the legacy normalizer pass before final frame compilation; no new model or tool authority |
| Hard-turn capability prompt | legacy `_hard_turn_capability_directive` in route builder | ACI packet/ActionCards for canonical turns | DEMOTE | 1 duplicate prompt injection | 0 on canonical ACI turns; compatibility routes retain it | removes redundant legacy capability guidance from canonical model context | focused ACI lifecycle regression | canonical turns retain the same binding/policy path with less prompt-control duplication |
| Cookbook remote probe trust | Cookbook binary/serve-adoption probes with permissive SSH options | existing SSH transport using owner known_hosts | HARDEN / REUSE | 3 bounded probe paths | strict `BatchMode` + `StrictHostKeyChecking=yes` on migrated probes | no new SSH authority; unknown/changed keys fail closed | focused Docker/probe + lifecycle suites | remote probe cannot silently accept an unverified host key |
| Shared SSH host-key boundary | `core.platform_compat` allowed caller-selected permissive mode | existing SSH adapter, fail-closed for every caller | HARDEN / EXTEND | permissive opt-out plus 3 production call sites | 0 production permissive call sites; adapter rejects `False` | all remote probes remain unattended and host-key verified without changing owner SSH configuration | 200 focused Cookbook/HWFit/shell/platform tests | no `StrictHostKeyChecking=no` remains in production source; unknown/changed keys fail closed |
| Cookbook remote setup transport | `server_setup` assembled local-shell SSH commands | existing `run_ssh_command_async` + shared SSH argv boundary | DELEGATE / HARDEN | 1 local-shell setup path | 0 local-shell SSH setup path | platform detection and setup reuse one validated transport; remote command mechanics preserved | 39 focused Cookbook/security tests + 6,636-test full regression | setup remains fixture/integration-verifiable and fails closed on missing/changed host keys |
| Post-packet network repair | legacy route could re-add a homelab binding after ACI projection | ACI ActionCard projection | DEMOTE / DELETE DUPLICATE | 1 branch | skipped for canonical ACI turns | prevents purpose-bounded canonical projections from being widened by legacy repair | 18 focused ACI lifecycle tests + 6,636-test full regression | no functional/security regression; canonical route remains single-binding |
| Post-round legacy action repairs | network continuation repair, host-context precheck, raw network conversion, explicit network recovery, first-class no-action repair, hard-action repair | ACI ActionCard/Result path; compatibility repairs remain legacy-only | DEMOTE / DELETE DUPLICATE | 6 post-provider repair paths | skipped for canonical ACI turns | prevents provider prose or malformed legacy tool output from selecting a second action after ACI projection | 18 focused ACI lifecycle tests + 6,636-test full regression | canonical ACI turns do not synthesize legacy `manage_homelab`/shell repairs; compatibility callers retain bounded recovery |
| Canonical homelab dependency callers | `homelab_operations.py` called compatibility health/handoff functions | `DependencyManager` methods with compatibility result shapes | DELEGATE / DELETE DUPLICATE CALLERS | 4 compatibility call sites | 0 canonical compatibility calls | homelab health and remediation now enter through the same manager used by ACI | 29 focused network/dependency/security tests | no authority or broker change; canonical dependency source remains preserved |
| Canonical status projections | persistent SelfState and intelligence status used compatibility health wrapper | `DependencyManager.inspect_operation` | DELEGATE | 2 compatibility call sites | 0 direct wrapper calls | status projections share manager ownership without changing API shape | 36 focused persistence/resource/intelligence tests | no health claims broadened; unavailable state remains explicit |
| Skills ACI caller boundary | Skills audit/test routes relied on the helper's legacy default | explicit `aci_mode="aci"` with legacy fallback only for unsupported contracts | STRANGLE / EXTEND | 2 implicit legacy call sites | 0 implicit production call sites | user-facing skill evaluation enters canonical ACI lifecycle | 11 focused Skills/approval tests | no new authority; exact approvals and owner scope remain unchanged |
| Teacher escalation authority | teacher recursion disabled ACI via `_is_teacher_run` | same canonical ACI lifecycle; `_is_teacher_run` is recursion guard only | DEMOTE / EXTEND | 1 legacy authority escape | 0 teacher ACI bypasses | stronger cognition cannot bypass ActionSpec, policy, approval, or executor boundaries | 24 focused teacher/resource tests | teacher output now re-enters ACI with the same authority model; teacher recursion remains disabled |
| Dogfood source provenance | run metadata recorded only `HEAD` | existing dogfood run envelope | EXTEND | missing dirty-state evidence | explicit `source_dirty` marker | prevents uncommitted evidence being mistaken for a source-matched candidate | 30 focused dogfood/resource tests; core generation green | current generated run records commit `4d20cd9` plus `source_dirty=true` and 105 coverage gaps |
| Unreferenced legacy helpers | four private helpers in `src/agent_loop.py` had no source or test references | no runtime owner | DELETE | 55 LOC | 0 | -55 legacy LOC; no authority or compatibility surface removed | 87 focused agent/ACI/resource tests green; syntax check green | no runtime path or evaluator behavior depended on these helpers |
| Unused Cookbook dependency import | `routes/cookbook_routes.py` imported both managers but used only the artifact projection | `artifact_manager` for model artifact contract checks; prerequisite ownership remains in `capability_dependencies.py` | DELETE | 1 LOC | 0 | removes misleading unused dependency-owner wiring; no installer behavior changed | canonical resource contract suite green | Cookbook download still validates through the shared artifact contract; no second dependency owner is introduced |
| Web evidence routing | `chat_routes.py` toggle/forced-tool shaping, legacy raw schemas, and existing `web.evidence` registry entries | `IntentFrame` WEB contracts + existing capability registry + canonical `web_search`/`web_fetch` ToolBindings; route policy remains the OFF boundary | EXTEND / DELETE duplicate | route toggle and duplicated schema paths | one semantic ACI projection plus compatibility transport handlers | removes manual routing and duplicate schema authority; AUTO is the default and OFF is explicit policy; ACI turns no longer prefetch web context | 164 focused route/intent/ACI/helper tests + 6,638-test full regression green | deterministic current/local reads avoid web; explicit current/external requests project bounded public evidence; schemas validate once and remain tainted/untrusted |
| Network intent/scope projection | `agent_loop.py` network CIDR/action predicates | `src/intent_contracts.py` pure semantic projections; broker remains execution authority | MOVE / DELEGATE | 42 | 0 authoritative LOC in loop; import aliases only | -42 loop LOC; fixes valid `10.x.x.x/CIDR` recognition while preserving private-scope bounds | 165 focused intent/ACI/network/resource tests green | explicit bounded private scopes are recognized; public/oversized/implicit scopes and explanatory near-misses remain non-actionable |
| Provider homelab alias translation | shared loop execution branch normalized legacy `manage_homelab` action names for every mode | legacy compatibility transport only; canonical ACI accepts registry-derived ActionSpec payloads | DEMOTE | 1 branch with 7 alias translations | skipped for canonical ACI mode | removes provider alias heuristics from the ACI control plane without changing legacy compatibility behavior | ACI/network/full regression suites | canonical provider decisions cannot widen or reinterpret an ACI-selected Action |
| ActionSpec trace projection | nested `_aci_action_trace` helper in `agent_loop.py` | `src/aci.py.action_trace` over existing registry | MOVE / DELEGATE | 29 | 0 authoritative LOC in loop; alias only | -29 loop LOC; telemetry remains observational | ACI lifecycle/resource focused tests | trace reports selected canonical identity without introducing a selector or executor path |
| Post-result transition | loop-local completion/failure branching over `classify_post_result` | `src/aci.py.project_post_result_transition` | MOVE / DELEGATE | 58 | 0 transition-decision LOC in loop | centralizes complete/read-failure/action-failure semantics; loop only applies flags and persists results | ACI lifecycle + full regression | failed canonical Actions cannot be reselected; deterministic reads transition directly to answer generation |
| Message envelope projection | loop-local latest-user/turn-count/context-insertion helpers | `src/aci.py` message projections | MOVE / DELEGATE | 31 | 0 authoritative LOC in loop; aliases only | consolidates ACI turn-envelope mechanics without changing upload security or delivery | ACI lifecycle + legacy agent-loop helper tests | protected context insertion and user-turn extraction remain deterministic and bounded |
| Chat Work-run pre-routing | `routes/chat_helpers.py` legacy classifier + normalizers followed by IntentFrame compilation | existing ACI provisional/final IntentFrame and canonical domain projection | DELETE DUPLICATE / EXTEND | 12 call-site lines plus duplicated domain map | 0 legacy classifier/normalizer calls | removes a second domain decision before durable Run creation; Work ledger and Action preparation remain the same | chat helper + ACI/intent focused tests | canonical communications/asset turns enter the same ACI semantic path before persistence |
| Network remediation intent projection | `agent_loop.py` diagnostic-install authorization and substantive network fallback helpers | `src.intent_contracts.explicitly_allows_diagnostic_install` and `network_substantive_fallback_command` | MOVE / DELEGATE | 64 | 0 authoritative LOC in loop; compatibility aliases only | -64 loop LOC; remediation evidence remains separate from broker/policy authority | 259 focused ACI/intent/network/chat/resource tests green | legacy text-tool fallback callers retain behavior through canonical contract imports; ACI still prefers registered ActionSpecs |
| Foreground ACI mode switch | `chat_routes.py` user-configurable `hades_aci_mode` selection | canonical foreground chat lifecycle with fixed `aci` entrypoint | DELETE DUPLICATE CONTROL | 4 | 0 mode-selection branch | removes a production setting that could re-enable a second authoritative orchestrator | 259 focused ACI/chat/resource tests green | stream helper retains its historical default only for explicit compatibility callers; generic settings API tombstones the old key |

## Measured dogfood checkpoint

The current local-model rerun used the existing synthetic fixture seam and real
local `qwen3:8b` endpoint. It is not a production or owner-data test.

| Metric | Frozen ACI baseline | Current local rerun |
|---|---:|---:|
| Scenarios | 62 | 62 |
| Functional success | 27 (43.55%) | 51 (82.26%) |
| Architectural success | 32 (51.61%) | 51 (82.26%) |
| Security checks | 60/62 (96.77%) | 62/62 (100%) |
| Model calls/task | 2.0323 | 0.9355 |
| Decision calls/task | 1.8226 | 0.1290 |
| Failed actions/task | 2.1613 | 0.6935 |
| Tool-index lookups/task | 0.0806 | 0.0806 |
| Prompt tokens/task | 5264.1774 | 1905.1452 |
| Context hydrations/task | 0 | 0 |
| Median / P95 latency | 6.3121 / 9.5282s | 2.8525 / 6.8872s |

The canonical-domain projection rerun (same 62-case contract and local model)
measured 52/62 functional (83.87%), 51/62 architectural (82.26%),
100% security, 0.9355 model calls/task, 0.129 decision calls/task, 0.6935
failed actions/task, 1,880.0323 prompt tokens/task, and 2.6082s / 7.8625s
median/P95 latency. After the generalized owner-hardware precedence fix, the
same contract measured 54/62 functional (87.10%), 51/62 architectural,
100% security, 1,865.4194 prompt tokens/task, and 3.3766s / 9.5481s
median/P95 latency. After declaring the canonical tool fixtures for frozen
cases, the latest rerun measured 53/62 functional (85.48%), 61/62
architectural (98.39%), 100% security, 0.8871 model calls/task, 0.0645
decision calls/task, 0.4839 failed actions/task, 1,779.5645 prompt
tokens/task, and 2.5001s / 10.3442s median/P95 latency. The subsequent
provisional canonical-concept routing slice measured 53/62 functional, 61/62
architectural, 100% security, 0.8871 model calls/task, 0.0645 decision
calls/task, 0.4839 failed actions/task, 1,779.5645 prompt tokens/task, and
2.8785s / 10.5633s median/P95 latency. Functional scoring is
stochastic across local-model runs; the architectural improvement is stable
in this comparison. This is a measured improvement, not a release gate pass.

The current rerun still fails the release gates and retains known semantic
failures. Generated coverage is an audit instrument; a generated case is not
counted as functional success until the runtime satisfies its oracle.

The latest canonical-capability projection rerun is recorded at
`/tmp/hades-dogfood-aci-canonical-projection.json` and is not a release artifact.
It retained 53/62 functional, 61/62 architectural, and 62/62 security success
while reducing prompt burden to 1480.5323 tokens/task. The run still has known
domain/reference and continuation failures, so this slice is retained as a
burden/duplication improvement rather than a readiness claim.

The failed-Action boundary rerun is recorded at
`/tmp/hades-dogfood-aci-failed-action-boundary.json`. It retains the same
functional result and 100% security result while fixing the journey-level
duplicate failure: architectural success is 62/62, decision calls/task are
0.0161, failed Actions/task are 0.4355, and prompt burden is 1373.3548
tokens/task. The full regression after the subsequent web-binding parity,
normalizer-boundary, and shared runtime-preflight changes is 6,638 passed, 3
skipped. The latest continuation/result-projection migration reran the full
suite at 6,641 passed, 3 skipped.

The generative scenario model is test infrastructure, not a runtime authority,
planner, package manager, or execution engine.  It must emit semantic fixtures
and expected invariants; production routing never imports its phrase variants.

The latest journey/scope rerun is recorded at
`/tmp/hades-dogfood-aci-final-journeys.json`. It used the existing local
`qwen3:8b` endpoint plus synthetic tool fixtures and is not a deployment or
owner-data test. It measured 62/62 functional, 62/62 architectural, and
62/62 security success; 0.8548 model calls/task, 0 decision calls/task,
0.4194 failed Actions/task, 0.0806 tool-index lookups/task, 1399.9516 prompt
tokens/task, 0 context hydrations/task, and 2.4538s / 8.7111s median/P95
latency. Unscoped network discovery refused with zero tool calls. Synthetic
multi-turn journeys now carry prior turns transiently, and provider recovery
cases inject a failed primary endpoint before using the configured fallback.
This remains a development checkpoint, not a production-readiness gate.

The evaluator generation checkpoint `2026-08-26` is preserved at
`/tmp/hades-dogfood-core-consolidation.json` with a fixed seed and
dirty-source marker.  It emitted 3,740
semantic cases (2,000 generated, 500 metamorphic, 500 negative near-miss, and
100 chaos-journey requests) and reported 62 explicit coverage gaps.  This is
coverage evidence only; no model or production data was used.  The current
working-tree `src/agent_loop.py` count is 9,470 LOC after moving additional
ACI network intent/scope and remediation intent projections out of the legacy loop, while the latest
full regression is 6,647 passed, 3 skipped. A refreshed web-AUTO generation is preserved at
`/tmp/hades-dogfood-web-auto.json`; it emitted 2,216 semantic cases and 62
coverage gaps without invoking a model. The latest runtime-contract
generation is preserved at `/tmp/hades-dogfood-runtime-contract.json`; it
emitted 3,740 reproducible semantic cases and 62 coverage gaps, with
`source_dirty=true` recorded in each run envelope.

The current local-model quick attempt could not be live-verified because the
configured Ollama endpoint at `127.0.0.1:11434` refused the connection. It is
recorded as provider-unavailable evidence, not as qwen performance evidence;
the historical qwen checkpoints above remain the only live-model measurements.

## Latest source-level checkpoint

The ACI binding visibility consolidation was verified against the current
working tree.  All six discovered production `stream_agent_loop` callers pass
`aci_mode="aci"`; `LEGACY_PRODUCTION_CALLERS=0`.  The focused caller,
projection, network, asset, dependency, and dogfood suites passed 87 and 106
tests respectively, followed by the full regression at 6,670 passed and 3
skipped.  The refreshed generate-only artifact is
`/tmp/hades-dogfood-semantic-universe-final3.json`: 6,540 reproducible cases,
84 semantic coverage gaps, and dirty-source provenance.  No deployment was
performed; the production image remains the known-good candidate sourced from
`d90bfbf9d05a22acc87411b8cbdc264cf4cd14fd`.

The subsequent ACI projection-failure boundary change is also covered by the
current full regression: 6,672 passed and 3 skipped. In `aci_mode="aci"`, a
packet-construction exception now enters the existing authority-free
`MODEL_FALLBACK` path and cannot disable ACI to re-enter legacy orchestration;
only explicit compatibility callers retain the old fallback behavior.

The CMDB persistence hardening extends the existing `asset_inventory.py` owner
with SQLite-native concurrency controls rather than introducing a state store:
connections use a bounded 30-second busy timeout and network observation
identity resolution runs inside `BEGIN IMMEDIATE`. The added invariant test and
the focused Network/Asset/ACI suites passed 81 tests; the full regression then
passed 6,674 tests, with 3 skipped. This preserves the existing NetworkState /
Asset split and makes concurrent discovery writers serialize before deciding
strong-identifier ownership.

The post-hardening semantic dogfood artifact is `/tmp/hades-dogfood-semantic-
universe-final5.json`: 6,540 reproducible cases, 84 coverage gaps (33
critical, 9 high, 42 normal), seed `20260826`, source commit
`4d20cd947015f7b8d4b8e5d600a6040c5f222610`, and `source_dirty=true`. It is a
generate-only coverage run; Ollama was unavailable, so it is not live-model
acceptance evidence.

Scheduled production execution was then consolidated: `src/task_scheduler.py`
no longer performs tool-index/RAG capability selection before invoking ACI.
It derives only the disabled-tool policy from `known_tool_names()` and passes
`relevant_tools=None`, making ACI the sole production shortlist/projection
authority for scheduled work. The task-shell, scheduler, ACI, and canonical
caller suites passed 65 tests. The retained `compose_task_relevant_tools`
helper is compatibility/test surface only and has no production caller.

The scheduler consolidation preserved the full regression at 6,674 passed and
3 skipped. `git diff --check` is clean. The production image was not rebuilt or
deployed because the working tree remains intentionally dirty and Ollama is
unavailable for live-model acceptance.

The follow-up policy-boundary slice removed the remaining production import
from `src/tool_policy.py` into the legacy prompt registry. Tool-name discovery
now uses canonical common names, native schemas, and security policy sets. The
focused policy/canonical/task suites passed 48 tests and the full regression
passed 6,675 tests with 3 skipped. This removes legacy prompt metadata from a
canonical authorization helper without changing execution authority.

The refreshed post-policy semantic artifact is `/tmp/hades-dogfood-semantic-
universe-final6.json`: 6,540 reproducible generate-only cases and 84 coverage
gaps, with the same fixed seed and dirty-source provenance. It remains
coverage evidence only because the local Ollama endpoint is unavailable.

Cookbook user-scoped package validation was consolidated into the existing
`DependencyManager`: its reviewed allowlist is now `USER_SCOPED_PACKAGES`, and
`plan_user_package()` returns installer/source/PEP-668/venv contract metadata.
`/api/cookbook/packages/install` remains the mature execution adapter after
admin validation; it no longer owns a duplicate package registry. Focused
Cookbook/dependency/security suites passed 178 tests with 1 skipped, followed
by the full regression at 6,676 passed and 3 skipped. Unreviewed package URLs
remain rejected.

Cookbook host-package planning was then consolidated into the same backend:
`DependencyManager.plan_host_packages()` now owns the reviewed host allowlist,
per-manager mappings, installer identity, and approval metadata for
apt/pacman/dnf/apk/zypper/brew. `/api/cookbook/install-system-deps` retains its
existing bounded admin/SSH execution adapter and no arbitrary package names or
commands are accepted. Focused coverage passed 179 tests with 1 skipped; the
full regression passed 6,677 tests with 3 skipped.

The corresponding generate-only semantic coverage refresh is
`/tmp/hades-dogfood-semantic-universe-final7.json`: 6,540 cases and 84
coverage gaps, fixed seed `20260826`, current dirty-source provenance, and no
live model calls.

The Network-to-Asset reconciliation slice extends the existing owner-scoped
CMDB and `network_projection.py`; no parallel asset store or reconciliation
service was introduced. `reconcile_candidate()` now provides explicit
confirm/reject/create semantics, keeps observations as evidence, and never
turns an observed IP into a canonical identifier. The existing authenticated
intelligence router exposes this as a thin `/api/network/assets/reconcile`
projection. Added coverage exercises owner promotion, named creation from an
unidentified observation, and cross-owner rejection. Module compilation and a
temporary isolated CMDB smoke test passed; the host Python environment lacks
the `pytest` executable, so the repository pytest suite could not be rerun in
this shell.

Using the candidate image as a disposable test environment, the current
checkout regression reached 4,806 passed and 4 skipped before the read-only
bind mount correctly caused `test_readiness_reports_core_subsystems` to fail
its writable-data probe. The preceding first failure was a real memory
grounding assertion: branch-aware current runtime evidence omitted the
historical qualification. `src/memory_grounding.py` now includes both the
current branch and `remembered branch state is historical`; the focused memory
suite passes 13 tests. No production data was mounted writable and no image
was rebuilt or deployed.

The Network/CMDB owner projection now exposes the same reconciliation contract
in the existing `static/js/intelligence.js` UI. Pending and unidentified nodes
show explicit owner Confirm/Reject controls; unidentified-node confirmation
requires a name, while rejection remains non-mutating evidence disposition.
The UI posts only candidate ID, decision, optional owner name, and bounded type
to `/api/network/assets/reconcile`; no frontend identity merge logic was added.
`node --check`, module compilation, diff checks, and an isolated confirm/reject
CMDB smoke test passed.

The broader production-caller compatibility suite was executed from the
current checkout in the project container: chat helpers and route policy,
scheduler task tools, background monitor, teacher escalation, and tool policy
passed 105 tests with 39 dependency deprecation warnings. This supplements
the 67-test ACI/CMDB/UI suite; no candidate image was rebuilt or deployed.

The focused current-checkout suite was then executed in the existing project
container (which supplies the declared pytest/httpx environment):
`tests/test_aci_lifecycle.py`, `tests/test_network_owner_scope.py`,
`tests/test_network_workspace_surface.py`, and
`tests/test_canonical_resource_contracts.py` passed 67 tests with 1 existing
SQLAlchemy deprecation warning. The first container run identified and fixed
only test-isolation/audit-boundary issues: CMDB projection tests now set both
the DB constant and environment path, and the caller audit excludes the
intentional ACI compatibility delegation itself.

Production stream entrypoint convergence then moved the six active callers in
chat, skills, background monitoring, scheduling, and teacher escalation from
direct legacy imports to `src.aci.stream_aci_turn`. That seam delegates to the
temporary implementation only after forcing `aci_mode="aci"`; it cannot be
used to select legacy or shadow behavior. A repository production-call audit
now finds six ACI imports/callers and zero direct legacy stream imports outside
the compatibility seam. Added coverage asserts that a legacy mode argument is
overridden to ACI. Compilation and diff checks passed; the full pytest suite
was not rerun because `pytest` is absent from the host shell.

The current checkout was also tested in a disposable candidate-image
container with read-only source plus isolated writable `data`, `logs`, and
fixture paths. The full suite produced 6,675 passed and 4 skipped; its only
six failures were storage-preflight tests because the container lacked the
expected `/home/.docker-data` mount. Re-running `tests/test_storage_preflight.py`
with a temporary bulk-storage mount passed all 6 tests. Thus the composed
current evidence is 6,681 passed and 4 skipped, with no source failure in this
cycle. The memory-grounding correction was independently verified by 13
focused tests.

The owner-managed built-in tool-description override loader was extracted to
`src/tool_overrides.py`. This is configuration projection only; it does not
define capabilities or authority. `agent_loop.py` retains the legacy
`TOOL_SECTIONS` prompt catalog because it is still coupled to prompt assembly;
moving that catalog without a schema-owner migration would only relocate
legacy control-plane complexity. Skills routes now consume the extracted
override owner directly. Affected compatibility/ACI/CMDB/UI tests passed 120
tests with 2 existing warnings; Python compilation and diff checks passed.

Reuse/deletion ledger delta: `get_builtin_overrides()` legacy implementation
removed from `agent_loop.py`; duplicate route-level configuration ownership
removed; no production execution authority changed. Remaining prompt-catalog
coupling is explicitly retained as compatibility debt pending a characterized
canonical textual projection migration.

Production stream callers no longer alias `stream_aci_turn` as the retired
`stream_agent_loop` name. Chat, Skills, background monitoring, scheduling, and
teacher escalation now call the canonical ACI entrypoint by name; the caller
audit rejects legacy aliases and all six callers still pass `aci_mode="aci"`.
The focused authority/ACI/chat/task suite passed 128 tests with 2 existing
warnings. This is a naming/observability consolidation only; the temporary
ACI compatibility seam remains the sole implementation bridge to the legacy
module and still forcibly sets ACI mode.

Intent normalization ownership was consolidated: `normalize_asset_inventory_intent`,
`asset_read_request`, and `normalize_homelab_intent` now live in
`src/intent_contracts.py`, the existing semantic resolver owner. `agent_loop.py`
retains import-stable aliases only; the three loop-local implementations were
deleted. The semantic intent, deterministic-read, dependency, ACI lifecycle,
regression, and dogfood suites passed 388 tests with 2 existing warnings.
`agent_loop.py` decreased from 9,496 to 9,461 LOC in this slice; no production
authority or security boundary changed.

Operational intent fusion now has a single implementation in
`src/intent_contracts.py`. The former 195-line loop-local implementation and
wrapper were removed; `agent_loop.py` retains only an import-compatible alias.
Post-removal compilation, diff checks, and the affected semantic/ACI/dogfood
suite passed 388 tests with 2 existing warnings. Current `agent_loop.py` size
is 9,268 LOC in the dirty checkout; no production authority or security
boundary changed.

Continuation audit (current checkout): background completion in
`src/bg_monitor.py` and scheduled execution in `src/task_scheduler.py` both
enter `src.aci.stream_aci_turn` with explicit `aci_mode="aci"`. The same audit
found no direct `stream_agent_loop` production calls outside `src/aci.py`; the
remaining legacy names are compatibility implementation seams and tests.
`src/agent_work_bridge.py` remains the durable Work projection and does not
execute model-supplied tools. Continuation-focused evidence passed separately:
canonical resource contracts 25, background monitor 3, Work bridge 25,
scheduler delivery 2, and scheduler restart/double-fire 4. The ACI lifecycle
file passed 29 tests separately. A combined multi-file invocation exposed
cross-module test monkeypatch interference (four failures), so that isolation
issue remains recorded rather than treated as a source regression.

Reuse/deletion ledger delta: continuation documentation now identifies ACI as
the control-plane owner; no new continuation daemon, Run store, executor, or
authority path was introduced. Background and scheduler compatibility names
remain only where existing tests/API shape require them.

Evaluator convergence: `scripts/hades_dogfood.py` now invokes the canonical
`src.aci.stream_aci_turn` entrypoint instead of importing the temporary loop
implementation directly. Added a source-contract regression asserting this
boundary. Canonical-resource and dogfood contract tests passed 49 tests after
the change; no model or production deployment was required.

Action-choice ownership: the model's validated packet choice is now resolved
through `src.aci.selected_action_for_decision`, which rechecks the selected
binding against the canonical CapabilityRegistry/ActionSpec before the stream
creates its transport `ToolBlock`. The loop no longer performs the raw
choice-map-to-action lookup. Existing execution, policy, approval, and Work
durability paths are unchanged. ACI/action/policy/bridge coverage passed 164
tests; the first attempt caught and corrected the actual ActionCard payload
shape (`payload.action`) rather than weakening the test.

Foreground compatibility repair: `routes/chat_routes.py` now exposes an
unset `stream_agent_loop` test hook while `_chat_stream_entrypoint` defaults
to `stream_aci_turn` and passes `aci_mode="aci"` explicitly. This restores
existing route-test injection without restoring a production legacy caller or
legacy authority. Foreground routing plus canonical caller audit passed 128
tests.

Full current-checkout regression after the action-resolution and foreground
compatibility slices passed 6,683 tests with 4 skips and 150 warnings in a
disposable candidate-image container with isolated data/log/probe paths and a
temporary storage fixture. This is source-matched test evidence only; no image
was built, deployed, or treated as live-model verification. The temporary
storage mount is required by the storage-preflight tests and is not a host
configuration change.

Cookbook/dependency owner audit: `src/capability_dependencies.py` is already
the canonical owner for typed dependency/artifact/runtime/verification
declarations, platform mapping, package allowlists, status, and prerequisite
resume plans. Cookbook model download and serve routes consume
`artifact_manager` for artifact/runtime validation, while their mature HF,
Ollama, venv, retry, tmux, Windows, SSH, and endpoint lifecycle mechanics
remain execution adapters. `/api/cookbook/setup` still contains the legacy
remote setup runner and is explicitly retained as migration debt: it uses
fixed reviewed commands and strict host-key SSH, but is not yet a canonical
installer execution path. No second DependencyManager was introduced and no
unsafe package or shell authority was widened.

Operational intent fusion was consolidated into `src/intent_contracts.py`,
the existing semantic resolver owner. The loop-local implementation and wrapper
were removed; only an import-stable compatibility alias remains in
`agent_loop.py`. ACI, deterministic-read, intent, dependency, and dogfood
coverage passed 388 tests with 2 existing warnings; a post-removal ACI/read
rerun passed 194 tests. `agent_loop.py` decreased from 9,461 to 9,268 LOC.

Decision interpretation consolidation: `src/aci.py` now owns the pure
interpretation of a validated `DecisionContract` through
`resolve_decision_outcome`, including registry-backed Action choice resolution,
narrow private-read contract fallback, and bounded answer projection. The
stream retains only the transport adapter that creates the existing
`ToolBlock`; policy, approval, execution, verification, and persistence remain
at their canonical owners. The focused ACI lifecycle/contract/resource suite
passed 69 tests with 2 existing warnings. This removed a duplicate decision
interpretation branch without adding a planner or execution path.

The stream adapter was tightened further to call `resolve_decision_outcome`
once for every valid ACI decision. Its previous separate ACTION/non-ACTION
branches were removed; only the returned ACI projection is converted into the
existing transport block or answer text. The affected ACI, fallback, route,
and canonical-resource suite passed 98 tests with 2 existing warnings.

Post-extraction repository regression: the full source-mounted suite passed
6,684 tests with 4 skips and 150 warnings in 268.47 seconds. It used the
disposable candidate image with isolated data/log/probe paths and the existing
temporary storage fixture; no image was built or deployed. Current
`agent_loop.py` is 9,274 LOC versus 10,284 LOC at the checked-out HEAD before
the dirty strangler work, and the static caller audit still reports zero
`stream_agent_loop(...)` calls outside `src/aci.py` and `src/agent_loop.py`.

Dogfood covering-array reporting was extended in the existing evaluator (no
parallel evaluator): scalar registry/semantic coverage now includes a bounded
pairwise/targeted-3-way report for the required high-risk dimensions. The
generate-only run with seed `20260827` produced 12,740 reproducible cases
(10,000 semantic, 1,000 metamorphic, 1,000 near-miss, and 100 chaos journeys
plus the contract corpus), with 86 scalar coverage gaps: 33 critical, 9 high,
and 44 normal. Targeted observed coverage included 100% for
network/authority/VPN, 99.03% for reference/domain-switch/stale, and 57.0%
for memory/current-observation/conflict. This is generator/report evidence,
not live-model acceptance; the dogfood unit suite passed 23 tests with 2
existing warnings.

Coverage-report correction: the high-risk report now carries explicit
`network_scope` (HOME/WORK/VPN/UNKNOWN), `address_state` (including
DHCP_CHANGED), and `asset_identity_strength` fields in each ScenarioFrame;
the prior broad proxy labels were removed. Replayed seed `20260827` therefore
reports 60.29% for network-scope/authority/cross-domain, 25.0% for
address-change/identity/reference, and 99.03% for reference/domain-switch/
stale. Scalar totals remain 12,740 cases and 86 gaps (33 critical, 9 high,
44 normal). This is a reporting correction, not a production behavior claim.

Bounded decision-recovery consolidation: `src/aci.py` now owns the pure
repair-versus-`MODEL_FALLBACK` decision for malformed/stale bounded model
packets through `resolve_decision_recovery`. `agent_loop.py` retains only the
transport work (append the repair instruction or enter the existing
authority-free fallback); it no longer decides the retry budget or recovery
mode. ACI/fallback/dependency/resource tests passed 73 tests with 2 existing
warnings. No execution, approval, or provider authority changed.

NetworkState projection slice: extended the existing canonical CMDB projection
with a 15-minute freshness policy, per-observation provenance/freshness, last
observed timestamps, and bounded derived-state metadata. No Network database or
identity store was added; IP-only observations remain non-canonical and
owner-scoped reconciliation is unchanged. Network/Asset/Homelab projection
coverage passed 43 tests with 2 existing warnings. This is fixture/source
integration evidence; live host discovery was not exercised or claimed.

Combined regression after NetworkState freshness and ACI recovery changes:
139 tests passed with 2 existing warnings, including ACI lifecycle, dependency
contracts, Network/Asset/Homelab projections, tool bindings, and semantic
dogfood tests. Compilation and `git diff --check` also passed.

SSH transport hardening: the retained admin-gated `builtin_actions` SSH
compatibility action now delegates to the existing `core.platform_compat`
`run_ssh_command` owner instead of constructing its own permissive argv. The
delegation preserves timeout/port behavior while enforcing batch mode and
strict host-key verification. Canonical/resource/platform/auth regression
coverage passed 66 tests with 2 existing warnings; no SSH keys or host
configuration were changed.

Invalid-decision convergence: extended the existing `src/aci.py` ACI
projection with `InvalidDecisionResolution` and `resolve_invalid_decision`.
Malformed model packets now have one ACI-owned disposition: the already-safe
deterministic contract fallback, one bounded repair, or the existing
authority-free model fallback. `agent_loop.py` only applies the returned
transport/recovery instruction. No new planner, registry, execution path, or
authority was introduced. Focused ACI lifecycle/contract/model-fallback tests
passed 48 tests with 2 existing warnings; compilation and `git diff --check`
passed.

Production cutover guard: added an AST-based regression test over runtime
packages. It reports six canonical `stream_aci_turn` callers and zero direct
`stream_agent_loop` callers outside the ACI seam/compatibility implementation.
The guard plus ACI lifecycle tests passed 35 tests with 2 existing warnings.

Post-consolidation full regression: the source-mounted disposable candidate
environment passed 6,690 tests with 4 skips and 150 warnings in 272.70s. The
run included the new ACI invalid-decision projection and production cutover
guard; no image was built or deployed and the known-good production image was
not modified.

Checkout reconciliation refresh: local HEAD remains
`4d20cd947015f7b8d4b8e5d600a6040c5f222610`; `origin/HEAD` is
`dbaddbdaac7ebb8586628e36dad62b397942cb67`, with 217 local commits ahead and
0 behind. The worktree currently has 54 tracked modified files and 20
untracked evaluator/spec/test artifacts. Current runtime counts are
`agent_loop.py` 9,282 LOC, `aci.py` 1,988 LOC, and 152,095 Python LOC across
`src`, `routes`, `core`, and `services`. These counts include preserved dirty
work and are not a clean release measurement.

Cookbook local installation consolidation: the existing allowlisted
`/api/cookbook/install-system-deps` projection now sends local package requests
through the existing `privileged_broker` `install_packages` action, preserving
the DependencyManager package allowlist and admin gate. Its prior local shell
execution branch was removed; remote package setup remains an explicit
compatibility adapter pending a canonical remote-package ActionSpec. Focused
canonical resource/shell/broker regression passed 151 tests with 2 existing
warnings. No package installation was performed on the host.

Post-installation-consolidation full regression: the source-mounted disposable
candidate environment passed 6,691 tests with 4 skips and 150 warnings in
275.76s. No image was built or deployed.

Dogfood measurement correction: fixed the existing evaluator's reference
accuracy denominator so `NOT_REFERENCE` turns are excluded while
`UNRESOLVED`/ambiguous reference attempts remain measured. Added a regression
test and retained all scoring gates; dogfood tests passed 24 tests with 2
existing warnings. This corrects reporting only and does not improve runtime
behavior by assertion.

Dependency revalidation hardening: ACI ActionSpec choice validation and the
narrow malformed-decision contract fallback now reject projected actions whose
canonical dependency plan is not `AVAILABLE`. This prevents missing or
approval-required prerequisites from becoming speculative execution while
leaving remediation with the existing DependencyManager/broker path. ACI,
work-bridge, dependency, and contract tests passed 90 tests with 2 existing
warnings; no installation was attempted.

Post-revalidation full regression: the source-mounted disposable candidate
environment passed 6,693 tests with 4 skips and 150 warnings in 274.18s. No
image was built or deployed.

ACI caller-mode guard: extended the existing production cutover AST guard to
require every runtime `stream_aci_turn` caller to pass the literal `aci` mode.
This keeps the compatibility default confined to direct compatibility callers
and prevents a future production caller from silently selecting legacy mode.
The ACI lifecycle/cutover suite passed 37 tests with 2 existing warnings.
No production image was built or deployed.

Document editor projection ownership: moved `_document_stream_events` from
`agent_loop.py` into the existing `src/agent_tools/document_tools.py` as
`document_stream_events`. The loop retains only a compatibility alias; events
are emitted only after the existing authorized document execution path. Focused
document/context/ACI coverage passed 256 tests with 2 warnings. The
source-mounted full regression passed 6,702 tests with 4 skipped and 150
warnings in 275.49s. `agent_loop.py` is 8,637 LOC. No image was built or
deployed.

Document stream projection ownership: audited and moved `_document_stream_events`
from the legacy loop into the existing `src/agent_tools/document_tools.py` as
`document_stream_events`. The loop retains only a compatibility alias; the
projection consumes an already-authorized document block and does not execute
or authorize anything. Focused document/context/ACI coverage passed 256 tests
with 2 warnings. The source-mounted full regression passed 6,702 tests with 4
skipped and 150 warnings in 275.49s. No image was built or deployed.

Full regression after context route-normalization extraction: source-mounted
candidate test run passed 6,702 tests with 4 skipped and 150 warnings in
275.10s. No production image was built or deployed.

Completion verifier strangler: the existing optional fresh-context verifier is
now gated by the canonical ACI module and cannot run for production ACI turns.
ACI completion remains owned by `project_post_result_transition` and durable
Run verification; compatibility streams retain the explicit legacy opt-in.
Focused coverage passed 68 tests, and the full source-mounted regression
passed 6,697 tests with 4 skips and 150 warnings in 270.30s. No production
image was built or deployed.

Completion authority strangler: added the ACI-owned
`legacy_completion_verifier_allowed` gate and routed the optional fresh-context
verifier through it. Production ACI turns now rely on the existing
`project_post_result_transition`/durable Run completion path and cannot incur a
second verifier model call; direct legacy compatibility callers retain the
explicit opt-in verifier. ACI, cutover, and dependency tests passed 68 tests
with 2 existing warnings. No production image was built or deployed.

Remote dependency projection: extended the existing DependencyManager with a
typed `plan_remote_packages` projection that reuses the host allowlist and
marks the strict-SSH execution boundary/target. The Cookbook remote package
path now consumes that projection. Reconciled an existing registry mismatch by
adding the already broker-allowlisted `nmap` package to the shared Cookbook
allowlist and DNF mapping. Focused dependency/SSH/Cookbook tests passed 152
tests with 2 existing warnings; no remote or local package installation was
attempted.

Post-remote-projection full regression: the source-mounted disposable
candidate environment passed 6,694 tests with 4 skips and 150 warnings in
275.63s. No image was built or deployed.

Package-allowlist parity: reconciled the existing privileged broker allowlist
with the DependencyManager/Cookbook reviewed host package set (`cmake`,
toolchain/build packages, `git`, `tmux`, `make`, and `nmap`). Added a regression
asserting the projection set is a broker subset. Focused broker/dependency
coverage passed 84 tests with 2 existing warnings; no package operation was
performed.

Post-parity full regression: the source-mounted disposable candidate
environment passed 6,695 tests with 4 skips and 150 warnings in 272.52s. No
image was built or deployed.

Semantic dogfood coverage: extended the existing generator to reserve a
deterministic archetype pass for canonical but thin product families before
general ScenarioFrame sampling. Kitchen, Finance, Background Work, and
Dependency cases are now represented in core generated runs without adding
production routing rules. Dogfood tests passed 25 tests; the 1,693-case core
coverage artifact reduced reported gaps from 173 to 165.

NetworkState projection: extended the existing owner-scoped CMDB projection
with bounded derived freshness totals (fresh, stale, unknown), projected
observation count, latest evidence timestamp, and explicit current-state
classification. Raw observations remain evidence and Assets remain identity;
no second store or identity merge was introduced. Network/asset/UI coverage
passed 16 tests, and the full source-mounted regression passed 6,698 tests
with 4 skips and 150 warnings in 274.43s. No production image was built or
deployed.

ACI dependency-status projection: enriched the existing ActionCard projection
with the observed prerequisite status and a bounded remediation/readiness note.
This is model-facing visibility only; `selected_action_for_decision` continues
to fail closed unless the canonical DependencyManager plan is AVAILABLE.
Focused ACI/dependency coverage passed 65 tests, and the full source-mounted
regression passed 6,698 tests with 4 skips and 150 warnings in 275.45s. No
production image was built or deployed.

Cookbook SSH health-probe hardening: audited retained Cookbook remote execution
paths and found the externally-adopted model server health probe lacked the
centralized unattended/host-key options. Added `BatchMode=yes` and
`StrictHostKeyChecking=yes` to that compatibility probe, preserving the
existing validated target flow. Added a regression that inspects the emitted
health command, while leaving all installer/runtime ownership in the existing
Cookbook/DependencyManager boundary. Focused Cookbook SSH/helper coverage
passed 93 tests with 1 existing skip; the full source-mounted regression passed
6,699 tests with 4 skips and 150 warnings in 276.22s. No package operation,
image build, or production deployment was performed.

Local-computer intent ownership: moved the pure local/named-machine target
predicate and its regex evidence from `agent_loop.py` into the existing
`intent_contracts.py` semantic owner. The loop retains only a compatibility
alias; no tool, executor, scope, or authority decision moved with it. This
removes the legacy loop's duplicate semantic implementation without adding a
router or execution path. Focused characterization and full regression are
the required verification gates for this slice.

Local-computer extraction verification: focused workspace/intent/ACI
characterization passed 352 tests with 2 existing warnings. The source-mounted
full regression passed 6,699 tests with 4 skips and 150 warnings in 272.80s.
`agent_loop.py` decreased from 9,292 to 9,265 LOC; the moved predicate is now
owned by `intent_contracts.py` and the loop exposes only a compatibility alias.
No image was built or deployed.

Dead compatibility residue: removed the now-unused `_LOW_SIGNAL_RE` constant
from `agent_loop.py` after low-signal classification and Skill suppression had
both moved to `intent_contracts.py`. Compile checks and `git diff --check`
passed; no runtime behavior changed and no image was built or deployed.

Semantic dogfood checkpoint after the Skill projection slice: the existing
authoritative generator produced 6,540 reproducible synthetic semantic cases
(`full`, seed 0, generation-only) and reported 65 coverage gaps. The gaps are
coverage metadata (mostly normal intent/combination expansion), not a claim of
runtime success; the generated artifact is `/tmp/hades-dogfood-full-after-skill.json`.
No live model, owner data, image build, or deployment was used.

Provider sampling ownership: moved Odysseus-Qwen model identification and its
temperature ceiling from `agent_loop.py` into the existing `llm_core.py` as
`is_odysseus_qwen_model` and `odysseus_qwen_temperature_cap`. The loop retains
compatibility aliases; primary and fallback route behavior remains unchanged.
Focused provider/ACI/cutover coverage passed 177 tests with 3 warnings. The
source-mounted full regression passed 6,702 tests with 4 skipped and 150
warnings in 278.07s. `agent_loop.py` is 8,624 LOC. No image was built or
deployed.

Action-requirement policy ownership: moved the pure domain-to-action-required
predicate into `src/aci.py` as `intent_requires_action`; `agent_loop.py` now
retains only a compatibility alias. The legacy domain prompt policy remains
unchanged for compatibility routing, while ACI owns this bounded lifecycle
predicate. Focused ACI/cutover/plan/network/continuity coverage passed 104
tests with 2 warnings. No production image was built or deployed.

Workspace intent ownership: moved workspace-coding and missing-workspace
reference predicates from `agent_loop.py` into `intent_contracts.py`. The loop
now retains only compatibility aliases; prompt text, workspace validation, and
developer execution authority remain unchanged. Focused intent/workspace/ACI
coverage passed 184 tests with 2 existing warnings. The source-mounted full
regression passed 6,699 tests with 4 skips and 150 warnings in 274.29s.
`agent_loop.py` decreased from 9,265 to 9,226 LOC. No image was built or
deployed.

Provider normalization ownership: moved the forward-only `<think>` block
sanitizer and empty-response fallback from `agent_loop.py` into existing
`llm_core.py` provider mechanics. The loop retains compatibility aliases for
historical callers/tests; no response semantics, fallback authority, or tool
execution behavior changed. Provider/reasoning regression coverage passed 44
tests with 2 existing warnings. The source-mounted full regression passed
6,699 tests with 4 skips and 150 warnings in 274.56s. `agent_loop.py`
decreased from 9,226 to 9,174 LOC. No image was built or deployed.

Provider normalization verification: removed the legacy helper bodies from
`agent_loop.py`; only compatibility aliases remain, while `llm_core.py` is the
single implementation owner. Reasoning/protocol coverage passed 44 tests with
2 existing warnings. The source-mounted full regression passed 6,699 tests
with 4 skips and 150 warnings in 274.56s. `agent_loop.py` remains at 9,174 LOC
after the extraction; no image was built or deployed.

Runaway guard consolidation: moved the existing identical-call loop breaker
from `agent_loop.py` into `aci.py`, retaining only a compatibility alias in the
loop. The isolated guard suite passed 6 tests and the isolated ACI/cutover
suite passed 38 tests (2 existing warnings each). The current source-mounted
full regression passed 6,699 tests with 4 skips and 150 warnings in 271.74s.
No execution semantics, policy, approval, or authority changed; no image was
built or deployed.

Document transport ownership: moved document-model artifact stripping and
truncated/compact document-fence normalization from `agent_loop.py` into the
existing `tool_parsing.py` protocol owner. The loop retains compatibility
aliases only; document parsing and execution contracts are unchanged. Focused
document/parser/ReDoS coverage passed 43 tests with 2 existing warnings. The
source-mounted full regression passed 6,699 tests with 4 skips and 150
warnings in 276.82s. `agent_loop.py` decreased from 9,164 to 9,082 LOC. No
image was built or deployed.

Document transport verification: the parser-family migration passed 43 focused
tests with 2 existing warnings and the current source-mounted full regression
passed 6,699 tests with 4 skips and 150 warnings in 276.82s. `agent_loop.py`
decreased from 9,164 to 9,082 LOC while `tool_parsing.py` became the single
document-fence normalization owner. No image was built or deployed.

Qwen artifact normalization ownership: moved the existing Odysseus/Qwen
dropped-letter repair table and normalizer from `agent_loop.py` into existing
`llm_core.py` provider mechanics. The loop retains a compatibility alias only;
the repair remains scoped to the known model path and does not become general
language rewriting. Focused provider/Qwen coverage passed 121 tests with 3
warnings. The source-mounted full regression passed 6,699 tests with 4 skips
and 150 warnings in 273.28s. `agent_loop.py` decreased from 9,082 to 9,035
LOC. No image was built or deployed.

ACI usage telemetry ownership: moved the pure per-round usage bucket and
aggregate usage projection into `src/aci.py` as `usage_bucket` and
`usage_bucket_summary`; the legacy loop now retains compatibility aliases only.
No provider, billing, or execution authority changed. Focused agent-loop,
metrics, ACI, provenance, and cutover coverage passed 112 tests with 2
warnings. `agent_loop.py` decreased from 8,758 to 8,715 LOC and `src/aci.py`
is 2,284 LOC. `git diff --check` is clean. No image was built or deployed.

ACI trace projection ownership: moved the owner-safe `aci_trace` construction
from the legacy stream body into `aci.py` as a pure projection over existing
IntentFrame/Action/Result observations. No execution, policy, approval,
completion, or persistence authority moved; the loop only supplies observed
values. Focused lifecycle/dogfood/metrics coverage passed 65 tests with 2
warnings. The current source-mounted full regression passed 6,699 tests with
4 skips and 150 warnings in 272.91s. `agent_loop.py` decreased from 9,035 to
9,017 LOC. No image was built or deployed.

Semantic scenario constraint ownership: retained the existing dogfood
generator as the semantic evaluator owner and added entity-compatible
property/relation constraints to `ScenarioFrame` generation. This improves
PERSON/HOST/NETWORK and related-entity coverage without adding production
routing rules or a phrase dictionary. Focused ACI/dogfood/cutover coverage
passed 63 tests with 2 warnings. No runtime authority or production code
changed; no image was built or deployed.

Continuation decision ownership: moved the bounded eligibility predicate for
safe automatic Run continuation from `agent_loop.py` into the existing ACI
projection module as `should_project_safe_auto_continuation`. The durable Run
and step validation remain owned by `agent_work_bridge`; the loop retains only
the compatibility stream/execution handoff. Focused ACI/work-bridge/cutover
coverage passed 64 tests with 2 warnings. The source-mounted full regression
passed 6,700 tests with 4 skips and 150 warnings in 276.69s. No image was
built or deployed.

Result observation ownership: moved post-Result verification, approval, policy,
and executor trace projection from inline `agent_loop.py` bookkeeping into the
existing ACI projection module as `project_result_observation`. This is
observational only; policy enforcement, verification execution, durable Result
persistence, and Run lifecycle remain in their existing owners. Focused
ACI/work-bridge/cutover/dogfood coverage passed 90 tests with 2 warnings. The
source-mounted full regression passed 6,701 tests with 4 skips and 150 warnings
in 275.51s. No image was built or deployed.

Execution progress plumbing consolidation: extracted the duplicated async
progress-queue/task-cancellation wrapper for approved and ordinary tool calls
from `agent_loop.py` into the existing canonical `tool_execution.py` dispatcher
as `stream_tool_execution`. The helper adds no authority or executor path and
preserves injected compatibility executors plus generator-close cancellation.
Focused execution/ACI/cutover coverage passed 41 tests with 2 warnings. The
source-mounted full regression passed 6,701 tests with 4 skips and 150 warnings
in 273.99s. `agent_loop.py` decreased from 9,020 to 8,970 LOC. No image was
built or deployed.

MCP discovery projection consolidation: moved browser-server qualified tool
enumeration from the legacy loop into the existing `McpManager` as
`qualified_tools_for_server`. The loop no longer owns raw MCP discovery; the
manager returns transport names only and execution authorization remains at
the dispatcher boundary. Focused MCP/ACI/cutover coverage passed 46 tests with
2 warnings; one stale ownership assertion was updated to the canonical owner.
The source-mounted full regression passed 6,702 tests with 4 skips and 150
warnings in 276.01s. `agent_loop.py` is 8,949 LOC. No image was built or
deployed.

Provider route ownership: moved endpoint/model tool-transport classification,
endpoint-key normalization, and API-host metadata from `agent_loop.py` into the
existing `endpoint_resolver.py` as `agent_route_tool_mode`,
`endpoint_lookup_keys`, `is_ollama_openai_compat_url`, and `API_TOOL_HOSTS`.
The loop retains compatibility aliases only; endpoint credential matching and
provider transport heuristics remain behaviorally unchanged and do not grant
execution authority. Focused provider-routing/ACI coverage passed 165 tests
with 3 warnings. The source-mounted full regression passed 6,702 tests with 4
skips and 150 warnings in 275.89s. `agent_loop.py` decreased from 8,949 to
8,819 LOC. No image was built or deployed.

MCP local-schema projection ownership: moved selected dynamic MCP schema
filtering and the compatibility keyword fallback from `agent_loop.py` into the
existing `mcp_manager.py` as `select_local_mcp_schemas` and `MCP_KEYWORDS`.
The loop retains compatibility aliases only; MCP discovery remains distinct
from authorization. Focused MCP/agent-loop/ACI characterization passed 108
tests with 2 warnings. The source-mounted full regression passed 6,702 tests
with 4 skips and 150 warnings in 274.35s. `agent_loop.py` decreased from
8,819 to 8,790 LOC. No image was built or deployed.

Response-grounding predicate ownership: moved the pure destructive-request
classifier used by final ungrounded-success suppression from `agent_loop.py`
into the existing ACI grounding module as `looks_like_destructive_request`.
The loop retains a compatibility alias; execution policy and mutation gates are
unchanged. Focused first-class/ACI/routing coverage passed 180 tests with 3
warnings. The source-mounted full regression passed 6,702 tests with 4 skips
and 150 warnings in 273.78s. `agent_loop.py` is 8,785 LOC. No image was built
or deployed.

Plan-note ownership audit: reviewed `build_active_plan_note` and its callers
against `run_planner.py` and `work_engine.py`. The existing planner owns
durable Run compilation/validation; the note is a route-specific prompt pin
for the temporary compatibility stream and has no independent Run, Action, or
completion authority. No new projection module was created. Focused ACI,
dogfood, MCP, deterministic-read, and cutover characterization passed 272
tests with 2 warnings. A reproducible semantic run generated 5,000
ScenarioFrames and 6,000 rendered cases (including metamorphic and negative
near-miss layers), covering 17 semantic entity types, 24 intents, 10
relations, and 17 reference strategies, with 65 reported coverage gaps. No
runtime or production deployment was changed.

Full regression after approved-plan projection extraction: source-mounted
candidate test run passed 6,702 tests with 4 skipped and 150 warnings in
274.83s. No production image was built or deployed.

Approved-plan context projection ownership: moved the pure
`build_active_plan_note` model-context projection into `src/aci.py`; the
legacy loop retains only the imported compatibility symbol. Durable plan truth,
Run compilation, and step validation remain owned by Work/Run infrastructure.
The existing plan-mode regression plus ACI, cutover, first-class, and
deterministic-read suites passed 251 tests with 2 warnings. `agent_loop.py`
decreased from 8,785 to 8,761 LOC; `src/aci.py` is 2,231 LOC. `git diff
--check` is clean. No image was built or deployed.

Action-requirement policy ownership: moved the pure domain-to-action-required
predicate into `src/aci.py` as `intent_requires_action`; `agent_loop.py` now
retains only a compatibility alias. The legacy domain prompt policy remains
unchanged for compatibility routing, while ACI owns this bounded lifecycle
predicate. Focused ACI/cutover/plan/network/continuity coverage passed 104
tests with 2 warnings. `agent_loop.py` is 8,758 LOC and `src/aci.py` is 2,242
LOC. No production image was built or deployed.

Directive projection ownership: moved `_prepend_agent_directive` into
`src/aci.py` as `prepend_agent_directive`; the legacy loop retains only a
compatibility alias. Focused routing/context/ACI coverage passed 314 tests with
3 warnings. The source-mounted full regression passed 6,702 tests with 4
skips and 150 warnings in 271.97s. `agent_loop.py` is 8,668 LOC and no direct
production callers invoke `stream_agent_loop`. No image was built or deployed.

Context route-normalization ownership: moved `_strip_agent_injected_messages`
from `agent_loop.py` into the existing `context_compactor.py` as
`strip_agent_injected_messages`. Protected ACI packets remain preserved while
route-specific prompt wrappers are rebuilt; no authority or durable state
semantics changed. Focused context/continuity/ACI/cutover coverage passed 240
tests with 2 warnings. `agent_loop.py` decreased from 8,699 to 8,681 LOC.
No production image was built or deployed.

Completion-evidence snapshot ownership: moved the bounded tool-event snapshot
used by the completion verifier into `src/aci.py` as
`build_actions_snapshot`; the loop retains a compatibility alias. It remains
observational only and does not grant or validate execution authority. Focused
agent-loop/ACI/external-context coverage passed 152 isolated external-context
tests and the full source-mounted regression passed 6,702 tests with 4 skips
and 150 warnings in 273.90s. No production image was built or deployed.

Full regression after ACI usage telemetry consolidation: source-mounted
candidate test run passed 6,702 tests with 4 skipped and 150 warnings in
276.66s. No production image was built or deployed.

Full regression after action-requirement predicate extraction: source-mounted
candidate test run passed 6,702 tests with 4 skipped and 150 warnings in
274.47s. No production image was built or deployed.

Provider-boundary audit: endpoint transport classification remains owned by
`src/endpoint_resolver.py` (`agent_route_tool_mode`), provider wire behavior
and Qwen-specific transport compatibility remain owned by `src/llm_core.py`,
and model capability profiles remain owned by
`src/model_capability_profiles.py`. The remaining `_route_finetune_modes` and
`_route_relevant_tools` closures in `agent_loop.py` are compatibility prompt
shaping that depends on the stream's active document, intent, guide mode, and
ACI projection state; extracting them would add a new abstraction without
removing an authority or duplicate registry. Decision: RETAIN temporarily as
legacy compatibility logic, with ACI bypassing its authoritative selection
when canonical projection is active. Current runtime has no direct production
`stream_agent_loop` callers; only `src/aci.py` is the compatibility seam.
Provider/ACI/cutover characterization passed 278 tests with 3 warnings,
including ACI production caller guards, foreground route behavior, provider
classification, endpoint construction, and local-only transport safety. The
semantic dogfood/ACI/cutover subset passed 65 tests with 2 warnings. Current
`agent_loop.py` is 8,624 LOC; `aci.py` is 2,318 LOC. No image was built or
deployed.

Full source-mounted regression after provider-boundary audit passed 6,702
tests with 4 skips and 150 warnings in 271.29s. No image was built or
deployed.

MCP disabled-policy projection ownership: moved `_load_mcp_disabled_map` from
`agent_loop.py` into `src/mcp_manager.py` as `load_mcp_disabled_map`. The
stream retains only an import alias; MCP execution continues to re-check
disabled tools at the execution boundary. Added malformed/empty policy
coverage. Focused MCP/cutover coverage passed 8 tests with 2 warnings;
`git diff --check` is clean. `agent_loop.py` decreased from 8,624 to 8,607
LOC; `mcp_manager.py` is 827 LOC. The prior full source-mounted regression
after this code change passed 6,702 tests with 4 skips and 150 warnings in
273.95s. No image was built or deployed.

Lifecycle telemetry ownership: moved pure `_compute_final_metrics` aggregation
from `agent_loop.py` into `src/aci.py` as `compute_final_metrics`. The loop
retains only a compatibility alias; telemetry remains observational and cannot
select, authorize, execute, or complete an Action. Added an import-boundary
fallback for lightweight compatibility test stubs so the extracted document
projection remains test-order independent. Focused agent-loop/chat-metrics/ACI
coverage passed 102 tests with 2 warnings; the source-mounted full regression
passed 6,703 tests with 4 skips and 150 warnings in 272.68s. `agent_loop.py`
is 8,607 LOC. No image was built or deployed.

Upload-context projection ownership: moved `_uploaded_files_context_message`
from `agent_loop.py` into the existing `src/context_compactor.py` as
`uploaded_files_context_message`. Attachment metadata remains bounded and is
wrapped as untrusted context; no file authority or execution semantics moved.
The loop retains only a compatibility alias. Focused agent/ACI/cutover and
prompt-security coverage passed 97 tests with 2 warnings plus 15 prompt
injection tests with 2 warnings. The source-mounted full regression passed
6,703 tests with 4 skips and 150 warnings in 274.49s. `agent_loop.py` is 8,472
LOC. No image was built or deployed.

Completion-verifier ownership: moved the compatibility-only verifier and its
effectful-tool/max-round constants into `src/aci.py` as
`run_legacy_completion_verifier`, `VERIFIER_EFFECTFUL_TOOLS`, and
`VERIFIER_MAX_ROUNDS`. `agent_loop.py` retains compatibility aliases only;
`legacy_completion_verifier_allowed` continues to reject production ACI turns.
Focused completion/ACI coverage passed 120 tests with 2 warnings. Full
source-mounted regression passed 6,703 tests with 4 skips and 150 warnings in
274.72s. No image was built or deployed.

Upload-context extraction full verification: the source-mounted full regression
passed 6,703 tests with 4 skips and 150 warnings in 275.44s. Current
`agent_loop.py` is 8,442 LOC and `context_compactor.py` is 781 LOC. No image
was built or deployed.

Operational domain contract ownership: moved hard/deterministic/specialized
operational-domain metadata from `agent_loop.py` into existing
`src/intent_contracts.py` constants. The loop retains import-compatible aliases
only; these flags describe projection/cognition requirements and do not own
policy or execution authority. Syntax and diff checks passed; focused intent,
ACI lifecycle, production-cutover, and first-class tool tests passed 200 tests
with 2 warnings. The deployed candidate remains the prior source checkpoint;
this local slice has not been built or deployed.

Approval projection deduplication: removed the redundant
`_privileged_action_requires_exact_approval` wrapper from `agent_loop.py` and
bound its compatibility name directly to the existing
`capability_registry.requires_exact_approval` function. Focused approval/tool
security/ACI coverage passed 135 tests with 2 warnings. The source-mounted
full regression passed 6,703 tests with 4 skips and 150 warnings in 278.41s.
`agent_loop.py` is 8,438 LOC. No image was built or deployed.

Document identity projection ownership: moved `_is_email_document_obj` from
`agent_loop.py` into existing `src/agent_tools/document_tools.py` as
`is_email_document_object`, preserving the exact language/title/header
contract. The loop retains only a compatibility alias. Isolated external
context coverage passed 152 tests; agent/ACI/document/cookbook characterization
passed 323 tests before the expected stateful-suite isolation, and the full
source-mounted regression passed 6,703 tests with 4 skips and 150 warnings in
273.08s. Current `agent_loop.py` is 8,427 LOC. No image was built or deployed.

Email-draft context compaction ownership: moved the pure bounded email-draft
context formatter `_compact_email_draft_context` from `agent_loop.py` into the
existing `src/agent_tools/document_tools.py` as `compact_email_draft_context`.
The stream retains only an import alias for compatibility; draft truncation and
history bounding remain unchanged, and no routing, authority, or execution
semantics moved. Isolated external-context coverage passed 152 tests with 2
warnings, and the source-mounted full regression passed 6,703 tests with 4
skips and 150 warnings in 277.17s. `agent_loop.py` is now 8,401 LOC, a net
26-line reduction in the current checkout. No image was built or deployed.

Result-summary projection ownership: moved the pure bounded note, calendar, and
email result formatters from `agent_loop.py` into `src/aci.py` as canonical
ResultProjection helpers. The stream retains import aliases only; output
formatting, truncation, and no-second-model-pass behavior are unchanged. No
new registry, execution path, or authority was introduced. Focused agent/ACI/
cookbook characterization passed 180 tests with 1 skip; isolated external
context coverage passed 152 tests with 2 warnings; the source-mounted full
regression passed 6,703 tests with 4 skips and 150 warnings in 271.67s.
`agent_loop.py` is now 8,230 LOC, a 171-line reduction for this slice. No image
was built or deployed.

Terminal result projection ownership: moved the deterministic local-model
terminal summary formatter `_ody_qwen_terminal_tool_summary` from
`agent_loop.py` into `src/aci.py` as `ody_qwen_terminal_tool_summary`. The loop
retains only a compatibility alias; it continues to use the same resolved tool
event and bounded note/calendar/email projections. No provider authority,
selection, or execution behavior changed. Focused agent/ACI/cookbook coverage
passed 180 tests with 1 skip; the source-mounted full regression passed 6,703
tests with 4 skips and 150 warnings in 274.26s. `agent_loop.py` is now 8,209
LOC, a 21-line reduction for this slice. No image was built or deployed.

Saved-memory context projection ownership: moved the bounded
`_minimal_saved_memory_message` helper from `agent_loop.py` into the existing
`src/memory_grounding.py` module as `minimal_saved_memory_message`. It continues
to preserve explicit canonical-result status, deduplicate and cap facts, and
wrap saved content as untrusted context. The loop retains only a compatibility
alias; no memory store, retrieval authority, or prompt trust boundary changed.
Memory/agent characterization passed 76 tests with 2 warnings; isolated
external-context coverage passed 152 tests with 2 warnings; the source-mounted
full regression passed 6,703 tests with 4 skips and 150 warnings in 275.16s.
`agent_loop.py` is now 8,156 LOC, a 53-line reduction for this slice. No image
was built or deployed.

Recent tool-context projection ownership: moved the bounded
`_minimal_recent_notes_tool_context_message` helper from `agent_loop.py` into
`src/aci.py` as `minimal_recent_notes_tool_context_message`. It continues to
project only recent relevant IDs/results, cap command/output/history sizes, and
mark the context untrusted for follow-up reference resolution. The loop retains
only a compatibility alias; no tool registry, execution authority, or durable
state owner changed. Memory/ACI/loop characterization passed 113 tests with 2
warnings; isolated external-context coverage passed 152 tests with 2 warnings;
the source-mounted full regression passed 6,703 tests with 4 skips and 150
warnings in 278.83s. `agent_loop.py` is now 8,062 LOC, a 94-line reduction for
this slice. No image was built or deployed.

Semantic dogfood checkpoint: executed the existing authoritative evaluator in
the supported disposable runtime with seed 0 and 1,000 generated semantic
frames, 500 metamorphic variants, 500 negative near-misses, and 50 generated
journeys. It generated 2,493 reproducible cases and reported 64 coverage gaps;
the current artifact identified 11 critical gaps, 2 high gaps, and the balance
as normal coverage expansion. This is generation/coverage evidence only (no
live model calls); Ollama remains unavailable. The older checked-in baseline
artifact reports 284 gaps and is retained as historical evidence rather than
silently rewritten.

Memory identity-intent ownership: moved the pure `_looks_like_memory_identity_turn`
predicate from `agent_loop.py` into existing `src/memory_grounding.py` as
`looks_like_memory_identity_turn`. The loop retains only a compatibility alias;
memory routing vocabulary remains owned beside canonical memory grounding. The
focused memory/loop/external suite passed 228 tests with 2 warnings; the
source-mounted full regression passed 6,703 tests with 4 skips and 150 warnings
in 279.04s. `agent_loop.py` is now 8,050 LOC, a 12-line reduction for this
slice. No image was built or deployed.

Notes/calendar intent ownership: moved `_looks_like_notes_turn` and
`_looks_like_notes_calendar_followup` from `agent_loop.py` into existing
`src/intent_contracts.py` as `looks_like_notes_request` and
`looks_like_notes_calendar_followup`. The loop retains compatibility aliases;
these predicates remain evidence only and do not select, authorize, or execute
tools independently. Intent/loop/cookbook characterization passed 299 tests
with 1 skip; the source-mounted full regression passed 6,703 tests with 4 skips
and 150 warnings in 277.91s. `agent_loop.py` is now 8,035 LOC, a 15-line
reduction for this slice. No image was built or deployed.

Active-document relevance ownership: moved `_turn_targets_active_document`
from `agent_loop.py` into the existing `src/agent_tools/document_tools.py` as
`turn_targets_active_document`. The loop retains only a compatibility alias;
the predicate remains bounded document-context evidence and cannot select,
authorize, or execute a tool. Separate characterization passed 299 tests with
1 skip; the isolated external-context suite passed 152 tests with 2 warnings;
the source-mounted full regression passed 6,703 tests with 4 skips and 150
warnings in 274.27s. `agent_loop.py` is now 7,969 LOC, a 66-line reduction for
this slice. No image was built or deployed.

Compact model-prompt projection ownership: moved the existing specialized
`_minimal_odysseus_doc_messages`, `_minimal_odysseus_notes_messages`, and
`_minimal_odysseus_general_messages` prompt projections from `agent_loop.py`
into `src/aci.py`. They retain the same bounded document/context contracts,
untrusted-context wrapping, model-specific tool syntax, and compatibility
behavior; the loop retains aliases only. No new model router, planner, or
authority path was introduced. Separated agent/foreground/memory/intent
characterization passed 294 tests with 3 warnings; isolated external-context
coverage passed 152 tests with 2 warnings; the source-mounted full regression
passed 6,703 tests with 4 skips and 150 warnings in 274.02s. `agent_loop.py`
is now 7,834 LOC, a 135-line reduction for this slice. No image was built or
deployed.

Full semantic dogfood coverage checkpoint: ran the existing evaluator at its
full named tier in the supported disposable runtime (`seed=0`, synthetic
generation only). It produced 6,540 reproducible semantic cases across the
existing contract, generated frames, metamorphic variants, negative
near-misses, and journeys. Coverage audit reported 65 gaps: 32 critical, 2
high, and 31 normal. Critical gaps are now explicit authority/lifecycle and
failure-class work items (including disabled policy, approval replay/digest,
completion/continuation, dependency/execution failures, and grounding); no
model inference or live production operation was claimed. The generated
artifact is `/tmp/hades-dogfood-full-current.json`; the checked-in historical
artifacts remain unchanged. No image was built or deployed.

Production caller audit: AST inspection of `routes`, `src`, and `core` found
six active production callers of `stream_aci_turn` (chat, skills, background
monitoring, scheduler, and teacher escalation) and no direct legacy caller.
The one remaining `stream_agent_loop` reference is the documented internal
compatibility implementation invoked lazily by `src/aci.py`; it is not an
owner-facing caller and receives `aci_mode="aci"` from the canonical seam.
This remains the principal strangler debt: the ACI entrypoint is authoritative
for production selection, while the implementation body has not yet been
fully relocated/deleted. No image was built or deployed.

Casual low-signal intent ownership: moved the existing bounded
`_is_casual_low_signal` predicate from `agent_loop.py` into
`src/intent_contracts.py` as `is_casual_low_signal`. The loop retains only a
compatibility alias and its punctuation-only regex; no routing, capability,
policy, or execution authority was added. Focused characterization passed 294
tests with 3 warnings. `agent_loop.py` is now 7,809 LOC, a 25-line reduction
for this slice. The source-mounted full regression then passed 6,703 tests
with 4 skips and 150 warnings in 277.08s. No image was built or deployed.

Tool-protocol normalization ownership: moved `_resolve_tool_blocks` from
`agent_loop.py` into the existing `src/tool_parsing.py` boundary as
`resolve_tool_blocks`. Native-call conversion and textual markup parsing now
share one provider/parser implementation; policy, target validation, and
execution remain downstream canonical owners. The loop retains only a
compatibility alias. Focused parser/loop characterization passed 303 tests
with 3 warnings; the source-mounted full regression passed 6,703 tests with 4
skips and 150 warnings in 276.92s. `agent_loop.py` is now 7,754 LOC, a
55-line reduction for this slice. No image was built or deployed.

Tool-result follow-up projection ownership: moved `_append_tool_results` from
`agent_loop.py` into the existing `src/aci.py` lifecycle projection as
`append_tool_results`. Native provider message shape, reasoning continuity,
tool-result provenance, and untrusted-result wrapping now have one owner; tool
execution, policy, and durable Result truth remain downstream canonical owners.
The loop retains only a compatibility alias. Focused message/security tests
passed 81 tests with 2 warnings; the source-mounted full regression passed
6,703 tests with 4 skips and 150 warnings in 273.60s. `agent_loop.py` is now
7,632 LOC, a 122-line reduction for this slice. No image was built or
deployed.

Compatibility intent classification ownership: moved the legacy retrieval-hint
classifier from `agent_loop.py` into the existing `src/intent_contracts.py` as
`classify_compatibility_request`, with the loop retaining a thin wrapper that
injects existing ACI continuation/reference/memory seams. First-class ACI
intent contracts remain the authority; this projection is only for legacy
concepts not yet covered by those contracts. Focused semantic/routing tests
passed 258 tests with 2 warnings; the source-mounted full regression passed
6,703 tests with 4 skips and 150 warnings in 276.16s. `agent_loop.py` is now
7,374 LOC, a 258-line reduction for this slice. No image was built or
deployed.

Admin intent evidence ownership: moved `_detect_admin_intent` and its keyword
contract from `agent_loop.py` into the existing `src/intent_contracts.py` as
`detect_admin_intent`. The loop retains only a compatibility alias; this
predicate controls prompt visibility evidence and does not grant execution
authority. The standalone policy suite passed 18 tests; the authoritative
source-mounted full regression passed 6,703 tests with 4 skips and 150
warnings in 550.38s. `agent_loop.py` is now 7,348 LOC, a 26-line reduction
for this slice. No image was built or deployed.

Machine/workspace prompt projection ownership: moved the pure
`_local_computer_rules` and `_workspace_coding_rules` blocks from
`agent_loop.py` into existing `src/aci.py` projections as
`local_computer_rules` and `workspace_coding_rules`. The loop retains aliases
only; these blocks remain context guidance and do not grant tool or execution
authority. Prompt and injection characterization passed 107 tests with 2
warnings; the source-mounted full regression passed 6,703 tests with 4 skips
and 150 warnings in 943.97s. `agent_loop.py` is now 7,318 LOC, a 30-line
reduction for this slice. No image was built or deployed.

Skill intent projection ownership: moved explicit Skill-request detection and
automatic Skill-context suppression from `agent_loop.py` into the existing
`src/intent_contracts.py` as `looks_like_explicit_skill_request` and
`suppress_automatic_skills`. The loop retains a compatibility alias and a thin
wrapper injecting the existing owner-scoped memory predicate. Focused memory,
Skill-injection, routing, and disconnect tests passed 130 tests with 3
warnings. A subsequent full regression was intentionally interrupted after
426 tests at 6% because runtime became anomalously long; it is not claimed as
passing. `agent_loop.py` is now 7,287 LOC, a 31-line reduction for this slice.
No image was built or deployed.

Prompt assembly projection ownership: moved selected-tool domain-rule
projection and builtin tool-section override lookup from `agent_loop.py` into
existing `src/aci.py` helpers `domain_rules_for_tools` and
`effective_tool_section`. The loop retains thin adapters that supply its
existing prompt registries and override source; no capability, policy, or
execution authority moved into the projection layer. An import-order defect
found by focused collection was corrected by making the override source an
explicit adapter dependency. Syntax and diff checks passed; focused prompt,
tool, routing, security, and continuity tests passed 70 tests with 2 warnings.
`agent_loop.py` is now 7,279 LOC, an 8-line reduction for this slice. The
latest full regression remains pending; no image was built or deployed.

Operational prompt guidance ownership: moved hard-action starters, bounded
fallback commands, follow-up hints, and turn capability directives from
`agent_loop.py` into existing `src/aci.py` projection helpers. The loop now
retains only compatibility aliases; execution, policy, approval, and target
authority remain outside this prompt layer. An initial focused command used a
nonexistent test path and was discarded as invalid evidence; corrected ACI,
parser, prompt-security, and cutover coverage passed 99 tests with 2 warnings.
Syntax and diff checks passed. `agent_loop.py` is now 7,176 LOC, a 111-line
reduction for this slice. The latest full regression remains pending; no image
was built or deployed.

Prompt assembly authority: moved the generic selected-tool prompt formatter
from `agent_loop.py` into `src/aci.py` as `assemble_prompt`, with tool sections,
rules, and override adapters injected by the compatibility wrapper. Formatting
is now an ACI projection; capability identity, policy, execution, and Result
truth remain canonical elsewhere. Focused ACI, lifecycle, cutover, prompt
security, and first-class tool coverage passed 99 tests with 2 warnings.
`agent_loop.py` is now 7,118 LOC; this local slice has not been built or
deployed.

Skill-index projection ownership: moved owner-scoped Skill catalogue
formatting from `agent_loop.py` into existing `src/aci.py` as
`skill_index_prompt`. The Skill manager remains the storage/registration owner;
the projection is explicitly untrusted and grants no authority. Focused ACI,
lifecycle, cutover, Skill-injection, prompt-security, and first-class tool
coverage passed 102 tests with 2 warnings. `agent_loop.py` is now 7,073 LOC;
this local slice has not been built or deployed.

Prompt tool-selection ownership: moved bounded prompt inclusion/disablement
selection from `agent_loop.py` into existing `src/aci.py` as
`select_prompt_tools`, with the registry, always-available set, and admin set
injected by the compatibility adapter. Static full-prompt cache behavior is
preserved; selected names remain projection metadata and do not grant
execution authority. Lifecycle/ACI/cutover coverage passed 99 tests in
isolation and Skill-index injection passed 3 tests in isolation. A combined
run that loaded the Skill test's import stubs first was discarded as test-order
contamination, not product evidence. `agent_loop.py` is now 7,070 LOC; this
local slice has not been built or deployed.

Intent preparation ownership: moved ACI-first provisional intent selection and
compatibility-normalizer gating from `agent_loop.py` into existing
`src/aci.py` as `resolve_turn_intent`. Legacy classification and normalizers
are injected adapters and cannot override an ACI-owned contract. Durable Run
hydration, reference persistence, continuation, policy, and execution remain
outside this projection helper. Focused intent/ACI/lifecycle/cutover tests
passed 212 tests with 2 warnings. `agent_loop.py` is now 7,048 LOC; this local
slice has not been built or deployed.

Durable reference-source ownership: added `reference_context_for_turn` to the
existing `src/agent_work_bridge.py` and replaced the loop's inline Run/session
lookup with that adapter. Active owner-scoped Run references remain preferred;
recent session results are consulted only for structured ordinal/pronoun
references, preventing unrelated turns from inheriting stale context. Focused
bridge, ACI, lifecycle, cutover, first-class tool, and corpus tests passed 117
tests with 2 warnings. `agent_loop.py` is now 7,033 LOC; this local slice has
not been built or deployed.

Intent-frame compilation ownership: moved IntentFrame compilation,
resolved-contract projection, continuation resolution, and canonical-domain
projection orchestration behind the existing ACI seam as
`compile_turn_contract`. The loop now consumes the compiled contract and
applies only the resulting durable-state/message transitions; it no longer
independently invokes those resolvers. Focused intent, ACI, continuation,
bridge, and first-class tool coverage passed 237 tests with 2 warnings.
`agent_loop.py` is now 7,024 LOC; this local slice has not been built or
deployed.

Owner-session hotfix ownership: extended the existing deterministic read and
Asset inventory owners for owner-scoped hardware/component aggregation. The
resolver now projects bounded component queries (for example `2080`) into the
existing canonical CMDB attributes read, and `asset_inventory` searches its
structured attributes without using model prose as state. Kitchen/household
mutations were exposed as additional ActionSpecs on the existing
`inventory.manage` capability and delegated through the existing `manage_assets`
ToolBinding to `inventory_service`/`inventory_tools`; no second registry,
binding, or execution engine was introduced. The live dogfood harness now
records and asserts `[DONE]`, terminal count, abrupt EOF, event/delta identity,
and duplicate-finalization telemetry. Focused inventory, binding, ACI, and
live-harness coverage passed 88 tests with 2 warnings. Checkpoint deployment
then committed and pushed source
`c55501290b73994b9651b5802295fa41661cc2cf`, built it as
`odysseus:candidate-c5550129b73`, and deployed it explicitly. The running
source marker and `/api/version` match that SHA. The prior known-good rollback
image remains `odysseus:rollback-b471e104-prev` (source
`b471e10455ba846373ca89449fc021cea21ace2e`).

Checkpoint verification: source-mounted full regression passed `6,713 passed,
5 skipped, 150 warnings` in approximately 305 seconds. Python compile and diff
checks passed. Focused suites passed. The deployed candidate is healthy with
zero restarts; Chroma, broker, scheduler, and readiness checks were verified.
Live owner-authenticated Qwen acceptance was not run because the required
acceptance credential was unavailable; that evidence remains explicitly
UNVERIFIED.

ACI prompt-base projection: moved the pure bounded tool-selection, prompt
rendering, static-prompt fallback, and untrusted Skill-index assembly from
`agent_loop.py` into `src/aci.py.build_base_prompt`. The loop retains only a
compatibility adapter supplying its historical registries and preserving
existing test/import seams. No capability, policy, execution, or durable
state authority moved into the prompt projection. Focused ACI, cutover, and
prompt-injection coverage passed 25 tests; `py_compile` and diff checks pass.
`agent_loop.py` is now 6,999 LOC (31 lines removed). This development slice
has not been deployed; production remains the last-green checkpoint source
`c55501290b73994b9651b5802295fa41661cc2cf`.

ACI prompt-message assembly: moved trusted-system insertion, consecutive
system-message merging, and placement/reordering of document, email,
integration, MCP, Skill, and time supplements into
`src/aci.py.finalize_prompt_messages`. The legacy loop now supplies the
already-built projections and receives the ordered message list through a
compatibility call; untrusted supplements remain outside the trusted system
role. Focused ACI, injection, workspace, lifecycle, cutover, and inventory
coverage passed 148 tests; full regression is pending for this working slice.
`agent_loop.py` is now 6,897 LOC (102 ACI lines added, 117 loop lines
removed). Production remains pinned to the deployed `c555012…` checkpoint.

Network/Asset vertical-slice evidence: added a permanent regression for DHCP
address changes. Two owner-scoped observations with the same MAC but different
IP addresses resolve to one Asset, retain both temporal observations, and
create no IP identity. Network owner-scope, intent, and workspace-surface
coverage passed 22 tests. This confirms the existing `asset_inventory` and
`network_projection` owners satisfy the identity boundary without adding a
second NetworkState store.

Remote homelab ownership audit: the existing `HomelabOperations` and
`manage_homelab` ActionSpec/ToolBinding remain the canonical local operator
path. Cookbook already exposes reusable strict SSH transport mechanics through
`core.platform_compat._ssh_exec_argv` and
`routes.cookbook_helpers.run_ssh_command_async`; those helpers enforce
`BatchMode=yes`, `StrictHostKeyChecking=yes`, bounded connection/process
timeouts, and captured results. Cookbook route handlers and the legacy
`builtin_actions` SSH wrapper remain compatibility/projection paths and are not
canonical remote-homelab authority. No remote ActionSpec was added in this
audit because the current canonical Asset schema has no reviewed SSH target
reference/credential binding. The next remote slice must extend the existing
Asset/Homelab contract with an opaque target reference and then delegate to
the strict transport; it must not accept a model-supplied host or import a
Cookbook route as an executor. No code was copied or moved and no production
caller changed. Focused SSH transport characterization remains the gate before
implementation.

Canonical remote-read slice: extended the existing `homelab.manage` capability
with `ssh_connect_test` and `remote_host_inspect`. The ActionSpec and binding
accept only an owner Asset reference; `HomelabOperations` resolves the stored
SSH target, validates it, and delegates fixed read-only commands to
`core.platform_compat.run_ssh_command`, which reuses Cookbook's strict SSH
transport mechanics. No caller can supply an arbitrary remote host, command,
credential, or permissive host-key setting. Focused contract/network/SSH tests
passed 137 tests with 1 skipped and 1 warning. This is fixture-verified only;
no remote host was contacted and production remains pinned to the last-green
image. The next slice is remote fixture/integration verification and canonical
Asset SSH enrollment metadata, before any remote mutation is considered.

Remote intent regression: explicit phrases such as “check the remote server
Morpheus via SSH” were initially classified as `TECHNICAL_ASSET` because the
generic server/asset read predicate ran before remote-target interpretation.
The existing `intent_contracts` compiler now gives explicit remote/SSH host
language precedence, extracts only the bounded host/Asset reference, and
projects the request to `HOMELAB_HOST/REMOTE_READ` →
`homelab.manage/remote_host_inspect`. Added paraphrase regressions for host,
server, and machine wording; intent and deterministic-read coverage passed
290 tests with 1 skipped and 1 warning. No phrase-specific production action
was added and no authority boundary changed.

Semantic dogfood expansion: added a dedicated `remote_host` ScenarioFrame
family to the existing evaluator, mapped to the canonical
`homelab.manage:remote_host_inspect` ActionSpec with a no-side-effect oracle.
The evaluator suite passed 26 tests. A seeded core generation produced 1,693
cases and reduced reported coverage gaps from 204 to 202; this is generation
coverage only, not live-model success. The generated artifact was kept outside
the repository and contains no raw prompts or answers.

Live protocol completion coverage: extended the authoritative
`scripts/hades_dogfood.py --mode live` path to retain sanitized SSE terminal
evidence (`done_seen`, terminal count, abrupt EOF, event identity, and
transport completion). Missing or duplicate `[DONE]` markers now fail the
architectural score instead of being silently discarded. Added deterministic
regressions for complete, abrupt, and duplicate-terminal streams. Focused
dogfood/live-harness coverage passed 48 tests; no owner credential or live
Qwen run was available. This is a development slice pending full regression
and candidate promotion.

Canonical Asset read grounding: added `src.aci.canonical_asset_read_answer` as
a bounded ResultProjection for successful `manage_assets` reads. Asset
collection/detail answers now derive names and present structured fields from
the canonical Result only; empty collections are explicit and failed or
non-Asset results are not synthesized. The loop emits a `response_replace`
event rather than a second answer delta. Focused ACI, inventory, deterministic
read, and dogfood coverage passed 276 tests. This prevents fabricated hardware
and inventory rows without changing policy, execution, or persistence
authority; full regression and live Qwen verification remain pending.

Canonical Asset aggregation projection: extended the existing
`intent_contracts` → `aci.canonical_read_fast_path_payload` →
`tool_execution` → `asset_inventory` chain for component/model counts. The
compiler marks a structured Asset query as a count projection, the executor
preserves only that bounded metadata alongside filtered canonical rows, and
`canonical_asset_read_answer` renders the count without model arithmetic or
prose-derived inventory. No new service, registry, store, or execution path
was introduced. Focused ACI/Asset regression passed 84 tests. Local changes
are not yet committed or deployed; live Qwen verification remains unavailable.

Household capability entry: moved the plain-chat auto-escalation eligibility
predicate into `intent_contracts.is_bounded_owner_capability_turn` and reused
it from the chat transport. The existing Household/Inventory contracts now
enter canonical ACI for reads and mutations from chat, while the resolved
contract still distinguishes read-only explanation from mutation. No new
executor, store, registry, or authority path was added. Focused intent,
inventory, and chat-policy coverage passed 198 tests with 1 skipped. Live
Qwen verification remains unavailable.

Canonical Household read projection: extended `src.aci` with a bounded
`canonical_household_read_answer` over the existing `read_household` Result
and wired it into the existing final `response_replace` path. Empty and
populated kitchen/household reads now render only structured inventory values;
mutations remain owned by the existing Inventory service adapter. No second
store or executor was added. Focused ACI/inventory/intent/binding coverage
passed 243 tests with 1 skipped. Live Qwen verification remains unavailable.

Canonical IT-asset write projection: extended the existing
`TECHNICAL_ASSET` DomainContract to expose the already-registered `add` and
`update` ActionSpecs through `manage_assets`. Explicit owner inventory writes
now resolve to the existing canonical binding instead of
`operation_not_registered`; policy, owner scope, and execution remain
downstream authorities. Focused intent/ACI regressions passed 215 tests with 1
skipped. Live Qwen verification remains unavailable.

Canonical inventory write verification: extended the existing
`manage_assets` → `ManageInventoryTool` adapter to read back the affected
item/lots through `inventory_service` after a successful mutation. Added
`canonical_inventory_mutation_answer` in ACI so final delivery reports one
structured outcome and distinguishes verified readback from incomplete
verification or failure. No new store/executor was introduced. Focused
ACI/inventory/intent/binding coverage passed 246 tests with 1 skipped. Live
Qwen verification remains unavailable.

Canonical final answer selection: consolidated Asset, Household, and Inventory
mutation replacement selection behind `aci.canonical_result_answer`, returning
an explicit `AnswerSource` and provenance. The compatibility loop now emits at
most one deterministic canonical replacement for these owner-state results;
the structured Result remains authoritative and no new persistence or
execution path was introduced. Focused lifecycle/routing coverage passed 250
tests with 1 skipped. Live Qwen verification remains unavailable.

Owner hardware/network regression family: expanded the existing deterministic
read compiler for conversational owner computer queries (including `got`,
terse collection language, and discourse prefixes) and added a structured
Network Result renderer for current context and persisted observations. This
prevents canonical hardware/network values from being invented by answer
synthesis and records the owner-session failure as a semantic regression
family. Focused intent/lifecycle coverage passed 132 tests with 1 skipped;
the complete owner-facing stream still requires live Qwen verification.

Owner computer-language normalization and NetworkState rendering: extended the
existing `deterministic_reads` semantic predicates for `got`/`yo`/terse
computer collection variants and added `aci.canonical_network_read_answer` to
the same canonical Result renderer selection. Network context and persisted
observations are now presented only from structured `manage_homelab` results;
there is no network-specific model or executor path. Focused post-fix coverage
passed 252 tests with 1 skipped. Live Qwen owner verification remains
unavailable.

Owner-state reliability closure: extended the existing deterministic-read
semantic owner for ordinary possessive/discourse Network variants (`my`,
`our`, `yo`, current-connection phrasing) while keeping network concepts and
purchase/recommendation near-misses off canonical reads. Added permanent
metamorphic-style owner Network and conceptual-question regressions. Focused
coverage passed 354 tests with 1 skipped. The isolated current-head full suite
recorded 6,729 passed, 5 skipped, and 7 failures: one near-miss fixed here and
six storage-preflight failures caused by the intentionally minimal test
container lacking `/home/.docker-data`; those six remain environment evidence,
not converted passes. Live Qwen verification remains unavailable.

Owner-state closure follow-up: extended the existing structured reference
resolver to carry active Asset identity through nounless detail questions,
possessives, and “other one” references, and added bounded property filters to
the existing `IntentFrame`. Extended canonical answer selection so a structured
owner Result suppresses intermediate model/legacy replacement summaries; added
per-stream duplicate terminal-marker suppression in the existing chat route.
No store, registry, planner, or execution path was added. Affected integration
suites passed `401 passed, 1 skipped`; current closure edits remain pending
explicit commit/build/deploy verification.

Final-answer owner migration: reused the existing ACI canonical Result and
grounding owners through `project_final_answer`, removing the compatibility
loop's separate replacement-emission branches. This reduces duplicate answer
authority without adding a store, planner, registry, or executor. Focused
ACI/cutover/resource-contract coverage passed `263 passed, 1 skipped` before
the source checkpoint; live Qwen remains unavailable.

Model-decision projection: extended the existing ACI owner with
`project_model_decision` for parsing, bounded invalid-decision recovery, and
choice/outcome projection; the loop keeps only transport retry/fallback and
execution handoff. Added direct contract coverage; focused suites passed `264
passed, 1 warning`. Source `76c64ce0e593f2d4a626fcf9384e5e6542629487` was
explicitly built and deployed with matching embedded source and healthy
runtime. No new authority, registry, store, or executor was introduced.

Semantic dogfood expansion: extended the existing `benchmarks.hades_dogfood`
generator with structured minimal-pair oracles and explicit chaos-journal
state-mutation metadata; extended the existing CLI tier defaults and dogfood
tests. The core generation smoke produced `1,793` reproducible cases from seed
`20260827`, including `100` minimal-pair cases. Also enabled push CI/security
workflow triggers for `hades-aci-v1`. No evaluator, routing, state, or
execution subsystem was added.

Hidden holdout expansion: extended the same dogfood generator/runner with
seeded `generated_hidden_holdout` cases and a CLI count option. Reports retain
oracle metadata and prompt digests but no literal holdout prompts. A 500-case
smoke produced `500` unique held-out cases; evaluator coverage passed `30
tests`. No second evaluator or runtime authority was introduced.

Exactly-once dogfood evidence: extended the existing normalizer and live
protocol observer with lifecycle-based response replacement and stale-delta
checks, preserving event identity rather than deduplicating prose. Focused
dogfood/live-selection coverage passed `51 passed, 1 warning`.

Current-head checkpoint: the CI branch-trigger regression test now matches the
intentional `main, dev, hades-aci-v1` push trigger. Source
`e4e80c03ae0acb380fa44b8272dc0d7f98df7fb5` was explicitly deployed with
matching image/source evidence; focused validation passed `102`, and the seven
affected full-regression tests passed `8` in a writable fixture. The remaining
read-only full-regression failures are documented environment evidence.

Foreground route authority closure: removed the mutable route-level
`stream_agent_loop` hook and redirected its test seam to `stream_aci_turn`.
This eliminates the remaining foreground redirection path without adding a
new owner. Focused cutover/lifecycle/routing/dogfood validation passed `204
tests`; the AST audit found zero direct legacy stream callers in production
runtime packages.

Current exact-head reconciliation: source/runtime documentation was corrected
to distinguish historical checkpoints from the active `8e2737847812` source.
The current candidate image and embedded source match exactly, focused
cutover/resource/ACI/dogfood validation passed `136`, and live Qwen remains
unverified because Ollama is unavailable.

Full current-head regression evidence: `6760 passed, 5 skipped, 149 warnings`
against source `8ea00f81`, using a writable project fixture and a read-only
mount of the host Docker storage path. Storage-preflight coverage passed `6/6`
under that corrected fixture; the earlier six failures were mount artifacts.

Dead compatibility residue: removed three unreferenced aliases from
`src/agent_loop.py` (`_canonical_result_answer`,
`_normalize_truncated_document_tool_fences`, and `_DOMAIN_POLICIES`). No source
or test consumer existed; focused ACI/cutover/resource/agent-loop/dogfood
coverage passed `173 tests`. This is a measured deletion, not a semantic move.

Latest cleanup checkpoint: source `e0a88d0d` retains the same semantic path;
focused coverage passed `173`, and the prior full regression remains
applicable at `6760 passed, 5 skipped, 149 warnings`. Live Qwen remains
unverified because Ollama is unavailable.

Semantic oracle scoring checkpoint: extended the existing dogfood scorer so
ScenarioFrame cases grade the traced canonical domain, ActionSpec identity,
grounding, and completion state; missing canonical Action evidence can no
longer pass as fluent prose. Imported/frozen cases retain their existing
contract. Focused dogfood/ACI/reference coverage passed `261 passed, 1
warning`. No production runtime behavior, registry, store, or authority path
was added.

Exact candidate verification: source `176e7aa5` was explicitly built and
deployed with matching embedded source and image label; the corrected
storage-fixture full regression passed `6761 passed, 5 skipped, 149 warnings`.
Container health was green with zero restarts. Live Qwen/Ollama remains
unverified because the provider is unavailable.

Semantic evidence strictness: semantic ScenarioFrame scoring now fails when
required grounding or completion trace evidence is absent, rather than
treating missing metadata as a pass. Focused dogfood scorer coverage passed
`32 passed, 1 warning`.

Canonical read failure closure: extended the existing `canonical_result_answer`
selection seam so recognized failed or malformed owner reads produce a
bounded `AnswerSource.ERROR` result rather than unconstrained model prose.
Added Network and Asset grounding regressions; focused ACI/reference/dogfood
coverage passed `263 passed, 1 warning`. No new store, registry, executor, or
authority path was introduced.

Canonical-read delivery closure: the existing ACI-compatible stream now
terminates a canonical read turn after Result persistence so the deterministic
Result renderer is the only final answer producer. This removes the
model-prose-then-replacement path for canonical reads; no text-based
deduplication or parallel answer owner was introduced. Focused ACI/routing,
dogfood, chat-metrics, and stream coverage passed `189 passed, 2 warnings`.
The exact source was built and deployed as `odysseus:candidate-959b5eab8826`;
embedded source, image digest, health, and zero restarts were verified. Full
regression passed `6763 passed, 5 skipped, 149 warnings`.

Current owner-state checkpoint (`b9693733f9a72f7b090d6f95356724321b30784e`):
the typed semantic fixture projection was extended for Work, service,
security, and Developer canonical reads, and the canonical ACI result seam now
renders explicit structured empty results without model synthesis. Focused
container-backed tests passed `90`. The exact candidate
`odysseus:candidate-b9693733f9a7` is deployed and source-label/health matched.
Qwen3:8B quick dogfood through the container-reachable Ollama endpoint passed
`62/62 functional`, `62/62 architectural`, and `62/62 security`, with no
failure clusters. Authenticated owner E6 remains unverified because no
isolated acceptance principal credential is configured.

Dead grounding alias removal: deleted the unreferenced
`agent_loop.ground_action_completion` compatibility alias and moved its test
consumers to `src.aci.ground_action_completion`. Affected coverage passed `68
passed, 1 warning`; no production semantic owner or execution path changed.

Dead canonical-read alias removal: removed the two unreferenced
`agent_loop.py` exports `_canonical_asset_read_payload` and
`_canonical_read_fast_path_payload`; tests now use `src.aci` directly. Focused
coverage passed `275 passed, 1 warning`.

Owner-scope reference correction: extended the existing structured reference
resolver so lower-case/ASR `it assets` is recognized as the `IT assets`
collection noun phrase, not the pronoun `it`. This prevents an active Asset
referent from narrowing an owner inventory list; focused container-backed
coverage passed `276 passed, 2 warnings`.

Dead loop export cleanup: removed the unreferenced `_canonical_read_action`
compatibility export and moved its test consumers to the canonical
`intent_contracts` owner. Delegates still referenced by active loop mechanics
were deliberately retained. Fresh-process focused coverage passed `131
passed, 2 warnings`.

Direct canonical trace calls: replaced the loop-only aliases for ACI
`action_trace`, `project_aci_trace`, and `detect_runaway_call` with direct
canonical calls and migrated the runaway tests to `src.aci`. No authority or
execution path changed; fresh focused lifecycle/runaway coverage passed `56
passed, 2 warnings`.

Hadolint CI noise closure: consolidated the adjacent Dockerfile provenance and
directory-creation layers and set the pinned action's failure threshold to
`warning`, preserving blocking warning/error findings while making INFO/style
findings advisory. The pushed `6e9fed64` Container scan run completed SUCCESS
in 17 seconds. The follow-up source `c84514f` was explicitly built and
deployed as `odysseus:candidate-c84514f29574`; embedded source and health
matched, with image digest `sha256:895ca25c66be688132604720a696f21be4c934bc8bc528d992601ae6a26ae0cb`.
No product assertions failed in the exact-image full regression: `6765
passed, 5 skipped, 187 warnings`, using isolated writable data/log/probe and
Docker-storage fixtures with the checkout read-only.

Semantic fixture-world closure (`0de31e0c`, local-only checkpoint): the
interrupted `aci-canonical_reads-*` family was reproduced and classified as
missing typed synthetic environment declarations, not a deployed ACI answer
delivery failure. Explicit fixture profiles were added for mixed domain,
continuation, and security/work cases; `read_setup` received a typed empty
result and the existing structured-empty renderer now claims it. Focused
container-backed coverage passed `96` tests; targeted replay passed all five
previously failing cases with zero failed Actions and complete deterministic
answers. A 245-case aggregate rerun was not accepted as benchmark evidence
because the disposable runner could not reach its configured Ollama endpoint.
Local HEAD is `0de31e0c6bab36a82fb90ce5235bf638da884352`, remote remains
`8e064b1d9c51ecd5b78a405da9ad82c0c6b472bf`, and the deployed runtime remains
the healthy `8e064b1d` image. Push is pending owner unlock of the existing
encrypted SSH key; no source/runtime match is claimed for this local-only
checkpoint.

Current convergence checkpoint (`3db8632c`, 2026-08-28): the generated
executor-fixture projection now derives synthetic tool availability from the
explicit environment fixture profile for registry-generated cases, including
workspace, local-intelligence, network-plan, and work executors. The evaluator
regression proves mutating `expected`/oracle fields does not change the fixture
set. This is evaluator-only code; no production authority, Action registry, or
executor was added. The exact current-head repository suite passed `6786
passed, 4 skipped, 186 warnings` in the project venv. A naive in-container
`pytest -q` remains an invalid full-suite command because the image lacks the
checkout's test tree and collects bundled third-party tests under `data/local`;
the supported checkout suite was used instead. The focused ACI/cutover/
lifecycle/dogfood suite passed `137 passed, 1 warning`.

At this checkpoint local HEAD, `origin/hades-aci-v1`, and the deployed
container source are all `3db8632cc3fd4af47da30459c96ffe94f0d0fbf1`; the
worktree was clean, the running image was
`sha256:6e886f92c674e3292582a194ef42ef5f193547f61f61af0261410d9e1f15b4e1`,
restart count was zero, `/api/health` was healthy, and qwen3:8b was reachable
from the container namespace. The remaining `agent_loop.py` implementation is
the compatibility stream/runtime seam. A static audit found no unreferenced
alias suitable for safe deletion; moving `TOOL_SECTIONS` would be a physical
refactor only because the Skills UI still consumes its legacy built-in
projection. No executable refactor was justified by current evidence.

## Current evidence checkpoint (`980f959f`, 2026-08-28)

Local and `origin/hades-aci-v1` are synchronized at
`980f959f39fa99f11fd3d9400d6e06f55366f129`; the worktree is clean. The full
project-venv regression passed `6806 passed, 4 skipped, 186 warnings`. The
focused restart/reconstruct execution-state regression passed alongside the
existing approval, verification, and ACI suites. This commit adds no
production executable code, so the deployed executable remains
`100d2e0f4e00ebf753a816984981603f666e6190` and has not been rebuilt.

The fixed-seed semantic audit (`20260828`) generated `1,793` scenarios and
reported `196` coverage metadata gaps, including `34` critical and `69` high.
Direct lifecycle tests cover multiple approval/post-result/failure branches;
the remaining audit entries are retained as explicit coverage debt rather
than relabeled as runtime failures. The 100-case registry-action runtime
probe retained 13 model/shortlist failures caused by underspecified exact
ActionSpec expectations; no authority or security regression was observed.

## Registry fixture-boundary checkpoint (`9f3f834e`, 2026-08-28)

The evaluator no longer projects unsupported registry executors into
neighboring read-only fixtures. `workspace_yolo` and `local_intelligence`
remain visible in registry coverage, but their synthetic environment is empty
and their expected outcome is an unavailable capability/fail-closed path.
Supported transports continue to use the explicit fixture profile and oracle
fields remain non-authoritative. The affected regression passed `184 passed,
2 warnings`; no production executable code or image changed.

The full current-head regression then passed `6807 passed, 4 skipped, 186
warnings`. The seeded generator replay (`20260828`) produced `1,793` cases
and `233` coverage metadata gaps (`33` critical, `69` high). The changed gap
count reflects explicit unsupported-executor coverage, not a runtime failure
rate.

## Exact deployed checkpoint (`5e8d8250`, 2026-08-28)

The compatibility-hook correction was committed and pushed after the initial
`c42a8e23` image, so a fresh exact candidate was required. Local and remote
now equal `5e8d8250ea3cc548472ec513901a02a7bde31615`; the worktree is clean.
Candidate `odysseus:candidate-5e8d8250ea3c` and the running container use image
`sha256:ace756fd4609f06c982a60773306653933b71e2b83ab7bed9f94c34ec16ce7e6`,
with OCI label, embedded marker, and running source matching that SHA.
`/api/health` is healthy and restart count is zero.

Focused seam coverage passed `64` tests and the full regression passed
`6807 passed, 4 skipped, 186 warnings`. In-container Qwen3:8B quick evidence
was `62/62` functional, architectural, and security, duplicate delivery `0`,
qualified reference accuracy `1.0`, failed Actions/task `0.0161`, model
calls/task `0.2581`, and P95 `2.9884s`. This is a deployment/checkpoint
verification; authenticated acceptance-principal replay remains separate.

## ACI runtime seam checkpoint

The production entrypoint now invokes the explicitly named
`stream_aci_runtime` implementation. The historical `stream_agent_loop` name
is retained as a thin async-generator compatibility facade and propagates
generator closure to preserve in-flight tool cancellation. This removes the
legacy-named entry from the production ACI path without creating a second
runtime or authority. Characterization coverage passed 79 focused tests; the
full current-head regression and exact-SHA candidate deployment remain
required before this executable slice is considered released.

## ACI runtime seam checkpoint (`c42a8e23`, 2026-08-28)

The production `aci.stream_aci_turn` entrypoint now selects
`agent_loop.stream_aci_runtime` directly. `stream_agent_loop` is retained as
a compatibility async-generator facade; it forwards generator closure so
in-flight tool cancellation remains intact. The focused characterization
suite passed `64` tests, and the exact current-head full regression passed
`6807 passed, 4 skipped, 186 warnings`.

The exact candidate `odysseus:candidate-c42a8e2313c4` was built and deployed.
Its image ID is
`sha256:b2d97c4521e19fff3a987598c404288d2d3f67f298df73805f099522a7c7009b`;
OCI label, `/app/.odysseus-source-commit`, and running source all equal
`c42a8e2313c483bcf950d0482b79c276aba6528d`. `/api/health` is healthy and the
container restart count is zero. Qwen3:8B is reachable from the Hades
container namespace with digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.

The in-container frozen quick run remained `62/62` functional,
`62/62` architectural, `62/62` security, duplicate delivery `0`, qualified
reference accuracy `1.0`, failed Actions/task `0.0161`, model calls/task
`0.2581`, and P95 `2.4794s`. No authenticated acceptance-principal replay was
performed in this checkpoint.
## Dead prompt cleanup checkpoint (`b0b94a67`, 2026-08-28)

Removed the unreachable first fenced-tool prompt definitions from
`agent_loop.py`; they were overwritten by the active native-tool definitions
before use. This deleted `120` lines with no change to the active prompt
projection or authority path (`agent_loop.py`: `6894` → `6774` LOC at the
source checkpoint). Prompt/cutover coverage passed `199` tests and the full
post-deletion regression passed `6807 passed, 4 skipped, 186 warnings`.

Candidate `odysseus:candidate-b0b94a6773f7` is deployed with image
`sha256:60af34bd9c1301b76268f3daafb3cac0cdc60b10c3600ba5538c7da63e898c3b`;
OCI label, embedded marker, and running source match
`b0b94a6773f705f131a26b74cb9ff9118379c806`. Health is healthy and restart
count is zero. In-container frozen Qwen evidence was rerun before this
entry: `62/62/62`, duplicate delivery `0`, reference accuracy `1.0`, failed
Actions/task `0.0161`, model calls/task `0.2581`, P95 `2.9884s`.

## Compatibility-alias reduction checkpoint (`c0e73ada`, 2026-08-28)

Removed four unused internal compatibility aliases and switched their runtime
call sites to canonical imports for usage summaries, action snapshots,
directive insertion, and the retired verifier seam. Aliases still referenced
by legacy scripts/tests remain preserved. Focused coverage passed `270` tests.

Pushed/deployed source: `c0e73ada0bce579506ca6fcacb5c92868b740f3a`.
Candidate: `odysseus:candidate-c0e73ada0bce`.
Image: `sha256:81e8095c91a8edcf99b72f3e0e52cf5cc850bd50213e58c765f90032c11d43b6`.
OCI marker and running source match; health is healthy; restart count is `0`.

The exact `c0e73ada` source then passed the corrected full regression in the
supported container environment: `6806 passed, 5 skipped, 149 warnings`.

## Canonical helper call-site checkpoint (`cf7cc7ba`, 2026-08-28)

After correcting indentation from the helper call-site substitution, syntax
compilation and affected coverage passed (`300 passed, 1 warning`). Exact
source `cf7cc7ba29b4e7c664f98d2204babb96a6de8d4f` was pushed and deployed as
`odysseus:candidate-cf7cc7ba29b4`; image
`sha256:02ccfdcc91df48cc8be09f794425c34f28fa32889cd3a821022164c4efc2584b`.
OCI marker and running source match; health is healthy and restart count is
zero. Full regression passed `6806 passed, 5 skipped, 149 warnings`.

The exact candidate's in-container Qwen3:8B frozen quick run passed `62/62`
functional, architectural, and security, duplicate delivery `0`, failed
Actions/task `0.0161`, model calls/task `0.2581`, reference resolution `1.0`,
and P95 latency `2.1386s`.

## Canonical internal-call checkpoint (`a8b3b7c5`, 2026-08-28)

Replaced seven production call sites that reached canonical ACI/intent owners
through retained underscore compatibility aliases. The aliases remain only
for compatibility imports/tests; the runtime now references canonical names
directly. Focused supported-image coverage: `304 passed, 1 warning`.

Pushed/deployed source: `a8b3b7c588e666520136f26439e39e24342072e9`.
Candidate: `odysseus:candidate-a8b3b7c588e6`; image:
`sha256:0b6cbd4dae1829140d8f0498a9eae8386f88b6212a1c053c34811966ce536eb6`.
OCI marker and running source match; health is healthy; restart count is `0`.

An initial isolated run exposed six storage-preflight environment failures
because the test image lacked the host runtime paths. Re-running in the
supported project image with `/home/.docker-data`, `/home/.containerd-data`,
and the Docker socket mounted passed all six storage tests and the full suite:
`6806 passed, 5 skipped, 149 warnings`. No storage logic was changed.

## Semantic coverage shard recovery (`20260828`, 2026-08-28)

The interrupted semantic shard had no surviving report or partial JSONL. A
replacement coverage-only shard (`0/4`, seed `20260828`) generated `474`
scenarios and reported `372` coverage gaps (`46` critical, `88` high). This is
coverage evidence only, with no model/runtime execution and therefore no
functional pass claim. Gaps are concentrated in ActionSpec/capability,
failure, policy/approval, and lifecycle dimensions.

## Compatibility-seam rejection (`5fb800d7`, 2026-08-28)

A broader runtime helper-alias migration was reverted after exact-candidate
testing found four compatibility failures in sanctioned monkeypatch seams
(fallback routing, notes, and MCP/document handling). The reverted checkpoint
passes the focused ACI/cutover suite (`301` tests) and the supported full
regression (`6807 passed, 5 skipped, 149 warnings`). Runtime is deployed from
the exact pushed SHA and remains healthy. Retained aliases remain compatibility
exports, not evidence of independent ACI authority.

## Real-Qwen semantic shard (`5fb800d7`, 2026-08-28)

On the Hades Compose network, the existing evaluator reached the actual
`qwen3:8b` endpoint and ran `327` bounded cases. Results: `260/327`
functional, `310/327` architectural, `327/327` security, duplicate rate `0`,
failed Actions/task `0.0581`, model calls/task `0.7278`, P95 `6.2559s`.
The one missing-answer case is a contract mismatch: `What's running in
Docker?` is oracle-labeled `CONTAINER/READ`, but canonical intent currently
selects `SERVICE/READ`; the service fixture is blocked. Treat this as an
ontology/fixture gap requiring a bounded owner decision, not as justification
for a sentence-specific router.

## Compatibility-authority guard (`5a204cb0`, 2026-08-28)

Added a focused AST regression that rejects calls from the canonical
`stream_aci_runtime` to retained compatibility aliases. This records the
semantic ownership boundary without deleting compatibility exports that are
still exercised by nested runtime paths and tests. Focused cutover/lifecycle
coverage: `61 passed`. Test-only checkpoint; running executable remains
`cf7cc7ba29b4e7c664f98d2204babb96a6de8d4f`.

## Frozen Qwen quick revalidation (`5fb800d7`, 2026-08-28)

The initial source-mounted run is excluded from image provenance evidence. The
corrected no-source-mount run used the baked candidate on the Compose network
with real Qwen3:8B: `61/62` functional, `62/62` architectural, `62/62`
security, duplicate delivery `0`, reference resolution `1.0`, failed
Actions/task `0.0161`, model calls/task `0.2581`, median latency `0.0195s`,
P95 `3.8855s`. The sole failure is the frozen evaluator's
`jarvis-environment-assumption` `response_excludes` grounding assertion; an
answer was present and delivery was complete. This is current checkpoint
evidence, not a claim that broader generated coverage gaps are closed.

The candidate image excludes `tests/` from the Docker build context, so
no-source-mount `pytest -q` cannot provide full image-backed regression
evidence (pytest reports no test files, exit `5`). Source-mounted targeted
anti-leak coverage passes `18` tests; the packaging limitation is recorded
explicitly rather than treated as a product result.

## Current authority audit (`c610b289`, 2026-08-28)

Static call-graph review found no unused top-level `agent_loop` helper safe to
delete. Production callers use `stream_aci_turn`; `stream_agent_loop` remains
a compatibility facade, while `stream_aci_runtime` is the executable ACI
runtime. Focused cutover/lifecycle/contract/canonical-resource coverage passed
`114` tests. Further alias removal remains deferred pending characterization of
the compatibility seams that previously regressed.

The characterization slice now directly proves the ACI-first intent boundary:
owned frames bypass compatibility classification and normalization; unowned
concepts retain the fallback adapter. Contract/cutover coverage passed `30`
tests. No executable runtime change or image rebuild was made.

## Executable alias-reduction checkpoint (`8e9c0766`, 2026-08-28)

Three unused internal compatibility aliases were removed and their runtime
uses now call canonical imports directly. Full supported regression: `6809
passed, 5 skipped, 149 warnings`; focused ACI/routing/context coverage: `284
passed`. Candidate `odysseus:candidate-8e9c0766` is deployed and healthy with
zero restarts; image digest is
`sha256:01da8785463d6266759065093ad5f7dfa271640ee7f658f01f20d957cae6ff30`,
and embedded/running source matches the pushed SHA.

The exact-image, no-source-mount frozen Qwen3:8B run passed `62/62` functional,
architectural, and security; duplicate delivery `0`, failed Actions/task
`0.0161`, model calls/task `0.2581`, median `0.0182s`, P95 `2.5476s`. Live
authenticated owner acceptance remains separate evidence.

## Qwen revalidation after second alias reduction (`11c4a7d6`, 2026-08-28)

The exact baked candidate passed `6809` full-regression tests with `5` skips
before deployment. Frozen Qwen3:8B revalidation passed `62/62` architectural,
`62/62` security, and `61/62` functional; duplicates `0`, reference resolution
`1.0`, failed Actions/task `0.0161`, model calls/task `0.2581`, median
`0.0181s`, P95 `3.379s`. The only failure is the known evaluator
`jarvis-environment-assumption` grounding assertion, with an answer present and
no Action selected. Embedded and running source match the pushed SHA and the
runtime is healthy with zero restarts.

## Qwen revalidation after result-summary alias reduction (`e4385a6d`, 2026-08-28)

The exact candidate passed `6809` full-regression tests with `5` skips before
deployment. Frozen Qwen3:8B passed `62/62` functional, architectural, and
security cases; duplicate delivery `0`, reference resolution `1.0`, failed
Actions/task `0.0161`, model calls/task `0.2581`, median `0.0192s`, and P95
`2.7039s`. Embedded/running source matches the pushed SHA and the runtime is
healthy with zero restarts.

## ACI helper-export reduction (`f5c07ff3`, 2026-08-28)

Removed three unused `agent_loop.py` exports for think-block stripping,
empty-response fallback, and exact-approval checking. Their implementations
and runtime call sites already belong to `src.llm_core` or
`src.capability_registry`; active compatibility/context exports remain
unchanged. Focused canonical helper/cutover coverage passed `59` tests after
isolating an unrelated test-only import-order fixture issue. The supported
full regression passed `6809` tests with `5` skips and `149` warnings.

Exact pushed executable source: `f5c07ff33e6754784fc328fa8392daea4b6178e0`.
Candidate image ID:
`sha256:b23213db1791e89d3ff3d96b90a72ea7106c50ea6311bb25602258cef06c9fbf`.
OCI/source markers match, health is healthy, and restart count is zero.
Exact-image Qwen3:8B evidence: `62/62` functional, architectural, and
security; duplicate delivery `0`; reference resolution `1.0`; failed
Actions/task `0.0161`; model calls/task `0.2581`; median `0.0164s`; P95
`2.5771s`.

## Foundation closure evidence (`f5c07ff3`, 2026-08-28)

Seeded RC coverage generated `2540` scenarios and reported `128` gaps (`31`
critical, `10` high), chiefly failure classes, approval branches,
post-result states, and policy branches. These are coverage gaps, not runtime
failures. A seeded Qwen3:8B holdout added `100` hidden cases (`345` total)
and produced `247/345` functional, `305/345` architectural, and `345/345`
security results; duplicate delivery was `0`, failed Actions/task `0.0754`,
model calls/task `0.8406`, and P95 `5.4353s`. Failures were concentrated in
generated registry-action domain/action/completion burden. This is diagnostic
evidence, not a release pass, and no production authority was changed.

## Qwen revalidation after memory/notes alias reduction (`2cf8a5fb`, 2026-08-28)

The exact candidate passed `6809` full-regression tests with `5` skips before
deployment. Frozen Qwen3:8B passed `62/62` functional, architectural, and
security cases; duplicate delivery `0`, reference resolution `1.0`, failed
Actions/task `0.0161`, model calls/task `0.2581`, median `0.0187s`, and P95
`3.15s`. Embedded/running source matches the pushed SHA and the runtime is
healthy with zero restarts.

## Qwen revalidation after document-adapter reduction (`2cf8a5fb`, 2026-08-28)

The exact candidate passed `6809` full-regression tests with `5` skips before
deployment. Frozen Qwen3:8B passed `62/62` functional, architectural, and
security cases; duplicate delivery `0`, reference resolution `1.0`, failed
Actions/task `0.0161`, model calls/task `0.2581`, median `0.0200s`, and P95
`2.5672s`. Embedded/running source matches the pushed SHA and the runtime is
healthy with zero restarts.

## Executable alias-reduction checkpoint (`dfa5a2a1`, 2026-08-28)

Removed two internal-only aliases for notes-message construction and document
artifact stripping; runtime call sites now use canonical imports directly.
Focused coverage passed `305` tests and the supported source-mounted full
regression passed `6809` tests with `5` skips and `149` warnings. The pushed
SHA, OCI revision, source marker, and running source are
`dfa5a2a13822fb33a7edf774a78916f2eab6aa64`. Candidate image ID is
`sha256:62987b38363f8c7adf27d348e0c20a169ea3b4cc191403408278c1d8eeedf56d`;
health is healthy and restart count is zero.

## ACI compatibility-export reduction (`a27806e1`, 2026-08-28)

Removed six unused underscore exports from `agent_loop.py` whose semantic
implementations already belong to `src.aci`: reference hints, reference
acknowledgement, explicit-memory detection, minimal ACI answer projections,
and canonical-read matching. Tests now import these helpers from canonical
owners; active provider/context compatibility seams remain unchanged.
Focused coverage passed `282` tests and the supported full regression passed
`6809` tests with `5` skips and `149` warnings.

The exact pushed executable source is
`a27806e1837576297aa0e4db3028e0a5423b4d72`. Candidate
`odysseus:candidate-a27806e1` is deployed with image ID
`sha256:a7013b6a9d6fed32eb9ed3a9521143b228fdbc0054851af339fac82129bc1b13`;
OCI/source markers match, health is healthy, and restart count is zero.
Frozen exact-image Qwen3:8B evidence: `62/62` functional, architectural,
and security; duplicate delivery `0`; reference resolution `1.0`; failed
Actions/task `0.0161`; model calls/task `0.2581`; median `0.0183s`; P95
`2.7525s`.

Exact-image Qwen3:8B frozen quick evidence: `62/62` functional,
`62/62` architectural, `62/62` security, duplicate delivery `0`, reference
resolution `1.0`, failed Actions/task `0.0161`, model calls/task `0.2581`,
median `0.0174s`, P95 `2.4932s`.

## Evaluator fixture-world correction (`8d432c51`, 2026-08-29)

Generated semantic fixtures now enact their declared ScenarioFrame result state
through explicit environment metadata. This removes unconditional synthetic
success, preserves oracle independence, and prevents false grounding and
completion failures caused by an impossible fixture world.

Focused dogfood tests pass (`55`). Full local regression passes (`6812 passed,
4 skipped, 186 warnings`). No production executable was changed or deployed;
the running executable remains `f5c07ff3`.

## Recovered canonical-read shard (`7e8eb47d`, 2026-08-28)

After the laptop restart, no surviving partial JSONL/report or benchmark
process was found for the interrupted `aci-canonical_reads-*` execution. The
smallest reproducible bounded shard was rerun against exact deployed candidate
`odysseus:candidate-7e8eb47d` (10 cases, seed `20260828`, shard `12/25`). It
completed with `10/10` functional, `10/10` architectural, `10/10` security,
zero duplicate delivery, and no top-level failure clusters. Failed
Actions/task was `0.1`, model calls/task `0.3`, median latency `0.235s`, and
P95 `2.3437s`. One embedded reference case was unqualified (`0/1`); this is
coverage debt, not a product-failure claim.

Source/runtime: local and remote `7e8eb47d6459e4affd6afe44776fd20b341337d5`,
candidate image `sha256:cea4e6012805c041afeacce8e0707c1baeeb1996be74cba644b0491a4db2e751`,
embedded/running source equal to that SHA, healthy, restart count `0`, and
Qwen endpoint `host.docker.internal:11434` from the Hades namespace.

This bounded shard does not replace full regression, frozen baseline, or live
owner acceptance gates.

## Executable route-projection cleanup (`de1ceeb7`, 2026-08-28)

Removed the identity-only `_filter_route_tool_schemas` wrapper from
`src/agent_loop.py` and inlined its two call sites. This deletes accidental
indirection without changing capability visibility, policy, Action identity,
or execution. Focused coverage passed `437` tests; full regression passed
`6819 passed, 4 skipped, 186 warnings`.

The exact pushed executable source is
`de1ceeb7e1ddd7391f12b9c832c7aaf89e462f31`. Candidate
`odysseus:candidate-de1ceeb7` was built with OCI revision and source marker
matching that SHA and deployed explicitly as the running `odysseus` image
`sha256:53610ab02bc53be8c6951c19a278689e62651e6e3e292d725512970bf129d784`.
The container is healthy with restart count `0`; Qwen3:8B is reachable from
the production container namespace. Authenticated browser acceptance passed
with `7` prompts and `8` streams.

The current runtime executable matches `de1ceeb7`. Later documentation-only
commits may advance the branch HEAD without requiring a product rebuild.

Frozen Qwen3:8B quick revalidation on the exact `de1ceeb7` image passed `62/62`
functional, architectural, and security cases. Duplicate delivery was `0`,
reference resolution `1.0`, failed Actions/task `0.0161`, model calls/task
`0.2581`, median latency `0.0314s`, and P95 `1.6759s`. The run used Qwen from
the Hades container namespace and is attributable to the deployed executable
SHA, not to the later documentation-only HEAD.

## Current semantic coverage audit (`de1ceeb7`, 2026-08-28)

The existing `core` generator audit (seed `20260828`) produced `1,793`
reproducible cases and `233` coverage gaps: `33` CRITICAL, `69` HIGH, and
`131` NORMAL. Critical gaps are coverage metadata gaps, not asserted runtime
failures; they include approval replay/expiry/mismatch branches, disabled
policy, post-result continuation/clarification states, and failure taxonomy
variants. The audit is preserved as the next dogfood work queue. No runtime
routing or authority was changed to make these dimensions appear covered.
## Descriptive tool-registry extraction (`225195aa`, 2026-08-28)

Moved the descriptive `TOOL_SECTIONS` registry (241 lines) from
`src/agent_loop.py` to `src/tool_sections.py`; Skills UI imports now avoid the
loop, while the compatibility import preserves the shared registry behavior.
No semantic execution authority moved. Focused coverage passed `99` tests;
full regression passed `6812 passed, 4 skipped, 186 warnings`.

The pushed source and exact candidate are
`225195aa1e4b3985c7fb00a128dd7c7e16160cef` and
`odysseus:candidate-225195aa-exact`, image
`sha256:20437b95b12b3b78f0cc46b0569586ce4bb784029cada1122367df4a44bb4003`.
OCI revision and `/app/.odysseus-source-commit` match the SHA. The candidate
was not deployed; the known-good running source remains `f5c07ff3` with zero
restarts. This is source/test/candidate evidence, not live evidence for the
new executable.

## Executable prompt-adapter cleanup (`a308ff06`, 2026-08-28)

Removed the unreferenced `_section_text` wrapper from `src/agent_loop.py`; the
existing ACI `effective_tool_section` formatter is now called directly with
the same dynamic built-in overrides. This removed compatibility indirection
without changing prompt content, capability identity, policy, or execution.
Focused tests passed `169`; full regression passed `6819 passed, 4 skipped,
186 warnings`.

Candidate `odysseus:candidate-a308ff06` was built from the pushed SHA and
deployed explicitly. Image ID is
`sha256:71d3ace70a69a70e863eb9f5fb13dad8132ea5994a4a445083b6c11ea784db24`;
OCI/source marker and running source match `a308ff06a57fe24ffb61e0cd7281ac7c96a73d55`.
Health is healthy, restart count `0`, Qwen3:8B is reachable in-container,
and authenticated browser acceptance passed (`7` prompts, `8` streams).

## Seeded hidden-holdout coverage (`936a40c5`, 2026-08-28)

A generation-only hidden holdout using seed `20260828` produced `542`
reproducible cases from the existing evaluator. Its `503` reported gaps are
coverage dimensions, not runtime failures: `75` are critical, concentrated in
approval outcomes (`REPLAY`, `EXPIRED`, missing/owner/digest mismatch),
disabled policy, post-result continuation/approval/clarification states, and
unrepresented action/executor combinations. No production decision or
authority code was changed for this audit. The holdout remains suitable for
future bounded execution after those lifecycle fixtures have explicit
environment semantics.

## Exact deployed soak characterization (`a308ff06`, 2026-08-28)

The interrupted broad semantic execution had no surviving process or partial
report after restart. The intact bounded soak report was retained at
`/tmp/soak-a308ff06.json` and is attributable to the exact deployed executable
source `a308ff06a57fe24ffb61e0cd7281ac7c96a73d55` (Qwen3:8B, synthetic
executor; not live-owner evidence).

It covered `769` cases: functional `283/769` (`0.3680`), architectural
`592/769` (`0.7698`), security `769/769`, duplicate delivery `0`, model
calls/task `0.9077`, decision calls/task `0.3615`, failed Actions/task
`0.1456`, median latency `1.1598s`, and P95 `4.6024s`. The dominant clusters
were `DOMAIN_ROUTING_FAILURE` (`336`), `BURDEN_REGRESSION` (`177`), and
`INTENT_FAILURE` (`139`).

Trace inspection showed mixed generated-oracle/model-burden and synthetic
fixture cases rather than a shared owner Network/Asset renderer failure.
Representative blocked developer and asset actions had explicit policy/result
state in their traces; no canonical-state security regression or
duplicate-delivery boundary was exposed. The existing focused anti-leak
regression continues to prove that changing `expected` metadata does not
change generated fixture selection. This soak remains an exploratory work
queue, not a production failure, and does not justify phrase-specific routing
changes.

At the same checkpoint, the workstation SSH agent was verified through the
persistent `/run/user/1000/ssh-agent.socket`; GitHub authentication and
`git ls-remote` succeeded. Branch `hades-aci-v1` is clean and local HEAD equals
remote HEAD `06598d717bf6d5fcf2aad18be0b1052a97f9375c`. The running executable
remains the healthy `a308ff06` candidate with restart count `0`; later branch
commits are documentation-only.

## Canonical failed-Action answer closure (`d3aee6e6`, 2026-08-28)

Added the existing ACI result-rendering seam's bounded failure projection for
an already-selected Action whose executor returns a nonzero result. The
projection consumes only the structured executor output, emits
`AnswerSource.ERROR`, and cannot retry, select, approve, or grant authority.
This closes the case where ACI correctly blocked/refrained from retrying an
Action but an empty model response left the owner with no final answer.

Focused ACI/network/dogfood coverage passed `172` tests; full regression passed
`6819 passed, 4 skipped`. The exact pushed candidate
`odysseus:candidate-d3aee6e6` was deployed with image
`sha256:96291c655dae147f85a84395b7fe2901535f399ec1e1db8f983f00e79dc3a639`;
OCI revision, source marker, and running source all match
`d3aee6e6eb6e2bb591f779f4e90dd95602a80f4c`. Health was healthy with zero
restarts; Qwen3:8B was available from the container namespace. Browser
acceptance passed (`7` prompts, `8` streams), and the frozen Qwen quick corpus
passed `62/62` functional, architectural, and security with duplicate delivery
`0`.

The follow-up singular-finalization assertion is test-only and was pushed as
`1d9549a9`; it does not change the deployed executable.

## Exact deployed generated sample (`d3aee6e6`, 2026-08-28)

A bounded generated run against the exact deployed d3 executable covered `345`
scenarios (seed `20260828`). Functional was `249/345` (`0.7217`), architectural
`306/345` (`0.8870`), security `345/345`, duplicate delivery `0`, missing
assistant answers `0`, and missing terminal completions `0`. Failed Actions/task
was `0.1159`, median latency `0.3217s`, and P95 `3.9807s`. The exploratory
failure clusters were domain routing (`57`), burden (`39`), intent (`26`), and
capability gaps (`23`); these are the next semantic-dogfood work queue and are
not evidence of a canonical-result delivery regression.

Product/runtime provenance at execution: branch `hades-aci-v1` was clean at
`b84c4154`; the deployed executable, OCI/source marker, and running container
were the earlier exact d3 source `d3aee6e6eb6e2bb591f779f4e90dd95602a80f4c`,
image `sha256:96291c655dae147f85a84395b7fe2901535f399ec1e1db8f983f00e79dc3a639`,
healthy with zero restarts. This was synthetic Qwen3:8B evidence, not live-owner
acceptance.

## ACI ownership audit (`0cb309f3`, 2026-08-28)

The production cutover, lifecycle, and dogfood contract audit passed `122` tests
with one dependency deprecation warning. Source inspection found no production
caller of the legacy `stream_agent_loop`; `aci.stream_aci_turn` is the sole
production stream boundary, and the remaining loop-local projection helpers
delegate to ACI or intent-contract owners. The compatibility facade remains for
tests and nested compatibility paths; removing it without a characterization
slice is not justified by current evidence.

Current-head full regression at `959ca1ec` passed `6819` tests with `4`
documented skips in `174.47s` (186 warnings). This validates the docs-only
descendant against the same executable code as the deployed d3 checkpoint.

## Canonical stream seam closure (`60980b5f` / `7edab187`, 2026-08-28)

Removed the canonical `aci.stream_aci_turn` fallback that inspected a replaced
legacy `stream_agent_loop` symbol. The ACI entrypoint now resolves only the
explicit `stream_aci_runtime` implementation and fails closed if it is absent;
the legacy facade remains available only to explicit compatibility callers.
The initial full-suite run exposed six stale tests patching the retired seam,
so scheduler, skills, and teacher tests were migrated to patch
`src.aci.stream_aci_turn` instead. The affected suite passed `85` tests and the
current full regression passed `6819 passed, 4 skipped` in `176.34s`.

The exact executable candidate `odysseus:candidate-60980b5f` was built from
`60980b5f67c51ea549fa6219e340f01e8e1ae9b8`, image ID
`sha256:710492e93387788767ad36239387448068b19556eab694195d4a0d83649a4c47`,
and deployed explicitly. OCI revision, `/app/.odysseus-source-commit`, and
running source match; health is healthy with zero restarts. Qwen3:8B is
reachable from the container namespace. Browser acceptance passed (`7`
prompts, `8` streams); frozen Qwen quick passed `62/62` functional,
architectural, and security, with duplicate delivery `0`, failed Actions/task
`0.0161`, median latency `0.0283s`, and P95 `1.6638s`.

The later `7edab187` changes are test-only seam migration; the running
executable remains the exact `60980b5f` candidate.

The follow-up guard at `5cc83fc` proves a replaced legacy stream symbol cannot
be selected by `aci.stream_aci_turn`; the canonical runtime remains the only
entrypoint through that seam. ACI lifecycle/cutover coverage passed `68` tests.
This is test-only evidence and does not alter the deployed executable.

## Dead metadata seam removal (`04391985`, 2026-08-28)

Removed unused `_API_HOSTS`, `_endpoint_lookup_keys`, and `_MCP_KEYWORDS`
imports from `src/agent_loop.py`; provider host policy and MCP metadata are now
consumed directly from their canonical owners. Provider/MCP/runtime coverage
passed `160` tests. Tests that had imported those private loop names were
migrated to `endpoint_resolver` and `mcp_manager`, removing compatibility
pressure from the runtime module without changing provider behavior.

The exact candidate `odysseus:candidate-04391985` has image ID
`sha256:f9a9ac088cbdee0df1db0b7da2a734686de86609b9559cb4604bafe7ef895241`,
OCI revision and `/app/.odysseus-source-commit` equal to
`0439198500f0cb13c18722b0a29c98ccf1641be2`, and is running healthy with zero
restarts. Qwen3:8B is reachable from the container namespace; browser
acceptance passed (`7` prompts, `8` streams), frozen Qwen quick passed `62/62`
functional, architectural, and security with duplicate delivery `0`, and the
full regression passed `6820` tests with `4` skips.

## Dead ACI import cleanup (`ee7eef7`, 2026-08-28)

Removed four unreferenced canonical helper imports from `src/agent_loop.py`:
`canonical_result_answer`, `skill_index_prompt`, `select_prompt_tools`, and
`normalize_truncated_document_tool_fences`. The focused runtime/cutover suite
passed `180` tests; the full regression passed `6820 passed, 4 skipped`.

The exact candidate `odysseus:candidate-ee7eef7c` was built from
`ee7eef7cc3163a85e3055b15ae28a36ee5dc9907`, image ID
`sha256:8fd1ae9357a8d4cd99a52eb0158408ca2ff66d107f104e3288c6e06fdbd1dded`.
OCI revision, source marker, and running source match; health is healthy with
zero restarts, and Qwen3:8B is reachable from the container namespace. Browser
acceptance passed (`7` prompts, `8` streams). This leaves provider-facing and
explicit compatibility exports intact while removing dead loop scaffolding.

## Test bootstrap isolation (`de9d4560`, 2026-08-28)

Hardened `tests/test_agent_loop.py` cleanup so mocked bootstrap imports do not
pollute canonical `src.*`/`core.*` modules for later tests. The focused
order-sensitive run (`test_agent_loop.py` plus
`test_external_context_tool_gate.py`) passed `209` tests. The full current
regression passed `6820` tests with `4` skips and `186` warnings.

This is test-only and does not change the deployed executable. The running
production candidate remains `odysseus:candidate-ee7eef7c`, sourced from
`ee7eef7cc3163a85e3055b15ae28a36ee5dc9907`; the branch/test source is
`de9d4560586c058ac2b6b024d670d09ca763108d`.

## Seeded Qwen soak checkpoint (`c930180f`, 2026-08-28)

The deployed executable candidate was exercised in its actual container
namespace with `qwen3:8b` using seed `20260828`: `769` cases across the frozen,
generated, metamorphic, near-miss, stateful-chaos, and minimal-pair families.
The run recorded `1.0` security, `0.7789` architectural, `0.3680` functional,
`0.0` duplicate delivery, `0.1456` failed Actions/task, `0.9064` model calls/task,
and `4.6313s` P95 latency. The low aggregate functional score is dominated by
generated continuation/domain/intent expectations, not the previously fixed
canonical owner-read regressions; those canonical network/asset/memory/work
cases completed successfully. The report is retained at
`/tmp/hades-soak-c930.json` for local diagnosis and is not source-controlled.

This is evidence against executable source
`ee7eef7cc3163a85e3055b15ae28a36ee5dc9907` (the branch descendant is
test/docs-only `c930180f`). Runtime image ID remains
`sha256:8fd1ae9357a8d4cd99a52eb0158408ca2ff66d107f104e3288c6e06fdbd1dded`,
embedded source matches `ee7eef7`, health is healthy, and restart count is zero.
