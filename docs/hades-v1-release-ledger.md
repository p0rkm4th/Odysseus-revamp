# Hades V1 release ledger

Status: active engineering release ledger; not a release declaration.

## Memory correction/readback checkpoint — exact candidate `cb8a3777` (2026-08-30)

`OWNER-MEMORY-CORRECTION-READBACK-001` passed in the isolated realistic
Qwen3:8B browser environment. The owner remembered a test color, read it,
corrected it as no longer true, and read the resulting state after the
correction. Evidence: 4 turns, 2 Memory mutations, 2 deterministic reads,
zero false successes, raw final Results, duplicate delivery, or abrupt EOF.
The exact candidate image was
`sha256:a71ecae56d433f4abe8dca6c52da4d754d3753a7e5d8c36358186d313bf5a1cf`;
the actual owner runtime remains untouched.

## Asset ordinal correction/reference-chain checkpoint — exact candidate `cb8a3777` (2026-08-30)

`OWNER-ASSET-REFERENCE-CHAIN-001` passed in the isolated realistic synthetic
Qwen3:8B browser environment. Through the GUI, the owner asked for the second
computer, corrected that to the first, then asked for its RAM. All three
turns resolved against canonical Asset state and produced deterministic human
answers. Evidence: 3 turns, 3 canonical reads, zero false successes, raw
final Results, duplicate delivery, or abrupt EOF. Candidate image:
`sha256:a71ecae56d433f4abe8dca6c52da4d754d3753a7e5d8c36358186d313bf5a1cf`;
runtime source marker `cb8a3777`, restart count 0. The actual owner runtime
remains untouched.

## Disposable application backup/restore replay — current head `2026-08-30`

The existing `scripts/odysseus-backup` CLI was exercised in a standalone
temporary repository containing synthetic owner state. Snapshot and archive
verification succeeded; after deliberate JSON/text drift and an extra file,
`restore --yes` restored the original state, removed the drift-only file, and
retained the pre-restore directory as a rollback stash. No repository `data/`,
owner data, Docker volumes, or owner deployment were used. This is direct
application-data recovery evidence; Docker Chroma recovery remains a separate
volume procedure.

## Isolated realistic visual acceptance checkpoint — harness commit `228809c7` (2026-08-30)

The realistic visual acceptance script was previously coupled to the owner
session file, preventing safe visual testing against a fresh candidate. It
now supports an explicitly supplied disposable credential file, requires
isolated-acceptance settings in that mode, and ignores expected unauthenticated
login-page API errors until normal login completes.

The full visual gate passed against exact candidate `6a713675` in a fresh
isolated Compose project at desktop, narrow, and mobile viewports. It checked
shared Inventory/Recipe window chrome, sidebar icon uniqueness, duplicate
Security/Research entries, window containment, tab behavior, long-content
wrapping, and horizontal overflow; desktop, narrow, and mobile screenshots
were captured and inspected. The synthetic OSINT fixture’s repeated label in
its own heading is fixture content, not a product defect. The disposable
stack was removed and owner state was untouched.

## Fresh-install restart durability checkpoint — exact candidate `6a713675` (2026-08-30)

A fresh disposable Compose project completed normal admin setup, registered
the host Qwen3:8B endpoint through the model-settings flow, and passed an
authenticated empty-Work browser read. The app container was then restarted;
health returned with the same image and source marker, Docker restart count
remained zero, and the same authenticated browser journey passed again.
Evidence: two isolated browser runs, one before and one after restart, with
zero false successes, raw final Results, duplicate delivery, or abrupt EOF.
This is fresh-install/restart evidence only; the actual owner deployment is
still stopped and was not touched.

## Recipe shopping-requirements checkpoint — exact candidate `6a713675` (2026-08-30)

`OWNER-RECIPE-SHOPPING-REQUIREMENTS-001` passed in a fresh isolated
Compose/Qwen3:8B project with a canonical pantry shortage. The owner asked
what recipes were available and then what was needed to make one; the final
answer remained grounded in the shortage rather than claiming full pantry
coverage. Evidence: two turns, two read journeys, two canonical readbacks,
and zero mutations, false successes, raw final Results, duplicate delivery,
or abrupt EOF.

## Current-head recovery/setup focused gate — `2026-08-30`

The current branch passed 40 focused tests covering application backup/restore
CLI safety, owner-scoped backup import and deduplication, skill import
handling, Chroma client/persistence and health contracts, setup admin-user
creation, and provider alias setup. No owner data, owner volumes, or live
deployment were used. This strengthens the recovery evidence but does not
replace a full fresh-fresh install/restart/recovery rehearsal.

## Recipe expiring-inventory composition checkpoint — exact candidate `6a713675` (2026-08-30)

`OWNER-RECIPE-EXPIRING-COMPOSITION-001` passed in a fresh isolated
Compose/Qwen3:8B project with a canonical expiring pantry fixture. The owner
asked what could be made with ingredients expiring soon; the response was a
grounded recipe candidate, and canonical Recipe readback remained correct
after reload. Evidence: one read turn, two canonical readbacks, and zero
mutations, false successes, raw final Results, duplicate delivery, or abrupt
EOF.

## Recipe pantry composition checkpoint — exact candidate `6a713675` (2026-08-30)

`OWNER-RECIPE-COMPOSITION-001` passed in a fresh isolated Compose/Qwen3:8B
project. With a canonical pantry fixture, the owner listed recipes, asked
whether the recipe was makeable from available stock, and scaled it to six
servings. All three turns produced deterministic semantic answers; canonical
recipe readback remained valid across reload. Evidence: three turns, three
read journeys, two independent readbacks, and zero mutations, false
successes, raw final Results, duplicate delivery, or abrupt EOF.

## Populated Memory recall checkpoint — exact candidate `6a713675` (2026-08-30)

`OWNER-MEMORY-POPULATED-001` passed in a fresh isolated Compose/Qwen3:8B
project. The owner asked what Hades knew about the acceptance setup; the
fixture-provided preference was returned with grounded Memory context, and
the canonical Memory readback remained correct after reload. Evidence: one
read turn, two canonical readbacks, and zero false successes, raw final
Results, duplicate delivery, or abrupt EOF. Broader contradiction and
reference-chain journeys remain open.

## Asset false-premise checkpoint — exact candidate `6a713675` (2026-08-30)

`OWNER-ASSET-FILTER-NO-MATCH-001` passed in a fresh isolated Compose project
after supplying its required disposable canonical CMDB fixture. The owner
asked which server had an RTX 4090 while the fixture contained no such asset.
The browser journey produced a grounded no-match answer with no hallucinated
entity and no raw Asset Result leak. Evidence: one read turn, one canonical
read journey, zero mutations, false successes, duplicate delivery, or abrupt
EOF. The initial missing-CMDB invocation was classified as
`ENVIRONMENT_FAILURE` and was not counted as feature evidence.

## Household sloppy-language checkpoint — exact candidate `6a713675` (2026-08-30)

`OWNER-HOUSEHOLD-SLOPPY-MUTATION-READBACK-001` passed in a fresh isolated
Compose/Qwen3:8B project through the normal browser chat surface. The owner
used informal language to add three cans, read the quantity, used one, and
read the remaining quantity after reload. Evidence: four turns, two actual
canonical mutations, two readbacks, and zero false successes, raw final
Results, duplicate delivery, or abrupt EOF. This provides browser evidence
for ordinary messy Household language, while broader fresh-install coverage
remains open.

## Work task mutation checkpoint — exact candidate `6a713675` (2026-08-30)

`OWNER-WORK-TASK-MUTATION-READBACK-001` passed in a fresh isolated Compose
project using the normal login/model setup and Qwen3:8B. The acceptance
fixture created only the prerequisite project through the API; the owner then
created the task through chat, read it back conversationally, and the harness
verified canonical persistence before and after reload. Evidence: two turns,
one mutation, two readbacks, and zero false successes, raw final Results,
duplicate delivery, or abrupt EOF. Basic Work project/task mutation is now
browser-proven; cross-suite remediation relationships remain intentionally
unimplemented until canonical ownership is defined.

## Work project mutation checkpoint — exact candidate `6a713675` (2026-08-30)

`OWNER-WORK-PROJECT-MUTATION-READBACK-001` passed in a fresh isolated
Compose project with normal login/model setup and Qwen3:8B. The owner created
an ordinary project through chat, followed up with a read, and the canonical
Work API confirmed the project before and after reload. Evidence: two turns,
one mutation, two canonical readbacks, and zero false successes, raw final
Results, duplicate delivery, or abrupt EOF. This proves the basic project
mutation path; task creation and cross-suite relationships remain open.

## Qualitative recipe fixture replay checkpoint — harness commit `76210b81` (2026-08-30)

The qualitative-amount review journey was initially blocked before the owner
turn because its declared existing-recipe fixture had no corresponding setup
hook. This was classified as `ENVIRONMENT_FAILURE`, not accepted as feature
evidence. The browser acceptance harness now owns that prerequisite through a
named `canonical_qualitative_existing_recipe` fixture setup, using the same
permitted API-only prerequisite pattern as the other composition journeys.

A fresh disposable replay then passed `OWNER-RECIPE-QUALITATIVE-REVIEW-001`
against exact candidate `6a713675`: one owner turn, one review-only mutation
attempt, two canonical readbacks, and zero false successes, raw final Results,
duplicate delivery, or abrupt EOF. The qualitative `salt to taste` and `oil as
needed` fields remained reviewable rather than being assigned invented
quantities. Disposable state was removed and owner state was untouched.

## Recipe video title-default checkpoint — exact candidate `6a713675` (2026-08-30)

The owner-facing video import path had a product gap: a valid video source
already supplied a trusted `Video title`, but an ordinary request to “save
this” without a display-name override could not produce a commit-ready draft.
The generalized recipe name extractor now uses that source title as the
default, while preserving explicit owner names when supplied.

The exact pushed candidate `6a713675b8fc374ba5a85f6795023381e8e6a278`, image
`sha256:66adb3baab70a52aad88f0af7dd06724f2e3e11dc7d56a1d5d556b247198f943`,
passed `OWNER-RECIPE-VIDEO-TITLE-DEFAULT-001` in a fresh isolated Compose
project using normal login/model setup and Qwen3:8B. The request entered via
GUI/chat, committed the public quantified recipe, preserved the source URL,
and independently read back the canonical recipe twice including after reload.
Evidence: one conversational turn, one mutation, two readbacks, zero false
successes, raw final Results, duplicate delivery, or abrupt EOF. The
disposable stack and volumes were removed afterward; the stopped owner
deployment was not touched.

## Owner read-only visual smoke and fresh-model provisioning note — 2026-08-30

The actual owner deployment passed `scripts/browser_realistic_acceptance.mjs`
against `http://127.0.0.1:7000`: shared Inventory/Recipe window chrome,
sidebar icon uniqueness, desktop and narrow viewport containment, and no
horizontal overflow. This was read-only and did not seed or mutate owner data.
The owner container remained healthy on source `34ced247` with zero restarts.

Current reconciliation at this checkpoint finds the owner Compose project
stopped as a group: `odysseus-odysseus-1` exited `0` and
`odysseus-ntfy-1` exited `2` at approximately `04:19 UTC`, with no recorded
restart. No sprint command stopped, recreated, or modified that owner
project. Live-owner health and read-only smoke claims therefore remain
historical until the owner deployment is intentionally restored.

A separate fresh disposable Memory correction attempt initially reached a
healthy application but `/api/models` exposed no usable `qwen3:8b` endpoint,
so no conversation was graded. This was classified as
`PROVIDER_FAILURE / MODEL_ENDPOINT_MISCONFIGURED`; the disposable stack was
removed. The documented normal admin model-registration flow was then
exercised successfully in a fresh-fresh lane, as recorded below.

The setup gap was reproduced and generalized in the acceptance helper: an
entrypoint-provisioned instance now authenticates the configured
`ODYSSEUS_ADMIN_USER` (default `admin`), while API-first setup retains its
dedicated bootstrap username. Through the normal admin login and
`/api/model-endpoints` flow, a fresh disposable project registered the host
Ollama endpoint and exposed `qwen3:8b`. The exact executable candidate
`f726b16b` then passed `OWNER-MEMORY-CORRECTION-READBACK-001`: four turns,
two canonical mutations, four terminal completions, and zero false
successes, raw final Results, duplicate delivery, or abrupt EOF. The browser
harness fix was tested from the worktree as a script/test descendant; the
product container remained source-matched to `f726b16b`. The stack and
temporary credentials were removed, and the actual owner runtime was not
touched.

## Docker Chroma persistence checkpoint — exact candidate lineage (2026-08-30)

Release testing found a product/recovery defect in all three Docker Compose
variants: the Chroma image persists to `/data`, but the named volume had been
mounted at `/chroma/chroma`. A disposable shopping stack confirmed that the
volume was empty while the live container layer contained `chroma.sqlite3` and
HNSW index files, so a volume archive did not contain the actual vector state.

The Compose mounts are corrected to `chromadb-data:/data` in the standard,
NVIDIA, and AMD files, with a regression test guarding the image/config
contract. In an isolated disposable project, the live vector files were
staged before recreation, copied into the corrected named volume, and the
collections API returned the existing collection. A tar backup of that volume
was unpacked into a separate restore volume; a fresh Chroma container mounted
on the restore volume returned the same collections API response. The actual
owner deployment was not touched. The correction is included in the exact
candidate lineage through `68beec69`; image marker and OCI revision for that
candidate were verified. Owner-data migration remains a separately controlled
operation, and a fresh candidate backup/restore replay remains release work.

The acceptance harness now refuses to run unless `APP_DATA_DIR` is set to a
disposable directory distinct from the repository's `data/` directory. A
manual persistence-health check exposed that the Compose overlay's comment
alone was insufficient protection; no browser mutation was run in that stack,
and it was stopped and removed before further testing. The owner container
remained running with zero restarts.

## Acceptance isolation and video safety checkpoint — exact candidate `7e01a053` (2026-08-30)

The exact candidate `7e01a053bb638810aec361b3914e4adefd088c0b`, image
`sha256:d2023c97033dadaf93515c4b0db7a68b3b647cf00395b7a2434b4fd878c5a48f`,
was browser-tested in a fresh temporary data directory with separate Compose
network, ports, and Chroma volume. The harness refused an intentional
`APP_DATA_DIR=data` invocation before provisioning, then the isolated stack
passed `OWNER-RECIPE-VIDEO-INSUFFICIENT-EVIDENCE-001` through the normal login/chat
surface using Qwen3:8B. The ordinary video request produced a clear no-evidence
outcome, made no canonical Recipe, and survived two independent readback
checks; one turn, one attempted mutation, zero false successes, raw final
Results, duplicate delivery, or abrupt EOF. The stack was removed afterward.
The candidate container had source marker `7e01a053` and zero restarts; the
owner runtime remained on source `34ced247` with zero restarts.

The same isolated lane also exercised a public cooking video URL whose
description contained a recipe-shaped ingredient list and numbered method.
The adapter retrieved metadata successfully, but the weak-model draft still
returned a bounded review error for missing verified structure. This remains
`PROVIDER_FAILURE / INSUFFICIENT_EVIDENCE`, not positive extraction evidence;
the safe no-save result is covered by
`OWNER-RECIPE-VIDEO-INSUFFICIENT-EVIDENCE-001`. Positive transcript/description
extraction with validated commit remains an open Recipe release gate.

The generalized parser now recognizes headingless video descriptions with a
`METHOD`/`DIRECTIONS` boundary and number-word quantities as an editable
review draft. Unresolved qualitative lines remain explicitly marked for human
correction; strict canonical commit still refuses them. Focused parser
coverage passed `4` tests before browser replay of this follow-up.

## Video import review-boundary checkpoint — exact candidate `f726b16b` (2026-08-30)

The exact pushed candidate `f726b16b5dfd0e3e587816f59c790d77c923751c`, image
`sha256:066fb2d33ffd677496a00c871a25ee209525b6d2469d45d3f6c6086ff652e938`,
was replayed through the isolated normal-login/browser/chat lane against the
public video URL in `OWNER-RECIPE-VIDEO-REVIEW-DRAFT-001`. The weak-model
proposal contained a recognizable recipe but an unresolved `olive oil spray`
quantity. The executor now routes that untrusted proposal to the existing
editable review event; it does not call a successful canonical mutation. The
owner-facing answer was deterministic, explicitly required review, and did
not claim the recipe was saved. Canonical recipe count remained zero across
two independent readbacks. One turn, one attempted mutation, two readbacks,
zero false successes, raw final Results, duplicate delivery, or abrupt EOF.

The browser replay initially found an acceptance-environment login failure
because the recreated disposable stack had its acceptance gate disabled; the
stack was restarted with the explicit gate and the journey then passed. The
candidate container had marker `f726b16b` and zero restarts. The actual owner
runtime remained on source `34ced247` with zero restarts and was not touched.
Positive video extraction followed by validated canonical commit remains open;
this checkpoint closes the unsafe/dead-end review-boundary defect only.
The focused recipe/execution slice passed `143` tests, and the full supported
regression at the pushed documentation checkpoint passed `7016` tests with
`8` skips and `186` warnings in `330.32s`.

## Positive YouTube recipe import checkpoint — exact candidate `68beec69` (2026-08-30)

