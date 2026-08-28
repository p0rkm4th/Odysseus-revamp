# Hades ACI Sol root-cause checkpoint

## 1. Root causes found

| Symptom | Exact cause and location | Architectural significance |
|---|---|---|
| `Tell me about me` failed identically on Qwen and Luna | `memory_grounding.is_explicit_memory_query` recognized neighboring wording, while `intent_contracts.compile_intent` classified both forms as `UNKNOWN`; only the known form received a compatibility rescue | Semantic equivalence diverged before model reasoning |
| A successful canonical read could enter another Decision | `agent_loop.stream_agent_loop` made answer-only completion depend on `_skip_model_round`, an execution-branch local rather than Result semantics | Loop availability accidentally controlled completion |
| ACI mode instructions disappeared | `_strip_agent_injected_messages` removed the protected `hades_aci_packet` while rebuilding provider messages | Provider routing erased machine state |
| Qwen mentioned `manage_memory` | answer synthesis still received generic tool-oriented prompt material even when native schemas were suppressed | Human answer phase was coupled to execution plumbing |
| Historical Memory appeared current | projection sorted stale records first and did not reconcile volatile remembered branch/runtime facts with current SelfState | `stale=false` meant not manually stale, not epistemically current |
| Most measured latency was unexplained | metrics did not count provider requests or separate preparation, model wait, and structured-output buffering | Extra inference and Python overhead could not be distinguished |

## 2. Fixes implemented

- `c0ea2955`: safe cached strict Decision JSON runtime probe and diagnostic
  protocol negotiation. Focused evidence: 31 tests and a live no-tools qwen3:8b
  probe. Authority remains downstream and unchanged.
- `ff14c3a0`: shared compositional deterministic-read resolver; metamorphic
  corpus; explicit `PostResultState`; protected packet preservation; minimal
  answer-only context; current-over-historical Memory reconciliation; model-call
  and latency instrumentation. Evidence: 67 checkpoint focused tests and full
  regression `6366 passed, 3 skipped`. No security boundary was broadened.

## 3. Model calls eliminated

- Newly recognized unambiguous owner-Memory paraphrases no longer require a
  bounded Action-selection call. Final answer synthesis remains.
- Exact successful resolved canonical reads no longer make a second Action
  decision merely because another loop iteration exists.
- Generic answer-only requests such as arithmetic still enter bounded decision;
  this is a measured candidate for a general semantic ANSWER gate, not a
  phrase-specific fix.

## 4. Paraphrase invariance

The frozen metamorphic corpus has 9 Memory, 4 Work, 4 Assets, and 4 current
Network utterances. All 21 converge on existing canonical harmless read
contracts with approval `none`. Unambiguous owner-Memory variants require the
essential trajectory:

`Intent -> owner Memory read -> CanonicalResult -> ResultProjection -> ANSWER -> complete`

with zero bounded Action-selection calls and no post-Result Action decision.
This is source/focused/full-regression evidence; owner-live rerun is pending.

## 5. Post-Result state machine

`PostResultState` now distinguishes answer-terminal exact reads from bounded
reasoning, context, clarification, approval, deterministic continuation, and
blocked states. Arbitrary successful Actions still require completion
evaluation and do not become complete automatically. Remaining complex
multi-step procedures still use legacy loop control and merit later migration
to the same explicit disposition model.

## 6. Memory/current-state reconciliation

Current source branch/runtime observations supersede contradictory volatile
Memory during projection. The remembered records remain canonical historical
evidence and are labeled historical/contradicted; they are not mass-mutated.
Broader cross-domain temporal reconciliation remains future work.

## 7. Answer-phase tool leakage

ACI answer-only synthesis now receives Objective, compact ResultProjection,
relevant state, and response constraints—not provider tool schemas, ActionSpec
implementation names, or ToolBinding names. A final semantic scrub covers known
legacy names as defense in depth. Non-ACI legacy answer paths still carry their
existing prompt/tool material.

## 8. Harness latency attribution

One current local diagnostic sample measured:

- raw Qwen completion: `0.238s`, 31 prompt tokens, 3 output tokens
- Hades completion: `8.723s`, 1406 prompt tokens, 22 output tokens
- context preparation: `1.432s`
- tool-selection/retrieval fallback within preparation: `1.288s`
- provider/model wait: `4.524s`
- structured generation, validation, and buffered visibility: approximately
  `2.77s`
- model calls: 1; tool calls: 0

The dominant contributors are the 1375-token prompt delta, local embedding/tool
selection fallback, and buffered strict Decision generation—not an extra model
call in this sample. Raw and Hades requests were not equivalent deliverables,
so this is diagnostic attribution rather than a final harness-overhead claim.

## 9. Agent-loop architectural debt

Only three extraction seams are currently justified:

1. A compact ACI turn disposition replacing incompatible answer,
   clarification, packet, and fast-path booleans.
2. DecisionGateway extraction for packet parsing, one repair, and validated
   deterministic fallback.
3. ResultProjection plus Completion transition extraction after remaining
   golden reads adopt `PostResultState`.

No AgentLoopV2 or cosmetic file split is warranted.

## 10. Benchmark validity

The authoritative frozen H0 remains `0.20` case success and `0.4333` weighted.
The corrected 15-case synthetic ACI result is `1.0/1.0`, but it does not yet
prove owner-language robustness. The 21-case separate metamorphic corpus
reduces known-wording leakage and passes source/focused/full-regression gates.
Its live Qwen and owner-browser result is not yet measured, so the final
synthetic score is not promoted to E6.

## 11. Subtraction ledger

LEGACY_PATHS_REMOVED: answer-only ACI no longer uses the generic tool-oriented prompt path.

LEGACY_PATHS_DEPRECATED: phrase-sensitive Memory prefetch classification is no longer authoritative.

DUPLICATE_DECISIONS_ELIMINATED: post-Result Action decision for exact successful canonical reads.

MODEL_CALLS_REMOVED: bounded Action selection for newly recognized unambiguous deterministic-read paraphrases; duplicate post-read decision.

LEGACY_REGISTRIES_NO_LONGER_AUTHORITATIVE: none newly removed; ActionSpec remains canonical.

PROVIDER_HACKS_MOVED_TO_ADAPTERS: none in this slice.

TEXT_TOOL_PROTOCOLS_REMOVED: none; compatibility removal awaits negotiated runtime wiring.

ANSWER_PHASE_SCHEMA_TOKENS_REMOVED: all native tool schemas and generic tool prompt material from ACI answer-only synthesis; exact token delta needs an equivalent warm benchmark.

## 12. Luna handoff

1. Run an owner-free live qwen3:8b metamorphic canary, then deploy exact
   implementation `ff14c3a0` without rebuilding for later docs commits.
2. Owner-retest Memory paraphrases on Qwen and Luna, including `Tell me about
   me`, and retain E6 pass/fail evidence.
3. Wire fresh negotiated runtime protocol evidence into DecisionGateway behind
   the existing rollout mode; keep policy and Action validation downstream.
4. Add a general non-Action `ANSWER` complexity gate so trivial answer requests
   avoid Action-selection packets without introducing phrase routing.
5. Cache or bypass tool-index embedding when a deterministic contract already
   resolved the unique safe read.
6. Re-run cold/warm raw-versus-Hades timing with equivalent deliverables and
   separate provider TTFT from buffered Decision visibility.
7. Replace the remaining incompatible ACI turn booleans with one small typed
   disposition; extract DecisionGateway only if the change deletes branching.
8. Preserve H0, rerun the frozen 15-case ACI suite after deployment, and do not
   repeat full pytest unless subsequent source edits warrant it.
