# Hades Suite Maturity — Productization Baseline

This ledger records observed owner-journey maturity on the post-merge
`hades-v1-productization` branch. A registered capability is not evidence that
the complete journey works.

| Suite | Existing canonical owner | Current state | Verified journeys | Immediate gap | V1 disposition |
|---|---|---|---|---|---|
| Homelab / Network / Infrastructure | `AssetInventory`, `HomelabOperations`, `NetworkState`, ACI contracts | IMPLEMENTED / PARTIAL | asset list/detail, network context/observations, host inspection, aggregate and target-qualified service status rendering | service target execution/readback and broader browser journeys | Tier 1 active |
| Household / Kitchen | `inventory_service`, `read_household`, inventory mutation Actions | IMPLEMENTED / PARTIAL | overview, owner-scoped location/item/list/search/get contracts, mutation/readback suites, isolated authenticated browser readback, deterministic stock/expiry rendering | chat-driven mutation browser journey and broader fresh-install journeys | Tier 1 active |
| Recipes / Meal Planning | existing `InventoryRecipe`, `RecipeService`, stock planner, and Cookbook code | IMPLEMENTED / PARTIAL | canonical list/search/get, pantry coverage, serving scale, expiring-inventory candidates, explicit Result contracts, isolated Qwen/browser trajectory | shopping-list/meal-plan projections and broader fresh-install journeys | Tier 1 active |
| Memory / Personal Knowledge | Memory store, grounding, `read_memory` | IMPLEMENTED | deterministic owner reads, stale/current precedence, browser acceptance | broaden everyday recall/correction journeys | Tier 1 next |
| Work / Projects / Tasks | Work Engine, Runs, Actions, `read_work` | IMPLEMENTED | overview, attention, continuation and persistence tests | add cross-suite remediation/task journeys | Tier 1 next |
| OSINT / Public Research | public web evidence and OSINT contracts | PARTIAL | contract/security characterization | end-to-end case/evidence/report journey | Tier 2 |
| Security Assessment / Pentest | security engagement/scope/finding contracts | PARTIAL | authorization and policy tests | bounded assessment-to-finding journey | Tier 2 |
| Developer ACI | canonical ACI workspace/tool bindings | IMPLEMENTED / PARTIAL | bounded search/view/patch/test and confinement tests | production-like browser coding trajectory | Tier 2 |
| Finance | no promoted read-only canonical ledger yet | DESIGN / DEFERRED | design material only | define read-only owner and provider boundary | Tier 3 |
| TTRPG / DM | no promoted campaign canonical owner yet | DESIGN / DEFERRED | none | design only; no runtime expansion before Tier 1/2 | Tier 3 |

### Household location projection checkpoint — `17b946a2`

The existing `InventoryService.household_overview` projection now resolves
owner-scoped `InventoryLocation` records into bounded `location_name` fields
and deterministic per-location item/stock totals. It does not add location
routing or a second store; missing and cross-owner locations remain absent.
The focused Household/Recipe/ACI container run passed `101` tests. The exact
candidate was built from pushed source `17b946a24938f71051ba2ab57a25b0cf7828f0d6`
and verified in a disposable runtime: OCI marker and running source matched,
health was healthy, restarts were `0`, and Qwen3:8B was reachable from the
container namespace with digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.

The corrected source-mounted full regression used isolated writable mounts for
`data/`, `logs/`, `tmp_pytest_probe/`, and pytest cache, plus the existing
Docker storage fixture. It completed `6934 passed, 6 skipped, 149 warnings` in
`363.42s`. The earlier `6921 passed` result with `10` failures and `2` setup
errors is retained as invalid read-only-mount evidence, not a product result.
This full run validates the current source tree; the exact candidate image was
also independently verified healthy, but the owner deployment was not
replaced.