The exact candidate `68beec697780510f2e9e0108d6d22211929571fc`, image
`sha256:a241f019bc811e4b15a476a337698e2291c5701685b11bac1a43c28d2e6f28cd`,
was tested in a fresh isolated Compose project after normal admin login and
Qwen3:8B endpoint registration. The owner request used the public cooking
video `5YcsrFC2h5U` and a display-name override. Its description contained
headinged instructions and two quantified ingredients but no parser-specific
owner syntax. Through GUI/chat, Hades fetched the untrusted video evidence,
created the canonical Recipe, preserved the requested name and source URL,
and independently read it back twice, including reload durability. One turn,
one mutation, two readbacks, one terminal completion, and zero false
successes, raw final Results, duplicate delivery, or abrupt EOF. The
disposable project, volumes, and credentials were removed; the owner runtime
was not touched.

This closes the previously open positive YouTube extraction gate for a
complete quantified description. Qualitative/missing-amount video evidence,
review correction UX, broader video variants, and meal-plan composition remain
separate Recipe release work.
The focused parser/import slice passed `93` tests, and the full supported
regression at this candidate checkpoint passed `7018` tests with `8` skips and
`149` warnings in `295.06s`.

## Owner Memory mutation/correction checkpoint — candidate `0ae8d463` (2026-08-29)

`OWNER-MEMORY-MUTATION-READBACK-001` passed on the exact disposable
candidate `0ae8d463f5a6f7770f9a4ca6fbc7b560ebf48971`, image
`sha256:fe832ff567816995ea7e8b5ec2773be0af84df5300364e4b761cb3f7475b4672`,
with Qwen3:8B. Through the GUI/chat surface, an ordinary owner completed:
remember a test color, read it, forget it, read it again, then reload. Both
mutations executed the canonical `manage_memory` Action with successful
Results; independent `/api/memory` readbacks showed the fact present after
add and absent after delete, including reload. Four conversational turns,
two mutations, two independent state checks, zero false successes, raw final
Results, duplicate delivery, and abrupt EOF.

The journey first exposed and fixed three generalized defects: owner memory
writes were blocked for non-admin owners, weak-model ACI selection could drop
the bounded mutation, and automatic extraction duplicated explicit memory
mutations. The candidate was browser-tested in the isolated fresh lane; the
actual owner runtime remained untouched.

## Populated Memory live-Qwen checkpoint — candidate `3a0d9555` (2026-08-29)

`OWNER-MEMORY-POPULATED-001` passed in the isolated disposable deployment on
the exact candidate. The browser used the normal login and chat surface with
the configured `qwen3:8b` endpoint, returned the seeded durable Memory fact,
and completed two independent canonical readbacks. The journey had one
ordinary owner read and zero false successes, raw final Results, duplicate
delivery, or abrupt EOF. This closes the previously unverified live-Qwen
evidence for this narrow populated-Memory read; everyday recall, correction,
contradiction, and reference-chain journeys remain open.

## Qualitative Recipe review workflow checkpoint — candidate `3a0d9555` (2026-08-29)

The qualitative-ingredient owner journey exposed two product defects. The
initial browser review state was only an error/retry panel, and the first
editable review implementation rejected decimal corrections because its
import-specific numeric regex was over-escaped. The generalized repair now
extracts a reviewable draft for ordinary sectioned recipe text, marks
qualitative amounts such as “to taste” and “as needed” for review, preserves
strict validation at canonical commit, and accepts corrected positive decimal
quantities.

On the exact pushed candidate, a browser owner corrected `salt` to `0.25 tsp`
and `oil` to `1 tbsp`. The browser sent one `/api/recipes/import/commit`,
canonical readback contained `Acceptance Taste Test`, and reload rendered the
saved recipe. The pre-correction review remained non-persistent. This replay
had one mutation, one independent readback plus reload, and zero false
successes, raw final Results, duplicate delivery, or abrupt EOF. Disposable
fixture setup used one direct prerequisite recipe; the behavior under test
entered through the GUI. Owner runtime was untouched.

## Empty Memory owner-read checkpoint — candidate `5fe5bf94` (2026-08-29)

`OWNER-MEMORY-EMPTY-001` passed on an isolated fresh principal. The ordinary
first-use Memory question returned a grounded empty-state answer through the
browser with one clean stream. False success, raw final Results, duplicate
delivery, and abrupt EOF were all zero.

## Complete URL Recipe import checkpoint — candidate `5fe5bf94` (2026-08-29)

`OWNER-RECIPE-URL-IMPORT-COMPLETE-001` passed on an empty disposable Recipe
store with a fresh principal. The browser/chat flow used the required approval,
completed one canonical `commit_import`, preserved the requested display name
and source URL, then listed and opened the recipe in follow-up turns. Two
independent readbacks, including reload durability, passed. False success, raw
final Results, duplicate delivery, and abrupt EOF were all zero.

## Expiring Recipe composition checkpoint — candidate `5fe5bf94` (2026-08-29)

`OWNER-RECIPE-EXPIRING-COMPOSITION-001` passed on the exact candidate with a
fresh acceptance principal and isolated canonical fixture. The ordinary owner
question about recipes makeable from soon-expiring ingredients produced the
expected canonical read, with 2 independent readbacks including reload
durability. False success, raw final Results, duplicate delivery, and abrupt
EOF were all zero.

## Recipe composition and shopping checkpoint — candidate `5fe5bf94` (2026-08-29)

On the exact candidate and isolated fresh data, `OWNER-RECIPE-COMPOSITION-001`
passed 3 owner turns covering recipe listing, pantry feasibility, and scaling;
canonical recipe readback and reload durability passed. A fresh acceptance
principal then passed `OWNER-RECIPE-SHOPPING-REQUIREMENTS-001` across 2 turns
with 2 canonical readbacks. Both journeys had zero false success, raw final
Results, duplicate delivery, or abrupt EOF.

The first shopping replay stopped before chat because the shared fixture
seeder added a duplicate recipe when rerun; this is test-fixture idempotency
drift, not product evidence. The clean-principal replay restored the declared
one-recipe precondition without touching owner data.

## Populated Memory owner-read checkpoint — candidate `5fe5bf94` (2026-08-29)

`OWNER-MEMORY-POPULATED-001` passed on the exact candidate in the isolated
fresh lane. The browser asked an ordinary question about the acceptance setup;
Hades returned the seeded durable Memory fact, and the harness independently
verified the canonical Memory read twice. The journey had 1 turn with zero
false success, raw final Results, duplicate delivery, or abrupt EOF.

## Work task mutation/readback checkpoint — candidate `5fe5bf94` (2026-08-29)

On the clean fresh-install lane with empty Memory,
`OWNER-WORK-TASK-MUTATION-READBACK-001` passed through the browser/chat
surface. One task mutation completed and two independent canonical readbacks
verified it across 2 turns, including reload durability. False success, raw
final Results, duplicate delivery, and abrupt EOF were all zero.

A reused lane first stopped on an unexpected approval because an earlier
project journey had auto-created Memory and armed the external-context safety
gate. That run did not mutate a task; it was classified as fixture/context
drift, not used as feature evidence, and the clean replay satisfied the
scenario's declared no-approval precondition.

## Household mutation/readback checkpoint — candidate `5fe5bf94` (2026-08-29)

`OWNER-HOUSEHOLD-MUTATION-READBACK-001` passed on the exact candidate in an
isolated disposable owner lane. The browser/chat journey completed 4 turns,
including 2 owner-facing household mutations, and independently verified both
canonical state changes. Reload durability was included; false success, raw
final Results, duplicate delivery, and abrupt EOF were all zero. The journey
used ordinary owner language and did not seed the behavior under test through
an API; no owner data was touched.

## Copied-webpage Recipe mutation checkpoint — candidate `5fe5bf94` (2026-08-29)

`OWNER-RECIPE-COPIED-WEBPAGE-PASTE-001` passed on a clean disposable Recipe
deployment running the exact candidate. The owner pasted webpage-shaped recipe
content through chat, Hades completed one canonical mutation, and two
independent readbacks verified the result and its reload durability. The run
covered 2 turns with zero false success, raw final Results, duplicate delivery,
or abrupt EOF. A prior attempt against an accumulated disposable lane stopped
before chat because its empty-Recipe precondition had drifted; that was
classified as fixture `ENVIRONMENT_FAILURE`, not feature evidence.

The clean lane used a fresh application state, normal admin model setup, and
`qwen3:8b`; no owner deployment or owner data was touched.

## Fresh-install Qwen/restart checkpoint — candidate `5fe5bf94` (2026-08-29)

A disposable empty deployment was started from the exact candidate image
`odysseus:candidate-5fe5bf94ca79` with fresh application data and isolated
ports/network. Normal browser-visible admin setup registered the Ollama
endpoint and `qwen3:8b`, then created a non-admin acceptance user. The user
logged in through the normal route and ran `OWNER-WORK-EMPTY-001`; the empty
Work read returned a deterministic human answer with zero false success, raw
final Results, duplicate delivery, or abrupt EOF.

The same browser journey passed after an app-container restart. Health returned
healthy, restart count remained `0`, and the image remained
`sha256:5838813a8dcbb9506f91bb0185341a0c98fb1b0ead78711f2d3500d7824c4c46` with
source/OCI revision `5fe5bf94ca7922b31357f293c07f9a2e33e44a43`. This is fresh
install/restart evidence only; no owner deployment or owner data was touched.

## Actual-owner Work provenance checkpoint — candidate `5fe5bf94` (2026-08-29)

Read-only owner dogfood asked “What work is outstanding?” in an existing
session and received a generic no-access answer, despite owner-scoped Work
APIs returning canonical records. The stream had tool output but no
`response_replace`, classified as `ANSWER_FINALIZATION_FAILURE` on the actual
runtime. The owner container is source `34ced247`, older than the candidate,
and was not changed.

The same ordinary prompt in plain Chat mode on exact candidate `5fe5bf94`
auto-escalated through bounded Work read and returned the canonical task
summary. The candidate three-paraphrase Work journey also passed with zero
false success, raw final Results, duplicate delivery, or abrupt EOF. This
separates stale owner-runtime evidence from current-candidate evidence.

## Recipe review visual usability checkpoint — candidate `5fe5bf94` (2026-08-29)

Visual owner testing found two defects in the new review workflow: the body
of the original Import form remained visible beside the review editor because
the HTML `hidden` attribute was overridden by inventory grid CSS, and the
critical Save/Cancel actions were below the normal viewport. The shared fix
keeps only the review surface visible and makes the dialog action footer
sticky while preserving scroll access to the full form. This was classified
as `UI_RENDER_FAILURE` / `UX_CONFUSION`; the first scoped CSS attempt was
caught by computed-style replay and corrected before acceptance.

Exact candidate `odysseus:candidate-5fe5bf94ca79` carries source marker and OCI
revision `5fe5bf94ca7922b31357f293c07f9a2e33e44a43`, image
`sha256:5838813a8dcbb9506f91bb0185341a0c98fb1b0ead78711f2d3500d7824c4c46`.
At 1366×768, the final browser probe showed only the title, review panel, and
action footer; the footer was `position: sticky` and inside the viewport, and
the full Instructions field was reachable above it at scroll end. The probe
edited and committed a recipe, independently read it back, and confirmed the
edited recipe after reload. Focused UI coverage passed `5` tests, frontend
static verification passed, and both shared browser dogfood and realistic
browser acceptance passed. Owner deployment remains untouched.

## Network owner-read projection checkpoint — candidate `dcf0a95d` (2026-08-29)

Read-only owner smoke against the actual deployment exposed a user-facing
projection defect: “Tell me about my network.” returned repeated opaque node
IDs and no useful distinction between identified records and observations.
This was classified as `RESULT_PROJECTION_FAILURE` / `UX_CONFUSION`, not an
execution or persistence failure. The generalized repair preserves bounded
identity and resolution metadata through Result projection, groups repeated
observations, separates named records from unidentified/unconfirmed records,
and includes freshness plus the saved-observation caveat. The source commits
are `b9a6b482`, `ec5dff0f`, `06672b29`, and `dcf0a95d`.

Focused network coverage passed `7` tests; the full regression passed `6973`
tests with `7` skips and `186` warnings in `236.92` seconds. Exact candidate
`odysseus:candidate-dcf0a95d2371` carries source marker and OCI revision
`dcf0a95d237162158dbd617856aa6cfc13b54b8c`, image
`sha256:a5c31d6cc9ec5577ee4293e4a09117de817740fe9715706e256fdffe52a8aeff`.
`OWNER-NETWORK-001` passed in the disposable accumulated-observation fixture:
one deterministic response, one tool card, zero false success, raw final
Results, duplicate delivery, or abrupt EOF. Visible replay showed bounded
named/unconfirmed sections, no opaque IDs, and freshness language. The actual
owner container remains source `34ced247` and was not rebuilt or mutated.

## URL Recipe review-safety replay — candidate `dcf0a95d` (2026-08-29)

`OWNER-RECIPE-URL-IMPORT-NAMED-001` passed on the exact candidate using a
disposable empty-Recipe fixture with the normal Qwen endpoint. The ordinary
URL-plus-display-name request took the expected review/error path; one
mutation was attempted but independent SQLite readback and the harness
readbacks both confirmed zero canonical Recipes. False success, raw final
Result, duplicate delivery, and abrupt EOF were all zero. A separate fresh
fixture could not run this journey because it had no registered model
endpoint; that remains an install/fixture setup gap, not feature evidence.
No owner data was touched.

## Qualitative Recipe review replay — candidate `dcf0a95d` (2026-08-29)

The current exact candidate replayed `OWNER-RECIPE-QUALITATIVE-REVIEW-001`
against a disposable one-Recipe fixture. Ordinary qualitative amounts such
as “salt to taste” and “oil as needed” remained a review-safe error path; the
attempted mutation left the canonical count at `1`. The run had zero false
success, raw final Result, duplicate delivery, or abrupt EOF. The full human
correction and validated commit workflow remains an open productization gap.

## Editable Recipe review workflow checkpoint — candidate `1ec3689d` (2026-08-29)

Recipe import now renders an editable Hades review panel instead of a browser
`confirm()` text summary. Name, servings, ingredient names/quantities/units,
instructions, and source are visible before save. The existing server-side
`RecipeDraft` validator and canonical import readback remain authoritative.

On exact candidate `odysseus:candidate-1ec3689d6f0b` (source marker
`1ec3689d6f0b89df577d4e88d03cb500c72a4eac`, image
`sha256:649e77fd1348b1a0cbf5aa07eae0aedec84376f32f494a9a28f57980b60b7107`),
a browser probe edited a prepared recipe to `Acceptance Edited Dinner` and
three cups of rice, committed it, independently read back canonical state,
and verified visibility after reload. Focused Recipe/UI coverage passed `38`
tests plus frontend static verification. The current static-test-only follow-up
is `a78daf1d`; owner runtime remains untouched.

## Exact-candidate restart durability checkpoint — `20d07aef` (2026-08-29)

The exact candidate stack completed normal first-run setup, authenticated
browser use with model configuration, browser reloads, and an app restart.
After restart `/api/health` was healthy with restart count `0`; the image and
embedded source marker remained `20d07aefc170ebd80219a97055939c549cfe5654`.
Independent SQLite and authenticated API readback both retained the one
canonical `Acceptance Expiring Pantry Pasta` Recipe. This was disposable
state; the owner deployment remained untouched.

## Visual/UI owner checkpoint — candidate `20d07aef` (2026-08-29)

The realistic browser acceptance passed on the owner-facing surface: duplicate
Security/Research navigation checks, one intentional sidebar icon per entry,
shared Inventory window chrome, empty/list states, desktop containment, narrow
tab behavior, and mobile window sizing. Frontend static verification and shared
window dogfood also passed. Screenshots were captured at desktop, narrow, and
mobile sizes for visual review; no production UI blocker was found. The
existing fresh-install/restart/Qwen and isolated Chroma backup/restore
rehearsals remain recorded below as separate release gates. Owner state was not
changed.

## Recipe composition and false-premise checkpoint — candidate `20d07aef` (2026-08-29)

Fresh isolated exact-candidate stacks passed `OWNER-RECIPE-SHOPPING-REQUIREMENTS-001`
(2 turns, canonical readbacks including reload),
`OWNER-RECIPE-EXPIRING-COMPOSITION-001` (1 turn, canonical readback including
reload), and `OWNER-ASSET-FILTER-NO-MATCH-001` (1 realistic messy prompt).
The RTX 4090 false premise produced no invented entity, and all three runs had
zero false success, raw final Result, duplicate delivery, or abrupt EOF. These
journeys used separate disposable fixture databases; no owner state changed.

## Continued Tier 1 acceptance checkpoint — candidate `20d07aef` (2026-08-29)

The isolated candidate also passed clean Recipe mutation/readback (3 turns,
one mutation, two canonical reload readbacks), empty Work (1 turn), and the
full regression after the latest shared Asset compiler changes: `6971 passed,
7 skipped, 186 warnings` in 231.51 seconds. A named URL-import replay was
not executed because the reused disposable stack already contained the Recipe
from the preceding mutation journey; its empty-state precondition correctly
classified the attempt as `ENVIRONMENT_FAILURE`. No owner state was touched.

## Tier 1 owner-journey sweep — candidate `20d07aef` (2026-08-29)

On the isolated exact candidate, additional nontechnical GUI journeys passed:
empty Recipe read (1 turn), Household mutation/readback (4 turns, 2
mutations), Work task mutation/readback (2 turns, 1 mutation), Recipe pantry
composition (3 turns), empty Memory (1 turn), and populated Memory (1 turn).
Across these runs there were zero false successes, raw final Results, duplicate
delivery, or abrupt EOFs; mutation readbacks and reload checks passed wherever
required. A Recipe expiring-composition attempt was correctly classified as
`ENVIRONMENT_FAILURE` because the reused disposable stack already contained a
different seeded recipe and its precondition rejected the contaminated count.
No owner deployment or owner data was changed.

