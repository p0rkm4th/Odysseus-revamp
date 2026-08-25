# Hades ACI V1 architecture

Status: T0 contract slice implemented on `hades-aci-v1`.

Hades ACI is a projection over the existing control plane:

`IntentFrame -> DomainContract -> Capability -> ActionSpec -> ToolBinding -> Result/Run`

`src/aci.py` owns no database, executor, policy, approval, or model registry.
`ObjectiveSpec` is the semantic view of durable Work/Run metadata; `WorkingSet`,
`AgentTaskPacket`, `ActionCard`, and `ResultProjection` are derived per-step
views. Exact approval, owner scope, sealed inputs, replay protection, and
verification remain downstream canonical checks.

The first weak-model boundary is strict Decision JSON. A packet contains only
opaque ephemeral choices (`A`, `B`, …) projected from canonical ActionSpecs.
The model cannot emit a binding, command, database, approval mode, or arbitrary
action name. Hades validates the choice against the packet and its state
fingerprint before normal execution.

Deterministic work is intentionally outside model cognition: structured
reference resolution, canonical reads, policy/approval, capability health,
completion predicates, and continuation state. The model remains responsible
for semantic diagnosis, evidence synthesis, and bounded choice among already
validated options.

Current convergence owners:

| Concern | Existing owner | ACI role |
|---|---|---|
| Intent/reference | `src/intent_contracts.py` | feed `ObjectiveSpec`/packet |
| Capability/action truth | `src/capability_registry.py` | project `ActionCard` |
| Execution/security | `src/tool_bindings.py`, policy, approvals | unchanged validator/executor |
| Run/objective continuity | Work Engine / `agent_work_bridge.py` | derived WorkingSet |
| Context | `context_compactor.py`, `model_context.py` | measured envelope target |
| Result/evidence | canonical Result adapters | `ResultProjection` |
| Provider transport | `llm_core.py` | adapter boundary; migration remains |

No `AgentLoopV2`, `RunEngineV2`, second memory store, or second tool registry
was introduced.
