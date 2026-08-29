# Hades Suite Maturity — Productization Baseline

This ledger records observed owner-journey maturity on the post-merge
`hades-v1-productization` branch. A registered capability is not evidence that
the complete journey works.

| Suite | Existing canonical owner | Current state | Verified journeys | Immediate gap | V1 disposition |
|---|---|---|---|---|---|
| Homelab / Network / Infrastructure | `AssetInventory`, `HomelabOperations`, `NetworkState`, ACI contracts | IMPLEMENTED / PARTIAL | asset list/detail, network context/observations, host inspection, service status contract | service target/detail rendering and readback coverage need a focused product slice | Tier 1 active |
| Household / Kitchen | `inventory_service`, `read_household`, inventory mutation Actions | IMPLEMENTED / PARTIAL | overview, item/list/search/get contracts, mutation/readback suites, isolated authenticated browser readback, deterministic stock/expiry rendering | location projections and browser mutation journeys need expansion | Tier 1 active |
| Recipes / Meal Planning | existing `InventoryRecipe`, `RecipeService`, stock planner, and Cookbook code | IMPLEMENTED / PARTIAL | canonical list/search/get, pantry coverage, serving scale, expiring-inventory candidates, isolated Qwen/browser trajectory | meal-plan/shopping projections and broader fresh-install journeys | Tier 1 active |
| Memory / Personal Knowledge | Memory store, grounding, `read_memory` | IMPLEMENTED | deterministic owner reads, stale/current precedence, browser acceptance | broaden everyday recall/correction journeys | Tier 1 next |
| Work / Projects / Tasks | Work Engine, Runs, Actions, `read_work` | IMPLEMENTED | overview, attention, continuation and persistence tests | add cross-suite remediation/task journeys | Tier 1 next |
| OSINT / Public Research | public web evidence and OSINT contracts | PARTIAL | contract/security characterization | end-to-end case/evidence/report journey | Tier 2 |
| Security Assessment / Pentest | security engagement/scope/finding contracts | PARTIAL | authorization and policy tests | bounded assessment-to-finding journey | Tier 2 |
| Developer ACI | canonical ACI workspace/tool bindings | IMPLEMENTED / PARTIAL | bounded search/view/patch/test and confinement tests | production-like browser coding trajectory | Tier 2 |
| Finance | no promoted read-only canonical ledger yet | DESIGN / DEFERRED | design material only | define read-only owner and provider boundary | Tier 3 |
| TTRPG / DM | no promoted campaign canonical owner yet | DESIGN / DEFERRED | none | design only; no runtime expansion before Tier 1/2 | Tier 3 |

### Recipe ingestion checkpoint — f29eaff1

Recipe creation now has a bounded validated ingestion seam in the existing
Inventory Service. `RecipeDraft.from_payload` validates proposed structured
data; `prepare_import` is read-only and accepts owner text or schema.org
JSON-LD evidence; `commit_import` is the effectful action and requires recipe
persistence plus readback verification. Natural-language complete recipe
creation continues to use the canonical `add` Action with the same draft
validation. URL fetching, video transcript extraction, and image extraction
remain deferred until an existing safe evidence source is connected; no
recipe is persisted from a URL or media reference without a validated draft.

Focused recipe/ACI coverage at this checkpoint: 300 passed. Full supported
regression: 6907 passed, 5 skipped. The follow-up URL-preparation checkpoint
`82cb7ba6809d3f7cc06c1202cce3c46c61fb0cd3` added URL evidence acquisition
through the existing bounded `web_fetch` binding and preserves fail-closed
NEEDS_REVIEW behavior when a page lacks sufficient recipe structure. Its full
regression is `6908 passed, 5 skipped`; the exact candidate image is
`sha256:469f6d2cb017a142373b70b9dc1319016cd44a94cd6837a5ede34d07d6b8f770`.
Neither candidate replaced the owner's running container.

The Recipe UI checkpoint `71947f5f32ac4f2611622d07d4fce2826fbc1ed0` replaces
opaque item-ID-first entry with human-readable `name | quantity | unit`
rows, retains UUID references for advanced users, and records an optional
source URL. Focused UI/Recipe coverage is `239 passed`; exact candidate image
is `sha256:a92afcbfcf5397f3070640200f5b108ca5505338e0afda218cd060473970e3f1`.