The follow-on UI checkpoint `f4227c9a` presents the same canonical location
projection in the Household workspace: named storage locations show bounded
item/stock totals, and item rows show their resolved location when available.
`node --check static/js/intelligence.js` and the focused UI/Household tests
passed (`9` tests). The exact candidate image
`sha256:4c32c5bfe61621dd921c7e66fec17560c760bee1e275f991771f6d09ea1929de`
was verified with OCI/running source `f4227c9a5262a6944b0b1e295d47415f5edf9fa7`,
healthy status, zero restarts, and in-container Qwen3:8B reachability. The
owner deployment was not replaced.

The follow-up executable checkpoint `9e2d62dc` keeps the location projection
consistent in item detail: `InventoryService.get_item` now adds an
owner-scoped `location_name`, so the Household detail window cannot discard a
location present in the overview. Focused Household/Recipe/binding coverage
passed `59` tests. Candidate image
`sha256:358935cb9a15790abf3f2695c120bd9f433ef8d143be7f0c6fd20cbce429b282`
was verified healthy with zero restarts and OCI/running source matching
`9e2d62dceea7dcffa74a76b1c22579067c97c4f6`; the owner deployment remains
unchanged.

### Household detail presentation checkpoint — `015c8e9a`

Household item detail now renders canonical stock lots as readable rows with
quantity, unit, expiry, and owner-scoped location instead of exposing raw JSON
as the primary surface. `InventoryService.list_lots` supplies the bounded
location projection used by the existing detail endpoint. JS syntax and the
focused Household/UI/binding suite passed `37` tests. Exact candidate image
`sha256:abbc965417f07e116430bfe551fd919551f26d53381a6f779b354cfab21cda3b`
was verified healthy with zero restarts and source marker/running source
`015c8e9a9d73f47999c5a0753702629f93cad55b`; Qwen3:8B remained reachable from
the container namespace. The owner deployment was not replaced.

### Recipe pantry-coverage contract checkpoint — `45f54ef6`

The existing `InventoryService.manage_recipes(can_make)` read now identifies
its result as `recipe_pantry_coverage` with operation `can_make`, explicit
`SUCCESS` status, canonical store, and `AVAILABLE` or `MISSING_INGREDIENTS`
availability. Existing deductions/shortages remain unchanged, so the
deterministic renderer continues to own the answer and no recipe-list shape
is overloaded. Focused Recipe/ACI/binding coverage passed `124` tests. Exact
candidate image
`sha256:ed14a1b49fbf76601736ccc79ccc977bbb96b40e9c01609f88683093ba88f574`
was verified healthy with zero restarts, OCI/running source
`45f54ef6babb8b367ef39988e4d3a032ca03c764`, and Qwen3:8B reachability from
the container namespace. The owner deployment was not replaced.

### Recipe scale result contract checkpoint — 26dac273

The existing deterministic `scale` read now returns explicit `SUCCESS`,
`recipe_scaled_quantities`, `scale`, and `inventory_service` metadata while
preserving the existing canonical recipe identity, requested serving count,
and quantity arithmetic. The result remains read-only and is rendered by the
existing canonical Recipe answer owner. Supported-container focused coverage
passed `124` tests. Exact candidate image
`sha256:720773cb97d2cc1c0e274b52eaf720809601c5a3efde696db66714ee2c190cb9` was
verified healthy with zero restarts, OCI marker/running source
`26dac273983ad51c571fba9a1df33e58e14aeeff`, and Qwen3:8B reachability from
the container namespace. The owner deployment was not replaced.

### Recipe collection/detail result contracts checkpoint — 9584fe4c

The existing Recipe `list`, `search`, and `get` reads now return explicit
`SUCCESS` status, operation-specific result types, canonical-store metadata,
and bounded canonical payloads. The change does not alter owner scoping,
recipe ordering, search semantics, or deterministic answer rendering; it
makes the read contract observable at the Result boundary alongside pantry
coverage and scale. Supported-container focused coverage passed `125` tests.
The exact candidate image
`sha256:83390cb6b6eab4fa2a7c7692751531ab77637af747889eab59cc32d00dd02d22`
was verified healthy with zero restarts, OCI marker/running source
`9584fe4cf86b96ca0f65f63b4b563809a4d063c2`, and Qwen3:8B reachability from
the container namespace. The owner deployment was not replaced.

