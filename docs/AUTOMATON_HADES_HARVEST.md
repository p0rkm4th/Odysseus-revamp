# Automaton → HADES WorkEngine harvest

Reconnaissance only. Automaton revision `d8f816881fd24b6f5e3d616e59edec387a447667`
is MIT, Copyright 2026 Conway. No Automaton code, database, scheduler, or
runtime was copied into HADES.

| Pattern | Automaton source@SHA | HADES evidence | Classification | Real gap | Proposed patch/test |
|---|---|---|---|---|---|
| Task DAG discipline | `src/orchestration/task-graph.ts` @ `d8f816881fd24b6f5e3d616e59edec387a447667` | `src/work_engine.py:102-115` validates same-project dependencies and cycles; `tests/test_work_engine.py:18-28` proves it. `core/work_models.py:26-36` persists dependencies. | `ALREADY_PRESENT` | No demonstrated gap for current WorkEngine creation path. | None. Keep the existing dependency tests as the HADES proof. |
| Leases / overlap guards | `src/heartbeat/scheduler.ts` @ `d8f816881fd24b6f5e3d616e59edec387a447667` | `src/work_engine.py:371-429` has owner-scoped shared/exclusive resource locks, conflict checks, release, and stale-lock recovery; `tests/test_work_engine.py:90-126` covers collision, release, and recovery. | `ALREADY_PRESENT` for action overlap; `DESIGN-HARVEST` for future worker leases | HADES has no demonstrated worker heartbeat/lease consumer; adding one now would be scheduler work outside this campaign. | If a worker runtime is later added, target `src/work_engine.py`/`core/work_models.py`; add an atomic lease-owner/expiry test and stale-worker recovery test. |
| Failure fingerprints | `src/orchestration/task-graph.ts` and `src/heartbeat/scheduler.ts` @ pinned SHA | HADES persists action error text and retry policy in `core/work_models.py:47-49`; `src/work_engine.py:146-184` bounds replay-safe retries. `action_loop_check` exists at `src/work_engine.py:821-825`, but no persisted normalized failure fingerprint is present. | `ADAPT` | Equivalent failures can be recorded as different text and still consume the bounded retry path; no evidence-based “new failure evidence required” contract is visible. | Target `WorkAction`/`WorkEngine.retry_action`; persist a normalized failure digest/evidence reference and reject an equivalent retry without changed evidence. Add deterministic same-fingerprint and changed-evidence tests in `tests/test_work_engine.py`. |
| Bounded retries | `src/orchestration/task-graph.ts:281-310` and `src/heartbeat/scheduler.ts:274-357` @ pinned SHA | `src/work_engine.py:146-184` reads `retry_policy.max_attempts`, clamps it to 1..10, requires replay-safe/idempotent capability, and does not copy approval. `tests/test_work_engine.py:78-88` proves this. | `ALREADY_PRESENT` | No demonstrated gap in action retry safety. | None. Preserve the current retry-policy and ambiguous-outcome boundaries. |
| Human-blocked work | `src/orchestration/task-graph.ts` status model and `src/orchestration/orchestrator.ts` @ pinned SHA | HADES has durable `awaiting_approval` and `awaiting_input` states in `core/work_models.py:41-49`, routes for approval/input progression in `routes/work_routes.py`, and bounded context projection in `src/work_engine.py:987-1005`. | `DESIGN-HARVEST` | HADES represents a blocked run but has no independent task scheduler that can select unrelated runnable work. That is a future orchestration concern, not a missing WorkEngine primitive. | Target a future external worker/launcher seam, not Kernel or the current route. Test that awaiting input does not hide unrelated owner-scoped ready work only when such a launcher exists. |
| Compact worker result envelopes | `src/memory/agent-context-aggregator.ts:54-200` @ pinned SHA | HADES has structured `WorkResult`, `WorkEvent`, verification, and bounded `context()` output in `core/work_models.py:55-60` and `src/work_engine.py:245-270, 492-524, 987-1005`; direct WorkEngine tests prove durable results and replay. | `ADAPT` | HADES stores durable evidence but does not yet provide a worker/supervisor summary contract that distinguishes full failure/blocker detail from compact routine progress. | Target a future WorkEngine context/projection seam; add tests for full failure/security detail, compact success/progress, and bounded output size. Do not add a generic context aggregator now. |

## Explicitly dropped Automaton material

Automaton SQLite ownership, treasury/funding/survival economics, crypto
identity, reproduction, revenue ontology, permissive auto-approval, model
self-approval, worker prose as verified completion, and unrestricted local
execution fallback are not HADES requirements and are not proposed for reuse.

## Concrete future HADES patch list

These are diagnosis-only follow-ups, not work performed in this campaign:

1. **Failure evidence seam** — `src/work_engine.py` and `core/work_models.py`:
   persist a privacy-minimal normalized failure fingerprint plus evidence
   reference; prove equivalent failures do not receive blind retries while a
   materially changed validator/provider result may retry.
2. **Worker lease seam, only if a worker exists** — the existing WorkEngine
   lock/recovery boundary: add owner/worker lease identity and expiry without
   changing authority; prove overlap prevention and stale-worker recovery.
3. **Result projection seam** — `src/work_engine.py:987-1005`: add a bounded
   supervisor projection only when HADES has a real worker consumer; prove
   failures/blocked/security events retain detail while routine progress is
   compact and bounded.
4. **Human-blocked launcher behavior** — the future external launcher around
   `routes/work_routes.py`: prove `awaiting_input`/`awaiting_approval` work does
   not prevent unrelated ready work, without adding a scheduler to this audit.

## Evidence command

The intended direct WorkEngine command was:

```text
python -m pytest tests/test_work_engine.py
```

The checkout has no pytest executable or installed pytest module in the audit
environment (`/usr/bin/python: No module named pytest`), so the test result is
an environmental blocker rather than an inferred pass. Source-level evidence
and the test bodies were inspected directly.
