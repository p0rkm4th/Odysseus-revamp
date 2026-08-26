# Hades V1 release ledger

Status: active engineering release ledger; not a release declaration.

## V1 blockers

None currently evidenced in the deployed core control plane. Security, owner
scope, exact approval, durable continuation, canonical reads, fallback
authority, and rollback invariants remain covered by the current focused/full
gates.

## V1 RC fixes and evidence

| Item | Status | Evidence |
|---|---|---|
| Deterministic Memory/Work/Assets/Network/Service reads | green | source tests; deployed Qwen E5 matrices |
| Asset ordinal continuation | green | source `8038e227` behavior; canonical `PHYSICAL-001` live trace; telemetry in `074d240f` |
| Durable Continue terminal-state handling | green | `177` focused tests; live Continue resumed with zero tool calls |
| General MODEL_FALLBACK | green | focused security/fallback gates; live ordinary-question cases |
| Conceptual explanation routing | focused green, deployment pending | `17cbbb97`; RAID/backup explanations no longer enter `storage_ops`; direct fallback diagnostics are initialized safely |
| Infrastructure failure normalization | green | executor/projection focused gates preserve unavailable/invalid status; host-operator reads now expose canonical success/failure status |
| Exact approvals and policy boundaries | green | security/control-plane suites; live unauthorized-scan case |
| Deployment provenance and rollback | green | runtime source match `074d240f`; rollback `odysseus:rollback-b471e104-prev` |
| Automated live Qwen canary | E5 partial/current | prior deployed matrix `53/53`; fresh cookie required to re-run `074d240f` telemetry assertions |
| Developer ACI read path | source-complete, E5 pending | focused developer/sandbox gates; production workspace mount intentionally absent |
| Provider switching/recovery | focused green, live E5 pending | `137` focused tests; only local Qwen endpoint live-available |

## V1.1+ deferred

- resource-scoped scheduler replacing the safe single-GPU global lock
- full negotiated provider protocol wiring and prefix-cache evidence
- broad agent-loop decomposition
- stronger developer sandbox resource/egress isolation
- large semantic corpus expansion beyond the current frozen/held-out suites
- additional provider live matrix
- cosmetic UI/accessibility and non-core integrations

## Owner E6 pending

Owner GUI use remains required for E6. Suggested spot checks are the natural
Memory, Work, asset-reference, current-network, ordinary fallback, ambiguous
restart, and durable Continue prompts. Automated E5 does not promote these to
E6.

## Current release state

- Branch: `hades-aci-v1`, synchronized with `origin`.
- Source head: `0e5360ac` (semantic read-family corrections, safe derived
  runtime facts for MODEL_FALLBACK); deployed runtime remains `c0a281f5`
  until the next storage-approved candidate build.
- Running image: `odysseus:candidate-c0a281f5`, source-matched and healthy.
- Last full regression before the latest fallback/runtime source slice:
  `6492 passed, 3 skipped, 186 warnings` in 123 seconds. Later focused gates:
  `210 passed` for fallback/control-plane behavior and `198 passed` for
  security/authority coverage.
- Current telemetry/reference gate: `97 passed`.
- Storage: 74% used / 23 GiB free; large replacement builds remain closed by
  the 30 GiB preflight guard. Current, rollback, and live-auth images are
  retained; no owner data, databases, volumes, backups, or model blobs were
  removed.
- Live canary accepts `--model`, `--endpoint-id`, and `--cookie-file`; cookie
  files support the existing Netscape export format without printing
  credentials.
- Real bridge overhead probe (Qwen3:8b, 172.18.0.1:11434, 64-token cap):
  cold raw `0.275s` vs Hades `12.850s`; warm raw `3.352s` vs Hades `12.600s`.
  Hades preparation was `0.235s`/`0.208s`, with one model call and zero tool
  calls. This is diagnostic only: raw stopped at 3 output tokens while Hades
  consumed 64, so it is not an equivalent-deliverable quality comparison.
- Tight-cap diagnostic rerun at 3 tokens measured raw `3.486s` vs Hades
  `5.955s` (`2.468s` total delta; `0.222s` preparation; `2.244s` extra
  provider span; one model call; zero tools). Both providers reported 3 output
  tokens, but Hades streamed 144 characters, so usage/stream accounting still
  needs correction before declaring an equivalent benchmark.
- The overhead harness now emits `output_accounting.consistent=false` for this
  mismatch (`hades_text_token_ratio implausible`) instead of allowing the run
  to be mistaken for an equivalent benchmark. Latest real-bridge run: raw
  `3.769s`, Hades `5.860s`, delta `2.091s`, prep `0.211s`, one model call,
  zero tools.
- The latest run classifies the discrepancy as
  `hades_framework_generated_fallback` (not provider token accounting): Qwen
  reported 3 provider tokens, while Hades emitted 99 characters of its
  domain-neutral fallback. Equivalent-deliverable latency remains unclaimed.
- Deployed fallback hardening at `c0a281f5`: empty model/synthesis responses no
  longer emit a search-specific false claim; the real-Qwen probe returned a
  domain-neutral fallback, one model call, zero tools, and
  `aci_empty_answer_fallback=true`.
- A matched normal-question probe after `17cbbb97` still produced a framework
  fallback from Qwen despite one authority-free model call and zero tools;
  this remains an attribution/ provider-output issue, not equivalent benchmark
  evidence. The harness now accepts `--prompt` so future matched probes do not
  depend on the old arithmetic wording.
- Direct bridge evidence then isolated the provider cause: this Ollama runtime
  ignored `think:false` on ordinary Qwen chat, while honoring
  `reasoning_effort:none`. After `16d42ccc`, the same probe produced normal
  content with consistent accounting: raw `4.695s` / Hades `7.319s`, total
  delta `2.624s`, preparation `0.245s`, extra provider span `2.375s`, one
  model call, and zero tools. This is source/live-bridge evidence; deployment
  E4/E5 for this newest adapter commit is still pending storage-approved build
  and authenticated live canary.
