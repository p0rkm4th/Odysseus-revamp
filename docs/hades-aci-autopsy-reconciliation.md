# Static autopsy reconciliation

The external static review was checked against current HEAD rather than copied
into the repository. Findings below are classifications, not claims of
completion.

| Finding | Current classification | Evidence / disposition |
|---|---|---|
| Model-name capability heuristics | PARTIALLY_FIXED | provider/model readers remain; runtime evidence now has explicit precedence, persisted TTL cache, and metadata-only Ollama characterization; active structured/native behavior probes remain |
| Protocol/runtime identity split | PARTIALLY_FIXED | provider readers distinguish vendors in places; generic runtime seam is incomplete |
| ContextEnvelope | PARTIALLY_FIXED | canonical `ContextEnvelope.from_runtime_profile` and per-ACI metrics now distinguish runtime allocation from architecture maximum; provider discovery wiring remains |
| Token accounting incl. schemas | PARTIALLY_FIXED | nested native schema JSON is now counted by the shared estimator; runtime tokenizer calibration and provider-reported error tracking remain |
| Output reservation | PARTIALLY_FIXED | reserve exists in compactor; requested-output coupling needs provider-aware integration |
| Endpoint metadata cache | PARTIALLY_FIXED | fresh endpoint/runtime/model characterization now reuses persisted profiles before metadata calls; fingerprint refresh and active capability probes remain |
| Global local inference lock | STILL_PRESENT | `_LOCAL_MODEL_LOCK` in `src/llm_core.py`; safe single-GPU serialization is preserved, resource scheduler deferred |
| Multiple tool protocols | PARTIALLY_FIXED | synthetic Ollama probes show strict Decision JSON PASS and native tools PASS; runtime selection wiring and broader A/B matrix remain |
| Reasoning/transport separation | PARTIALLY_FIXED | Decision JSON transport is isolated from free-form text and synthetic probes pass; broader negotiated runtime selection remains |
| Canonical action registry | PARTIALLY_FIXED | `ActionSpec` registry is canonical for new projections; legacy schema/parser/tag compatibility paths remain |
| oversized agent loop/core | STILL_PRESENT | strangler decomposition not yet justified by an integrated seam |
| internal message repair | PARTIALLY_FIXED | provider normalization exists; counters and strict internal state validation incomplete |
| structured state vs compaction prose | PARTIALLY_FIXED | Run/Work persistence exists; full invariant audit remains |
| stable prompt prefix/cache | PARTIALLY_FIXED | chat prefix ordering exists; ACI packet integration and cache evidence remain |
| loose ~50-round budgets | PARTIALLY_FIXED | local profile caps exist but are not authoritative in current loop |
| harness overhead benchmark | PARTIALLY_FIXED | `ab11579c` adds a local-only matched benchmark and two synthetic samples; broader workload matrix remains |
| runtime diagnostic profile | PARTIALLY_FIXED | sanitized runtime profile/cache primitives and owner-scoped `/api/hades/runtime-profile` now exist; active probe UI remains |
| outbound URL/SSRF boundary | PARTIALLY_FIXED | `url_safety.py`/`url_security.py` exist; one unified policy boundary remains |
| developer sandbox | PARTIALLY_FIXED | Workspace YOLO is non-root, repo-scoped, leased and audited; stronger resource/egress isolation remains |
| test order independence | PARTIALLY_FIXED | broad suite infrastructure exists; ACI-specific order checks are new work |
| lower-priority dependency/frontend cleanup | DEFERRED | outside T0/T1 |

The ACI contract slice intentionally does not claim to repair the STILL_PRESENT
or PARTIALLY_FIXED runtime integrations.
