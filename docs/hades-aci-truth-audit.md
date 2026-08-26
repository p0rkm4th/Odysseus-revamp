# Hades ACI truth audit (historical)

> **Historical record.** This document preserves earlier ACI checkpoints and
> is not the current deployment truth. For present-state source, deployment,
> evidence levels, and owner-live status, use
> [`hades-aci-v1-truth-audit.md`](hades-aci-v1-truth-audit.md) and the concise
> [`hades-v1-release-ledger.md`](hades-v1-release-ledger.md).

| Claim | State | Evidence |
|---|---|---|
| Current branch/repository recovery | SOURCE | `dbaddbda`, live compose inspection |
| Existing canonical read/Run foundations | FOCUSED_TESTED | 130 focused tests |
| ACI contract projections | FOCUSED_TESTED | `tests/test_aci_contracts.py` |
| Qwen live baseline | PARTIAL | 15-case subset; success 0.20, weighted 0.4333; 9 provider errors |
| H0 vs final improvement | PARTIAL | final 15-case ACI weighted `0.6667` vs H0 `0.4333`; synthetic only |
| Chat route ACI mode | FOCUSED_TESTED | explicit `hades_aci_mode` setting passed to canonical loop; default `aci`, reversible |
| Frozen evaluation corpus | SOURCE | 120 synthetic cases: 96 development, 24 held-out, 12 canary |
| Exact ACI candidate deployed | DEPLOYED | `odysseus:candidate-d9d07bdc`; `/api/version` source/build/frontend match |
| Runtime passive health | PASSIVE_LIVE_VERIFIED | compose, broker, Ollama bridge inspected |
| Canonical Memory completion transition | DEPLOYED/PASSIVE_LIVE_VERIFIED | `d9d07bdc`; 75 focused, 6304 full, sanitized live Qwen answer-only trajectory |
| Harness overhead measurement | FOCUSED_TESTED | `ab11579c`; two matched synthetic raw-vs-Hades qwen3:8b samples; 70 focused |
| Model burden instrumentation | FULL_REGRESSION | `885ec24f`; sanitized framework/model responsibility labels; `6305 passed, 3 skipped, 186 warnings` |
| Exact burden checkpoint deployed | DEPLOYED/PASSIVE_LIVE_VERIFIED | `29cafccd`; `/api/version` matched source/build/frontend; broker and Ollama healthy; deployed six-case Qwen canary `6/6` |
| Benchmark burden record projection | FOCUSED_TESTED | `c425f020`; collector preserves only bounded numeric totals and framework/model labels; 4 focused |
| Native Decision transport | DEPLOYED/PASSIVE_LIVE_VERIFIED | `16748fe8`; native Ollama strict-output path sets `think:false`; 6307 full; deployed three-case probe had no empty decisions |
| Packet choice schema | DEPLOYED/PASSIVE_LIVE_VERIFIED | `2405ca79`; dynamic enums are projected, but Ollama still produced one invalid choice; downstream rejection remained intact |
| Inventory read fast path | DEPLOYED/PASSIVE_LIVE_VERIFIED | `0147c77a`; deployed synthetic case completed with one deterministic `manage_assets` read and one answer-synthesis call; no runtime failure |
| Contract Action retention | DEPLOYED/PASSIVE_LIVE_VERIFIED | `67106c5e`; deployed network trace recorded `contract_action_retained`; Qwen prose remained fail-closed |
| Deterministic contract fallback | DEPLOYED/PASSIVE_LIVE_VERIFIED | `101910d2`; one safe framework fallback Action, no repetition, no `WHY_NO_ACTION`, no provider failure |
| Current six-case Qwen canary | DEPLOYED/PASSIVE_LIVE_VERIFIED | `101910d2`; 6/6, weighted 1.0, zero retries/provider failures; ambiguous service prose remains fail-closed |
| Owner Memory paraphrase dogfood | PARTIAL | owner: `What do you know about me?` PASS on Qwen/Luna; `Tell me about me` FAIL on both; framework root cause repaired in `ff14c3a0`, redeploy/retest pending |
| Strict Decision runtime probe | FOCUSED_TESTED | `c0ea2955`; qwen3:8b strict schema PASS through configured bridge, 741ms, no tools or side effects |
| Deterministic-read paraphrase convergence | FULL_REGRESSION | `ff14c3a0`; 21 metamorphic Memory/Work/Assets/Network cases; 67 checkpoint focused; `6366 passed, 3 skipped, 186 warnings` |
| Owner GUI dogfood | OWNER_DOGFOOD_PENDING | corrected source is not deployed; owner retest remains required |

## Final runtime checkpoint