## Asset collection-property paraphrase checkpoint — `20d07aef` (2026-08-29)

Owner testing found two related Asset usability defects. “What's the RAM in my
machines?” narrowed to the last Asset through conversational detail-reference
logic, and “RAM across my PCs?” produced model prose instead of the
deterministic canonical projection. Collection nouns now suppress singular
reference narrowing, and bare collection-property phrasing is marked as an
explicit owner-state read. Focused intent coverage passed `332` tests.

Exact candidate `odysseus:candidate-20d07aefc170` carries source marker and OCI
revision `20d07aefc170ebd80219a97055939c549cfe5654`. Fresh authenticated GUI
acceptance for `OWNER-ASSET-RAM-001` passed all three natural prompts with
three deterministic canonical reads: Atlas 64 GB and Erebus 128 GB. It had
zero false success, raw final Result, duplicate delivery, or abrupt EOF; the
isolated runtime had zero restarts. Owner runtime remains source `34ced247`
and was not changed.

## URL Recipe replay-idempotency checkpoint — `4c2c9f23` (2026-08-29)

Owner testing found that an approved URL Recipe import could execute twice
across stream replay, leaving two canonical rows while the conversation still
looked successful. `commit_import` now treats owner + source URL + normalized
recipe name as an idempotent import identity and reuses the verified canonical
row on replay. Focused Recipe/ACI/replay coverage passed `49` selected tests.

Exact candidate `odysseus:candidate-4c2c9f236d98` carries source marker and OCI
revision `4c2c9f236d9839826bf720592838d49fb4726c23`. The fresh authenticated
GUI scenario `OWNER-RECIPE-URL-IMPORT-COMPLETE-001` passed three turns (import,
list, show), one chat mutation, two independent readbacks including reload,
and zero false success, duplicate delivery, raw final Result, or abrupt EOF.
Independent SQLite readback found one `Acceptance Budget Chili` row for the
source URL. The isolated runtime had zero restarts. Owner runtime remains
source `34ced247` and was not changed.

## Qualitative Recipe review-safety checkpoint — `9703eeb4` (2026-08-29)

Owner testing found that an incomplete text Recipe save with “salt to taste”
and “oil as needed” reached `manage_recipes.add` with an empty model-supplied
name and exposed a low-level validation error. The mutation boundary now
marks incomplete text proposals for review and fails closed with an explicit
“Nothing was saved” explanation; it does not invent quantities or persist
state. Focused ACI/Recipe/projection coverage passed `113` tests.

Exact candidate `odysseus:candidate-9703eeb42ba6` carries source marker and OCI
revision `9703eeb42ba6391959e0ee91fe550219815029a1`. The authenticated GUI
scenario `OWNER-RECIPE-QUALITATIVE-REVIEW-001` passed with one attempted chat
mutation, two independent canonical count readbacks including reload, and
zero false success, raw final result, duplicate delivery, or abrupt EOF. The
isolated runtime had zero restarts. Full human correction/validated commit
review UI remains open; owner runtime remains source `34ced247` and was not
changed.

## Copied Recipe webpage-paste checkpoint — `141e0728` (2026-08-29)

Owner testing found that a normal copied recipe page could route to the
Household read path when its surrounding text mentioned a cooking site, and
standalone `Ingredients`/`Instructions` headings were not accepted by the
text extractor. The shared intent precedence and bounded page-text extractor
were repaired; numeric ingredients remain validated before persistence.
Focused Recipe/owner coverage passed `60` tests. Exact candidate
`odysseus:candidate-141e072873af` has source marker and OCI revision
`141e072873afd48ec6d213ddef9c624a8509f66d`.

The exact candidate passed the authenticated GUI scenario
`OWNER-RECIPE-COPIED-WEBPAGE-PASTE-001`: two turns, one chat mutation, two
independent canonical readbacks including reload, two terminal `[DONE]`
events, and zero false success, raw final result, duplicate delivery, or
abrupt EOF. The isolated runtime had zero restarts. Qualitative-only
ingredients remain a separate review-flow acceptance gap; no quantity was
invented. Owner runtime remains source `34ced247`; it was not rebuilt or
changed.

The post-fix shared regression completed at the docs-only descendant with
`6966 passed, 7 skipped`; frontend static verification, realistic browser
acceptance, and window dogfood also passed. This does not close the remaining
qualitative-ingredient or fresh-install acceptance work.

## Work paraphrase routing checkpoint — `9c3d2acb` (2026-08-29)

Owner testing found that “What's outstanding for me?” fell through to model
prose even though equivalent Work questions used the deterministic overview
read. The shared intent compiler now recognizes bounded personal
outstanding/remaining phrasing while preserving Household phrases such as
“what's left in the freezer?”. Paraphrase and owner-contract focused coverage
passed `147` tests. Exact candidate `odysseus:candidate-9c3d2acb6585`, image
`sha256:92a05b2f8f31a7b0aa798581e7d619c505761098a71bc0bf054dbaab315acfc5`,
has matching OCI revision/source marker.

The exact candidate passed the three-turn Work overview journey through the
authenticated browser with three deterministic final answers, three terminal
`[DONE]` events, two independent canonical readbacks, and zero false success,
raw final result, duplicate delivery, or abrupt EOF. Owner runtime remains
source `34ced247`; it was not rebuilt or changed.

## Work project mutation result-boundary checkpoint — `b8b340c0` (2026-08-29)

Owner-journey testing found a genuine Work mutation defect: chat project
creation persisted the canonical project, then failed with
`UnboundLocalError` before returning its verified Result because the binding
constructed its result only in the task branch. The generalized binding fix
and executor regression were pushed at `b8b340c0e49fcde4a0c1fb646637f6059df0d915`.
Focused Work/ACI/owner-contract coverage passed `18` tests. Exact candidate
`odysseus:candidate-b8b340c0e49f` has image
`sha256:b7493580163c12a01e004921b6247d15a34bae9ac1c8ba4e251175b309b03eec`;
OCI revision, source marker, and pushed source match.

The exact candidate passed clean isolated browser Work project creation with
one chat mutation, two canonical readbacks including reload, one verified
human-readable final answer, and zero false success, raw final result,
duplicate delivery, or abrupt EOF. Clean isolated Household mutation passed
four turns / two mutations / two independent readbacks; clean Recipe chat
mutation passed three turns / one mutation / two readbacks. Empty Recipe,
Memory, and Work reads also passed. An earlier empty-Recipe replay was
correctly classified as stale fixture state because its disposable database
contained two prior recipes; an earlier Work task ambiguity was likewise
caused by duplicate fixture projects. The strict task runner expectation was
temporarily corrected and restored to the registry's approval-free semantics;
the clean exact-candidate stream itself showed verified task creation, but that
invocation is not counted as a formal runner PASS. Owner deployment remains
unchanged at source `34ced247`; no owner data was touched.

## Current-head regression and fresh-install isolation — `b2b14765` (2026-08-29)

The supported project environment reran the full current-head regression after
the Compose isolation correction and CI assertion update: `6963 passed, 7
skipped` in `221.67s`. The earlier single failure was a stale test expectation
for the intentionally active `hades-v1-productization` push trigger; no
product behavior failed. The host `pytest` command is absent, but
`./venv/bin/pytest` is the authoritative project runner.

The exact executable candidate for the Compose change was built from
`3df6d9d6d6497e5f1445b2c1adaf032e96caf0b7` as
`odysseus:candidate-3df6d9d6d649`, image
`sha256:14e6da5cc932ece0bb29cfc6c92aa261dff98d75794a0c00edf916bcd63fe1dd`;
its OCI revision and `/app/.odysseus-source-commit` matched. A later
test/documentation-only descendant is `b2b14765`; the owner deployment was
not changed. The isolated fresh rehearsal was healthy, logged in normally,
reloaded, restarted, and verified Qwen3:8B from the Hades namespace. The
productization branch remains 303 commits ahead of `origin/main`; merge
reconciliation and explicit merge authorization remain outstanding.

## Isolated Docker Chroma backup/restore rehearsal — `8da4fe5d` (2026-08-29)

An explicit temporary Docker volume was populated with representative vector
state, archived with the documented Alpine volume procedure, deliberately
drifted, and restored. The marker and index entry returned and the drift file
was absent after restore. The temporary volume/archive were removed. This
closes the isolated volume-procedure rehearsal; live owner Chroma was not
touched. Application data and Docker Chroma remain separate backup artifacts,
as documented in `docs/backup-restore.md`.

## Isolated fresh-install Compose checkpoint — `2c37478a` (2026-08-29)

The fresh-install rehearsal found and closed a parallel-install/rehearsal
failure in Compose: SearXNG, ChromaDB, and ntfy host bindings were not all
overridable, and the default network name was shared across Compose projects.
Base and GPU Compose files now expose port overrides and
`ODYSSEUS_NETWORK_NAME`. A new isolated project with separate data, volumes,
network, ports, and a normal first-run `fresh-owner` account booted healthy,
logged in through the real browser login route, reloaded successfully, and
survived an app restart with zero app restarts. Qwen3:8B was verified from the
Hades container namespace at `http://host.docker.internal:11434`. This is
fresh-install evidence only; the literal Compose build carried `unknown`
source provenance, so exact release evidence still requires the candidate
build loop with an embedded pushed SHA. Owner data/deployment was untouched.

## Exact Recipe browser verification — candidate `c734628f` (2026-08-29)

The isolated authenticated browser lane exercised the exact candidate image
`odysseus:candidate-c734628f` through normal login, real `/api/chat_stream`,
Qwen3:8B, Recipe URL import, canonical persistence, and reload readback. It
passed `3/3` streams and `[DONE]` events, with `1` mutation, `2` canonical
readbacks, `falseSuccess=0`, `rawFinalResults=0`, `duplicateDelivery=0`, and
`abruptEOF=0`. OCI revision and `/app/.odysseus-source-commit` matched
`c734628f787d147f1e5ae0d4efeffc07a1dbd3c6`. The host-side runner was the
evaluator-only health-wait descendant `a3c20aef`; this does not claim that
candidate's evaluator code was embedded in the product image. The owner
deployment was not changed.

## Recipe editor / acceptance readiness — `a3c20aef` (2026-08-29)

The productization branch now presents Recipe creation with repeatable,
labeled ingredient rows and deterministic client-side quantity validation,
while retaining the existing InventoryService recipe owner and canonical
payload. Focused Recipe/UI/owner-contract tests passed `81`; the exact
candidate image built from `c734628f` matched its OCI revision and source
marker. A fresh isolated stack showed that FastEmbed initialization can delay
health beyond the browser runner's former 60-second window; the existing
runner now has a bounded configurable 30–300 second wait, default 180 seconds.
The isolated stack was torn down, credentials were temporary, and the owner
deployment was not changed. Browser acceptance against the branch tip remains
unverified, so this is not a live product PASS.

## Owner-language corpus expansion — `0f5a0988` (2026-08-29)

The black-box owner journey corpus now exercises equivalent Work overview
phrasing (outstanding work, still working on, and outstanding for me) and
equivalent Asset RAM phrasing (RAM in machines and RAM across PCs). Each
variant retains the same canonical action, tool binding, deterministic answer
source, and fixture facts. The owner-journey/deterministic validation passed
`83` tests; the preceding RAM corpus change passed `30` tests. These are
evaluator-only changes and do not require an image rebuild.

The Recipe maturity ledger also records the already-tested bounded YouTube
metadata/transcript evidence path through the existing RecipeDraft and
Inventory Service owners; its focused coverage passed `3` tests. The exact
deployed executable remains source `87dab0ff`; current branch HEAD is
`0f5a0988` and the owner deployment was not changed.

## Network freshness renderer checkpoint — `87dab0ff` (2026-08-29)

The authenticated browser lane exposed that a successful canonical
`read_network_observations` Result was rendered without its freshness
qualification. The deterministic Network renderer now carries the bounded
canonical freshness value into readable prose (without exposing raw Result
keys); if only node-level freshness is available, it uses that single shared
value. Focused ACI/Recipe coverage passed `58` tests, including the new
freshness regression.

The exact candidate `odysseus:candidate-87dab0ff5bc0` was built with OCI
image digest
`sha256:6d0a1036e7f4ca68004f852bbafbf109ee189aa63ac44da42d5c34c089f73040`.
The disposable runtime marker matched `87dab0ff5bc0097c46d29628d5e93cfbbb8cc35c`,
health was healthy, restart count was `0`, and Qwen3:8B was reachable from the
container namespace. The owner deployment was not changed.

After correcting the browser oracle so legitimate `Freshness:` prose is not
classified as raw JSON, the authenticated browser smoke passed `7/7` turns
(`1` Network tool card plus `1` human-readable final answer, `7` `[DONE]`,
zero raw-final-result, false-success, duplicate-delivery, and abrupt-EOF
failures). The data-driven URL Recipe import scenario then passed `3/3`
turns, including normal approval, canonical mutation readback, reload
readback, and `3` terminal `[DONE]` events. Browser execution used the host
test harness at branch descendant `87b1f28d`; the executable image remained
the exact `87dab0ff` candidate.

The supported full regression was rerun from the current checkout after
recovering space from two exact disposable test trees: `6953 passed, 5
skipped` in `218.18s`, with no test failures. This is source/evaluator
evidence for executable source `87dab0ff` plus browser-only evaluator commit
`87b1f28d`; the branch tip is a documentation-only descendant and the owner
deployment was not changed.

## Recipe URL argument projection verification — `4f5c235f` (2026-08-29)

The exact URL request with the explicit display name was recompiled and
projected through the canonical ACI path. The `IntentFrame` retained
`recipe_source_url` and `recipe_requested_name`; `resolve_intent` selected
`manage_recipes/commit_import`, and the projected payload retained both
values. The focused Recipe/ACI suites passed `58` tests. An authenticated
HTTP/SSE replay against the exact candidate also emitted the sealed payload
with both fields intact; execution stopped at the normal `write_private`
approval gate, with no mutation or false success. This disproves the former
`{"action":"add"}` argument-loss path on the deployed candidate.

The replay had one terminal `[DONE]`, no abrupt EOF, and no duplicate
finalization. Browser proof remains separately blocked by Chromium
`ERR_INSUFFICIENT_RESOURCES` before the composer loads, including on a fresh
disposable data root; no browser product result is inferred from that run.

## Recipe shopping UI/API checkpoint — `4f5c235f` (2026-08-29)

The existing recipe detail route now exposes the deterministic
`shopping_requirements` read through the existing Inventory Service owner.
The Recipe detail UI presents missing ingredients or the recorded
availability state as a readable secondary section instead of making raw
structured output the primary surface. No new store, router, or authority was
added. Focused UI/Recipe/binding/journey coverage passed `71` tests; the full
current-source regression subsequently passed `6952 passed, 5 skipped`.

The exact disposable candidate `odysseus:candidate-4f5c235f804a` has image
digest
`sha256:f0fa9396076c3acfa089afe2d5de92e3122c156ba96008726ba5f9f953df34ac`.
Its OCI marker and running source match
`4f5c235f804af36aab0c8327d61879497bdf51c9`, health is healthy, and restart
count is `0`. The owner deployment was not replaced. Qwen3:8B is currently
unavailable from the configured Hades container endpoint, so live model and
browser evidence remain unverified for this checkpoint.

