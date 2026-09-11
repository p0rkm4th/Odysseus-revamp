# Hades reliability and owner-dogfood sprint checkpoint

Date: 2026-09-11 18:55 UTC
Repository: `p0rkm4th/Odysseus-revamp`
Branch: `luna/plaid-readonly-budgeting`
Head: `9249e32a8bfb20578e92af762c9e258e4bd35ddf`

## Verified in this checkpoint

- The open PR is #6. Its title and description were still template
  placeholders at inspection time; the repository API rejected the attempted
  metadata update with HTTP 401, so no PR mutation is claimed.
- PR base is `main`, which is the repository's actual default branch. No base
  change was made based on the stale template text that refers to `dev`.
- Focused Plaid Link, Plaid sync, Finance, network, household inventory, and
  world-model UI coverage passed locally: `101 passed, 2 warnings` on Python
  3.14.
- The full local CI-equivalent suite passed: `7147 passed, 5 skipped, 150
  warnings` on Python 3.14. This does not reproduce the hosted Python 3.11
  failure.
- Hosted syntax, JavaScript syntax, ACI/security, container, secret,
  workflow-security, and pip-audit checks were green for the PR head.
- The hosted broad pytest job failed on the prior head, but its test-level
  failure output is not available through the unauthenticated API. The fresh
  CI run for `9249e32a` was still in progress at this checkpoint. This remains
  an unresolved CI gate, not a diagnosed product defect.
- Dependency Review failed with the exact diagnostic: `Dependency review is
  not supported on this repository. Please ensure that Dependency graph is
  enabled`, directing the maintainer to repository Settings → Code security
  and analysis (`/settings/security_analysis`). The gate remains enabled.
- The fresh run for `9249e32a` reproduced the same Dependency Review failure;
  secret, container, and workflow-security checks remained green.

## Follow-up runtime evidence

- The bounded synthetic conversational run was repeated with the configured
  host-side Docker bridge endpoint `http://172.18.0.1:11434` rather than the
  invalid host-loopback default. It completed 62 cases with 59 functional,
  60 architectural, 100% security, zero duplicate rate, and 1 timeout. The
  prior loopback run is classified as environment/configuration failure, not
  Hades semantic evidence.
- After the owner clarified the port mapping, only `odysseus-hades.service`
  was started. The test instance on port 7000 became healthy in about 10
  seconds; `/api/health` returned 200 and `/api/ready` returned 401 without
  authentication, as expected. The port-7001 original comparison service was
  not restarted.
- Running Hades provenance reports runtime source commit
  `5c5d8feabb5f61f7c4490c3e9fb30b95594cc1f3`, checkout-tree runtime,
  `source_match: null`, and `build_id: unbuilt-source`. This is a running
  source checkout, not an immutable promoted release.
- The corrected port mapping is now established: port 7000 is the Hades test
  instance and port 7001 is the original Odysseus comparison instance. The
  Hades service is active; the comparison service was not restarted.
- The Hades test instance's auth metadata exposes only the bootstrap account;
  no usable acceptance/owner session is available to this agent. Authenticated
  chat dogfood remains gated on an existing authorized session or owner action.

## Owner/runtime coverage

The Hades test runtime is active on port 7000 from the source checkout; the
original Odysseus comparison instance remains on port 7001. No authenticated
Hades owner interaction was replayed, no real Plaid authorization was
attempted, and no live network scan was issued. Unit, contract, and synthetic
conversational tests therefore do not claim owner acceptance, provider
behavior, screenshot evidence, or live scan completion.

The affected implementation is nevertheless covered by existing bounded
tests for Plaid configuration/link authorization/sync recovery, canonical
Finance and grocery/pantry state, network approval/continuation/results, and
Hades branding/UI projections. No new duplicate subsystem was introduced.

## Web-search runtime repair

- The test runtime initially had no SearXNG container and port 8080 refused
  connections. Only the compose `searxng` service was started; the Hades
  service on 7000 and the original comparison service on 7001 were not
  container-restarted.
- SearXNG is now healthy at `127.0.0.1:8080/healthz` (HTTP 200). Its pinned
  engine query path returned 11 results for a synthetic `OpenAI` lookup; the
  provider-level Hades call returned 5 results.
- Chat logs also identified a separate dispatch defect: canonical
  `web_search` was still being sent to retired `mcp__web_search__web_search`.
  Native folded-tool dispatch now routes `web_search` and `web_fetch` through
  their in-process handlers. A regression test covers this boundary.
- The first live weather-shaped dogfood also showed the canonical ACI payload
  omitted the owner query. Web search/fetch fast-path payloads now preserve
  the bounded query or URL, and final answer projection renders the returned
  public evidence instead of model filler such as `Done.`
- The previously failing unscoped-network contract now terminates
  deterministically in about 0.7 seconds with zero model calls and zero tool
  calls; the scorer reports refusal true. A missing private CIDR or persisted
  continuation cannot enter the model decision loop.
