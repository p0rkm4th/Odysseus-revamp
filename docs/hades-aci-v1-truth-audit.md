# Hades ACI V1 truth audit

Status: active engineering checkpoint, not a release declaration.
Date: 2026-08-26

This document separates current checkout evidence from deployed-runtime evidence.
It is intentionally conservative: focused tests do not promote a behavior to
live evidence, and automated E5 does not promote a behavior to owner E6.

## State and evidence

| Item | Current truth | Evidence |
|---|---|---|
| Branch | `hades-aci-v1` | clean checkout |
| Pushed source | `72f41428` | `origin/hades-aci-v1` matches |
| Deployed source | `cfbe6244` | `/api/version`, image labels |
| Running image | `odysseus:candidate-cfbe6244` | Docker inspect |
| Rollback | `odysseus:rollback-b471e104-prev` | Docker inspect |
| API | healthy | `/api/health` |
| Broker | active; socket present | systemd/socket check |
| Owner E6 | pending | no owner GUI claim |
| Automated E5 | prior deployed canary verified | 36-case sanitized live matrix |
| Full regression | `6399 passed, 3 skipped` at the prior runtime gate | progress ledger |
| Current focused gate | `181 passed` security/control-plane; `204 passed` latest ACI/reference slice | pytest logs |

The latest source contains reference-projection, homelab executor, live-canary,
and auditable storage-preflight changes that are not yet source-matched in the
running image. A supported dangling-image prune reclaimed 9.067 GiB; storage
preflight still blocks a large replacement build at 23 GiB free / 74% used
against its 30 GiB guard.

## ACI control-plane truth

- Canonical architecture remains `Domain → Capability → ActionSpec →
  ToolBinding`; the model is advisory and does not own authority.
- Deterministic owner Memory, Work, Assets, Network-context, and safe service
  reads have canonical projections and terminal post-Result answer handling in
  the tested paths.
- `MODEL_FALLBACK` is authority-free and receives no tool schemas or bindings.
- The previous direct-fallback buffering defect was fixed: fallback prose now
  crosses the answer boundary instead of being lost in the ACI buffer.
- Successful deterministic reads do not re-enter bounded Action selection in
  the covered paths.
- Asset ordinal resolution now prefers server-owned ordered/eligible result
  entities and uses `last` only when no ordered set exists. This is source-level
  focused evidence, not yet deployed evidence.
- Homelab binding now maps structured `UNAVAILABLE`, `INVALID_RESULT`, and
  related statuses to failed executor semantics instead of transport success.
  This is source-level focused evidence, not yet deployed evidence.

## Required metrics and present evidence

| Area | Truth |
|---|---|
| H0 | Frozen 15-case synthetic baseline: success `0.20`, weighted `0.4333`. |
| ACI improvement | Historical synthetic ACI checkpoint: approximately `0.8667` case success / `0.9333` weighted; not a substitute for broad held-out live evidence. |
| Live Qwen | Prior deployed matrix: `36/36` answers, corrected trajectory scorer `36/36`, zero transport errors/leaks. |
| Model calls | Live deterministic reads generally used one answer/model call and zero tool-index lookup in recorded probes. |
| Tool-index subtraction | Unique canonical reads record bypass; broad current totals require a fresh source-matched run. |
| Result projection | Memory raw result was historically ~17K characters; the repaired path projects before answer synthesis in covered tests. |
| Latency | Existing matched benchmark records total, TTFT, prep, model wait, tokens, and calls. The prior owner report was roughly raw 3.5s vs Hades 14.5s; a fresh attribution run is still required. |
| Model burden | Framework/model burden labels and totals are instrumented; latest broad source-matched aggregate is pending deployment. |
| Context envelope | Runtime allocation, ACI target, requested input, reserved output, and effective context are instrumented. |

## Security invariants

Focused security/control-plane evidence remains green (`181 passed` in the
latest gate). The following remain non-negotiable and are not delegated to
MODEL_FALLBACK: exact consequential approval and digest sealing, replay
protection, owner isolation, broker peer/location validation, policy and
disabled-tool authority, target/scope authorization, external-content taint,
CMDB strong identity, and the absence of generic Hades root/sudo/Docker
authority. No current evidence authorizes weakening any of these.

## Continuity and epistemics

- Intentional asset ordinal continuation and durable Continue behavior have
  focused and prior live evidence.
- Fresh-session versus intentional-continuation selection is now explicit in
  the live harness; seeded core/held-out/rotating selection is reproducible.
- Current canonical/observed operational state is intended to supersede stale
  remembered state in present-tense projections while preserving history. A
  broad current-state reconciliation audit remains incomplete.

## Runtime and storage

- Current/rollback/harness/pinned images were preserved.
- Exact unreferenced obsolete Odysseus candidate images were removed; no broad
  `docker system prune -a` was used and no containerd storage was manually
  deleted.
- Root Btrfs is at approximately 80% used with 18 GiB free. The storage
  preflight correctly fails closed below its 30 GiB build-headroom target.
- The next deployment must preserve the current candidate and rollback, build
  once after a passing preflight, verify exact source/image/migration
  provenance, then rerun live Qwen E5.

## Open requirements before claiming V1 complete

1. Deploy and source-match the latest runtime fixes.
2. Rerun the expanded live Qwen core/held-out/rotating matrix on that image.
3. Produce a fresh raw-vs-Hades latency attribution with equivalent
   deliverables and model-call counts.
4. Complete the broad truth reconciliation audit, including provider/runtime
   characterization and answer-phase leakage checks on the final image.
5. Perform owner GUI dogfood for E6; automated E5 cannot replace it.

Until these are verified, this remains an active V1 engineering checkpoint.