### Recipe expiring-candidate contract checkpoint — bc6781f7

The existing expiring-inventory → recipe coverage projection now identifies
itself as a successful `recipe_expiring_candidates` operation owned by the
Inventory Service. Existing deterministic expiry horizon, freshness,
candidate, shortage, and non-mutation semantics are unchanged; the metadata
makes the cross-suite read boundary explicit for downstream rendering and
acceptance. Supported-container focused coverage passed `125` tests. Exact
candidate image
`sha256:5d0a4bc45a135edff719a9771c21acaa7f7d963c57db64d401915013b0d4a80d`
was verified healthy with zero restarts, OCI marker/running source
`bc6781f73947117c908dbed43bc07ce343adc5ce`, and Qwen3:8B reachability from
the container namespace. The owner deployment was not replaced.

### Work read projection contract checkpoint — 8976228f

The existing `read_work` adapter now marks every canonical Work projection
with its operation, result type, and `work_engine` store while retaining the
existing status inference, including `SUCCESS_EMPTY` for empty collections.
This is metadata at the existing adapter boundary; it does not add a planner,
workflow engine, or alternate Work store. Focused ACI/binding/intent coverage
passed `241` tests. Exact candidate image
`sha256:e92b27ffe5130f510666327881ca128d473183c4c3567065eebcf91ba1d03b40`
was verified healthy with zero restarts, OCI marker/running source
`8976228f1f5129db2cc9f2496dbb3d9b39bab7a0`, and Qwen3:8B reachability from
the container namespace. The owner deployment was not replaced.

### Recipe URL import checkpoint — e6734a9c

The public recipe fetch path now requests a bounded, opt-in schema.org Recipe
projection from the existing SSRF-safe web fetcher. Ordinary web-fetch output
is unchanged; only recipe import receives up to four recipe objects and the
validated `RecipeDraft` gate remains the sole path to `InventoryService`.
Unicode and mixed quantities are parsed deterministically without inventing
amounts. Focused extraction/import coverage is `33 passed` in the supported
container test environment.

The exact live Sunday Supper URL remains `NEEDS_REVIEW`, not a mutation success:
its structured data includes an unquantified `salt and pepper` ingredient, so
the existing positive-quantity canonical schema correctly refuses commit.
The live browser trace showed one approval card, one failed canonical Action,
one bounded error AnswerSource, one `[DONE]`, and no abrupt EOF; no recipe was
persisted. This is a real remaining Recipe import product gap, not a false
success.

The complete natural-language Recipe mutation journey was subsequently
verified on candidate `c490b61557550c44b73e1ecceac801328a16a6a4`: 3 turns,
including two independent readbacks across reload, with one canonical chat
mutation, `false_success=0`, `raw_final_results=0`, `duplicate_delivery=0`,
`abrupt_eof=0`, and `DONE=3`. This separates the healthy canonical mutation
path from the incomplete-source URL case above.

Candidate `36de0bec` also promotes the existing `NEEDS_REVIEW` response into
the normal Inventory UI: incomplete imports identify the source/name and
bounded missing fields instead of surfacing raw Action validation. The exact
URL remains non-persisting until its missing quantity is supplied or reviewed.

The exact product candidate `c6f07fdb` passed the supported containerized full
regression with `6925 passed, 6 skipped, 149 warnings`. The six skips are
documented test skips; the earlier storage-preflight failures were reproduced
as an artifact of missing configured host storage mounts and disappear when
those paths are mounted read-only.

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

## Owner empty-state routing checkpoint — `7570719f`