The endpoint was subsequently verified from the candidate namespace after a
disposable-only bridge correction: `host.docker.internal` was mapped to the
host's actual Ollama listener at `172.18.0.1:11434`. Qwen3:8B was listed with
digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`,
and the existing authenticated HTTP live runner completed `3/3` core cases
with `0` abrupt EOF, `0` duplicate delivery, `0` internal leaks, and exactly
one terminal event per case. The full Playwright lane remains unverified: its
session-reload page crashed reproducibly while loading static resources;
minimal equivalent Playwright login/session/reload smoke passed. This is
retained as a browser-environment/harness blocker, not a product pass.

The follow-up harness checkpoint `f0198202` adds the standard headless GPU
disable flag and its source regression passes. A fresh disposable retry still
crashed at the authenticated session reload before the first chat turn;
therefore browser acceptance remains `UNVERIFIED` and is not counted as a
product pass. The same candidate's authenticated HTTP live runner completed
`3/3` core cases with Qwen3:8B, zero abrupt EOF, zero duplicate delivery,
zero internal leaks, and one terminal event per case. The browser crash is
tracked separately from that successful HTTP/SSE evidence.

## Latest branch checkpoint — `bb27c5c4`

The productization branch is synchronized with `origin/hades-v1-productization`
at `bb27c5c4601299461be76de2f9d8350ced305de9`; the worktree is clean. This
latest checkpoint is evaluator/documentation-only: it adds seeded sampling
coverage proving declared continuation groups retain their prerequisite turns
and fresh-session runs do not manufacture reference context. The deployed
executable remains the previously recorded exact product candidate, so this
checkpoint has not been rebuilt or presented as new runtime evidence.

The focused Recipe/owner/evaluator slice after the checkpoint passed `266`
tests. A bounded 100-seed selector audit found no orphaned declared
continuation. The current branch is `216` commits ahead of `origin/main` and
zero behind; no merge is implied by that divergence.

## Isolated fresh-start/restart rehearsal — `d1559078` (2026-08-29)

The exact retained executable candidate `odysseus:candidate-d1559078` was
started in a new Compose project with empty bind-mounted data, logs, and host
broker directories. The first attempt was stopped before service creation by
an environment-only Docker subnet collision (`172.30.0.0/16` was already in
use). A retry selected an explicit unused `172.40.0.0/16` network and passed:
the application reported healthy, `/app/.odysseus-source-commit` matched
`d1559078a414d7f2e7a8571ebf75028126121632`, normal first-run admin login
succeeded, and the authenticated session remained valid after an application
restart. Restart count was `0` before and after; post-restart health was
healthy. Only the disposable Compose project and temporary directories were
removed. This is fresh-start/bootstrap and restart durability evidence; it
does not claim empty-state suite journeys or owner-data behavior.

## Fresh empty-state browser Recipe journey — `d1559078` (2026-08-29)

Using a separate disposable Compose project and the exact retained candidate,
the normal first-run admin login registered the local Qwen endpoint, then the
existing gated non-admin acceptance principal authenticated through the real
login UI. The browser created a complete Recipe through natural-language chat,
read it back through chat, reloaded the conversation, and read it back again.
The result was `3` turns / `3` streams, `1` chat mutation, `2` canonical
readbacks, and `3` terminal `[DONE]` events. False success, raw final result,
duplicate delivery, and abrupt EOF counts were all `0`. The disposable
principal, credential, project, volumes, and temporary state were removed.
This proves the fresh empty-state Recipe mutation/readback lane on the
retained executable; it is not owner-data evidence and does not cover all
empty-state suites.

## Household browser fixture callback correction — `d1559078`

The isolated Household journey initially exposed a browser-harness setup
defect: `seedHouseholdAcceptanceState` destructured an argument its caller did
not provide, so the run failed before chat execution. The callback now accepts
no unused argument, and the static browser regression covers that invocation
shape. Replayed against the exact retained candidate, the four-turn
natural-language add/read/use/read journey passed with two canonical mutation
readbacks, four terminal `[DONE]` events, and zero false-success, raw-final-
result, duplicate-delivery, or abrupt-EOF failures. The earlier failure was
evaluator infrastructure, not product behavior; the disposable deployment
and all temporary credentials/state were removed.

The same exact retained candidate also passed the fresh realistic-messy Asset
browser journey `OWNER-ASSET-FILTER-NO-MATCH-001`. Its disposable canonical
fixture included incomplete and duplicate-like records; the natural-language
RTX 4090 filter completed with one human-readable answer and one `[DONE]`,
with zero raw final results, false success, duplicate delivery, or abrupt EOF.
The fixture database, acceptance principal, and disposable deployment were
removed. This is isolated Asset product evidence, not owner-inventory
evidence.

The paired positive Asset property journey `OWNER-ASSET-RAM-001` also passed
against the exact retained candidate in a fresh isolated deployment. The
Atlas/Erebus canonical fixture was seeded through the existing Asset owner;
the natural-language RAM aggregation returned one human-readable answer and
one `[DONE]`, with zero raw final results, false success, duplicate delivery,
or abrupt EOF. Together with the no-match RTX 4090 journey, this covers both
bounded positive property projection and fail-closed negative filtering in the
browser lane. The disposable database, principal, credentials, and containers
were removed afterward.

## Recovery and backup focused gate — `c1a5e4e4` (2026-08-29)

The current branch recovery slice passed `31` focused tests: backup import
ownership/deduplication, archive/restore CLI security, skill import handling,
unreadable-memory preservation, scheduler restart behavior, and task
cancellation. This supplements the isolated application-data backup/restore
rehearsal already recorded above. No owner data or volumes were used, and no
executable source changed, so the exact product image was not rebuilt.

## Fresh empty-state Memory and Work browser reads — `d1559078` (2026-08-29)

Two additional fresh disposable Compose projects exercised the existing
authenticated browser harness after normal first-run admin setup and Qwen
endpoint registration. The empty Memory journey and empty Work journey each
completed one natural-language owner read with one human-readable final
answer and one terminal `[DONE]`. Both reported zero raw final results, false
success, duplicate delivery, and abrupt EOF. Acceptance credentials, volumes,
and projects were removed after each run. These are isolated empty-state
product checks, not evidence about the owner's accumulated data.

The current-tree supported full regression at this checkpoint completed
`6945 passed, 5 skipped` in `212.46s`. This run includes the evaluator
selection regressions above. The five skips remain documented test skips; no
product failure was observed. Because this checkpoint changes only tests and
documentation, the previously verified executable candidate was not rebuilt
or redeployed.

The existing non-mutating realistic browser acceptance lane also passed at
this checkpoint (`browser_realistic_acceptance: PASS`). It exercises shared
window/layout, Household/Recipe surfaces, long-content containment, and
responsive narrow/mobile behavior against the local healthy application. It
does not replace authenticated owner-journey evidence.

The current branch also passed frontend static verification
(`npm run test:frontend`) and the existing windowed browser smoke
(`browser_window_dogfood: PASS`). These are UI/release checks only and do not
claim authenticated owner-state acceptance.

## Current productization checkpoint — `f60d9334`

- Branch `hades-v1-productization` is synchronized with its remote at docs
  head `f60d93341dec4212701a5c014bcd940c9aec2e4e`; the worktree is clean.
- The latest executable checkpoint is `8976228f1f5129db2cc9f2496dbb3d9b39bab7a0`.
  Its exact candidate `odysseus:candidate-8976228f` was verified in a
  disposable runtime as image
  `sha256:e92b27ffe5130f510666327881ca128d473183c4c3567065eebcf91ba1d03b40`.
  OCI marker, image label, and running source matched; health was healthy and
  restart count was zero. Qwen3:8B was reachable from the Hades container
  namespace.
- The executable change exposes explicit operation/result/store metadata for
  canonical Work reads while preserving WorkEngine status inference and empty
  results. Supported-container focused ACI/binding/intent coverage passed
  `241` tests. A later Tier 1 cross-suite source-mounted run passed `65`
  tests against the current checkout. The last authoritative full regression
  remains `6934 passed, 6 skipped`; it predates this small Work metadata
  change and is not relabeled as current-head evidence.
- A current-tree full regression run completed `6935 passed, 5 skipped` with
  one environment setup failure in `test_blocks_symlink_into_ssh`: the
  source-mounted checkout was intentionally read-only, so the test could not
  create its temporary `/app/.ssh` target. The same confinement file passed
  `25 passed` from a temporary writable checkout with isolated data/log/.ssh
  mounts. This remains an environment classification, not a hidden product
  pass or a changed security expectation.
- Owner deployment was not replaced. No owner data, credentials, or volumes
  were changed. The branch remains in productization stabilization; this is
  not a merge or release declaration.

## V1 blockers

None currently evidenced in the deployed core control plane. Security, owner
scope, exact approval, durable continuation, canonical reads, fallback
authority, and rollback invariants remain covered by the current focused/full
gates.

## Owner journey acceptance expansion

The legacy browser smoke lane remains unchanged. A supplemental data-driven
black-box lane is now defined in `benchmarks/hades_owner_journeys.json` and is
run by `test:browser:owner-journeys` against an isolated acceptance deployment.
It covers canonical Asset/RAM and filtered reads, Network, empty Recipe reads,
chat-driven Recipe mutation/readback, and chat-driven Household mutation/
readback. Expectations are evaluator-only; they are not supplied to routing or
model prompts. Mutation scenarios refuse to run without an external isolated
acceptance credential, preventing accidental writes to the owner instance.

The lane is prepared and contract-tested; live execution remains a separate
acceptance result and is not claimed by this documentation-only checkpoint.

To run the synthetic profiles, the operator must provide a disposable
isolated deployment and set `HADES_BROWSER_ISOLATED_ACCEPTANCE=true` together
with `HADES_BROWSER_EXTERNAL_CREDENTIAL_FILE`; the runner will not provision
or use the current owner Compose volumes for those cases. The
`actual_owner_read_only` profile remains a separate explicitly supplied
read-only smoke lane.

The lane now refuses synthetic scenarios unless the operator explicitly marks
the deployment as isolated (`HADES_BROWSER_ISOLATED_ACCEPTANCE=true`) and
supplies an external acceptance credential. Per-turn action/tool-binding
expectations are mandatory, semantic oracles support required-all facts, and
recipe/household mutations perform independent allowlisted canonical GET
readback before and after browser reload. The acceptance output reports
scenario/turn/read/mutation/readback/DONE/EOF counts. Checkpoint
`c1e9aa72` is evaluator/docs-only; the deployed executable remains `34ced247`.

## V1 RC fixes and evidence

### Browser acceptance synchronization — `78a79bde`

The empty-state Recipe browser regression passed on the disposable candidate
after the runner began waiting for the explicitly created session to be
selected and for application/history hydration to settle before submitting
the first turn. This is a generic startup synchronization fix; it preserves
the strict user-message, final-answer, persistence, and terminal-DONE
assertions. `OWNER-RECIPE-EMPTY-001` completed through normal login and
`/api/chat_stream` with one human-readable deterministic answer, one persisted
turn, one `[DONE]`, zero raw-final results, zero duplicate delivery, and zero
abrupt EOF. The owner deployment was not changed.

| Item | Status | Evidence |
|---|---|---|
| Deterministic Memory/Work/Assets/Network/Service reads | green | source tests; deployed Qwen E5 matrices |
| Asset ordinal continuation | focused and authenticated live green | route no longer materializes asset `get` without strong identity; source `dcb57621`; live core `assets_list` and ordinal continuation green |
| Durable Continue terminal-state handling | green | `177` focused tests; live Continue resumed with zero tool calls |
| General MODEL_FALLBACK | green | focused security/fallback gates; live ordinary-question cases |
| Conceptual explanation routing | focused green, deployment pending | `17cbbb97`; RAID/backup explanations no longer enter `storage_ops`; direct fallback diagnostics are initialized safely |
| Infrastructure failure normalization | green | executor/projection focused gates preserve unavailable/invalid status; host-operator reads now expose canonical success/failure status |
| Exact approvals and policy boundaries | green | security/control-plane suites; live unauthorized-scan case |
| Deployment provenance and rollback | green | runtime source match `074d240f`; rollback `odysseus:rollback-b471e104-prev` |
| Automated live Qwen canary | E5A core slice green | fresh isolated normal-auth acceptance runtime, synthetic `hades-acceptance`, real qwen3:8b; core `8/8`, no internal leaks |
| Authenticated automated fuzzing | E5A partial/current | `scripts/hades_live_fuzz.py`; disposable Chroma/state, real login/chat/control plane; core `8/8`, held-out sample `20/22`, full regression `6535 passed, 3 skipped`; remaining failures are Work paraphrase direct-routing and network deep-dive disposition |
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

### Productization owner-journey checkpoint — 2026-08-28

- Branch `hades-v1-productization` is pushed at `171e61af0738`; worktree is
  clean. The executable candidate `odysseus:candidate-e140a0accc52` embeds
  `e140a0accc525646c42eb674027cbac436e9a4c7` and runs only in the disposable
  owner-journey Compose project; the owner deployment remains on `34ced247`.
- Exact isolated browser evidence: empty Recipe read passed; complete recipe
  CREATE executed `manage_recipes.add`, persisted/read back the recipe, and
  rendered one deterministic human answer plus one `[DONE]`. The prior false
  success is closed on this candidate.
- The browser harness now records nested tool completion outcomes and does not
  mistake a tool card for a successful effect. Household `add_item` currently
  fails closed because the existing canonical action has no initial-stock
  semantics; this is a product capability gap, not a green acceptance result.
- The isolated Network/Asset lanes still require their declared fixture
  profiles. No owner data was modified. Full browser owner-journey acceptance,
  current owner deployment, and merge readiness remain pending.

- Branch: `hades-aci-v1`, synchronized with `origin` at `dcb57621` after the
  bounded upstream harvest and asset-reference fix.
- Source head: `dcb57621`; deployed runtime implementation is source-matched
  at `dcb576219516`, with the peak-aware build guard retained.
- Running image: `odysseus:candidate-dcb576219516`, source-matched and healthy.
- Last full regression before the latest fallback/runtime source slice:
  `6492 passed, 3 skipped, 186 warnings` in 123 seconds. Later focused gates:
  `210 passed` for fallback/control-plane behavior and `198 passed` for
  security/authority coverage.
- Current source-tip full regression: `6535 passed, 3 skipped, 186 warnings`
  in 230.81 seconds. Authenticated core live evidence is E5A; owner E6 remains
  supplemental.
- Current matched Qwen3:8b probe: raw `3.659s` vs Hades `5.462s` at a
  16-token cap; delta `1.803s`, including `0.218s` framework preparation and
  one Hades model call with zero tools/index lookups. Diagnostic only.
- Current agent-loop/provider transport gate: `101 passed`.
- Current telemetry/reference gate: `97 passed`.
- Storage: 77% used / 22 GiB free after removing superseded candidates and
  disposable acceptance containers/volumes.
  The peak-aware preflight reports CAUTION but permits only when projected
  growth preserves a 12 GiB emergency reserve; no further build is currently
  planned.
  Current, rollback, and live-auth images remain retained; no owner data,
  databases, volumes, backups, or model blobs were removed.
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

## Productization checkpoint — `65d61e9a` (2026-08-29)

- Added deterministic projection/rendering for successful canonical Homelab
  `service_status` reads, closing the observed gap where non-empty service
  health could fall through to unconstrained synthesis.
- Focused supported-container tests: `99 passed`, one SQLAlchemy deprecation
  warning.
- Exact candidate: `odysseus:candidate-65d61e9a1b65`, image
  `sha256:2aca24361b21f5e9876b25f89c7b4cace7803728e67b0a115a74893b14a1dd0b`;
  OCI marker and running source match the pushed SHA; health healthy; restart
  count `0`.
- Qwen3:8B was verified from the candidate container namespace at the
  configured host-gateway endpoint; digest
  `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- The prior authoritative full-regression result remains `6935 passed, 5
  skipped, 1 environment setup failure`; the isolated affected confinement
  suite passed `25`. This checkpoint did not rerun the full suite.
- Owner deployment remains unchanged; browser/live owner acceptance against
  this candidate remains separate evidence.

## Productization checkpoint — `fe7b6b74` (2026-08-29)

- Extended the existing canonical Homelab service renderer to target-qualified
  `service_status` reads, preserving bounded subprocess evidence instead of
  falling through to model synthesis.
- Focused supported-container tests: `100 passed`, one SQLAlchemy deprecation
  warning.
- Exact candidate image: `odysseus:candidate-fe7b6b74`,
  `sha256:1e20b8d3136cc4ea43b978f428ad115351f8bd12886b902fb19bb0a1b63c955f`;
  marker/OCI label/running source matched the pushed SHA; health healthy;
  restart count `0`.
- Qwen3:8B remained reachable from the candidate container namespace with
  digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- The prior full-regression evidence remains `6935 passed, 5 skipped, 1
  environment setup failure`; this checkpoint did not rerun the full suite.
- Owner deployment remains unchanged.

## Productization checkpoint — `d41c67fc` (2026-08-29)

- Closed the demonstrated Asset RAM owner-journey defect. `how much` is now
  included in the shared explicit-read predicate, so collection property reads
  cannot silently fall through to model-only prose.
- Focused owner/core suite: `535 passed, 2 skipped`.
- Full current-source suite: `6931 passed, 6 skipped`, with six
  storage-preflight environment failures because the source-mounted container
  did not contain `/home/.docker-data`; no product test failures were observed.
- Pushed source and candidate: `d41c67fcbc5e04dd932712beaf049389a5e1d4d5`,
  `odysseus:candidate-d41c67fc`, image
  `sha256:310bdcb9c37e6f1aa0533593ff2160f60e09a3b92a06319b7a9f90b97784f32c`.
  OCI marker/source matched; candidate health was healthy; restart count `0`.
- Browser acceptance against the exact disposable candidate passed the RAM
  property journey with canonical `manage_assets/list`, deterministic answer,
  correct Atlas/Erebus values, one persisted answer, and one `[DONE]`.
  Qwen3:8B was reachable from the candidate namespace. Disposable acceptance
  principal/container were removed; owner deployment was unchanged.

## Productization live Recipe checkpoint — `d41c67fc` (2026-08-29)

- Exact candidate browser acceptance passed the empty Recipe read with one
  deterministic human answer, one persisted answer, and one `[DONE]`.
- Chat-driven Recipe mutation/readback passed `3/3` turns: creation entered
  through natural-language chat, canonical readback found the recipe, and the
  recipe remained after reload. The run had `2` readback checks, `0` false
  successes, `0` raw final results, `0` duplicate delivery, and `0` abrupt EOF.
- Candidate source was `d41c67fcbc5e04dd932712beaf049389a5e1d4d5`, image
  `sha256:310bdcb9c37e6f1aa0533593ff2160f60e09a3b92a06319b7a9f90b97784f32c`;
  OCI/source marker matched, health was healthy, and restart count was `0`.
  Qwen3:8B was reachable from the candidate namespace. The disposable
  acceptance principal and credential were revoked/removed; owner deployment
remained unchanged.

## Productization Asset filter checkpoint — `d41c67fc` (2026-08-29)

- The exact disposable browser/chat journey for `Which of my servers has an
  RTX 4090?` passed against incomplete/duplicate-like synthetic canonical
  assets with no 4090. It used `manage_assets/list` and returned a bounded
  deterministic no-match answer with no invented server or raw JSON final.