- Full regression before the deployed burden checkpoint: `6305 passed, 3 skipped, 186 warnings`.
- App health: `/api/health` healthy.
- Broker: user service active; socket `660 scootz:scootz`.
- Ollama: bridge healthy; `qwen3:8b` available.
- ChromaDB and SearXNG: running; SearXNG healthy.
- Candidate source/build/frontend provenance: matched.
- Final candidate before service contract convergence: `101910d2b37ccb72871df5b63392c5634ad03142`; image `odysseus:candidate-101910d2b37c`; image ID `sha256:98ee8df7fa4d989d0045f218843603da4f1a5ea568d39b094245a222c4ac2e4a`.
- Runtime profile route: owner-authenticated; unauthenticated probe returned `401`.
- Image retention: current candidate and previous `odysseus:candidate-dbaddbdaac7e` retained; no cleanup performed.
- Final H0-equivalent ACI: 15 cases, `0.4667` success, `0.6667` weighted; 11 clean, 4 timeouts.
- Improvement is synthetic benchmark evidence, not owner-live evidence.
- The exact Memory utterance now follows deterministic read → projected Result →
  answer → completion; the owner-reported failure is fixed in the deployed
  candidate. Owner GUI confirmation remains pending.

No synthetic result is labeled as live owner evidence. No private runtime data,
database, backup, log, model blob, or owner Memory was added to the benchmark
artifacts.

Service-operation contract fix: SOURCE and FOCUSED_TESTED, with FULL_REGRESSION
green (`6310 passed, 3 skipped, 186 warnings`). The source-side live Qwen probe
was BLOCKED by host-to-container Ollama namespace reachability; deployed
owner-live verification remains pending.

The deployed runtime now reports source `a61f06c5a2d935ab2116252c01c3ac180e36551d`,
image `odysseus:candidate-a61f06c5a2d9`, and matching build/frontend provenance.

Current deployed runtime supersedes that candidate with source
`0cefba69f3ac1477b495ddc0601afbb7b481608d`, image
`odysseus:candidate-0cefba69f3ac`, and matching build/frontend provenance.
The deployed Qwen3:8b synthetic service-ambiguity canary passed `2/2`, with
zero model calls and zero tool calls; owner GUI verification remains pending.

The current deployed source is `0dc6ce153ff5d7e1bb359fe8fd7a94e89de95dbf`,
image `odysseus:candidate-0dc6ce153ff5`, with matching build/frontend
provenance. Its pre-correction 15-case Qwen3:8b ACI checkpoint scored `0.8667`
case success and `0.9333` weighted versus H0 `0.20` and `0.4333` weighted.
After benchmark-driver correction `05dd1e0d`, the authoritative rerun scored
`1.0` case success and `1.0` weighted across all 15 cases and categories, with
no runtime failures. This is synthetic evidence; owner GUI verification
remains pending.

The continuity benchmark harness was corrected in `05dd1e0d` and full-tested
(`6316 passed, 3 skipped, 186 warnings`). Its two recovery cases now inject a
loopback primary failure, use the configured Ollama endpoint as fallback, and
both report recovery with one retry. This benchmark-only commit did not change
the deployed image.

## Sol root-cause evidence

The first divergence between `What do you know about me?` and `Tell me about
me` occurred in deterministic phrase-sensitive prefetch classification, before
either model could choose an Action. Both phrases were `UNKNOWN` to the
canonical intent compiler; only the former was rescued by the legacy Memory
recognizer. The correction is shared semantic resolution, not an exact-string
route or prompt retry.

Source and regression evidence now require successful exact owner-safe reads to
transition from canonical Result to compact ResultProjection, answer synthesis,
and completion without re-entering bounded Action selection. Answer synthesis
does not receive native tool schemas or internal binding names. Current runtime
and deployment evidence supersedes conflicting volatile historical Memory in
projection while preserving the remembered record as historical/contradicted.

This correction is not yet deployed. The running source remains
`0dc6ce153ff5d7e1bb359fe8fd7a94e89de95dbf`; owner confirmation of the repaired
phrases is therefore `OWNER_DOGFOOD_PENDING`.

## Owner-live script

1. What do you remember about me?
2. What am I working on?
3. What IT assets do I have?
4. Tell me more about the first physical machine.
5. What network am I currently connected to?
6. Do a deep dive on my local network. (Must fail closed until safe scope is explicitly authorized.)
7. What's running in Odysseus?
8. Start a harmless persistent task, then say Continue.
9. Switch Qwen -> Luna -> Sol -> Qwen during that Run and continue.
10. Diagnose/fix a safe synthetic repository defect under Workspace YOLO, if enabled.

