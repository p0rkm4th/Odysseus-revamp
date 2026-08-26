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
| Multiple tool protocols | PARTIALLY_FIXED | synthetic probes show strict Decision JSON and native tools PASS; `c0ea2955` adds a cached live strict-schema probe and diagnostic negotiation projection; authoritative DecisionGateway selection wiring remains |
| Reasoning/transport separation | PARTIALLY_FIXED | Decision JSON transport is isolated from free-form text and synthetic probes pass; broader negotiated runtime selection remains |
| Canonical action registry | PARTIALLY_FIXED | `ActionSpec` registry is canonical for new projections; legacy schema/parser/tag compatibility paths remain |
| oversized agent loop/core | PARTIALLY_FIXED | `PostResultState` makes the successful-read transition explicit; a compact ACI turn disposition and DecisionGateway are now evidence-justified seams, but broad splitting remains deferred |
| internal message repair | PARTIALLY_FIXED | protected ACI packets now survive provider route rebuilding; provider normalization exists, while counters and strict internal state validation remain incomplete |
| structured state vs compaction prose | PARTIALLY_FIXED | Run/Work persistence exists; full invariant audit remains |
| stable prompt prefix/cache | PARTIALLY_FIXED | chat prefix ordering exists; ACI packet integration and cache evidence remain |
| loose ~50-round budgets | PARTIALLY_FIXED | local profile caps exist but are not authoritative in current loop |
| harness overhead benchmark | PARTIALLY_FIXED | model-call and phase accounting now attributes preparation, provider wait, and structured-output buffering; equivalent-deliverable cold/warm matrix remains |
| runtime diagnostic profile | PARTIALLY_FIXED | sanitized runtime profile/cache primitives and owner-scoped `/api/hades/runtime-profile` now exist; active probe UI remains |
| outbound URL/SSRF boundary | PARTIALLY_FIXED | `url_safety.py`/`url_security.py` exist; one unified policy boundary remains |
| developer sandbox | PARTIALLY_FIXED | Workspace YOLO is non-root, repo-scoped, leased and audited; stronger resource/egress isolation remains |
| test order independence | PARTIALLY_FIXED | broad suite infrastructure exists; ACI-specific order checks are new work |
| lower-priority dependency/frontend cleanup | DEFERRED | outside T0/T1 |

The ACI contract slice intentionally does not claim to repair the STILL_PRESENT
or PARTIALLY_FIXED runtime integrations.

## Current root-cause reconciliation

- Runtime capability profile: `c0ea2955` safely probed qwen3:8b strict Decision
  JSON through the configured bridge. The probe passed in `741ms` and selected
  `STRICT_DECISION_JSON` in the diagnostic projection. It does not yet alter
  authoritative DecisionGateway routing.
- Tool protocols before: strict Decision JSON, native tools, and textual
  compatibility paths existed as overlapping capabilities. After this slice,
  one negotiated protocol is projected from empirical evidence, but legacy
  compatibility transport remains and runtime wiring is incomplete.
- Reasoning/tool separation: the strict probe uses a bounded schema with no
  tool authority. The current qwen transport keeps `think=false` for strict
  serialization; no chain-of-thought is stored or treated as a Decision.
- Canonical registry: no new tool registry was introduced. Deterministic read
  concepts compile into existing DomainContracts, ActionSpecs, and bindings.
- Structured-state protection: Objective/Result completion is represented by
  `PostResultState`; protected packet state is no longer lost during provider
  message rebuilding. Compaction is not used as machine-state storage.
- Local inference lock: the process-global lock remains. Resource-scoped
  scheduling and preemption behavior are deferred to a later measured slice.
- Prefix cache: deterministic answer packets are smaller and consistently
  ordered, but no provider prefix-cache hit evidence is claimed.
- Outbound URL policy and Developer sandbox were not changed in this sprint.