- The run had one persisted answer, one `[DONE]`, zero raw final results,
  zero duplicate delivery, and zero abrupt EOF. No executable source changed;
owner deployment remained unchanged.

## Productization Recipe coverage checkpoint — `d41c67fc` (2026-08-29)

- Stateful browser/chat acceptance passed Recipe list followed by the
  pronoun/reference continuation `Can I make that recipe?`.
- The second turn used canonical `read_recipes/can_make` pantry coverage and
  deterministic rendering. Two streams produced two final answers and two
  `[DONE]` events, with zero raw final results, duplicate delivery, or abrupt
  EOF. No executable source or owner deployment changed.
- Meal-plan mutation remains explicitly deferred until Recipe read/composition
  coverage is broader and green.

## Productization Household checkpoint — `d41c67fc` (2026-08-29)

- Chat-driven Household mutation/readback passed `4/4` turns on the exact
  candidate: add three synthetic cans, read quantity, consume one, and read
  the remaining quantity after reload.
- The run had `2` canonical mutations and `2` readback checks, one persisted
  answer and one `[DONE]` per turn, zero false successes, zero raw final
  results, zero duplicate delivery, and zero abrupt EOF.
- This was isolated synthetic state using the existing Inventory Service; the
  acceptance principal was revoked/removed and the owner deployment remained
  unchanged.

## Productization URL import checkpoint — `d41c67fc` (2026-08-29)

- The live URL Recipe journey reached `manage_recipes/commit_import` through
  normal authenticated browser/chat execution and approval handling.
- The source contained an unquantified `salt and pepper` ingredient, so the
  canonical importer correctly returned review-required failure and explicitly
  said no recipe was saved. It emitted one `[DONE]` with no false success,
  invented quantity, or persistence claim.
- This confirms incomplete imported drafts fail closed. Complete URL import
  acceptance remains pending; no executable source or owner deployment changed.

## Productization Work projection checkpoint — `7c54a485` (2026-08-29)

- Fixed the demonstrated Work owner-answer disappearance: a successful
  `read_work` result could exceed the display envelope and leave the
  deterministic renderer with truncated JSON. The canonical projection now
  preserves bounded collection counts before display/history truncation.
- Focused supported-container tests: `77 passed`.
- Pushed source: `7c54a4859c9503dd264bd2e1459354f16321ef98`.
- Exact candidate: `odysseus:candidate-7c54a485`, image
  `sha256:4c1c70ed79502e482378310c27e6c680182c1a52a8624b579bc063cebac3f78e`;
  OCI marker/source matched, health was healthy, and restart count was `0`.
- Exact disposable browser acceptance for the previously failing empty Work
  journey passed: one deterministic human answer, one persisted answer, one
  `[DONE]`, zero abrupt EOF, and zero duplicate delivery. Qwen3:8B was
reachable from the candidate namespace. Disposable acceptance resources
were removed; owner deployment was unchanged.

- The authoritative supported-container full regression completed `6938
  passed, 5 skipped, 149 warnings` in `293.80s`, with exit status `0`.

## Productization Work/Recipe checkpoint — `7ea39f04` (2026-08-29)

- Exact disposable authenticated browser acceptance passed the non-empty Work
  overview against executable source `5c9e1be3465e352463479b698619663cf250be52`:
  one human-readable deterministic answer, one persisted turn, one `[DONE]`,
  zero abrupt EOF, and zero duplicate delivery.
- The browser harness now waits for asynchronous normal-login initialization
  before submitting the real login form. This is acceptance infrastructure;
  no auth semantics or owner deployment changed.
- Exact Recipe URL argument projection was rechecked with mixed read/manage
  capability visibility. The request resolves to `manage_recipes/commit_import`
  and carries the explicit requested name plus source URL. Recipe/import
  focused coverage: `46 passed`; the original `{"action":"add"}` loss was
  not reproducible on current source.
- Executable candidate remains `odysseus:candidate-5c9e1be`, image
  `sha256:96d8f900e19f0f43e2df15d07fe48da147a7d12498740cc50683643cf4cf42b`;
  OCI/source marker matched, health was healthy, restarts were `0`, and
  Qwen3:8B was reachable from the candidate namespace. Current branch/docs
  HEAD is `7ea39f044e0cde88d6d089c7ed020cd10122b2de`; this test-only descendant
  did not require a rebuild. Owner deployment remains unchanged.
- Full executable regression: `6932 passed, 5 skipped, 6 known
  storage-preflight environment failures`; the environment failures remain
  explicitly isolated.

## Recipe complete-URL mutation acceptance — `d1559078` (2026-08-29)

- Executable candidate: `odysseus:candidate-d1559078`, source
  `d1559078a414d7f2e7a8571ebf75028126121632`, image
  `sha256:3ec804a8a516deb0c9bb7e801598c70b1f7191e7a41a4cec9ab052521c38fce8`;
  OCI revision matched. This was an isolated disposable deployment; the
  owner deployment was not changed.
- Browser acceptance passed the complete URL journey through normal login,
  approval, chat-driven `commit_import`, list, and show. Requested name and
  source URL survived projection; canonical readback verified persistence
  before the deterministic success answer. Two readbacks (including reload),
  three terminal `[DONE]` events, `falseSuccess=0`, `rawFinalResults=0`,
  `duplicateDelivery=0`, and `abruptEOF=0`.
- The live SSE envelope now exposes only bounded `success`, `verified`, and
  `status` outcome scalars. Acceptance aggregates proposal and continuation
  streams for one logical turn; model prose and hidden raw Results remain
  non-authoritative.

## Current productization candidate regression — `d1559078` (2026-08-29)

- Full supported-container regression against the exact executable candidate,
  with the real storage roots mounted for the storage-preflight tests:
  `6940 passed, 6 skipped, 149 warnings` in `301.27s`.
- The same suite without those mounts produced six explicitly classified
  storage-preflight environment failures (`/home/.docker-data` absent); the
  six tests pass when the supported fixture paths are present. No product
  failure was hidden or converted into a pass.
- The current branch tip is a test/documentation-only descendant of this
  executable candidate; no owner deployment was changed.

## Household chat mutation acceptance — `d1559078` (2026-08-29)

- The isolated authenticated browser journey added three synthetic
  `Acceptance Tomatoes`, consumed one, and read the quantity back after each
  mutation through the normal chat route. No mutation was performed by a
  direct setup API.
- Result: `4` turns, `2` mutations, `2` canonical readbacks, `4` `[DONE]`,
  `falseSuccess=0`, `rawFinalResults=0`, `duplicateDelivery=0`, and
  `abruptEOF=0`, against the exact candidate image and source recorded above.
- This validates the existing Inventory Service owner for the seeded
  Household journey; fresh-install and broader Recipe/Household composition
  remain distinct release work.

## Frozen Qwen3:8B quick revalidation — `d1559078` (2026-08-29)

- The exact executable candidate ran the bounded `quick` tier from the Hades
  container namespace against `qwen3:8b`: `62/62` functional, `62/62`
  architectural, `62/62` security, duplicate rate `0`, and reference
  resolution `1.0`.
- Measured `model_calls/task=0.2581`, `decision_calls/task=0`,
  `failed_actions/task=0.0161`, median latency `0.0271s`, and P95 latency
  `3.9145s`. All 62 cases completed with incremental evidence; no timeout or
  provider-unavailability classification occurred.
- The report was generated against executable source
  `d1559078a414d7f2e7a8571ebf75028126121632`; subsequent branch commits are
  documentation/test-only and did not change the product image.

## Productization branch reconciliation — `38f2d048` (2026-08-29)

- `origin/main` is `364380ed3f46c1d14d3229e5b7530698cfa22e65`, the merge base
  of the productization branch, with no main-only commits. The branch is
  `190` commits ahead and `0` behind; no reconciliation conflict is pending.
- Current branch HEAD is `38f2d048`; worktree is clean and the branch matches
  `origin/hades-v1-productization`. The deployed owner runtime remains a
  separate older source and was not changed during productization acceptance.
- Merge/release is not declared: fresh-install, broader cross-suite, and
  release-candidate gates remain outstanding.

## Isolated fresh-start smoke — `d1559078` (2026-08-29)

- A disposable container was started from the exact candidate with empty
  data, logs, and broker volumes. The documented entrypoint created the first
  `admin` account and emitted a temporary credential; no owner state or
  credential was reused.
- Headless Chromium reached the real login page, authenticated through the
  normal form, and landed at `/`. After a container restart, the authenticated
  session remained valid and `/api/health` was healthy. The isolated instance
  was removed after the check.
- This is first-run/bootstrap and session-restart evidence only. Empty-state
  suite journeys, backup/restore, and a second clean fresh-fresh run remain
  release work.

## Recipe URL import acceptance checkpoint — `1c8c22a7` (2026-08-29)

- The exact isolated authenticated browser request for the named Sunday
  Supper recipe reached `manage_recipes/commit_import` and completed normal
  approval continuation.
- The source had an unquantified `salt and pepper` ingredient. Review-required
  fail-closed behavior was correct: no recipe persisted and the answer said no
  recipe was saved.
- Browser result: `PASS`, one terminal `[DONE]`, `falseSuccess=0`, zero raw
  final results, zero duplicate delivery, and zero abrupt EOF.
- Requested name and source URL remain preserved by the canonical mixed-
  capability projection regression. Complete-source persistence is still
  pending. Executable candidate remains `odysseus:candidate-5c9e1be` with image
  `sha256:96d8f900e19f0f43e2df15d07fe48da147a7d12498740cc50683643cf4cf42b`;
  test-only HEAD is `1c8c22a7`, and owner deployment was unchanged.

## Recipe complete-text mutation checkpoint — `359e518e` (2026-08-29)

- The exact isolated authenticated browser journey for a complete pasted
  recipe passed through normal chat mutation and readback: 3 turns, 2
  readbacks, and 3 `[DONE]` events.
- It reported zero false-success claims, raw final results, duplicate
  delivery, or abrupt EOF. This validates ordinary canonical `add` persistence
  independently of the URL import review case.

## Recipe import action-contract checkpoint — `3af8b2f8` (2026-08-29)

- The `manage_recipes` native schema now permits the staged `commit_import`
  payload (`action`, source metadata, and later validated `draft`) without
  incorrectly requiring primitive `add` fields. `requested_name` is explicitly
  represented in the contract. This prevents URL imports from being projected
  as an under-specified `add` action.
- Focused contract evidence: `357 passed, 1 warning`. Exact candidate image
  `odysseus:candidate-3af8b2f8` has OCI revision and
  `/app/.odysseus-source-commit` equal to
  `3af8b2f8b3c3845ff537233197ee38ac8df05e60`; isolated runtime health was
  healthy with zero restarts and Qwen3:8B visible from the container namespace.
- Browser replay was not graded: the isolated fresh data volume had no
  registered chat model endpoint, so normal session creation failed closed
  before the Recipe turn (`no usable endpoint for qwen3:8b`). This is an
  acceptance-environment readiness failure, not a product PASS. The temporary
  acceptance principal was removed and the disposable deployment was stopped.

## Full regression revalidation — `3af8b2f8` (2026-08-29)

- The complete repository suite ran in the supported project `venv` after the
  Recipe contract change: `6942 passed, 5 skipped, 186 warnings` in `215.25s`.
- The current branch tip is documentation-only relative to the executable
  candidate; no additional image build was required. Browser acceptance remains
  unverified on this candidate until the isolated deployment has a registered
  Qwen3:8B chat endpoint.

## Recipe URL browser revalidation — `3af8b2f8` (2026-08-29)

- A fresh disposable deployment registered its Qwen3:8B endpoint through the
  normal admin endpoint flow, then authenticated the gated acceptance principal
  through the normal login UI. The complete URL-import journey passed: `3`
  turns, `1` chat mutation, `2` canonical readbacks including reload, and `3`
  terminal `[DONE]` events. False-success, raw-final-result,
  duplicate-delivery, and abrupt-EOF counts were all `0`.
- The exact named Sunday Supper request also passed its review-required lane:
  `1` turn, `1` bounded failure, `1` `[DONE]`, no persisted recipe, and zero
  false-success/raw-result/duplicate/abrupt-EOF failures. The explicit name and
  source URL were retained through the projected import contract.
- Candidate image `odysseus:candidate-3af8b2f8` had OCI revision and source
  marker `3af8b2f8b3c3845ff537233197ee38ac8df05e60`, healthy runtime, and zero
  restarts. The principal, credentials, disposable volumes, and containers were
  removed after both runs; the owner deployment was untouched.

## Fresh Recipe onboarding acceptance — `3af8b2f8` (2026-08-29)

- A clean disposable Compose project was bootstrapped with no application
  state. A normal first-run admin login registered the Qwen3:8B endpoint through
  the existing admin endpoint route; the separate gated acceptance principal
  then authenticated through the normal login UI.
- The empty Recipe read plus natural-language Recipe mutation/readback journey
  passed: `2` scenarios, `4` turns, `1` chat mutation, `2` canonical readbacks
  including reload, and `4` terminal `[DONE]` events. False-success,
  raw-final-result, duplicate-delivery, and abrupt-EOF counts were all `0`.
- The acceptance principal, credential, database, volumes, containers, and
  network were removed after the run. This is isolated fresh-install evidence;
  it does not substitute for real-owner data validation.

## Backup/recovery focused validation — `69dc51af` (2026-08-29)

- Existing backup CLI security and recovery ownership tests passed in the
  supported project environment: `16 passed, 3 warnings`. Coverage includes
  safe snapshot output placement, symlink/hardlink/path traversal rejection,
  restore staging of the previous data directory, backup-import owner scope,
  and setup/readiness behavior.
- The documented Docker caveat remains: application `data/` is covered by the
  host snapshot, while Compose-managed Chroma vectors require a separate
  volume backup. A full live backup/restore rehearsal remains release work and
  was not represented as passed by this focused result.

## Isolated backup/restore rehearsal — `9d08d75d` (2026-08-29)

- The existing `scripts/odysseus-backup` CLI was exercised against a stand-alone
  temporary data tree. Snapshot creation and read-only archive verification
  both succeeded (`2` archive members).
- After deliberate SQLite/JSON drift and an extra file, `restore --yes`
  restored the original database row and JSON state, removed the drift file,
  and retained one `data.before-restore-*` rollback stash. No owner data or
  live application directory was involved.
- This validates the application-data backup/restore path. Docker Chroma
  volume backup remains a separate documented operational step.

## Bounded live Qwen candidate shard — `3af8b2f8` (2026-08-29)

- The exact candidate completed all `10/10` selected cases through the real
  authenticated HTTP/SSE path with incremental JSON evidence. Qwen3:8B was
  reached through `http://host.docker.internal:11434` from the Hades namespace;
  the candidate source marker matched and the runtime had zero restarts.
- Transport/security invariants held for every case: `answers=10`,
  `internal_leaks=0`, no abrupt EOF, no duplicate delivery, and one terminal
  event per stream. The trajectory score was `8/10`.
- `network_1` is an environment fixture classification: the disposable run
  had no host-network broker observation, so the canonical read correctly
  produced a bounded failure outcome rather than fabricated state. The
  `assets_reference` failure is an evaluator/session-selection classification:
  a continuation was sampled without its prerequisite context and therefore
  resolved no referent. Neither result supports a production semantic fix.

# Dogfood sampled-trajectory integrity checkpoint — `603b80dc`

The live dogfood selector now preserves the prerequisite turns for a declared
continuation group when a seeded bounded sample selects a follow-up. Fresh
session mode continues to strip continuation context deliberately, so it tests
the no-context behavior instead of manufacturing a reference. This closes an
evaluator integrity gap exposed by the interrupted bounded Qwen shard: an
`assets_reference` follow-up must not be scored as a product reference failure
when its `assets_list` setup turn was omitted by sampling. Focused coverage is
11 passed. This is evaluator-only; the deployed executable candidate remains
the previously recorded exact product SHA.
# Recipe shopping requirements checkpoint — `d772096f` (2026-08-29)

- Added a bounded `recipe.read/shopping_requirements` ActionSpec and explicit
  result contract over the existing Inventory Service. It computes missing
  ingredients deterministically from canonical pantry coverage and does not
  mutate inventory or create a second shopping-list store.
- Focused contract/composition/paraphrase tests: `264 passed`.
- Full supported regression: `6950 passed, 5 skipped`.
- Pushed source and exact candidate: `d772096fef17f4690d0d2e6f4dd5a10aea3f6c0e`,
  `odysseus:candidate-d772096fef17`,
  image `sha256:248f9d1d496fdda514796415d412e1958caf969732112dfea5a82476d1b9cb58`.
- Disposable runtime marker/source matched and `/api/health` was healthy with
  zero restarts. Qwen live/browser acceptance remains unverified because
  `host.docker.internal:11434` was unavailable.
# Recipe adapter parity checkpoint — `7ca4f8b1` (2026-08-29)

- The existing `ManageRecipesTool` now exposes Recipe `search` and
  `shopping_requirements` actions consistently with the canonical capability,
  schema, service, and executor.
- Focused binding/Recipe/owner-journey validation: `66 passed`.
- Exact candidate: `odysseus:candidate-7ca4f8b13245`, image
  `sha256:b0518b578b6ea97949759cce17edf579d797e76f06ab2deb6c7a021d9263c956`;
  embedded and running source `7ca4f8b132454206b68ffc6345d44eb59d303b84`.