The reviewed import UI/API checkpoint `aa9f230bd04384d736b66f533aff46b01b4d7ab1`
adds authenticated `prepare` and `commit` endpoints and an Import dialog with
explicit preview/confirmation. Its exact candidate image is
`sha256:a6f771890c53f0800e8be82b7692428f737c2a8b4e47440406badc4f6a7a156a`.

The HTML JSON-LD extraction checkpoint `e638686a4977f8c4fdc7de07be2f427456dc4108`
passes `6909 passed, 5 skipped` full regression. Its exact candidate image is
`sha256:05a5884029f7921a6feda1427f60d19e802d989b6b4718f3b6c9d65e7a29d8c9`.

The bounded video-source checkpoint `0d80484491fc0b1197ea61141c7784b1ea21b68c`
reuses the existing YouTube transcript owner for recipe `prepare_import`. A
transcript is still untrusted review evidence: validated RecipeDraft commit,
persistence, and readback remain required before any success claim. Missing or
insufficient transcripts return NEEDS_REVIEW; no quantities or instructions are
invented. Focused recipe/tool/UI coverage is `44 passed`; full regression is
`6910 passed, 5 skipped`. Exact candidate image:
`sha256:9e0325dc681f1a9105e26d08d80c60cffbc0bbb9ce5610b685e164ea287c1cb2`.

The image evidence checkpoint `899faa121b9c95d6acbcd71094a632a4b5a9788e`
adds owner-checked image upload handling to the same review endpoint. Existing
VL output is treated as untrusted description text; it is accepted only when
the conservative RecipeDraft validator finds complete recipe structure.
Otherwise preparation remains `NEEDS_REVIEW`. No direct image-to-state path was
introduced. The exact candidate image is
`sha256:7053c166341d7be8026a8bb9c11902479f2cb43002c1676dbb05abe2f90ba4c0`.

The executable checkpoint `d7c406abfcf7aa9df320bc59d8ee93aab27f33b1` also
accepts fenced JSON RecipeDraft proposals by stripping the presentation fence
before the existing validator runs; it does not make model text authoritative.
On an isolated fresh deployment of the exact candidate, the normal login route,
chat-driven long-text Recipe CREATE, two independent readbacks, reload, and a
third readback all passed: `3` streams, `3` terminal `[DONE]` events, zero
false-success, zero duplicate delivery, and zero abrupt EOF. The endpoint was
provisioned through the normal admin-only model-endpoint route and the browser
used the gated least-privilege acceptance principal. The disposable principal,
credentials, data, volumes, and containers were revoked and removed afterward.

The URL-backed chat CREATE checkpoint `12b56b8849ed2806c00793fb7073f164c849231d`
extends the same canonical mutation seam: a URL is carried only as untrusted
source metadata, fetched through the bounded source adapter, converted by the
validated `RecipeDraft` gate, and then persisted/read back by `InventoryService`.
A focused container run passed `240` tests, including proof that the URL path
cannot call the owner without a validated draft. The exact candidate image is
`sha256:f6696677c2a2a594919f5ef88c901c197125494dfac70887dcd6e46aea0329eb`,
with OCI and marker source `12b56b8849ed2806c00793fb7073f164c849231d`. The
owner runtime was not replaced. The full current-tree run reached `6903
passed, 6 skipped` with nine environment/setup failures (repository metadata
absent from the image mount and storage-preflight host paths unavailable), not
Recipe failures; these remain environment evidence rather than a product pass.

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
- Recipe delivery checkpoint `71611f15a382602dcfc6c7755f4c58a46e0ccf3c` is
  deployed exactly as candidate image `sha256:d72e277685dd6cabe02e7c9c4ccc81f872a484757fa16873722ea6a389a75d24`; isolated
  authenticated Qwen3:8B HTTP/SSE list, detail/reference, scale, and pantry
  coverage all returned one `DETERMINISTIC_RESULT`, one `[DONE]`, and zero
  model calls. The isolated Playwright lane passed the same four Recipe turns
  through normal login, session UI, reload persistence, and cleanup.