- The existing transport eligibility predicate now includes canonical `MEMORY`
  and `WORK` owner reads, while conceptual questions remain outside the
  bounded ACI path.
- Focused contract/lifecycle coverage: `214 passed, 2 skipped`.
- Exact disposable candidate `odysseus:candidate-7570719f` was built from the
  pushed SHA and deployed with matching OCI marker/running source, healthy
  status, and zero restarts.
- Browser replay exposed a remaining shared product defect: the route now
  logs `chat→agent` and selects `read_memory`, but the execution path sent
  `tools=0` to Qwen and emitted model prose without a canonical Result; the
  analogous empty Work journey behaved the same way. Memory and Work browser
  acceptance therefore remain FAIL, despite one terminal `[DONE]` and no
  abrupt EOF. This is a product execution integration defect, not an
  evaluator pass; disposable principal, credentials, containers, and volumes
  were removed after capture.

## Recipe URL argument-projection checkpoint — `b43742dd`

- URL-backed Recipe CREATE now carries `recipe_source_url` and the explicit
  `recipe_requested_name` in the compiled IntentFrame. The canonical action
  projection exposes only `manage_recipes/commit_import` for that intent, so a
  weak-model selection cannot fall back to the under-specified `add` Action
  and lose the user's source/name fields.
- Focused ACI, intent, recipe import, and binding coverage: `343 passed`.
- Exact candidate `odysseus:candidate-b43742dd` was built and deployed in a
  fresh isolated Compose project with matching image/OCI source
  `b43742ddd5a73776317c1385fa3bd164506c6482`, healthy startup, and the
  acceptance principal enabled only for the run.
- Browser execution reached the normal login route, but the fresh isolated
  deployment had no configured model endpoint (`/api/models` returned an empty
  list), so no chat session could be created. URL-import browser acceptance is
  therefore `UNVERIFIED / MODEL_ENDPOINT_MISCONFIGURED`; this is not counted
  as a product routing pass or failure. The false-success guard remained
  unchanged.
- A follow-up exact-candidate browser run with a normally registered
  container-reachable Qwen3:8B endpoint exercised the real login, session,
  approval, `/api/chat_stream`, and import path. The selected Action was the
  sole `commit_import` projection; the explicit URL/name therefore survived
  the routing boundary. The run correctly failed closed at
  `RECIPE_DRAFT_VALIDATION`: the page's Schema.org data contains the
  ingredient `salt and pepper` without a verifiable quantity. Result was not
  persisted, one bounded `ERROR` answer and one `[DONE]` were delivered, with
  zero abrupt EOF and zero false success. This is a truthful `NEEDS_REVIEW`
  outcome, not permission to invent a quantity.

## Recipe import review UX checkpoint — `0c708f92`

- Failed URL imports now have a canonical owner-facing renderer: it explains
  that the recipe could not be imported, confirms that no recipe was saved,
  and asks for missing or ambiguous details. Internal Action and validation
  data remain diagnostic rather than the primary answer.
- Focused ACI/Recipe coverage: `316 passed`; full supported regression before
  this renderer-only slice: `6927 passed, 5 skipped`.
- The exact candidate image `odysseus:candidate-0c708f92c660` was deployed in
  an isolated runtime with matching OCI/source marker and Qwen3:8B reachable
  through the container endpoint. Real browser login, session creation,
  approval, `/api/chat_stream`, and URL import produced the bounded review
  answer, one terminal `[DONE]`, and no abrupt EOF. No canonical recipe was
  persisted because the source lacked a verifiable quantity for `salt and
  pepper`.

## Recipe import projection checkpoint — `5d3a047a`

The shared `RecipeDraft` import contract now accepts an explicit
`requested_name` override for both `prepare_import` and `commit_import`.
Schema.org/page presentation names cannot overwrite the owner's explicit name;
the source URL and import provenance remain attached to the draft. The service
boundary regression also proves preparation remains read-only. Focused Recipe,
ACI, and deterministic-intent coverage is `317 passed`; the full current
checkout regression is `6930 passed, 5 skipped` at test/docs head
`95584a83`.

