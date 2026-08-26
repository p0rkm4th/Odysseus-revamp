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
| Pushed source | `a38f1c4d` | `origin/hades-aci-v1` |
| Deployed source | `1aa1c95d` | `/api/version`, immutable image marker |
| Running image | `odysseus:candidate-1aa1c95d` | Docker inspect |
| Rollback | `odysseus:rollback-b471e104-prev` | Docker inspect |
| API | healthy | `/api/health` |
| Broker | active; socket present | systemd/socket check |
| Owner E6 | pending | no owner GUI claim |
| Automated E5 | current deployed canary verified | 25-case core + 12 held-out + 16 rotating sanitized live cases, 53/53 trajectory passes |
| Live security E5 | unauthorized network-scope request | 1/1 trajectory pass; zero tool calls/approvals/errors |
| Full regression | `6414 passed, 4 skipped, 186 warnings` after current source slice | container test gate |
| Current focused gate | `181 passed` security/control-plane; `204 passed` latest ACI/reference slice | pytest logs |
| Matched local latency | raw `3.596s`; Hades `10.484s`; delta `6.888s`; extra provider inference `6.684s` | benchmark with equal 128-token budget |

The running process is source-matched through the immutable image marker.
Storage preflight still blocks a large replacement build at 24 GiB free / 74%
used against its 30 GiB guard. Default compose runs baked image source; the
developer checkout mount is explicit via `docker-compose.developer.yml`.

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
  entities and uses `last` only when no ordered set exists; deployed core E5
  verified the list → “first physical one” continuation.
- The same source-matched image passed seeded held-out (`12/12`) and rotating
  (`16/16`) live slices, including cross-domain contamination, infrastructure
  near-misses, fallback, and asset continuation families.
- Completed canonical asset reads now expose their ordered/eligible entity set
  through the owner-scoped session reference projection, so a later ordinal
  turn can resolve without an active Run or lexical target guessing. The
  focused reference bridge gate is green (`234 passed` with the executor
  slice).
- Homelab binding maps structured `UNAVAILABLE`, `INVALID_RESULT`, and related
  statuses to failed executor semantics instead of transport success; deployed
  infrastructure reads completed in the core E5 matrix.
- Unqualified `service_status` now projects the existing bounded Hades runtime
  health collector instead of invoking container-local `systemctl --user`;
  explicit unit-targeted reads remain on the separate path. This is source-level
  focused evidence, not yet deployed evidence.
- Unknown benign ACI reads now bypass generic tool-index retrieval before the
  authority-free MODEL_FALLBACK path. The source-path benchmark reduced tool
  selection from `1.363s` to `0.076s`; focused fallback/intent/benchmark tests
  pass (`103 passed`).
- `/api/version` now distinguishes declared image metadata from the imported
  runtime tree (`runtime_source_commit`, `runtime_source_kind`, and
  `source_match`), preventing bind-mounted checkout code from being misreported
  as the image's declared source. Provenance/root-path focused tests pass
  (`18 passed`).

## Required metrics and present evidence

| Area | Truth |
|---|---|
| H0 | Frozen 15-case synthetic baseline: success `0.20`, weighted `0.4333`. |
| ACI improvement | Historical synthetic ACI checkpoint: approximately `0.8667` case success / `0.9333` weighted; not a substitute for broad held-out live evidence. |
| Live Qwen | Prior deployed matrix: `36/36` answers, corrected trajectory scorer `36/36`, zero transport errors/leaks. |
| Model calls | Live deterministic reads generally used one answer/model call and zero tool-index lookup in recorded probes. |
| Tool-index subtraction | Unknown benign fallback bypass reduced source-path selection to `0.076s`; canonical reads also bypass. Broad final-image totals remain pending deployment. |
| Result projection | Memory raw result was historically ~17K characters; the repaired path projects before answer synthesis in covered tests. |
| Latency | Before bypass: raw `0.223s`, Hades `5.375s`, prep `1.587s`. After bypass: Hades `3.568s`, prep `0.219s`, tool selection `0.076s`, provider `3.350s`, extra inference `3.118s`, framework residual `0s` within timing noise. |
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
  focused and current deployed E5 evidence (`assets_list` → `assets_reference`,
  and `continuation_start` → `continuation_resume`).
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
- Root Btrfs is at approximately 74% used with 24 GiB free. The storage
  preflight correctly fails closed below its 30 GiB build-headroom target.
- The next deployment must preserve the current candidate and rollback, build
  once after a passing preflight, verify exact source/image/migration
  provenance, then rerun live Qwen E5.

## Open requirements before claiming V1 complete

1. Rerun the expanded live Qwen held-out/rotating matrix on the source-matched image.
2. Produce a fresh raw-vs-Hades latency attribution with equivalent
   deliverables and model-call counts.
3. Complete the broad truth reconciliation audit, including provider/runtime
   characterization and answer-phase leakage checks on the final image.
4. Perform owner GUI dogfood for E6; automated E5 cannot replace it.

Until these are verified, this remains an active V1 engineering checkpoint.