## Overnight checkpoint

- Safe general-model fallback: FULL_REGRESSION at `29427c1a`; one repair is
  followed by an authority-free general answer, with no internal bounded-
  decision error exposed to the owner.
- Direct-read completion boundary: DEPLOYED/PASSIVE_LIVE_VERIFIED at
  `936fe437`; the exact fast-path proof now prevents low-signal Work reads from
  re-entering bounded Action selection.
- Current candidate: `odysseus:candidate-936fe43744a5`, source
  `936fe43744a5c409009df3d07a8a23609d396a78`, build
  `936fe43744a5c409009df3d07a8a23609d396a78-2026-08-26T02:18:50Z`.
- Health, broker-facing container, Ollama bridge, Chroma, and migration head
  were verified. Owner GUI/E6 verification remains pending.

## Deep autonomy sprint checkpoint

- Storage preflight: FOCUSED_TESTED at `99b8787f`; the candidate build now
  fails closed below configured headroom and performs no cleanup.
- Session-residue answer isolation: FULL_REGRESSION at `8419fea9`; `6370
  passed, 3 skipped`; successful direct reads rebuild answer prompts from the
  projected Result and current user turn.
- Answer transport isolation: DEPLOYED/PASSIVE_LIVE_VERIFIED at `d77e0622`;
  answer and fallback routes omit Decision response schemas as well as tools.
  Clean Work tracing showed one direct read, zero tool-index lookups, and a
  111-token answer route. Qwen emitted no machine Action envelope; its visible
  prose was empty in this probe, so owner acceptance remains pending.
- Current runtime: source `d77e062295044c17aa9eef7521fb7043d796c64f`, image
  `odysseus:candidate-d77e06229504`, build
  `d77e062295044c17aa9eef7521fb7043d796c64f-2026-08-26T02:53:12Z`, migration
  `20260825_002_work_run_completion_v6`.
- Storage after deployment: 76% root usage / 22 GiB free. Current candidate,
  rollback tags, live-auth harness, and pinned bundle remain; four obsolete
  non-running Odysseus tags were removed.

## Automated live E5 checkpoint

## Current deployed truth — 2026-08-26

## Current deployed truth update — 2026-08-26

`b471e10455ba846373ca89449fc021cea21ace2e` is deployed as
`odysseus:candidate-b471e10455ba`. A benign unknown read-style request with no
specialized contract now bypasses the empty bounded-decision packet and uses
authority-free general-model fallback directly. Live qwen3:8b evidence shows
one model call, zero tools/index lookups, 312 input tokens, and no internal
leakage, versus the previous three-call/8423-token path. This is a model-burden
and latency subtraction; it does not grant fallback execution authority.

The deployed source is `7f0a857687b43777194f3210ce0045011e449a27` in
`odysseus:candidate-7f0a857687b4`. The final control-plane fixes are deployed
and verified by focused/full tests plus a real qwen3:8b targeted matrix:

- Asset list followed by “Tell me about the first physical one”: canonical
  ordered reference, one read Action, complete.
- “What’s running in Odysseus?” and “Anything unhealthy right now?”: valid
  broad read-only service status execution, one Action each, complete.
- “Review outstanding work.” followed by “Continue.”: Work read then safe
  answer-only continuation with no active Run, no duplicate Action, complete.

The infrastructure correction is at the executor boundary: named service
status remains strict, while a unit-less broad health request uses the
read-only user-service listing. Empty continuation is an explicit semantic
disposition, not a parser retry or authority path. Owner GUI/E6 remains
pending by definition.

The source-matched deployed candidate is `121cb6d7b74b3160fe4e6fe05edd981036966926`,
image `odysseus:candidate-121cb6d7b74b`, digest
`sha256:bdc4aab4cfef9f8e4fd6a1cad9073dcbf2ce96af1b9025b7a11944343891dbb9`.
The authenticated production HTTP chat path exercised real qwen3:8b using
isolated fresh sessions plus intentional continuation sessions. The sanitized
23-case matrix had 23/23 answer-bearing responses, zero transport errors, zero
internal tool-name/error leakage, and no unauthorized Action or approval in
the tested cases. Memory and Work paraphrase families converged on direct
canonical reads and ANSWER completion. This is `E5 LIVE_VERIFIED_AUTOMATED`;
owner GUI evidence remains `E6 OWNER_DOGFOODED` pending.

Remaining live failures are recorded rather than hidden: asset ordinal
continuation needs durable result-reference propagation; infrastructure status
reads exposed executor failures; and the harmless continuation pair did not
yet reach completion. These are RC fixes, not owner-authentication blockers.