- Recipe composition checkpoint `5f05f1fad8476c70b868cce19873406432781add`
  adds the read-only `expiring_candidates` contract. It composes expiring
  canonical Inventory lots with deterministic per-recipe pantry coverage and
  explicit shortages through the existing `InventoryService`; focused coverage
  is `247 passed, 1 warning`. It has been built as candidate image
  `sha256:79304d95ed2f5831b005ef608c5ff8905cac8b10b5d42350b5966d8565cbc9f9`
  and deployed with marker/source `5f05f1fad8476c70b868cce19873406432781add`,
  healthy and at zero restarts. Meal-plan mutation remains deferred.
- Contract-parity checkpoint `42a7fcd1b75e0f7c7371e15cfc8621abecf17123`
  exposes `expiring_candidates` in the existing textual Recipe binding after
  full-regression parity tests found the native/textual projection mismatch.
  Focused coverage is `415 passed, 1 skipped`; corrected full regression is
  `6875 passed, 4 skipped`. The exact candidate image is
  `sha256:26fa612317e5e9cfdc3d99d818dd91d91e640b90903c16c3c9996fc534ad5987`,
  with matching OCI/source marker, healthy runtime, zero restarts, and Qwen3:8B
  reachable from the Hades container namespace.
- A disposable authenticated Recipe-composition replay was attempted after
  that checkpoint. Normal admin and non-admin acceptance logins succeeded, but
  the disposable model-endpoint probe returned connection refused before any
  Recipe state or chat turn was executed. This is recorded as
  `MODEL_ENDPOINT_UNAVAILABLE` evidence, not as Recipe product evidence; the
  disposable container and credentials were removed. The owner runtime was not
  used for synthetic Recipe seeding.
- A subsequent isolated candidate replay used a disposable Compose-network
  container after confirming the endpoint was reachable. Normal authenticated
  HTTP/SSE `expiring_candidates` returned a human-readable Chicken/Rice
  coverage answer with one `DETERMINISTIC_RESULT`, one `[DONE]`, zero model
  calls, and no abrupt EOF. The existing Playwright Recipe lane also passed
  four Recipe turns plus reload continuation (`streams: 5`). Disposable state
  and credentials were removed; this does not claim owner-data evidence.
- The full-regression process was attempted against `b8b24f82` but was
  externally terminated around 2% before pytest emitted a summary; this is
  recorded as unresolved environment/process evidence, not as a pass.
- Household readback coverage now proves, against one `InventoryService` owner,
  idempotent stock addition, canonical litre-to-millilitre normalization,
  quantity decrement to zero, and fail-closed over-consumption without state
  drift. The focused ACI/Household/Recipe regression is `307 passed, 1 warning`.
- The existing Playwright lane now has an explicitly isolated Household mode.
  It requires an externally supplied disposable acceptance deployment, seeds an
  `Acceptance Milk` item and stock through the authenticated owner-scoped
  Inventory APIs, verifies the canonical `2000.000000` millilitre readback,
  then exercises three kitchen reads plus reload continuation through normal
  login and `/api/chat_stream`. The exact candidate `42a7fcd1` run passed with
  `3 prompts / 4 streams`; this is acceptance-principal evidence, not owner
  data evidence. The disposable container and credentials were removed after
  the run.

- Executable checkpoint `e73f15876744cb9c8226ca3c15f42a7eab227e23` extends the
  existing Household renderer to present canonical `expiring_lots` and
  `low_stock` projections as human-readable secondary sections. It does not
  add a route, Action, store, or deterministic-read classifier. Focused
  coverage for the changed renderer and Tier 1 contracts is `37 passed, 1
  skipped`; the exact candidate image is
  `sha256:3d70fe0d76b2072d9af805c590f37e4f29540e5a66a534d84fa095cf80c03f21`,
  with matching OCI marker/running source, healthy runtime, and zero restarts.
  A fresh disposable deployment of that exact image passed the strengthened
  authenticated Household Playwright lane (`3 prompts / 4 streams`), including
  canonical stock readback, one deterministic finalization per turn, reload
  continuation, and cleanup. This is acceptance-principal evidence, not owner
  data evidence.

