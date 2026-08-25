# Static autopsy reconciliation

The external static review was checked against current HEAD rather than copied
into the repository. Findings below are classifications, not claims of
completion.

| Finding | Current classification | Evidence / disposition |
|---|---|---|
| Model-name capability heuristics | PARTIALLY_FIXED | provider/model readers remain; runtime evidence now has explicit precedence and a persisted TTL cache, but active provider probes are still a follow-up |
| Protocol/runtime identity split | PARTIALLY_FIXED | provider readers distinguish vendors in places; generic runtime seam is incomplete |
| ContextEnvelope | PARTIALLY_FIXED | canonical `ContextEnvelope.from_runtime_profile` and per-ACI metrics now distinguish runtime allocation from architecture maximum; provider discovery wiring remains |
| Token accounting incl. schemas | PARTIALLY_FIXED | schema counts are instrumented, but estimator remains approximate |
| Output reservation | PARTIALLY_FIXED | reserve exists in compactor; requested-output coupling needs provider-aware integration |
| Endpoint metadata cache | PARTIALLY_FIXED | cached model lists/dead-host cooldown exist; fingerprint+TTL runtime characterization remains |
| Global local inference lock | STILL_PRESENT | `_LOCAL_MODEL_LOCK` in `src/llm_core.py`; safe single-GPU serialization is preserved, resource scheduler deferred |
| Multiple tool protocols | STILL_PRESENT | native/fenced/provider-specific parsing remains authoritative in legacy loop; Decision JSON is only a pure contract slice |
| Reasoning/transport separation | PARTIALLY_FIXED | thinking cleanup exists; negotiated decision channel not wired |
| Canonical action registry | PARTIALLY_FIXED | `ActionSpec` registry is canonical for new projections; legacy schema/parser/tag compatibility paths remain |
| oversized agent loop/core | STILL_PRESENT | strangler decomposition not yet justified by an integrated seam |
| internal message repair | PARTIALLY_FIXED | provider normalization exists; counters and strict internal state validation incomplete |
| structured state vs compaction prose | PARTIALLY_FIXED | Run/Work persistence exists; full invariant audit remains |
| stable prompt prefix/cache | PARTIALLY_FIXED | chat prefix ordering exists; ACI packet integration and cache evidence remain |
| loose ~50-round budgets | PARTIALLY_FIXED | local profile caps exist but are not authoritative in current loop |
| harness overhead benchmark | STILL_PRESENT | no matched raw-vs-Hades timing report yet |
| runtime diagnostic profile | PARTIALLY_FIXED | sanitized runtime profile/cache primitives and owner-scoped `/api/hades/runtime-profile` now exist; active probe UI remains |
| outbound URL/SSRF boundary | PARTIALLY_FIXED | `url_safety.py`/`url_security.py` exist; one unified policy boundary remains |
| developer sandbox | PARTIALLY_FIXED | Workspace YOLO is non-root, repo-scoped, leased and audited; stronger resource/egress isolation remains |
| test order independence | PARTIALLY_FIXED | broad suite infrastructure exists; ACI-specific order checks are new work |
| lower-priority dependency/frontend cleanup | DEFERRED | outside T0/T1 |

The ACI contract slice intentionally does not claim to repair the STILL_PRESENT
or PARTIALLY_FIXED runtime integrations.
