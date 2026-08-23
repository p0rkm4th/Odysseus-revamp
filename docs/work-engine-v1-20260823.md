# Durable Work Engine V1

Source lineage and runtime acceptance are recorded in the release handoff.

The Work Engine owns orchestration history only: goals, projects, tasks,
dependencies, runs, actions, result/artifact references, append-only events,
and commitments. Security engagements/findings and Inventory items/drafts
remain domain-owned.

V1 provides:

- owner-scoped durable state with revisioned lifecycle fields;
- deterministic bounded task dependency cycle rejection;
- Capability/ActionSpec-compatible action identity and approval references;
- compact context projection with active work, pending approval/input,
  commitments, actions, and recent events;
- idempotent completed-action replay behavior;
- read/review-only Security and Inventory adapters;
- no autonomous retry, execution escape hatch, or automatic domain mutation.

Migration: `20260823_005_work_engine_v1`.
