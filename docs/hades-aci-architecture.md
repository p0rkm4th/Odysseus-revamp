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

## Terminal canonical reads

Explicit Memory context is a deterministic owner-scoped read. When the chat
context plane has already materialized its protected ResultProjection, the ACI
loop enters answer-only mode and does not create a duplicate `read_memory`
Action. For direct callers that use the deterministic fast path, a successful
read clears the ephemeral decision packet immediately and transitions the same
turn to `ANSWER`; a failed read alone may re-enter bounded recovery.

The historical failure was caused by leaving `_aci_packet` alive after the
fast-path Result. The next loop round therefore parsed the answer as another
Action decision. The raw Memory execution envelope also reached the model/UI
because the generic formatter serialized its `output` JSON. Memory now projects
bounded L1 records, epistemic reconciliation, current runtime provider/model,
and canonical references before either boundary. Full canonical evidence stays
behind the Action/Memory store.