- Disposable runtime health was healthy with zero restarts. Qwen was not
  available at `host.docker.internal:11434`, so live model/browser acceptance
  is not claimed.
# Current full-regression checkpoint — `cee5372e` (2026-08-29)

- Full supported project regression on the exact executable source passed
  `6952 passed, 5 skipped` with `186` warnings.
- The candidate remains `odysseus:candidate-cee5372e81e7`, image
  `sha256:fb8e69155d12c7d38e81d6e2131b4100df0fcbddb3411d5a602b8554798c7e9f`,
  with matching embedded/running source, healthy status, and zero restarts.
- Qwen3:8B remains unverified because the configured
  `host.docker.internal:11434` endpoint is unavailable from the Hades
  namespace; no live model/browser pass is claimed.

# Canonical Work project-create checkpoint — `93655993` (2026-08-29)

- Promoted one bounded Work mutation through the existing control plane:
  explicit project creation now resolves to `work.project.manage`, projects the
  user-supplied title, executes through `WorkEngine`, and requires canonical
  persistence/readback before the deterministic answer claims success.
- Added the existing capability/security registration and fail-closed result
  renderer; task creation remains deferred until a canonical project reference
  path is established.
- Focused ACI/binding/fence/Recipe validation: `62 passed`; full supported
  regression on the exact pushed candidate: `6953 passed, 7 skipped, 149
  warnings`.
- Exact pushed source/candidate: `9365599353e94f1be8bbbd1aa3579c89a24f9254`,
  `odysseus:candidate-9365599353e9`, image
  `sha256:4f49591d696d51bd635c988e77603edf166ab3439797e56f30b6075f4d9a7206`;
  OCI marker matches the source. This is a productization candidate and has
  not replaced the owner deployment.

# Work owner-read routing checkpoint — `da4f55ef` (2026-08-29)

- Reproduced the isolated browser failure where project creation succeeded but
  the follow-up `What projects do I have?` was submitted as plain chat and
  bypassed canonical ACI. The shared transport eligibility predicate now
  includes first-class Work read concepts (`PROJECT`, `TASK`, `GOAL`, `RUN`,
  `COMMITMENT`, `MISSION`, and `WATCH`); no phrase-specific route was added.
- Exact isolated browser journey passed on the candidate: natural-language
  create, canonical verified readback, follow-up canonical `read_work/list_projects`,
  reload persistence, `2/2` terminal DONE, zero abrupt EOF, zero duplicate
  delivery, and zero false success.
- Focused intent/ACI/binding validation: `251 passed, 3 skipped`. Full
  supported regression: `6955 passed, 7 skipped, 149 warnings`.
- Exact executable source/candidate: `da4f55efa0feedd3cacc8370ec30e5221513ef2c`,
  `odysseus:candidate-da4f55ef`, image
  `sha256:75adb96c1bc998282d7da603ed788e5338473fc9c86df45021db99a5afc84cd8`;
  OCI marker matches. The branch tip `65d09299` is evaluator-only readback
  metadata and was not rebuilt. The owner deployment remains untouched at
  source `34ced2478c014cc529775460b5a6d4350b68239c`.

# Recipe import result-projection checkpoint — `451b40cd` (2026-08-29)

- Reproduced a real URL-import failure where `manage_recipes` committed and
  verified a recipe, but its large Result was truncated before the deterministic
  mutation renderer parsed it; the owner received an error despite persistence.
- Added `manage_recipes` to the existing bounded canonical Result projection.
  The projection retains only verified mutation evidence (recipe id/name/source
  and verification status); raw ingredient/instruction payloads remain bounded
  diagnostic output. The false-success guard is unchanged.
- Focused Recipe/ACI validation: `45 passed, 1 skipped`. Exact isolated
  browser URL-import journey: `3/3` streams reached DONE, mutation and reload
  readbacks passed, zero abrupt EOF, duplicate delivery, raw final results, and
  false success.
- Full supported regression on this exact executable candidate: `6956 passed,
  7 skipped, 149 warnings`.
- Exact pushed executable source/candidate: `451b40cdbac39146c460575eaae5574a93c014b6`,
  `odysseus:candidate-451b40cd`, image
  `sha256:3939ca86e5a6cf6542934b7d9345b8c097938d6071aea7b1291a5e6d5268850d`;
  embedded marker matched. The owner deployment remains untouched.

# Recipe chat-mutation acceptance checkpoint — `451b40cd` (2026-08-29)

- Re-ran `OWNER-RECIPE-MUTATION-READBACK-001` through a fresh isolated
  acceptance deployment using the normal browser login, chat composer, real
  `/api/chat_stream`, and Qwen3:8B. The mutation was not API-seeded.
- Natural-language Recipe creation persisted canonical state, the list
  readback succeeded, and the reload readback still contained the created
  recipe. The run covered `1` scenario and `3` turns: `3` terminal `[DONE]`,
  zero abrupt EOF, duplicate delivery, raw final results, and false success.
- The first rerun was correctly rejected by the fixture precondition after a
  stale disposable bind-mounted state was reused. A subsequent fresh isolated
  state exposed an acceptance setup issue: the principal was created while
  the app process still had the default disabled flag. The app correctly
  rejected login until the disposable deployment was explicitly configured
  with `HADES_ACCEPTANCE_PRINCIPAL_ENABLED=true`; no production code change or
  auth bypass was made.
- The disposable principal, credential artifact, and stack were revoked/stopped
after the run. The owner deployment remains untouched.

# Work task chat acceptance checkpoint — `a91c1623` (2026-08-29)

- Promoted one explicit Work task mutation through the existing `manage_work`
  binding and `WorkEngine`; project resolution is owner-scoped and requires a
  unique existing project title. Canonical task persistence/readback is
  required before success is rendered.
- Exact candidate `odysseus:candidate-a91c16236f1c`, image
  `sha256:97425212ad750284393793ad0d46f7f040937c961cd3f849d9f72b876275962c`,
  embedded/running source `a91c16236f1c65e59ae5b45e85a59b1dc678aac7`, health
  healthy, restarts `0`.
- Isolated authenticated browser acceptance passed `2/2` turns with canonical
  task readbacks before and after reload, `2` `[DONE]`, zero abrupt EOF,
  duplicate delivery, raw final results, or false success. The task was
  created through chat; only the prerequisite project was setup-seeded. The
  disposable principal/state were removed afterward.

# Productization evidence-boundary correction — `558d6062` (2026-08-29)

- The suite maturity matrix now distinguishes the current documentation head
  from the latest executable browser candidates. It no longer reports Work
  task chat creation as pending: exact candidate `a91c1623` proved a
  natural-language task mutation, canonical readback, reload persistence, and
  exactly-once delivery in an isolated authenticated browser run.
- This is documentation-only. The deployed executable remains the previously
  recorded candidate; no rebuild or owner-instance deployment was performed.

# Populated Memory journey checkpoint — `2e58a5fe` (2026-08-29)

- Added `OWNER-MEMORY-POPULATED-001` to the existing data-driven browser
  corpus. It seeds two unmistakably synthetic memories through the normal
  authenticated Memory API, then grades the read through chat, canonical
  `/api/memory` readback, and reload persistence.
- Focused owner-journey contract suite: `65 passed`.
- An exact candidate was built with OCI/source marker `2e58a5fe` and started
  in a fresh isolated Compose project. The browser reached normal login but
  `/api/models` reported no usable endpoint, so no chat turn was graded.
  An in-container probe did reach `http://host.docker.internal:11434` and
  reported `qwen3:8b` digest
  `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
  Live browser status is therefore `UNVERIFIED / MODEL_DISCOVERY`, not PASS.
- The disposable principal, credential, containers, and network were removed;
  the owner deployment was not changed.

# Populated Memory browser acceptance — `2e58a5fe` (2026-08-29)

- `OWNER-MEMORY-POPULATED-001` passed against exact candidate
  `odysseus:candidate-2e58a5fe` in a fresh isolated deployment. The journey
  used normal login, Qwen3:8B through the real chat/SSE route, one populated
  Memory read, canonical `/api/memory` readback, and reload persistence.
- Result: `1` scenario, `1` turn, `1` deterministic final answer, `1` `[DONE]`,
  `0` abrupt EOF, duplicate delivery, false success, or raw final results.
- The first attempt correctly exposed missing endpoint registration in the
  fresh fixture. Registering the existing `ModelEndpoint` prerequisite with
  cached `qwen3:8b` metadata allowed the normal session path to proceed; this
  was fixture setup, not a production routing change. The in-container probe
  confirmed the configured endpoint and digest
  `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- The acceptance principal, credential, containers, and network were removed;
  the owner deployment remained untouched.

# Read-only candidate verifier — `0a9f3802` (2026-08-29)

- Added `scripts/verify_candidate.sh <sha>` for repeatable provenance checks.
  It reports local/remote source, worktree state, expected candidate tag, OCI
  revision and source marker, matching running container/source, configured
  Ollama endpoint, Qwen3:8B digest when a matching container is running, and
  an optional `/api/health` probe via `HADES_VERIFY_BASE_URL`.
- The verifier never builds, deploys, stops, mutates, or reads credentials.
  Shell syntax and a read-only image-marker check passed; the current owner
  container was not changed.

# Current-head full regression — `4e30c0a4` (2026-08-29)

- The supported project suite ran against the current branch head and passed
  `6961 passed, 7 skipped, 186 warnings` in `219.73s`.
- The warnings are existing deprecation/runtime warnings; no test failure or
  environment exception was reported. This is source-level current-head
  evidence. The owner deployment was not rebuilt or changed.

# Recipe URL argument-projection checkpoint — `94d324a3` (2026-08-29)

- Added a direct ACI projection regression for the owner URL request. The
  resolved `manage_recipes/commit_import` choice carries both the explicit
  `requested_name` and `source_url`; it cannot regress to an under-specified
  `{"action":"add"}` payload. Recipe/intent/binding focused tests passed
  `293`.
- Exact candidate `odysseus:candidate-94d324a3419d`, image
  `sha256:2b3de614a89dccd4e8e09b04a5c4257997c91f8c160eb7857efcc613859a5b29`,
  embedded/running source `94d324a3419d9c0b76ed8ef230ba7289b05b4a7b`, health
  healthy, restart count `0`; Qwen3:8B was reachable from the Hades namespace
  with digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- The exact authenticated browser URL journey fetched the requested source and
  preserved the route to `commit_import`, but the source contained an
  unquantified ingredient and correctly returned bounded review/no-write
  semantics. Canonical recipe count remained `0`; no false success occurred.
  The existing browser scenario is therefore not valid mutation PASS evidence
  because it lacks a required persisted readback assertion. This is an
  evaluator gap to close before claiming URL-import mutation acceptance, not a
  reason to invent quantities or weaken canonical validation.

# Recipe import acceptance hardening — `53670937` (2026-08-29)

- The existing browser lane now verifies recipe collection-count readbacks, so
  a review-required import cannot pass without proving its canonical no-write
  result. Syntax/JSON and focused owner-journey/Recipe tests passed `37`.
- Exact candidate `odysseus:candidate-536709378507`, image
  `sha256:cb516194248e65ecab025f5a6f2581399f6aaaf826f3e71cb6176a6678035a1b`,
  ran with matching OCI/source marker, health healthy, restart count `0`, and
  Qwen3:8B digest
  `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- Complete URL import passed through the real authenticated browser/chat path:
  `1` mutation, `2` canonical readbacks including reload, `3` streams and
  `[DONE]`, with zero false success, raw final results, duplicate delivery, or
  abrupt EOF. The Sunday Supper URL correctly remained `NEEDS_REVIEW` because
  fetched evidence contained an unquantified ingredient; its canonical count
  remained zero. Acceptance credentials and isolated deployment were revoked
  and removed afterward.

# Recipe import provenance assertion — `af0c984b` (2026-08-29)

- Successful browser Recipe URL readbacks now verify both the canonical recipe
  name and persisted `source_url`. This is an evaluator-only assertion and does
  not alter production routing or persistence.
- Syntax/JSON, UI, owner-journey contract, and Recipe focused tests passed
  `41`. This checkpoint was not separately deployed; the last exact live
  candidate remains `53670937`, so no live result is attributed to `af0c984b`.

# Exact-HEAD Recipe import acceptance — `98728b47` (2026-08-29)

- Candidate `odysseus:candidate-98728b47103`, image
  `sha256:2bab8b594e27b7fc5b877190ec41e151c6ab6c5aaf1be61a0715a1325181f042`,
  embedded source `98728b47103e608d391a74baded90a258264d72a`, health healthy,
  restart count `0`.
- Complete URL import passed the exact authenticated browser/chat path with
  persisted `source_url` verification: `1` mutation, `2` readbacks including
  reload, `3` streams and `[DONE]`, zero false success, raw final results,
  duplicate delivery, or abrupt EOF. The disposable principal and stack were
  revoked and removed afterward; the owner deployment was untouched.
# Exact Recipe workspace search checkpoint — `9285a7e1` (2026-08-29)

The Recipe workspace now supports bounded client-side search over the
owner-scoped canonical recipe collection and exposes canonical culinary units
in its ingredient editor. Focused JavaScript/Recipe/UI coverage passed (`36`
tests). Candidate `odysseus:candidate-9285a7e1dda2` was built from pushed
source `9285a7e1dda257414b632722f6f4d2782fd4694f`; image ID is
`sha256:f13b31e24c27b2f644b290325997e6f712c11e4c423b84fb8b6da5ea64a73171`,
and OCI/source-marker provenance matched exactly. The candidate was not
deployed, so this entry is build/focused-test evidence only.
# Authenticated Recipe workspace browser checkpoint — candidate `a76af992` (2026-08-29)

The isolated Chromium browser lane logged in through the normal Hades UI using
the gated disposable acceptance principal, seeded one synthetic canonical
recipe as prerequisite state, and verified Recipe search, detail rendering,
ingredient visibility, and reload persistence against
`odysseus:candidate-a76af9922f0d`. The image ID was
`sha256:2eb81cba236a083fe681ed554e30971562d2aa5cb8fa7657ebc0a2c557374544`,
with OCI/source marker `a76af9922f0dcb2a8e4997e208b92f7fb9f36597`. The run passed;
pre-login optional probes produced expected unauthenticated `401/403`
diagnostics, with no post-login uncaught browser errors. The isolated
principal and stack were cleaned up. This is UI-surface evidence, not chat
mutation or real-owner evidence.
## Work workspace owner UX checkpoint — `4c7696a3` (2026-08-29)

The Work workspace now uses the shared Hades styled prompt for goal creation
and presents readable goal/project/task details before a collapsed technical
record. Native `prompt()` and raw canonical JSON as the primary detail view
were removed from this surface. Frontend/static and focused UI/layout checks
passed (`11`). Exact pushed candidate: `odysseus:candidate-4c7696a3e7aa`,
image `sha256:5386055c9d2bbe9321f5af5fd00cd19a26f817c1e3f4094a318b2fb0703ae828`.
The owner deployment was not changed.
## Populated Memory exact-candidate browser checkpoint — `4c7696a3` (2026-08-29)

`OWNER-MEMORY-POPULATED-001` passed through the isolated authenticated browser
lane on exact candidate `4c7696a3e7aaafcc760bde8fad205b51bbdd1ffe`: one scenario,
one turn, one final answer, one terminal `[DONE]`, two canonical readbacks,
zero false success, zero raw final result, zero duplicate delivery, and zero
abrupt EOF. The disposable runtime reached Qwen3:8B via
`http://host.docker.internal:11434`; temporary principal and state were removed.
## Kitchen → Recipe exact-candidate browser composition checkpoint — `cb34789d` (2026-08-29)

The isolated authenticated browser lane passed `OWNER-RECIPE-COMPOSITION-001`
against exact product candidate `4c7696a3`: three chat turns, three final
answers, three terminal `[DONE]` events, two canonical readbacks, zero raw
final results, zero duplicate delivery, and zero abrupt EOF. The run exercised
Inventory-backed pantry coverage and deterministic serving scaling. A missing
browser-fixture `shortage` projection was corrected as evaluator-only commit
`cb34789d`; the product image was unchanged.
## Expiring inventory → Recipe exact-candidate browser checkpoint — `717a1dd9` (2026-08-29)

`OWNER-RECIPE-EXPIRING-COMPOSITION-001` passed against exact product candidate
`4c7696a3`: one authenticated chat turn, one final answer, one terminal
`[DONE]`, two canonical readbacks, zero raw final results, zero false success,
zero duplicate delivery, and zero abrupt EOF. This covers expiring Inventory
stock feeding Recipe candidate selection and pantry coverage. Temporary state
and credentials were removed.
## Kitchen → Recipe expiring-inventory browser checkpoint — `48f5c01a` (2026-08-29)

`OWNER-RECIPE-EXPIRING-COMPOSITION-001` passed against exact product candidate
`4c7696a3`: one authenticated chat turn, one final answer, one terminal
`[DONE]`, two canonical readbacks, zero raw final results, zero false success,
zero duplicate delivery, and zero abrupt EOF. This verifies expiring Kitchen
stock feeding Recipe candidate selection and pantry coverage. Temporary state
and credentials were removed.
## Homelab/Network → Work composition audit — `02690560` (2026-08-29)

The existing Work mutation path was audited for infrastructure composition.
`manage_work.create_task` requires an explicitly named existing Project, while
`WorkTask` and its Action projection have no canonical Asset/Service/Workload
target reference. The requested infrastructure-to-Work journey is therefore
not yet a supported product path; implementing it would require a defined
canonical relation contract rather than another prompt route. No production
change was made and the gap is deferred explicitly.