The executable candidate `odysseus:candidate-5d3a047a960e` was built from
`5d3a047a960ef91420b6c14b041e2262ae28da46` with image
`sha256:5c18e05727eb1accd887535eb5bfcc5fdbdc8946a9ae3a2259a6c7dbeb9b8d93`.
OCI revision, `/app/.odysseus-source-commit`, and running source matched; the
isolated runtime was healthy with zero restarts and Qwen3:8B reachable from the
project Docker namespace. The disposable runtime was removed afterward. The
real Sunday Supper source remains correctly `NEEDS_REVIEW` until its
unquantified ingredient is supplied or reviewed; no quantity is invented.

## Recipe import UI continuity checkpoint — `adfbc496`

The authenticated Inventory Import dialog now accepts an optional human-facing
display name and forwards it to the canonical `prepare_import` endpoint. The
route passes that value into the same `RecipeDraft` owner used by chat and
commit, so source presentation names cannot discard an explicit owner choice.
Frontend syntax and affected UI/Recipe/ACI coverage passed (`322` tests); the
full current checkout regression passed `6930` tests with `5` skips. The exact
candidate was built and source/OCI/health/Qwen verified in an isolated runtime;
that disposable runtime was removed without touching owner state.

## Recipe import review surface checkpoint — `a7fe204c`

Incomplete URL/text/media imports now remain in the Import dialog as an
explicit review state rather than falling into a generic toast. The UI shows
the bounded reason, missing or ambiguous fields, a `Review Draft` disclosure,
and a retry path. It cannot commit while `RecipeDraft` validation has failed;
the canonical owner still requires a validated draft, persistence, and
readback. Focused UI/Recipe coverage passed `27` tests and the full current
regression passed `6931` tests with `5` skips. Exact candidate
`odysseus:candidate-a7fe204ca5a2` was source-matched, healthy, zero-restart,
and Qwen-reachable in an isolated runtime; the disposable container was
removed afterward.

### Live importer evidence — 2026-08-28

The bounded public fetch for the owner-requested Sunday Supper URL completed
successfully (`10,016` bytes, no fetch error). Schema.org extraction found the
page recipe and `11` ingredients, but one ingredient was the unquantified
phrase `salt and pepper`. `recipe_import_draft()` therefore returned no
persistence-ready `RecipeDraft`; the review projection returned
`NEEDS_REVIEW` with that field identified. This is the intended fail-closed
behavior: the URL and requested display name reach the import projection, but
the canonical owner does not invent a quantity or persist an incomplete
recipe. No further executable change is justified by this evidence.

## Recipe video evidence checkpoint — `5369b5d9`

The existing YouTube source adapter now obtains bounded public metadata and
description evidence alongside the existing transcript path. If captions are
missing but the description is available, that description can still reach
RecipeDraft preparation; if neither source has usable evidence, the importer
returns a bounded unavailable/review outcome. Metadata and transcript remain
untrusted input, and persistence still requires validated RecipeDraft,
canonical `manage_recipes`, and readback verification.

Focused Recipe/ACI/UI coverage passed `255` tests. The full supported
regression at this executable checkpoint passed `6933` tests with `5` skips.
The exact candidate `odysseus:candidate-5369b5d9` was built from the pushed
SHA, image ID `sha256:8e29abd778c0bef043316e401e31273551dd7b7e5c010e9c8e10295a04d723b0`,
and verified in an isolated container: OCI marker/runtime source matched,
health was healthy, restarts were `0`, and Qwen3:8B was reachable from the
container namespace. The disposable container was removed afterward; the
owner deployment was not changed.

## URL Recipe import live checkpoint — `d41c67fc`

