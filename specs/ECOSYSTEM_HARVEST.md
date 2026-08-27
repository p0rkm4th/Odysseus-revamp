# Hades ecosystem harvest ledger

This is a decision and provenance ledger, not an import list. Hades retains
authority over canonical state, capabilities, Actions, policy, approvals,
execution, verification, completion, and owner isolation. Upstream projects
may supply commodity mechanics or test design only.

## Sprint state

- Date opened: 2026-08-27
- Checkout: `hades-aci-v1`
- Source under development at ledger creation: `1356224279883559658e9adb2fbff1495c5a134c`
- Checkpoint source: `c55501290b73994b9651b5802295fa41661cc2cf`
- Checkpoint status: committed, pushed, explicitly built and deployed as
  `odysseus:candidate-c5550129b73`; running source matches the checkpoint.
- Current release blockers: live owner-authenticated Qwen acceptance is
  unverified because its credential is unavailable; broad operator slices
  remain incomplete.
- Evidence rule: an entry remains `REFERENCE` or `REJECT` until its exact
  upstream revision, license, security review, and measured Hades delta are
  recorded.

## Candidate decisions

| Project | Class | Hades target | Current owner | Decision |
|---|---|---|---|---|
| Pydantic AI Harness | REFERENCE | output bounds, context/session mechanics | `src/constants.py`, `src/context_compactor.py`, `src/aci.py` | Inspect; adapt only if it deletes code or lowers burden |
| SWE-agent | ADAPT | bounded view/search/patch result semantics | `src/tool_execution.py`, `src/agent_tools/filesystem_tools.py` | MIT; commit `3ea751c087f32b16e039a2233dd6eefecef325d5`; behavior characterized locally, no loop/authority imported |
| Aider | DESIGN_HARVEST | deterministic repo map and context ranking | `src/tool_execution.py`, `src/agent_tools/filesystem_tools.py`, `src/aci.py` | Apache-2.0 project metadata; commit `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`; design reference only pending license-file path confirmation |
| Goose | TEST_HARVEST | crash/restart transition matrix | `tests/test_work_engine.py`, `tests/test_agent_work_bridge.py`, `src/work_engine.py` | Apache-2.0; commit `caf59517cc280dd3523a80131f388024eaaede9d`; harvest test philosophy only |
| Inspect AI | REJECT (provisional) | eval runner/scoring | `benchmarks/hades_dogfood.py`, `scripts/hades_dogfood.py` | Compare complexity; no second evaluator |
| Pydantic AI Core | REFERENCE | deferred tool search/data flow | `src/capability_registry.py`, `src/aci.py`, `src/tool_index.py` | MIT; commit `2dbcf1dff61b439d4dcb9f027a764802cc669b6`; use only after owner hotfixes; authority stays Hades |
| OpenHands SDK | REJECT (provisional) | workspace/event mechanics | `src/tool_execution.py`, `src/execution_nodes.py`, `src/agent_runs.py` | MIT; commit `1a7130ce96331a4c645b36e42c25b7e92af555fa`; no second Conversation/Agent runtime |
| mini-SWE-agent | DESIGN_HARVEST | simple Agent/Model/Environment separation | `src/aci.py`, `src/agent_loop.py` | Upstream revision/license not yet pinned; complexity-control reference only |
| LangGraph | DESIGN_HARVEST | replay/side-effect isolation tests | `src/work_engine.py`, `src/run_planner.py`, `src/tool_execution.py` | Upstream revision/license not yet pinned; do not add workflow engine |

## Candidate record template

For each candidate that proceeds beyond inspection, fill every field below.

```text
PROJECT:
UPSTREAM_REPOSITORY:
UPSTREAM_COMMIT:
UPSTREAM_PATHS:
LICENSE:
COPYRIGHT / NOTICE REQUIREMENTS:
HARVEST_CLASS: PORT | ADAPT | TEST_HARVEST | DESIGN_HARVEST | REFERENCE | REJECT
HADES_TARGET:
WHY_USEFUL:
CURRENT_HADES_OWNER(S):
INTEGRATION_PLAN:
CODE_COPIED:
CODE_ADAPTED:
DESIGN_ONLY:
TESTS_HARVESTED:
LOCAL_MODIFICATIONS:
LEGACY_HADES_CODE_REPLACED:
LOC_REMOVED:
SECURITY_REVIEW:
DOGFOOD_EVIDENCE:
UPSTREAM_WATCH_STATUS:
```