## Memory correction and owner transport checkpoint — `eb9d2ac8` (2026-08-29)

Two generalized defects found by the nontechnical owner journey were fixed:
background Memory extraction now suppresses the recent transcript window after
an explicit canonical mutation, and the shared plain-chat capability gate now
routes `DELETE` operations into ACI. Focused coverage passed `494` tests with
`5` unrelated skips and one SQLAlchemy deprecation warning.

The exact candidate `odysseus:candidate-eb9d2ac8`, image
`sha256:47f88ae2389061f8102dc0d8c2c71f6b003e75a3d7e7b7b7366620422ad3daf2`,
embedded source `eb9d2ac87affd8b29e0f37745c28c8aba835ab1f`, matched its OCI
revision and source marker, and ran healthy with zero restarts in the isolated
Qwen3:8B deployment. The browser journey passed four natural-language turns:
remember a fact, read it, say it is no longer true, and read it again. It
produced two canonical mutations, two reads, zero false successes, zero
duplicate delivery, zero raw final Results, and zero abrupt EOF. Independent
durable-state inspection found no remaining owner color record after the
verified delete. The journey was added to the corpus in follow-up docs/test
commit `bdfd0fef`; no rebuild was needed for that data-only change.

The Work task mutation/readback journey was also rerun against the same exact
candidate: two turns, one chat mutation, two canonical readbacks including
reload, and zero false success, raw final Result, duplicate delivery, or abrupt
EOF. The actual owner deployment remains untouched and is still running its
separate older source/image.

## Asset owner-journey checkpoint — executable candidate `eb9d2ac8` (2026-08-29)

The disposable Assets database was wired into the candidate bind mount after
an initial harness-only fixture mismatch. On exact candidate
`odysseus:candidate-eb9d2ac8`, the Atlas/Erebus RAM collection journey passed
three natural-language paraphrases, and the RTX 4090 false-premise journey
passed one bounded no-match read. Across these four GUI turns there were zero
false premise claims, raw final Results, duplicate delivery, or abrupt EOF.
The fixture database was disposable and the actual owner deployment was not
touched. One earlier run failed before login because its short-lived
acceptance credential expired; it was classified as `AUTH_SESSION_FAILURE` and
did not count as a product result.

## Capability schema parity checkpoint — executable candidate `50a9fdf2` (2026-08-29)

The canonical V1 capability projection now replaces shadowing legacy native
schemas, keeping `manage_memory` mutation-only (`add/edit/delete`) while
preserving legacy line-format Memory reads as read-private compatibility
classification. Binding, capability, approval, and external-context focused
coverage passed `51` tests after the repair. The exact candidate
`odysseus:candidate-50a9fdf2`, image
`sha256:01491af25a791567f7b7f92060c70ab215dffffd322663b78db2aad5f35bb4d6`,
matched its OCI revision and `/app/.odysseus-source-commit`, ran Qwen3:8B with
zero restarts, and passed a fresh authenticated Asset false-premise browser
read plus one default owner walk read. Both had zero false success, raw final
Results, duplicate delivery, or abrupt EOF.

The broad regression immediately before the final compatibility repair was
`6979 passed, 8 skipped, 1 failed`; the sole failure was the legacy
`manage_memory` search safety case and passes in the focused repair suite. A
full rerun after `50a9fdf2` remains required before calling the regression
green.

The required rerun completed on the same source: `6980 passed, 8 skipped`,
with `186` existing warnings and no failures. This closes the broad regression
gate for candidate `50a9fdf2`; the candidate remains the exact browser-tested
executable and the owner deployment remains untouched.

## Messy recipe review checkpoint — `347d5326` (2026-08-29)

Copied recipe paste handling now classifies sectioned text without a URL as an
import, ignores serving metadata as page chrome, preserves unquoted owner
display names, and routes qualitative amounts to the existing editable review
draft. Strict canonical commit remains unchanged, and successful review
preparation is terminal so Qwen3:8B cannot repeat the same Action.

Focused coverage passed `379` tests. Exact candidate
`odysseus:candidate-347d5326`, image
`sha256:bf8339535013f80a4c978df096de0f1880dea5f563abe739a637728c71429984`,
embedded source `347d5326`, ran healthy with zero restarts. The browser journey
passed one messy webpage-shaped recipe review turn with zero false success,
raw final Result, duplicate delivery, or abrupt EOF. Independent SQLite
inspection found zero canonical rows for `Acceptance Web Paste Dinner`, proving
review preparation did not write state. The temporary negative readback exposed
an acceptance-harness gap (`absent_name` is unsupported); it was verified
independently. The actual owner runtime remains untouched and older.

## Household sloppy-language checkpoint — executable candidate `3147dd01` (2026-08-29)

The Household compiler now recognizes ordinary remaining-quantity phrasing such
as “how much X is left now” in addition to “how much X we got”, while excluding
infrastructure terms from the household route. The permanent owner corpus now
includes a four-turn messy-language mutation/readback journey: add three cans,
read the quantity, use one, and read the remaining quantity.

On exact candidate `odysseus:candidate-3147dd01`, the clean disposable browser
journey passed four turns, including two chat mutations and two canonical
readbacks. Independent SQLite inspection found `Acceptance Thyme` quantity 2.
There were zero false successes, raw final Results, duplicate delivery, or
abrupt EOFs. The stack was healthy with zero restarts and source marker
`3147dd01`; the actual owner deployment was untouched. A prior contaminated
retry exposed duplicate-like inventory ambiguity; consumption correctly failed
closed rather than guessing.

The current-source full regression after this executable change is
`6987 passed, 8 skipped, 186 warnings`.

The clean fresh-install stack initially returned HTTP 400 for session creation
because no model endpoint existed. Registering Qwen3:8B through the normal
admin model-endpoint setup route resolved it. This remains a fresh-install
onboarding/release gap to improve, not a feature-acceptance failure.

The same exact candidate also passed the isolated Work project mutation journey:
one natural-language project creation followed by canonical readback and
reload readback. The mutation entered through chat, not fixture setup; there
were zero false successes, raw final Results, duplicate delivery, or abrupt
EOFs.

## Approved-mutation duplicate-delivery checkpoint — executable candidate `a784b35e` (2026-08-29)

An owner task journey exposed a serious approval-continuation defect: the
approved `manage_work/create_task` Action could be repeated by the resumed
provider response, creating two canonical tasks while displaying one success.
This was classified as `DUPLICATE_DELIVERY` at the shared agent-loop mutation
boundary. The per-turn duplicate guard now covers all canonical mutation
bindings, while the legacy completion verifier remains unchanged.

Focused approval/work coverage passed 33 tests and the current full regression
passed `6987 passed, 8 skipped, 186 warnings`. The exact candidate
`odysseus:candidate-a784b35ed8b6`, image
`sha256:dc01946bc9416862486ef0c65a349b584db7363aa94bc9a0c0592a69b549e80d`,
source marker `a784b35e`, ran healthy with zero restarts. Its approved Recipe
URL import journey passed three turns with one canonical mutation, two
readbacks including reload, and zero duplicate delivery, false success, raw
final Result, or abrupt EOF.

The original Work retry also exposed an acceptance-fixture contamination
problem: repeated setup calls created same-title projects. Hades correctly
failed closed on the ambiguous reference; no owner data was involved. The
contaminated disposable data was moved to a recoverable backup before fresh
 verification.

## Asset owner-read checkpoint — executable candidate `a784b35e` (2026-08-29)

The exact candidate passed three natural-language Asset RAM reads against the
Atlas/Erebus fixture (`64 GB` and `128 GB`), including paraphrases such as
"what's the memory in my machines?" and "which machine has the most memory?".
It also passed the false-premise query "Which of my servers has an RTX 4090?"
without inventing an entity. The journeys produced zero false premises, raw
final Results, duplicate delivery, or abrupt EOFs.

The first RAM replay used an unmounted host fixture path and was correctly
classified as `ENVIRONMENT_FAILURE`/fixture wiring, not a product result. The
replay was corrected to grade the container's canonical mounted Asset database.

## Current Recipe composition checkpoint — executable candidate `a784b35e` (2026-08-29)

A fresh disposable Compose project was bootstrapped with normal admin setup,
Qwen3:8B endpoint registration, and the gated acceptance principal. The exact
candidate passed the three-turn GUI composition journey: list the recipe, ask
whether it can be made with available pantry stock, and scale it to six
servings. Fixtures were setup prerequisites; all exercised behavior entered
through chat. Canonical readback and reload verification passed with two
readbacks, zero false success, raw final Result, duplicate delivery, or
abrupt EOF.

## Current qualitative Recipe review checkpoint — executable candidate `1a2b62e5` (2026-08-29)

On a fresh isolated stack with exactly one prerequisite recipe, the owner
paste containing `salt to taste` and `oil as needed` passed through chat as a
review-safe import. The journey recorded one turn, two canonical readbacks,
and no recipe-count increase; false success, raw final Result, duplicate
delivery, and abrupt EOF were zero.

## Current Household mutation checkpoints — executable candidate `1a2b62e5` (2026-08-29)

The fresh isolated Household journey passed four owner turns with two chat
mutations and two independent readbacks: Acceptance Tomatoes moved from 0 to
3 and then to 2 after consumption. The messy-language variant likewise passed
four turns for Acceptance Thyme using "yo add 3 cans..." and "use one...".
Both journeys verified canonical state and recorded zero false success, raw
final Result, duplicate delivery, or abrupt EOF.

## Current Work task mutation checkpoint — executable candidate `1a2b62e5` (2026-08-29)

The first task replay on a reused stack was classified as fixture contamination:
prior Memory context correctly triggered the external-untrusted-context exact
approval gate. A truly fresh no-memory Work stack then passed the task journey
with two turns, one chat mutation, two canonical readbacks including reload,
and zero false success, raw final Result, duplicate delivery, or abrupt EOF.

## Current Recipe mutation checkpoint — executable candidate `1a2b62e5` (2026-08-29)

On the same fresh isolated stack before any recipe state existed, the normal
long-form Recipe mutation passed three owner turns. One canonical Recipe was
created through chat and independently verified by two readbacks including
reload; false success, raw final Result, duplicate delivery, and abrupt EOF
were zero.

An earlier reused-database replay was rejected before chat because its
recipe-count precondition no longer held. That was disposable fixture
contamination, not a product result.

## Current Recipe composition variants — executable candidate `a784b35e` (2026-08-29)

Two additional fresh disposable Compose projects passed the current-candidate
owner journeys. Expiring-inventory composition passed one natural-language
request with two canonical readbacks including reload. Shopping requirements
passed recipe listing and an ordinary request for ingredients to buy, again
with two canonical readbacks including reload. Both Qwen3:8B GUI runs recorded
zero false success, raw final Result, duplicate delivery, or abrupt EOF.

## Current Work task mutation checkpoint — executable candidate `a784b35e` (2026-08-29)

A fresh disposable Compose project with normal admin setup and Qwen3:8B passed
the exact Work task mutation/readback journey. The prerequisite project was
setup-seeded; the task itself entered through owner chat. One task mutation and
two canonical readbacks including reload passed with zero false success, raw
final Result, duplicate delivery, or abrupt EOF. This is the clean replay of
the journey that originally exposed approval-continuation duplicate delivery.

## Current fresh-install restart checkpoint — executable candidate `a784b35e` (2026-08-29)

A fresh disposable Compose project using the exact candidate image booted with
empty application state. A normal browser first login reached Hades, the
authenticated browser state was saved, and after restarting the app container
the browser reloaded the authenticated home surface successfully. The
post-restart `/api/health` response was HTTP 200; the candidate source marker
matched `a784b35e` and the container restart count was zero after the explicit
restart. Owner data was not involved.

## Current Tier 1 read-only walkabout — executable candidate `a784b35e` (2026-08-29)

The isolated current candidate passed seven ordinary read-only browser turns
covering network, homelab, memory, Asset collection/reference questions, and
Work overview. Each turn produced one human answer and one terminal event;
there were zero false successes, raw final Results, duplicate delivery, or
abrupt EOFs. An earlier replay using an expired disposable credential was
classified as `AUTH_SESSION_FAILURE` before login and was not counted as a
product result. A fresh principal was provisioned through the normal admin
route for the successful replay.

The subsequent full supported regression on branch head `35be6afd` passed
`6991 passed, 8 skipped, 186 warnings` in 248.35 seconds. The branch-head
change after executable candidate `1a2b62e5` was documentation-only.

## Current empty-Memory owner-read checkpoint — executable candidate `1a2b62e5` (2026-08-29)

The ordinary owner question "What do you know about me?" passed on the empty
Memory fixture with one human-readable terminal answer and one terminal stream;
false success, raw final Result, duplicate delivery, and abrupt EOF were zero.

## Current populated-Memory owner-read checkpoint — executable candidate `1a2b62e5` (2026-08-29)

The populated-memory fixture journey passed its ordinary "What do you know
about me?" read on Qwen3:8B. Canonical setup/readback verification recorded
two readbacks and one terminal stream; false success, raw final Result,
duplicate delivery, and abrupt EOF were zero.

## Current actual-owner read-only smoke — 2026-08-29

Against the real healthy owner deployment, a browser session completed three
ordinary read-only prompts covering computers, food, and current work. No
mutation was attempted. The separate window-management dogfood also passed
open, deduplicate, focus, snap, minimize, restore, maximize, reload, and
narrow-viewport checks. The owner runtime remained on source `34ced247` with
zero restarts; this evidence is read-only owner smoke, not candidate feature
acceptance.

## Current Work-overview checkpoint — executable candidate `1a2b62e5` (2026-08-29)

The disposable Work overview fixture passed three ordinary read turns on the
exact candidate with two canonical readbacks and three terminal streams. No
false success, raw final Result, duplicate delivery, or abrupt EOF occurred.

## Current continuation safety checkpoint — executable candidate `1a2b62e5` (2026-08-29)

Owner testing found two related control-plane defects: bare `Restart it.`
could fall through as unknown/model prose, while bare `Continue.` stayed in
plain chat mode and could inherit unrelated date/setup retrieval context. The
generalized repair routes explicit continuations through ACI, preserves the
literal current turn, and projects ambiguous or no-active-run states as
human-readable `CLARIFICATION` answers with zero execution authority. The
browser oracle distinguishes intentional clarification from execution-bearing
Actions.

The exact pushed candidate `odysseus:candidate-1a2b62e59e32` has image ID
`sha256:34cbbcfe0f98f84d3bccf02c2f624883d4c9e4115eeb2ae95ff1047642099a7b`,
source marker `1a2b62e59e323afe5817fd69e7c271620b7f2efd`, and migration head
`20260825_002_work_run_completion_v6`. The isolated container was healthy with
zero restarts. Separate Qwen3:8B GUI runs for `Restart it.` and `Continue.`
both passed with one terminal stream, `CLARIFICATION` provenance, zero tool or
Action execution, zero false success, raw final Result, duplicate delivery, or
abrupt EOF.

## Current complete URL Recipe import checkpoint — executable candidate `1a2b62e5` (2026-08-29)

On a fresh empty-recipe isolated stack, the owner-facing URL import with an
explicit display name passed its three-turn review/approval flow. One
canonical Recipe mutation was independently verified by two readbacks,
including reload; the requested name and source URL were retained. False
success, raw final Result, duplicate delivery, and abrupt EOF were zero.

## Current copied-webpage Recipe checkpoint — executable candidate `1a2b62e5` (2026-08-29)

The fresh empty-recipe owner journey accepted a webpage-shaped recipe paste
through chat and review. It passed two turns with one canonical mutation and
two readbacks including reload; false success, raw final Result, duplicate
delivery, and abrupt EOF were zero.

## Current Work-empty and Memory-correction checkpoints — executable candidate `1a2b62e5` (2026-08-29)

The empty Work owner read passed with one deterministic answer and zero false
success, raw final Result, duplicate delivery, or abrupt EOF. The four-turn
Memory correction journey passed two owner mutations and two grounded reads,
including the ultraviolet-orange remember/read/correct flow, with the same
zero-defect result.

## Current URL import error checkpoint — executable candidate `1a2b62e5` (2026-08-29)

The fresh empty-recipe journey for the named Sunday Supper URL passed the
review/error path without claiming a successful save. Independent API
readback confirmed the canonical recipe store remained empty; false success,
raw final Result, duplicate delivery, and abrupt EOF were zero.

## Current authenticated UI smoke — executable candidate `1a2b62e5` (2026-08-29)

Authenticated desktop and narrow-width checks passed on the isolated
candidate. Desktop navigation rendered 27 visible entries with exactly one
intentional icon each, no horizontal overflow, and one shared Inventory
titlebar; the Recipe pane rendered one readable empty/list state. A 390px
viewport also had no document overflow. Screenshots were captured at
`/tmp/hades-ui-desktop-current.png` and `/tmp/hades-ui-narrow-current.png`.

## Current isolated Chroma volume recovery checkpoint (2026-08-29)

An isolated disposable Chroma volume was populated with marker data, backed
up using the documented Docker-volume tar procedure, deliberately drifted,
restored, and independently verified. The original marker values were
restored and the drift-only file was absent after restore. This was an
operational recovery rehearsal only; no owner volume or deployment was
modified.

## Current exact-candidate fresh-install checkpoint — `1a2b62e5` (2026-08-29)