The exact owner-like URL import journey reached canonical
`manage_recipes/commit_import` and normal approval handling. The source page
was fetched as untrusted evidence, but its structured ingredients included an
unquantified `salt and pepper` field. Validation therefore returned a bounded
review/failure answer stating that no recipe was saved, with one terminal
`[DONE]`; no false success, invented quantity, or persistence claim occurred.
This is the intended fail-closed incomplete-draft behavior, not evidence to
weaken import validation. A complete URL import remains a separate acceptance
case to prove. The disposable principal and container were removed; owner
deployment was not changed.

## Recipe pantry-coverage owner-journey checkpoint — `d41c67fc`

The stateful browser/chat journey `What recipes do I have?` followed by `Can
I make that recipe?` passed through the existing Recipe read owner and
Inventory Service coverage operation. The active recipe reference was resolved
across turns, `read_recipes/can_make` returned the canonical pantry result, and
both turns produced deterministic human answers and terminal `[DONE]` events.
The run had two streams, zero mutations, zero raw final results, duplicate
delivery, or abrupt EOF. Meal-plan mutation remains deferred until broader
Recipe read/composition acceptance is complete.

## Household mutation owner-journey checkpoint — `d41c67fc`

The isolated browser/chat journey for adding three synthetic cans, reading the
quantity, consuming one, and reading it again passed all `4/4` turns. Both
mutations entered through natural-language chat, and the canonical Inventory
Service readbacks verified the resulting quantity and reload durability. The
run reported `2` mutations, `2` readbacks, one final answer and one `[DONE]`
per turn, with zero false-success claims, raw final results, duplicate
delivery, or abrupt EOF. The disposable acceptance principal was revoked and
removed; owner deployment was not changed.

The post-refactor full regression completed at `6933 passed, 5 skipped` with
no new failures. This confirms the executor-to-service ownership change did
not regress the broader product tree; browser/live URL mutation acceptance
against this exact executable remains a separate pending evidence class.

The follow-up regression `test_chat_recipe_url_prepare_review_never_reaches_commit`
proves an incomplete canonical proposal stops before `commit_import`; the
executor returns failure evidence and cannot produce a mutation success from
model-facing or source text alone. This test-only checkpoint is `f1ddb4a2`;
the deployed executable remains `5c434f06`.

## Homelab service-health renderer checkpoint — `65d61e9a`

The canonical `manage_homelab` `service_status` read now has a bounded
ResultProjection and deterministic owner-facing renderer. Successful runtime
health results no longer need model synthesis merely to become readable;
diagnostic metadata is limited to service name, status, and detail. Focused
ACI/projection coverage passed `99` tests in the supported container. The exact
candidate `odysseus:candidate-65d61e9a` was built from the pushed SHA, image
ID `sha256:2aca24361b21f5e9876b25f89c7b4cace7803728e67b0a115a74893b14a1dd0b`,
and verified in an isolated runtime: OCI marker/runtime source matched,
health was healthy, restarts were `0`, and Qwen3:8B was reachable from the
container namespace. The owner deployment was not changed.

## Recipe canonical preparation checkpoint — `5c434f06`

URL-backed chat mutations now send fetched evidence through the existing
`InventoryService.manage_recipes(prepare_import)` proposal operation before
the effectful `commit_import` Action. The executor no longer parses a second
RecipeDraft path; only the service-owned prepared draft can reach commit.
Focused ACI/Recipe coverage passed `321` tests and the supported full
regression passed `6933` tests. Candidate `odysseus:candidate-5c434f06` was
built from the pushed executable SHA, with image ID
`sha256:17b08b1ab09983ec4acedf0b8828e7dfca2b50743d420f3992e05ca80956d7ae`.
An isolated runtime matched the OCI marker and source, reported healthy with
zero restarts, and reached Qwen3:8B from its container namespace. The owner
deployment was not replaced.

## Homelab targeted service checkpoint — `fe7b6b74`

