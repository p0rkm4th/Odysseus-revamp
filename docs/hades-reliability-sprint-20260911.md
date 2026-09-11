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
