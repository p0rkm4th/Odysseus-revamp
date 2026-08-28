# Hades Suite Maturity — Productization Baseline

This ledger records observed owner-journey maturity on the post-merge
`hades-v1-productization` branch. A registered capability is not evidence that
the complete journey works.

| Suite | Existing canonical owner | Current state | Verified journeys | Immediate gap | V1 disposition |
|---|---|---|---|---|---|
| Homelab / Network / Infrastructure | `AssetInventory`, `HomelabOperations`, `NetworkState`, ACI contracts | IMPLEMENTED / PARTIAL | asset list/detail, network context/observations, host inspection, service status contract | service target/detail rendering and readback coverage need a focused product slice | Tier 1 active |
| Household / Kitchen | `inventory_service`, `read_household`, inventory mutation Actions | IMPLEMENTED / PARTIAL | overview, item/list/search/get contracts, mutation/readback suites | natural stock/expiry/location projections and browser journeys need expansion | Tier 1 active |
| Recipes / Meal Planning | existing `InventoryRecipe`/Cookbook code and recipe tests | PARTIAL / OWNER AUDIT | cookbook dependency/recipe characterization only | identify the canonical recipe read/coverage owner before adding routing | Tier 1 next |
| Memory / Personal Knowledge | Memory store, grounding, `read_memory` | IMPLEMENTED | deterministic owner reads, stale/current precedence, browser acceptance | broaden everyday recall/correction journeys | Tier 1 next |
| Work / Projects / Tasks | Work Engine, Runs, Actions, `read_work` | IMPLEMENTED | overview, attention, continuation and persistence tests | add cross-suite remediation/task journeys | Tier 1 next |
| OSINT / Public Research | public web evidence and OSINT contracts | PARTIAL | contract/security characterization | end-to-end case/evidence/report journey | Tier 2 |
| Security Assessment / Pentest | security engagement/scope/finding contracts | PARTIAL | authorization and policy tests | bounded assessment-to-finding journey | Tier 2 |
| Developer ACI | canonical ACI workspace/tool bindings | IMPLEMENTED / PARTIAL | bounded search/view/patch/test and confinement tests | production-like browser coding trajectory | Tier 2 |
| Finance | no promoted read-only canonical ledger yet | DESIGN / DEFERRED | design material only | define read-only owner and provider boundary | Tier 3 |
| TTRPG / DM | no promoted campaign canonical owner yet | DESIGN / DEFERRED | none | design only; no runtime expansion before Tier 1/2 | Tier 3 |

## Baseline evidence

- Post-merge `main`: `364380ed3f46c1d14d3229e5b7530698cfa22e65`.
- Productization branch starts from that merged tree.
- Deployed executable remains `05c32fb520ec91556ee3cef75697ccdab17e86ab`;
  its image is healthy with zero restarts. The branch is not claimed deployed
  until an executable checkpoint is pushed and rebuilt.
- Initial Tier 1 semantic audit found unsupported/unknown routing for service
  variants, household stock/expiry language, and recipe planning language.
- First productization slice resolves the service and household variants via
  existing contracts; recipe planning remains deferred pending owner audit.
- Productization checkpoint `818a0a218900c4f173e2773e1469050057ea8b61` was
  pushed and deployed exactly; focused routing/household coverage is
  `342 passed, 1 skipped`, runtime health is healthy, and Qwen3:8B is reachable
  from the Hades container namespace.

## Product quality rule

Each suite must progress through canonical state, bounded Action/Result,
verification/readback where effectful, deterministic rendering where possible,
Qwen3:8B dogfood, and browser acceptance where user-visible. Capability names
alone do not advance a suite to IMPLEMENTED.