## Local semantic-owner audit before new infrastructure

| Proposed concept | Existing semantic owner(s) | Action | Canonical owner after | Legacy paths to remove/demote |
|---|---|---|---|---|
| Dependency/artifact/runtime management | `src/capability_dependencies.py`, Cookbook adapters | EXTEND | `capability_dependencies.py` (`DependencyManager`/`ArtifactManager`) | Cookbook-independent installers |
| Action/capability identity | `src/capability_registry.py`, `src/tool_bindings.py`, `src/tool_capabilities.py` | EXTEND | Capability → ActionSpec → ToolBinding | builtin/tool-name authority |
| Durable composition substrate | `src/work_engine.py`, `src/agent_runs.py`, `src/run_planner.py` | REUSE | WorkRun/WorkAction | legacy loop planning |
| Developer file/search/patch mechanics | `src/tool_execution.py`, `src/agent_tools/filesystem_tools.py`, `routes/workspace_routes.py` | EXTEND | existing `developer_read` binding and workspace-confined adapters | ad hoc shell/file branches |
| Context compaction/output bounds | `src/context_compactor.py`, `src/constants.py`, `src/aci.py` | REUSE/EXTEND | WorkingSet/context projection | giant prompt/result paths |
| Crash/restart durability | `src/work_engine.py`, `src/bg_jobs.py`, `src/task_scheduler.py` | TEST_HARVEST | WorkRun durable truth | re-invoke-agent-loop continuation |
| Dogfood/evaluation | `benchmarks/hades_dogfood.py`, `scripts/hades_dogfood.py`, live runner | EXTEND | existing Hades dogfood | parallel evaluator |
| Workspace placement | `src/execution_nodes.py`, `src/tool_execution.py`, SSH bindings | REUSE | Hades execution/workspace boundary | permissive legacy SSH/shell paths |
| Stream finalization/delivery | `routes/chat_routes.py`, `routes/chat_helpers.py`, `static/js/chat.js`, `src/agent_loop.py` | EXTEND | one persisted turn + one terminal stream + explicit replacement events | full-answer-as-delta duplication |

## Measurement ledger

No ecosystem code has been added from an upstream project yet. Measurements
below must be populated only after a focused characterization and dogfood run.

| Harvest | Hades LOC before | Adapted LOC | Legacy LOC removed | Net runtime delta | Tests | Dogfood delta |
|---|---:|---:|---:|---:|---:|---|
| SWE-style Developer ACI result normalization | existing adapter | 56 | 0 (existing adapter extended) | +56 source lines, pending deletion candidate | 39 focused adapter/security tests; 68 hotfix/adapter tests | no live Qwen run yet; deterministic burden unchanged |
| Grounding/tool-summary replacement event | existing stream path | small | replaces full-answer-as-delta behavior | pending | focused route/JS/ACI tests | pending live owner replay |
| Response replacement / owner hotfix | existing ACI/stream path | 337 cumulative hotfix lines | 0 additional legacy lines measured | deployed checkpoint | 68 focused; 197 broader focused; full 6,713 pass | live owner regressions remain unverified |

## Deployment checkpoint

- `LOCAL_HEAD = REMOTE_HEAD = RUNNING_SOURCE = c55501290b73994b9651b5802295fa41661cc2cf`
- Candidate: `odysseus:candidate-c5550129b73`
- Rollback: `odysseus:rollback-b471e104-prev`
- Worktree at checkpoint: clean
- Live authenticated Qwen acceptance: UNVERIFIED (credential unavailable)

## License and notice policy

Exact upstream commits and licenses must be verified before copying code. Any
adapted code must retain required notices and identify local modifications.
Design-only references do not create a dependency. No floating `main` or
unverified download is an acceptable provenance record.

## Rejection rule

Reject an upstream integration if it creates a second planner, registry,
workflow engine, approval authority, durable truth store, agent runtime, or
meaningful prompt burden; if it weakens Hades security; or if adapters plus
compatibility code exceed the commodity value. A rejected candidate remains
documented so it is not reconsidered as a new subsystem by accident.
