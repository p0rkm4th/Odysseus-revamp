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
| Pushed source | `8038e227` | `origin/hades-aci-v1` |
| Deployed source | `8038e227` | `/api/version`, immutable image marker |
| Running image | `odysseus:candidate-8038e227` | Docker inspect |
| Rollback | `odysseus:rollback-b471e104-prev` | Docker inspect |
| API | healthy | `/api/health` |
| Broker | active; socket present | systemd/socket check |
| Owner E6 | pending | no owner GUI claim |
| Automated E5 | current deployed canary verified | prior 25-case core + 12 held-out + 16 rotating sanitized live cases, plus corrected seeded 7/7 continuation-aware run |
| Live security E5 | unauthorized network-scope request | 1/1 trajectory pass; zero tool calls/approvals/errors |
| Full regression | `6422 passed, 3 skipped, 186 warnings` | host virtualenv gate; source before the final fallback guard |
| Current focused gate | `177 passed` continuation/intent/loop; `122 passed` infrastructure/reference; `82 passed` fallback/workspace seam | pytest logs |
| Matched local latency | raw `3.596s`; Hades `10.484s`; delta `6.888s`; extra provider inference `6.684s` | benchmark with equal 128-token budget |

The running process is source-matched through the immutable image marker and
reports branch `hades-aci-v1`.
Storage preflight still blocks a large replacement build at 23 GiB free / 74%
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
- The typed `TurnDisposition` precedence helper is deployed and its live
  six-case canary passed `6/6`; focused coverage is green (`86` tests).
- Provider-switch/recovery source coverage is green (`137` focused tests), but
  this is not live multi-provider evidence; the available live provider here is
  qwen3:8b through the Ollama bridge.
- Developer/sandbox coverage is green (`62` historical tests plus `175` focused
  canonical Developer/projection tests) for the bounded workspace path and the
  new `developer.read` semantic binding. This is source evidence only: the
  production image has no selected workspace mount, so live E5 is pending.
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
- Ordinary unknown/action-like turns with no resolved domain, workspace, or
  continuation now bypass generic tool-index retrieval for safe/unknown
  operation classes and use the authority-free fallback floor. This removes a
  false Cookbook/developer route for ordinary imperatives; focused coverage is
  green (`82 passed`), and the deployed targeted live check used zero tools and
  zero index lookups.
- Terminal/blocked durable continuation is now an explicit answer-only
  disposition. It preserves the durable state explanation and prevents a
  completed or unavailable Run from re-entering model Action selection.
- Live intentional continuation now passes asset list → first physical asset
  and Review outstanding work → Continue. The asset follow-up preserved strong
  identity `PHYSICAL-001`; Continue resumed with zero tool calls and no
  fallback.

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