- Hades was restarted once after the code change; port 7000 remained healthy.
  Recent chat logs showed the failed search attempts and routine research
  polling; no owner message content was copied into the sprint record.
- The restart also reported ChromaDB unavailable at `localhost:8100`; only the
  compose `chromadb` service was started afterward. Its heartbeat now returns
  HTTP 200. No Hades, owner, or vector records were written by this repair.

## Remaining gates and exact actions

1. A maintainer with GitHub write access must update PR #6's title and body
   using the verified implementation/evidence and exclusions, then rerun CI.
2. A repository maintainer must enable Dependency graph at the settings path
   reported by the gate, or explicitly retain the gate as an owner-blocked
   configuration issue. The workflow must not be weakened to hide the error.
3. Obtain authenticated hosted pytest diagnostics (or a fresh rerun) under the
   hosted Python version before calling CI green.
4. The owner must authorize Plaid Link separately from configuring Hades's
   Plaid application credentials, then accept a read-only Finance sync/query.
5. The owner must exercise one explicitly authorized network scan and the
   grocery/pantry and branding workflows in the installed Hades runtime. No
   live external action is safe to infer from this checkpoint.

## Observation boundary

This checkpoint observed repository state, public PR/check metadata, local
tests, and local service/process state only. It did not observe owner chat,
browser clicks, background Hades work, or private financial payloads. Durable
owner monitoring is not installed or active in this session.

## Current handoff refresh (2026-09-11)

- Current branch is `luna/plaid-readonly-budgeting` at pushed commit
  `39b7d1cbe6e8b0e266a5300385795a9b09286b97`. The worktree is clean and the
  PR head matches this commit.
- The installed Hades process on port 7000 reports
  `runtime_source_commit=39b7d1cbe6e8b0e266a5300385795a9b09286b97`,
  `runtime_source_kind=checkout_tree`, and `build_id=unbuilt-source`.
  `/api/health` returned HTTP 200. This remains a source-checkout runtime,
  not an immutable promoted release.
- A recent Hades lifecycle stop/start completed with systemd result `success`,
  exit status 0, and `NRestarts=0`; it was not an OOM or crash recovery.
  ChromaDB returned HTTP 200 during startup and SearXNG remains healthy at
  `127.0.0.1:8080/healthz`. Embedding uses the existing local FastEmbed
  fallback because the optional HTTP embedding lane is unavailable.
- Port 7001 remains active and was not restarted. No related dogfood worker,
  fuzz worker, pytest process, or persistent observer remains active.
- For the current PR head, focused ACI/security, syntax, secret, workflow,
  container, and audit checks pass. Hosted broad pytest is still in progress;
  Dependency Review still fails with the repository's unsupported-configuration
  diagnostic. PR title and description checks still fail because PR metadata
  has not been updated; an unauthenticated metadata write previously returned
  HTTP 401.
- Current observation coverage remains repository, public PR/check metadata,
  local service/process state, and sanitized runtime logs. No authenticated
  owner chat, browser interaction, live Plaid authorization, or live network
  scan was observed. Monitoring is not persistent after this session.

## Newly correlated owner dogfood

- Sanitized Hades logs exposed an owner-authenticated weather interaction in
  session `bf163fd2-3371-4bab-b6f2-7220a0de2850` on the pre-refresh runtime.
  The request intent was classified as web search and `web_search` was
  selected, but the first tool payload was the bare `{"action":"search"}`;
  SearXNG consequently searched that JSON text and fetched unrelated pages.
  This is a confirmed interpretation/payload-projection failure, not a
  provider or authorization failure.
- The same trace shows the model returned no streamed text before the search,
  then a later completion call succeeded. That success signal did not prove
  the weather objective was met. The repeated `stream_status` 404s occurred
  after the stream was no longer active and match the existing frontend
  cleanup path, so they are not independently actionable.
- The repair is the bounded web-search payload preservation and canonical
  result projection in commits `5dc07f29` and `39b7d1cb`. Focused regression
  coverage and a direct handler dogfood run verified the owner query survives
  and the returned evidence replaces generic filler. The repaired path is
  installed in the current `ac2a3db3` checkout; no replay of the owner request
  was performed.

## Finalization handoff

- The final focused regression command
  `pytest -q tests/test_network_intent_execution.py tests/test_review_regressions.py -k 'network or web_search'`
  passed: 15 tests passed and 41 were deselected. `git diff --check` also
  passed.
- The last running Hades test revision before shutdown is
  `562a4791cba10668c93f25d5cb2af552b7f168bb`; it reported healthy and matched
  its checkout provenance. The owner-directed endpoint is now a stable,
  documented handoff rather than an ongoing dogfood campaign.
- The owner requested the Hades project be stopped. The Hades test service on
  port 7000 is the shutdown target. The original comparison service on port
  7001, the laptop, and owner data remain outside that action.
- Production promotion/merge is not asserted from this host: PR metadata,
  Dependency Review repository settings, hosted pytest/Trivy completion, and
  authenticated owner acceptance still require the corresponding maintainer or
  owner action listed above.
