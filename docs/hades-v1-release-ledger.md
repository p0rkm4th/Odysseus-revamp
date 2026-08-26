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
| Infrastructure failure normalization | green | executor/projection focused gates preserve unavailable/invalid status |
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
- Source head: `695183d9` (canary harness after deployed runtime source
  `074d240f`).
- Running image: `odysseus:candidate-074d240f`, source-matched and healthy.
- Full regression: `6424 passed, 3 skipped` on behavior-identical parent
  `8038e227`.
- Current telemetry/reference gate: `97 passed`.
- Storage: 74% used / 24 GiB free; large replacement builds remain closed by
  the 30 GiB preflight guard. Current, rollback, and live-auth images are
  retained; no owner data, databases, volumes, backups, or model blobs were
  removed.
- Live canary accepts `--model` and `--cookie-file`; cookie files support the
  existing Netscape export format without printing credentials.
