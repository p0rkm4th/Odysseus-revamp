# Hades ACI responsibility map

This is the Phase 0/3 inventory for the `hades-aci-v1` strangler effort. It
records the current state before architectural deletion; it is not a claim
that the legacy loop has already been removed.

## Reconciled state

| Evidence | Value |
|---|---|
| Repository | `/home/scootz/Odysseus/odysseus` |
| Branch | `hades-aci-v1` |
| Local HEAD | `3e7b66124c4cff877f4fb9d9f2b6bde7d5f22953` |
| Origin HEAD | `3e7b66124c4cff877f4fb9d9f2b6bde7d5f22953` (`origin/hades-aci-v1`) |
| Divergence | 0 ahead, 0 behind (verified with `git rev-list --left-right --count origin/hades-aci-v1...HEAD`) |
| Worktree | clean at checkpoint; no intentional changes discarded |
| Deployed image | `odysseus:candidate-3e7b66124c4c` (Compose service tag points to same image ID) |
| Deployed source | `3e7b66124c4cff877f4fb9d9f2b6bde7d5f22953` |
| Production health | `/api/health` healthy; app restart count 0 |
| Rollback image | `odysseus:rollback-b471e104-prev` |
| Storage | GREEN; 59 GiB root free, 251 GiB bulk free |
| `src/agent_loop.py` | 6,897 LOC in the current checkpoint worktree; remaining implementation is behind the ACI entrypoint, with compatibility-only callers outside the production path |

The uncommitted evaluator and RC2 files are preserved as existing work. The
deployed image is intentionally source-matched to the origin commit, not to
the local worktree.

## Authority map

| Responsibility | Current canonical seam | Legacy/duplicate risk in `agent_loop.py` | Strangler decision |
|---|---|---|---|
| Intent/domain/reference frame | `src.intent_contracts.compile_intent` plus ACI provisional projection | legacy classifier remains only for compatibility stream callers | ACI frame becomes the semantic source; chat Work-run creation no longer invokes the legacy classifier or normalizers |
| Domain contract/action identity | `src.intent_contracts.DOMAIN_CONTRACTS` and `src.capability_registry` | `_canonical_read_action`, hard-coded domain maps, prompt rules | Registry and DomainContract remain authoritative; prompt rules are projections |
| Deterministic reads | `src.deterministic_reads`, `src.intent_contracts`, and `src.aci` | phrase-specific fast paths and fallback branches in the loop | Resolve known reads before model decision; payload/action projection moved out of the loop; keep executor/policy unchanged |
| WorkingSet/objective context | `src.aci.WorkingSet` contracts; durable work/run stores | context assembled in several loop branches | one bounded projection per turn; historical context is not automatic hydration |
| Capability projection | `src.tool_bindings` and `src.capability_registry` | tool-index, keyword hints, `TOOL_SECTIONS` and route-specific additions | capability registry owns identity; transport lists are derived views |
| Action selection | ACI `AgentTaskPacket` / `DecisionContract` | legacy model tool syntax and hard action repairs | direct reads bypass selection; non-deterministic choices use one DecisionGateway |
| Policy/approval | `src.tool_policy`, `src.tool_approvals`, `src.tool_execution` | loop-side disabled/forced-tool shaping | policy, exact approval, target and replay checks remain downstream authorities |
| Execution | `src.tool_execution.execute_tool_block` and canonical bindings | direct fallback command branches and provider alias normalization | one executor path; legacy alias translation is skipped for canonical ACI decisions and compatibility adapters delegate only |
| Result/verification | tool result contracts, `ground_action_completion`, durable run bridge | textual success heuristics and continuation branches | ResultProjection/completion state owns terminal decisions |
| Continuation | `src.intent_contracts.resolve_continuation` and `agent_work_bridge` | `_is_explicit_continuation`, retry/follow-up heuristics | durable Run is the only continuation truth |
| Answer/fallback | ACI answer projection and provider adapter | generic model fallback and empty-answer fallbacks | fallback is authority-free cognition, never an execution path |
| Message delivery | route/session persistence plus one stream finalizer | multiple summary/finalization paths in the loop | one message-delivery identity; summaries remain result projections |

