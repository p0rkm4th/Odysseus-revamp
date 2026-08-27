# Hades V1 Finalization Status

This is an exact-head reconciliation against the current local checkout. It
is an engineering status record, not a readiness declaration.

## Source and runtime truth

| Field | Current evidence |
|---|---|
| Branch | `hades-aci-v1` |
| Local HEAD | `1dcd084e4f905875ae919210da54dcbf6663c019` |
| Remote HEAD | `1dcd084e4f905875ae919210da54dcbf6663c019` |
| Worktree | clean; tracking `origin/hades-aci-v1` |
| Running container | `odysseus-odysseus-1` |
| Running image reference | `odysseus-odysseus` (Compose-managed name; candidate tag retained locally) |
| Running image digest | `sha256:7a95786c681038159df7c51fca47eb4dec775a61964819e6c4028a10e4c4719e` |
| Embedded source label | `1dcd084e4f905875ae919210da54dcbf6663c019` |
| Runtime status | running, restart count 0 |
| Health | `GET /api/health` returns `healthy` |
| Last known-good source | `1dcd084e4f905875ae919210da54dcbf6663c019` |
| Rollback images | preserved locally, including `odysseus:rollback-b471e104-prev` |

The running image's source label matches both local and remote HEAD. The
runtime image reference is not itself an immutable candidate tag; a future
release checkpoint should deploy and verify an explicit SHA-tagged image.

## Sol review reconciliation

The independent review examined `c91a65bd2bcbd63598741b93b701452f6b736254`.
The current checkout is newer by six commits. Findings below are classified
against the current source rather than copied forward as assumptions.

| Review area | Prior grade | Current classification | Evidence / remaining work |
|---|---:|---|---|
| Control-plane architecture | A- | PARTIALLY FIXED | Production callers use `stream_aci_turn`; compatibility tests and the legacy implementation remain. Semantic ownership and physical strangling still need completion. |
| Security / authority | A | FIXED / MAINTAIN | Focused control-plane and security coverage remains green in the latest recorded runs. Continue treating any regression as release-blocking. |
| Grounding | A- | PARTIALLY FIXED | Asset, household, aggregation, and inventory mutation projections now use structured results/readback. A unified final `AnswerSource` and complete canonical-read audit remain. |
| Local-model architecture | B+ | AUDIT METRIC STALE | Profiles and ACI seams exist, but current-head live Qwen evidence is unavailable; no new portability claim is made. |
| Performance | C+ | STILL PRESENT | Deterministic paths were improved, but current-head latency phase timings and complete model-call/burden evidence are not yet recorded. |
| Maintainability | C+ | STILL PRESENT | `src/agent_loop.py` remains a large compatibility/implementation surface; no claim of a thin facade. |
| CI / release | C | PARTIALLY FIXED | CI workflows exist, but current branch push-gating/required checks and an exact immutable candidate deployment still need verification. |
| Provider portability | B- | STILL PRESENT | Provider/model contracts exist; a current-head conformance matrix and live second-provider evidence are absent. |
| Owner UX | B- | PARTIALLY FIXED | Canonical Asset/Household grounding and mutation verification improved owner paths. Repeated owner E6, exact stream completion, and unified failure language remain open. |
| Current-head readiness | B- | AUDIT METRIC STALE | The reviewed SHA is no longer current. Current HEAD is source-matched to the running container and healthy, but full current-head release evidence is incomplete. |

## Current measurable baseline

- Latest focused checkpoint: `252 passed, 1 skipped` across ACI lifecycle,
  first-class regressions, intent contracts, household projection, and tool
  binding projection tests.
- Latest recorded full regression on the writable test setup: `6720 passed,
  5 skipped, 6 failed`; all six failures were storage-preflight environment
  assumptions for `/home/.docker-data`, not a claimed clean release result.
- Current-head full regression and current-head Qwen evidence are still
  required before any V1 readiness claim.
- Local Ollama was previously unavailable at `127.0.0.1:11434`; live Qwen
  verification is therefore **UNVERIFIED**, not passed by fixture evidence.
- Chroma and SearXNG were previously healthy; that does not substitute for a
  complete current-head acceptance run.

## Priority finish gates

1. Run current-head full regression with storage fixtures isolated and report
   the remaining failures honestly.
2. Prove one final answer owner and exactly-once stream/finalization behavior.
3. Audit and remove remaining production semantic authority from
   `agent_loop.py`; retain only tested compatibility delegation where needed.
4. Record latency/model-burden and reference-resolution evidence at this SHA.
5. Verify CI push gating, build one explicit SHA-tagged candidate, and verify
   running image/source/digest together.
6. Run owner-failure regressions and live Qwen only when the provider is
   actually available.

## Verification labels

- **LIVE VERIFIED:** source/runtime health and embedded source-label match for
  the running container.
- **INTEGRATION VERIFIED:** focused ACI and projection tests listed above.
- **FIXTURE VERIFIED:** prior broad regression and dogfood evidence recorded in
  the reuse ledger; not proof of live Qwen behavior.
- **UNCONFIGURED / UNVERIFIED:** live Ollama/Qwen and any external provider or
  credential-dependent path not exercised in this environment.

This document must be updated whenever the source, deployment, or release
evidence changes.