An isolated fresh Compose deployment of the exact candidate booted on a free
project-specific network and ports. Normal browser login succeeded, the
authenticated session survived an app-container restart, health returned
`healthy`, and the app restart count remained zero. The running container
reported image `odysseus:candidate-1a2b62e59e32` and source marker
`1a2b62e59e323afe5817fd69e7c271620b7f2efd`. From inside that fresh Hades
namespace, the host Ollama endpoint was reachable and exposed `qwen3:8b`.
The isolated data, volumes, and network were separate from the owner lane.

## Current realistic Asset false-premise checkpoint — executable candidate `1a2b62e5` (2026-08-29)

The `assets-incomplete-duplicate-like` fixture was seeded only in the
isolated acceptance database. The ordinary owner prompt asking which server
has an RTX 4090 produced a grounded no-match answer despite incomplete and
duplicate-like records. The one-turn browser run had zero mutations, false
success, raw final Result, duplicate delivery, and abrupt EOF.

## Current populated-Memory checkpoint — executable candidate `1a2b62e5` (2026-08-29)

The disposable populated-memory fixture passed its live Qwen browser read on
the exact candidate. It produced one human-facing answer with two canonical
readbacks, including reload verification; false success, raw final Result,
duplicate delivery, and abrupt EOF were zero.

## Current actual-owner and network provenance checkpoint (2026-08-29)

The real owner deployment completed ordinary read-only Asset, Household, Work,
and Network prompts with no mutation attempted. Its network answer came from
older source `34ced247` and was flatter than the current candidate renderer,
so it is not evidence against the candidate. Replaying `OWNER-NETWORK-001`
against the exact candidate was classified `ENVIRONMENT_FAILURE` because the
disposable stack lacked its CMDB; the transport and bounded unavailable-state
answer still completed without false success, raw final Result, duplicate
delivery, or abrupt EOF.

## Corrected exact-candidate Network checkpoint — `1a2b62e5` (2026-08-29)

After adding the required owner-scoped network observations to the disposable
CMDB fixture, `OWNER-NETWORK-001` passed on the exact candidate. The browser
run produced one deterministic human answer and one `read_network_observations`
Action with zero mutations, false success, raw final Result, duplicate
delivery, or abrupt EOF. The earlier `UNAVAILABLE` result was retained as
fixture-wiring evidence and is not counted as a product failure.

## Messy pantry recipe-candidate checkpoint — exact candidate `303fde19` (2026-08-29)

The ordinary owner prompt `can i make anything w what we got` initially
reached Recipe routing but ended without a human answer. Trace evidence showed
the canonical `pantry_candidates` Result was generated server-side while the
client dropped the first `response_replace` during final rendering. The repair
registered the ActionSpec, added bounded Recipe read projection, and recreated
the visible answer round while preserving its replacement accumulator.

On the exact pushed candidate, the original prompt and the paraphrases `can i
cook something w what we have` and `what can we make from whatever we have`
each executed one canonical `read_recipes` `pantry_candidates` read and visibly
answered from the isolated recipe/pantry fixture. Reload preserved both
answers. No mutation was attempted; false success, raw final Result, duplicate
delivery, abrupt EOF, and browser page errors were zero. The disposable
candidate source marker matched `303fde19`; the real owner deployment
remained on older source `34ced247`.

## Recipe reference continuity checkpoint — exact candidate `a0681fc1` (2026-08-29)

The isolated Qwen3:8B browser candidate passed the ordinary same-session
conversation `what recipes do i have?` followed by `what am i missing for that
recipe?`. The first turn listed the canonical recipe, and the second resolved
the pronoun to that recipe and returned a grounded shopping answer. The
bounded read projection now preserves recipe IDs, names, and servings for
durable follow-up resolution without exposing ingredient payloads. A separate
false-premise turn, `which recipe did i cook last night?`, failed closed with an
honest no-recorded-history answer; reload preserved it. No mutation was
attempted, false success, raw final Result, duplicate delivery, abrupt EOF, or
browser page error was observed. Candidate source marker matched `a0681fc1`;
the real owner deployment remained on older source `34ced247`.

## Household mutation and Work read walkabout — exact candidate `a0681fc1` (2026-08-29)

On the isolated candidate, ordinary chat mutation `yo add 3 cans of
Acceptance Walkabout Tomatoes 20260829c to the pantry` reached the canonical
`manage_assets/add_item` path. The tainted-run security boundary displayed the
visible exact-action approval card; after `Allow for this task`, independent
`/api/inventory/overview` readback confirmed quantity 3. `use one ...` followed
the same approval path and independent readback confirmed quantity 2. Chat
readback and reload both retained quantity 2, with no page errors. The corpus
currently expects these bounded household writes to be approval-free; this is
tracked as a policy/acceptance expectation mismatch, not bypassed.

The same candidate also passed Work read variants `what am i working on?`,
`whats outstanding`, and `whats left`, each returning a truthful empty-state
answer. Reload preserved the conversation. No mutation, false success, raw
final Result, duplicate delivery, abrupt EOF, or browser page error was
observed. The real owner deployment remained on older source `34ced247`.

## Qualitative Recipe review checkpoint — exact candidate `1e950047` (2026-08-29)

An ordinary pasted recipe containing `salt to taste`, `oil as needed`, and
`parsley for garnish` initially exposed a technical approval card even though
the operation was only preparing an unpersisted review draft. The generalized
security-boundary repair recognizes the explicit review-only payload and
allows the existing `prepare_import` path to run without weakening validated
commit approval. On the exact candidate, the browser returned a readable
review answer naming all three ambiguous ingredients, exposed no raw Action
JSON or approval card, and an independent `/api/recipes` read confirmed that
nothing was saved. Page errors were zero. The candidate source marker matched
`1e950047`; the real owner deployment remained on older source `34ced247`.

## Recipe URL import checkpoint — exact candidate `c6ac382e` (2026-08-29)

The first live URL replay fetched the public Budget Bytes page successfully but
Qwen declined the already-resolved import action, producing no Action and no
canonical change (`WRONG_ACTION`/model-arbitration failure). The generalized
Recipe import fast path now selects the sealed `commit_import` Action directly;
external source content still enters the existing approval boundary. After the
owner-approved replay, the exact candidate persisted `Acceptance Budget Chili
20260830c`, independently read it back, and confirmed the requested source URL
was retained. The browser answer was human-readable; false success, raw final
Result, duplicate delivery, abrupt EOF, and page errors were zero.

## Unreachable Recipe URL failure checkpoint — exact candidate `cb96ea09` (2026-08-29)

An approved import of an unreachable public URL failed closed with the
human-readable answer `The recipe source could not be fetched for review.`
Canonical Recipe readback confirmed no row was created and no raw Action JSON
was shown. Trace inspection found the resumed model had previously repeated
the same failed `commit_import` Action, producing duplicate failure cards; a
per-turn attempted-effect signature guard now suppresses that repeat. The
replay produced exactly one failed Action, zero false success, duplicate
delivery, abrupt EOF, or browser page errors. The real owner deployment was
untouched and remained on source `34ced247`.

## Owner-readable tool-thread checkpoint — exact candidate `03bc782b` (2026-08-29)

The copied-webpage recipe mutation reached the existing approval boundary,
persisted the requested recipe after approval, and was independently verified
through `/api/recipes`. The normal conversation showed a readable `SAVING
RECIPE` thread label instead of the internal `MANAGE_RECIPES` binding; the
exact Action payload remains available inside the collapsed technical content.
The compact qualitative replay also showed the same owner-readable label,
returned a clear review answer, and created no row. Both replays had zero page
errors and zero duplicate Actions. The exact candidate OCI/source marker was
`03bc782b`; the real owner deployment remained on older source `34ced247`.

The prior acceptance Compose project was found to mount the real repository
`data/` directory despite being named disposable. Its container was stopped
without deleting or resetting data. Subsequent acceptance used an explicit
`/tmp/hades-isolated.../data` bind mount and a separate network; this harness
provenance defect remains a release-infrastructure follow-up.

## YouTube recipe no-evidence checkpoint — exact candidate `03bc782b` (2026-08-29)

An owner-facing request to save a recipe from a public video with no verified
recipe structure reached the existing exact approval boundary. After approval,
the candidate returned a bounded review-needed answer naming the missing
verified fields, created no canonical Recipe, exposed no raw binding or
duplicate Action, and produced zero browser page errors. This is recorded as a
false-premise/no-evidence safety journey, not as successful video import
coverage. The inline editable review handoff remains open.

## Recipe review handoff checkpoint — exact candidate `fd289209` (2026-08-29)

The previous chat review result correctly explained the draft but failed to
open the existing Inventory review form because its UI event was nested inside
the Result data. The generalized result-boundary repair forwards the review
event and draft to the shared UI. A duplicate-event guard then ensured one
dialog per draft. On the exact candidate, a qualitative chat request opened
exactly one editable recipe dialog, left canonical state unchanged, allowed
the owner to correct the draft, and saved it through the existing reviewed
commit path. Independent `/api/recipes` readback confirmed the corrected row;
the dialog closed, the save toast appeared, raw bindings were absent, and page
errors were zero.

The same candidate includes `yt-dlp==2026.8.19` as a core dependency. A direct
candidate probe retrieved public YouTube metadata successfully. A video with
recipe titles but no verified structure still failed safely into review with
no invented or persisted recipe; positive extraction remains subject to the
existing validation bar.

## Recipe import display-cleanliness checkpoint — exact candidate `f3d847fa` (2026-08-29)

The public Budget Bytes URL journey was replayed through GUI/chat on the exact
candidate after adding a narrow parser sanitizer for trailing schema.org site
price and footnote artifacts. After visible approval, the requested recipe
name and source URL persisted, and independent `/api/recipes` readback found
12 ingredients with no trailing `($...)`, `*`, `†`, or `‡` display artifacts.
Meaningful preparation text, including parenthetical amounts, was retained.
Reload preserved the row; the final answer reported verified canonical
readback, with zero page errors and no raw technical binding. Positive YouTube
extraction remains unverified. The real owner deployment remained on source
`34ced247`.

## Household approval-gate classification — candidate `f3d847fa` (2026-08-30)

A fresh-chat owner replay used sloppy language to add three cans, read the
quantity, consume one, read again, and reload. Canonical inventory readback
verified `3 -> 2`, with zero page errors and readable owner-facing answers.
Both mutations nevertheless displayed exact approval cards, including when a
new chat was created before the prompt. Trace inspection found the shared
cause: Agent-mode context injects the editable `skills` index as an untrusted
user-role block (`tool_gate_untrusted=true`), so the run-level taint gate
requires approval before private writes. The canonical `manage_assets`
`add_item` and `consume_stock` ActionSpecs are `ApprovalMode.NONE`; therefore
this is classified as a security-policy/UX friction mismatch, not a routing or
false-success failure. The safety gate remains intact pending a scoped repair
that cannot let editable skill text authorize mutations.

## Sloppy Work read checkpoint — exact candidate `7a0f3882` (2026-08-30)

The owner walkabout found that `whats outsanding` fell through to a generic
model answer instead of the canonical Work empty state. The generalized
deterministic-read normalizer now corrects bounded edit-distance slips only
within routing vocabulary and preserves valid singular/plural forms. Focused
intent tests passed (`394 passed, 5 skipped`); exact-candidate browser replay
of both `whats outsanding` and `whts outsanding` reached `CHECKING WORK` and
returned `No outstanding work is recorded for this owner.` with no raw binding
or page errors. `whats left` remains intentionally clarification-safe because
it is ambiguous between Work and household stock.

## Context-taint convergence checkpoint — exact candidate `682eb6c6` (2026-08-30)

The household approval replay exposed a second shared source of unnecessary
approval: the MCP server catalog was injected into known non-MCP routes. The
route-scoped MCP repair (`563e5bca`) passed 14 prompt-injection/security tests
and replayed the realistic sloppy household journey with two GUI mutations,
two independent canonical readbacks, reload durability, zero false successes,
zero raw final Results, zero duplicate delivery, and zero abrupt EOFs.

The next Work mutation replay then exposed passive keyword-recalled Memory
context tainting unrelated ACI actions. ACI turns now suppress opportunistic
memory injection; explicit Memory questions still use the canonical
`read_memory` Action and deterministic projection. The repair (`682eb6c6`)
passed 59 focused chat/context/security tests. On the exact pushed candidate,
Work project creation required no approval, persisted the requested project,
read it back independently after reload, and completed with zero false
successes, raw final Results, duplicate delivery, or abrupt EOFs.

The isolated acceptance data directory is intentionally disposable but now
contains prior journey state. The `empty-memory` benchmark correctly failed
fixture semantics because it was not empty; this is recorded as fixture
hygiene/environment failure, not a product pass. Asset fixture journeys also
still require an explicit disposable asset database and owner setup. The real
owner deployment remains untouched at source `34ced247`.

## Acceptance fixture hygiene checkpoint — exact candidate `729f9066` (2026-08-30)

The owner journey harness now establishes the declared `empty-memory`
precondition through the normal owner-scoped API on the disposable acceptance
principal and verifies that no records remain before testing. Asset fixture
seeding now uses the supplied acceptance username instead of a hard-coded
principal, while still requiring an explicit disposable asset database.
`node --check` and `git diff --check` passed. Replays passed for empty Memory,
Atlas/Erebus RAM, and the no-RTX-4090 false premise; each had zero false
successes, raw final Results, duplicate delivery, and abrupt EOFs.

The repair was pushed as `729f9066` and built as
`odysseus:candidate-729f9066`; the exact candidate was recreated, reported
healthy with zero restarts and source marker `729f9066`, and passed the empty
Memory browser journey. The real owner deployment remains untouched at
source `34ced247`.

The same candidate also passed the Work task-create/readback journey (2
turns, one GUI mutation, two independent readbacks, reload durability, and
zero false successes/raw finals/duplicate delivery/abrupt EOF). Broad
regression after the shared runtime changes completed with `7010 passed, 8
skipped, 186 warnings` in 5m24s. Candidate image `odysseus:candidate-682eb6c6`
remains the browser-tested executable; the docs checkpoint commit that records
this result is `3dab0f79`.

The fixture repair was then validated on a separate fresh application-data
project. Normal browser-visible model setup registered the Ollama endpoint and
Qwen3:8B before the journey. `OWNER-RECIPE-COMPOSITION-001` passed 3 owner
turns covering recipe listing, pantry feasibility, and scaling, with 2
independent canonical readbacks including reload durability and zero false
successes, raw final Results, duplicate delivery, or abrupt EOF. The fresh
stack was healthy with zero restarts and source marker `729f9066`.

The same fresh stack passed the qualitative Recipe review journey: ordinary
`salt to taste` / `oil as needed` input produced the review/no-save flow with
two independent no-persistence checks and no raw final Result, false success,
duplicate delivery, or abrupt EOF. The four-turn realistic Memory correction
journey also passed: remember, read, correct/delete, and read again completed
with two canonical mutations and zero false success, raw final Result,
duplicate delivery, or abrupt EOF.

## Expiring Recipe result-contract checkpoint — exact candidate `7cbd7666` (2026-08-30)

Fresh Qwen3:8B browser testing found that a valid canonical
`expiring_candidates` payload was being rejected as `INVALID_RESULT`: the
binding validator omitted the `READ_EXPIRING` filter and fell through to the
ordinary recipe-list contract. The generalized contract mapping now validates
the `candidates` collection and preserves the deterministic owner-facing
projection. Focused Recipe/intent/projection coverage passed `226 tests, 5
skipped`; the full fresh replay passed the expiring-Recipe journey with one
turn, two canonical readbacks including reload, and zero false successes, raw
final Results, duplicate delivery, or abrupt EOF.

On a separate fresh application-data project, the exact same candidate passed
the Recipe shopping-requirements journey across 2 turns with 2 canonical
readbacks and reload durability. Both disposable stacks were healthy with
zero restarts and Qwen3:8B configured through the normal model endpoint flow.
The real owner deployment remains untouched at source `34ced247`.

Focused and broad verification for this contract repair is complete: the
current source full regression passed `7011 tests, 8 skipped, 186 warnings`
in 5m31s. The candidate image used for browser replays remains
`odysseus:candidate-7cbd7666`; the branch head after documentation-only
checkpoints is tracked separately.

Narrow visual smoke on the disposable Qwen stack reached the authenticated
shell at 1024×700 and 768×600. Both widths had zero horizontal document/body
overflow and zero page errors; the sidebar, Hades chrome, model selector, and
composer remained visible and visually coherent. The first 1024 replay hit a
post-login `waitForURL` timeout, but the DOM-content-loaded retry passed, so it
is classified as harness timing rather than a product failure.

## Fresh restart and vector-recovery boundary — exact candidate `7cbd7666` (2026-08-30)

The disposable Recipe/Work acceptance app was explicitly restarted after
normal browser-visible Qwen3:8B endpoint setup. The container returned healthy
with source marker `7cbd7666`, zero restarts, and the post-restart Work
overview journey passed 3 turns with 2 canonical readbacks and reload
durability. A Chroma archive was also created from the exact Compose volume,
but that volume contained no vector records for these journeys; therefore
archive/restore command safety is not promoted to nontrivial vector-state
recovery evidence. A populated Chroma restore rehearsal remains open.

The same disposable stack passed `OWNER-WORK-OVERVIEW-001` across 3 owner
turns with 2 canonical readbacks and reload durability. The ambiguous restart
and no-active-context continuation journeys also passed 2 turns without false
execution claims, duplicate delivery, or abrupt EOF. These are safety/read
evidence only; active homelab/security execution remains separately approval-
scoped.
