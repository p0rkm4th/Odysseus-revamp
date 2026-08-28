# Hades Suite Maturity — Productization Baseline

This ledger records observed owner-journey maturity on the post-merge
`hades-v1-productization` branch. A registered capability is not evidence that
the complete journey works.

| Suite | Existing canonical owner | Current state | Verified journeys | Immediate gap | V1 disposition |
|---|---|---|---|---|---|
| Homelab / Network / Infrastructure | `AssetInventory`, `HomelabOperations`, `NetworkState`, ACI contracts | IMPLEMENTED / PARTIAL | asset list/detail, network context/observations, host inspection, service status contract | service target/detail rendering and readback coverage need a focused product slice | Tier 1 active |
| Household / Kitchen | `inventory_service`, `read_household`, inventory mutation Actions | IMPLEMENTED / PARTIAL | overview, item/list/search/get contracts, mutation/readback suites | natural stock/expiry/location projections and browser journeys need expansion | Tier 1 active |
| Recipes / Meal Planning | existing `InventoryRecipe`, `RecipeService`, stock planner, and Cookbook code | IMPLEMENTED / PARTIAL | canonical recipe list/search/get and pantry-coverage binding plus inventory recipe tests | add seeded end-to-end recipe journeys and meal-plan/shopping projections | Tier 1 active |
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
- Deployed executable is `b8b24f8233007ca89fee8da0e03de6e45856f1b5`; its
  exact candidate image is `sha256:b6b6645403610ebf1e946a41f2852c0b32e9f45044b2299037c9675b0578eedb`,
  with OCI/running source matching and healthy runtime with zero restarts.
- Initial Tier 1 semantic audit found unsupported/unknown routing for service
  variants, household stock/expiry language, and recipe planning language.
- First productization slice resolves the service and household variants via
  existing contracts.
- Recipe read projection now uses the existing `InventoryService` owner;
  persisted list/search/get, pantry coverage, and deterministic serving-scale
  arithmetic are covered by service integration tests. Recipe mutations/cooking
  and meal-plan/shopping composition remain deferred until Qwen3:8B and browser
  read/composition journeys are green.
- Deterministic-read boundary: recipe predicates are only high-confidence
  owner/read/coverage/scale fast paths. Conceptual questions such as `what is a
  recipe` remain UNKNOWN/ANSWER and must reach bounded semantic resolution;
  this layer is not a general domain classifier.
- Productization checkpoint `818a0a218900c4f173e2773e1469050057ea8b61` was
  pushed and deployed exactly; focused routing/household coverage is
  `342 passed, 1 skipped`, runtime health is healthy, and Qwen3:8B is reachable
  from the Hades container namespace.
- Recipe checkpoint `62de705f71814e0728e66bf2abe73077ba823bbb` is pushed and
  deployed exactly; the full supported regression is `6866 passed, 4 skipped`,
  the authenticated browser lane passes its 7-prompt/reload trajectory, and
  Recipe list/search/get, pantry coverage, scaling arithmetic, and owner
  isolation are covered by persisted InventoryService integration tests.
- Recipe reference-continuity checkpoint `b8b24f8233007ca89fee8da0e03de6e45856f1b5`
  extends the canonical bridge with persisted Recipe refs and session-context
  compilation; focused coverage is `414 passed, 1 skipped`. The existing
  authenticated browser smoke remains green (`7 prompts / 8 streams`), with
  the network turn producing one deterministic replacement and one terminal
  `[DONE]`. Recipe-specific seeded browser/Qwen evidence remains pending: the
  current browser acceptance fixture has no disposable Recipe seed and the
  public API has no recipe-delete operation. Do not seed Recipe rows into the
  owner's database; run those journeys only against an isolated acceptance
  deployment.
- The full-regression process was attempted against `b8b24f82` but was
  externally terminated around 2% before pytest emitted a summary; this is
  recorded as unresolved environment/process evidence, not as a pass.

## Product quality rule

Each suite must progress through canonical state, bounded Action/Result,
verification/readback where effectful, deterministic rendering where possible,
Qwen3:8B dogfood, and browser acceptance where user-visible. Capability names
alone do not advance a suite to IMPLEMENTED.