Target-qualified `service_status` Results from the existing host-operator read
now receive the same bounded projection and deterministic human renderer as
aggregate service health. Focused supported-container coverage passed `100`
tests. Candidate `odysseus:candidate-fe7b6b74` was built from the pushed SHA,
with image ID `sha256:1e20b8d3136cc4ea43b978f428ad115351f8bd12886b902fb19bb0a1b63c955f`;
OCI marker/runtime source matched, health was healthy, restarts were `0`, and
Qwen3:8B was reachable from the candidate namespace. The owner deployment was
not changed.

## Asset property owner-journey checkpoint — `d41c67fc`

The exact browser trace for `How much RAM do my computers have?` showed the
remaining defect: the compiler populated `asset_property=ram`, but the shared
deterministic read predicate did not recognize `how much` as an explicit read.
The turn consequently reached model-only prose with no Action or canonical
Result. Adding `how much` to the shared read-request predicate closes that
boundary without adding a phrase-specific route. Focused owner/core coverage
passed `535` tests with `2` skips; the full current-source regression passed
`6931` tests with `6` skips and had `6` storage-preflight environment failures
because the source-mounted test container lacked `/home/.docker-data`.

Exact candidate `odysseus:candidate-d41c67fc` was built from pushed SHA
`d41c67fcbc5e04dd932712beaf049389a5e1d4d5`, image
`sha256:310bdcb9c37e6f1aa0533593ff2160f60e09a3b92a06319b7a9f90b97784f32c`.
OCI/source marker matched, health was healthy, restarts were `0`, and Qwen3:8B
was reachable from the candidate namespace. Browser acceptance then produced
one `manage_assets/list`, one deterministic final answer containing Atlas
`64 GB` and Erebus `128 GB`, one persisted answer, and one `[DONE]`; the
disposable acceptance container and principal were removed afterward. The
owner deployment was not changed.

## Live owner-journey checkpoint — `d41c67fc`

Against the exact disposable candidate, normal login and browser/chat passed
`OWNER-RECIPE-EMPTY-001`: the empty canonical Recipe collection produced one
human-readable deterministic answer, one persisted answer, and one terminal
`[DONE]`. `OWNER-RECIPE-MUTATION-READBACK-001` passed all three turns through
chat: the mutation executed through the canonical owner, the recipe was
independently read back, and it remained after reload. The run reported `3`
streams, `3` DONE events, `2` readback checks, zero false-success claims, zero
raw final results, zero duplicate delivery, and zero abrupt EOF. The
acceptance principal was revoked and its temporary credential removed; owner
deployment was not changed.

## Asset filter owner-journey checkpoint — `d41c67fc`

The isolated browser/chat journey for `Which of my servers has an RTX 4090?`
passed against a canonical CMDB containing incomplete and duplicate-like
synthetic assets but no RTX 4090. The route used `manage_assets/list` and
returned a bounded deterministic no-match answer rather than raw asset JSON or
an invented server. It produced one persisted final answer and one `[DONE]`,
with zero raw-final results, duplicate delivery, or abrupt EOF. This was a
read-only disposable run; the owner deployment was not changed.

## Work result-projection checkpoint — `7c54a485`

The isolated browser run for `What work is outstanding?` exposed a shared
large-result boundary: the canonical `read_work` Action completed and emitted
`[DONE]`, but the browser had no answer because the deterministic renderer was
reparsing a truncated display payload. `read_work` now receives a bounded
collection-count projection before UI/history truncation, and its renderer
consumes that projection. Focused supported-container coverage passed `77`
tests. Exact candidate `odysseus:candidate-7c54a485` was built from pushed SHA
`7c54a4859c9503dd264bd2e1459354f16321ef98`; the disposable runtime marker
matched, health was healthy, restarts were `0`, and Qwen3:8B was reachable
from the candidate namespace. The browser Work journey then passed with one
human-readable deterministic answer, one persisted turn, one `[DONE]`, and no
abrupt EOF or duplicate delivery. Disposable acceptance resources were
removed; the owner deployment was unchanged.