- UI consolidation checkpoint `4969925a3c88ae4354e82119840900564a6e5d5e`
  establishes the first shared visual migration for Household/Inventory:
  the existing window/titlebar/body, tabs, buttons, panels, grouped intake
  fields, progressive technical-details disclosure, focus treatment, and
  reduced-motion rules now use shared Hades primitives while retaining legacy
  behavior selectors. Navigation hydration now replaces legacy inline glyphs
  instead of appending a second SVG, and the redundant `securityResearch`
  Research-workspace destination was removed. Static and browser layout checks
  cover one icon per visible sidebar entry, viewport containment,
  constrained-width overflow, and existing window behavior. Focused UI
  coverage is `16 passed`, Node layout coverage is `3 passed`, frontend
  verification passes, and the existing Playwright realistic and window lanes
  pass against exact candidate image
  `sha256:2d6c63a509408c9c4144d9acd69e8021976e1bf9b4bf9c60dc0f3964baeec010`.
  The image embeds/runs source `4969925a`; health is healthy with zero
  restarts. Remaining UI migration is incremental across Recipes and later
  suites; no broad redesign or frontend framework was introduced.

- Recipe UI migration checkpoint `cc7f215435e0c814caf364adf74d71b5005da877`
  carries that shared system through the Recipe list, readiness badges,
  detail/create dialogs, grouped serving fields, and empty state. Recipe
  semantics and persistence remain owned by the existing Inventory Service and
  recipe APIs; no store or router was added. The authenticated Playwright
  realistic lane now opens the real Inventory surface, switches to Recipes,
  waits for the canonical loaded state, and verifies a shared empty/list state
  plus viewport containment. The exact executable candidate is
  `sha256:b9df84071d1ec10000630e065cef9aebcaf3e6736b869c70afd3bbe08682c26c`,
  source `cc7f2154`, healthy with zero restarts; realistic and window browser
  lanes pass. Follow-on Recipe work remains functional journey coverage and
  broader migration, not a new visual architecture.

- Household mutation checkpoint `9cdc1a3cbff28709c52ae4e639cb47505ceaf96a`
  closes the chat-driven stock-consumption identity gap through the existing
  Inventory Service. Direct canonical turns derive a replay key from the
  dispatcher-owned run identity and request digest when no durable WorkAction
  projection exists; WorkAction-backed turns carry their action identity into
  the same binding. Focused coverage is `256 passed, 1 warning`, and the full
  regression is `6902 passed, 5 skipped`. The exact candidate image is
  `sha256:98b9b2edbb3774a24e9ee77474cb8cf9fd748b2d09eb706cf85692a64d2c0b88`
  with matching OCI/source marker, healthy disposable runtime, zero restarts,
  and Qwen3:8B reachable from the Hades container namespace. On fresh
  isolated acceptance deployments, the authenticated Playwright household
  journey passed 4 turns, 2 chat mutations, 2 independent readbacks, and 4
  terminal `[DONE]` events; the Recipe create/readback/reload journey passed
  3 turns, 1 chat mutation, 2 readbacks, and 3 terminal `[DONE]` events. Both
  had zero false-success, duplicate-delivery, or abrupt-EOF failures. These
  are acceptance-principal results, not owner-data evidence; the owner runtime
  was not changed.

## Product quality rule

Each suite must progress through canonical state, bounded Action/Result,
verification/readback where effectful, deterministic rendering where possible,
Qwen3:8B dogfood, and browser acceptance where user-visible. Capability names
alone do not advance a suite to IMPLEMENTED.
## Recipe P0 ingestion checkpoint — `c1de67a1`

- `RecipeDraft` is now an explicit untrusted proposal schema owned by the
  existing intent/Inventory path.
- Recipe CREATE accepts the reproduced owner-style long paste (`as "name":`,
  multiline ingredients, instructions, optional servings/source URL) while
  remaining fail-closed for incomplete or malformed drafts.
- `manage_recipes.add` remains the sole canonical persistence Action; the
  existing executor performs persistence and readback before verified success.
- The browser acceptance runner now treats multiline/list formatting
  structurally and removes superseded model answer bubbles when a canonical
  `response_replace` arrives, preserving one visible final AnswerSource.
- Focused contract/lifecycle/recipe tests: `297 passed`.
- Exact disposable candidate `odysseus:candidate-c1de67a1`, source-matched and
  healthy: long-paste chat mutation/readback/reload browser journey `PASS`
  (`3/3` streams, `3/3` DONE, `0` false-success, `0` duplicate delivery).
- URL/video/image import preparation/commit remains deferred; no unverified
  importer was added. Meal-plan mutation remains gated on that future import
  slice.