Web evidence is now treated as an ACI capability projection over the existing
`web.evidence` capability and `web_search`/`web_fetch` ToolBindings. `AUTO` is
the route default; explicit `allow_web_search=false` is the privacy `OFF`
policy. Current/local evidence does not require web, while explicit
current/external language can project the bounded public evidence primitives.
The transport handlers remain compatibility adapters and do not select
domains, targets, or authority; the DomainContract and capability registry own
the semantic action identity.

The shared dependency seam now also plans prerequisites at the canonical
ActionSpec boundary through `DependencyManager.ensure_action`. It returns an
approval-bound remediation plan or a fail-closed blocked result and preserves
the selected action for resume; it does not execute installers.

Post-execution ACI transitions now come from
`project_post_result_transition`. The loop applies the resulting transient
flags and persists the Result; it no longer independently decides whether a
canonical read or failed Action may re-enter selection.

Network intent and explicit private-CIDR scope extraction now live in
`src/intent_contracts.py`. The legacy loop retains import-stable aliases only;
scope extraction never authorizes scanning, and the existing broker/policy
boundary remains the execution authority.

The retired loop-local canonical-read helpers are now delegating import aliases
only. Their implementations live in `src/aci.py` and `src/intent_contracts.py`;
the aliases remain temporarily because existing callers/tests import private
names. They make no decisions independently.

## Duplicate decision audit

The important current duplicates are:

1. Domain selection is made by `_classify_agent_request`, then independently
   inferred by `compile_intent`, then re-expanded by `_DOMAIN_TOOL_MAP` and
   keyword/RAG selection.
2. Read/action identity is present in `DomainContract`, the capability
   registry, `_canonical_read_action`, and tool prompt sections.
3. Capability relevance can be selected by caller-provided tools, deterministic
   domain seeding, embedding index, keyword fallback, skill expansion, and
   forced tools.
4. Completion can be inferred from durable Run state, canonical read state,
   tool success, verifier output, and prose/success heuristics.
5. Continuation can be inferred from a user phrase, assistant follow-up text,
   recent conversation, and durable Run state.

For every migration, the server-owned frame/contract, capability registry,
policy/executor, durable Run, and finalizer are the intended single authorities
respectively. Compatibility code must call those seams and must not select a
different domain, action, completion, or permission.

## Migration order

The first implementation slice is the ACI action projection: construct the
bounded shortlist, distinguish `NEED_CONTEXT` from `NO_APPLICABLE_ACTION`, and
derive deterministic read fast paths in one reusable seam. Composition and
capability creation are represented as validated ACI contracts only after the
direct-action path remains policy-bound; neither creates a second executor or
registry.

The capability registry also contains the bounded meta-capability surface
(`inspect_registry`, `identify_gap`, `propose`, and `stage`). The current slice
only validates and projects the request contract; Developer ACI implementation,
tests, review, staging, and trusted registration remain deliberately separate
from model choice and are not yet a production CREATE_CAPABILITY workflow.

The exit criterion for this map is a thin compatibility facade whose only job
is to receive a turn, invoke the canonical ACI lifecycle, and persist/deliver
the result. Until then, `agent_loop.py` remains legacy orchestration under
strangler control and is not treated as removed.

Background continuation callers now select `aci_mode="aci"` explicitly in
`src/bg_monitor.py` and `src/task_scheduler.py`; this removes their accidental
dependence on the helper's compatibility default while preserving the public
legacy default for unmigrated provider/tool adapters. The default flip was
characterized and reverted because it caused 21 compatibility regressions in
legacy parsing/approval tests; those adapters remain a measured migration
boundary, not an unreported second success path.

All active callers now import `stream_aci_turn` from `src.aci` (aliased locally
where the surrounding call shape is retained). The seam force-binds
`aci_mode="aci"` before delegating to the temporary implementation, so a
production caller cannot select legacy or shadow orchestration. The sole
remaining direct stream import is inside this compatibility seam itself.
