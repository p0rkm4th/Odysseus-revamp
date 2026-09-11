# Hades reliability and owner-dogfood sprint checkpoint

Date: 2026-09-11 18:55 UTC
Repository: `p0rkm4th/Odysseus-revamp`
Branch: `luna/plaid-readonly-budgeting`
Head: `0cdd47238ead2dd8c28c7e04986ad731e3139d7e`

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
- The hosted broad pytest job failed, but its test-level failure output is not
  available through the unauthenticated API. This remains an unresolved CI
  gate, not a diagnosed product defect.
- Dependency Review failed with the exact diagnostic: `Dependency review is
  not supported on this repository. Please ensure that Dependency graph is
  enabled`, directing the maintainer to repository Settings → Code security
  and analysis (`/settings/security_analysis`). The gate remains enabled.

## Owner/runtime coverage

The installed owner runtime available on this host is not Hades: the AEGIS
owner service is stopped, and the only unrelated listening application is an
Odysseus process on port 7001. No authenticated Hades owner interaction was
replayed, no real Plaid authorization was attempted, and no live network scan
was issued. Unit and contract tests therefore do not claim owner acceptance,
provider behavior, screenshot evidence, or live scan completion.

The affected implementation is nevertheless covered by existing bounded
tests for Plaid configuration/link authorization/sync recovery, canonical
Finance and grocery/pantry state, network approval/continuation/results, and
Hades branding/UI projections. No new duplicate subsystem was introduced.

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
