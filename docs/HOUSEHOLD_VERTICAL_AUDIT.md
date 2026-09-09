# HADES household vertical foundation audit

Baseline: `main` at `364380ed3f46c1d14d3229e5b7530698cfa22e65`.
This is diagnosis only. No Finance, Kitchen, Telegram, auth, model-routing,
or Homelab remediation was performed. No production feature, migration,
database, service, credential setup, external action, auth change,
model-routing change, or Homelab authority expansion was performed. AEGIS was
halted in its own repository first and is reference-only for this HADES
campaign.

## 1. Finance — ASPIRATIONAL

No Plaid adapter, Finance canonical transaction model, expense-sharing model,
or settle-up implementation was found in the baseline. The current generic
WorkEngine provides the likely orchestration seams but not the vertical:

`authenticated route → WorkEngine goal/project/run/action → WorkResult and
verification` is available through `routes/work_routes.py:14-36, 116-145, 131`
and `src/work_engine.py:53-60, 245-270, 597-741`.

The future Finance path must add, without conflation:

* Plaid/live sync → a Finance-owned canonical transaction persistence seam;
* private per-owner state through `require_user()` and
  `effective_storage_owner()` (`src/auth_helpers.py:74-119`,
  `src/owner_identity.py:31-55`);
* an explicitly shared household-expense projection, separate from private
  transactions;
* bounded conversation/model context through the existing chat/tool seams;
* independent sync, import, sharing, and settle-up verification.

Those are missing seams, not an implementation plan executed here. No Plaid
credentials were accessed.

## 2. Kitchen / Grocery — ASPIRATIONAL

The baseline has reusable inventory-shaped primitives, not a proven household
grocery vertical. Relevant current seams are `core/inventory_models.py`,
`src/inventory_service.py`, `routes/inventory_routes.py`,
`src/agent_tools/inventory_tools.py`, and `tests/test_household_projection.py`.
They can provide future canonical item state, owner-scoped route access, and
projection tests, but no inspected end-to-end grocery read/write/verification
path was established.

The smallest future seam is:

`inventory/grocery canonical state → shared-household projection → existing
authenticated route/tool binding → verified result`.

No kitchen schema, migration, parser, or mutation was added.

## 3. Telegram — ASPIRATIONAL

Telegram is scaffolded but not proven as a configured reachable application
path. `routes/telegram_routes.py:1-140` exposes authenticated lifecycle and
pairing/session controls. `src/telegram_runtime.py:17-38` constructs an
explicitly supervised runtime; `src/telegram_poller.py:30-209` handles private
long-poll dispatch, receipts, pairing, and approval callbacks; and
`src/telegram_transport.py:62-208` validates private updates and calls the Bot
API. `core/telegram_models.py:13-109` persists owner-bound connections,
sessions, receipts, and callback approvals.

The application comments in `app.py` state that Telegram polling is not
started merely by route registration. No token or live reachability evidence
was available in this audit. Therefore the complete configured transport →
session → conversation path is not REAL.

## 4. Auth / owner scoping — ASPIRATIONAL for the three-person household

Single-owner scoping is real for WorkEngine: `routes/work_routes.py:15-20`
requires an authenticated request and converts it to a storage owner;
`src/work_engine.py:56-60` and the route projections query by that owner.
`tests/test_work_engine.py:178-186` proves cross-owner run access is rejected.

The login/session identity path is implemented through the auth middleware and
`src/auth_helpers.py:6-119`; named users can be resolved, and
`src/owner_identity.py:31-55` distinguishes authenticated owners from sentinel
or local identities.

That does not establish the requested household boundary. No inspected
canonical shared-expense membership/projection policy proves that Scotty,
his girlfriend, and her roommate can each see explicitly shared rows while
private finance rows remain private. Verdict is therefore ASPIRATIONAL for
the three-person platform, despite real single-owner isolation.

## 5. Model routing — REAL for configurable provider/model selection

HADES has a runnable provider-selection path. `core/database.py:520-582`
persists owner-aware model endpoints and provider-auth metadata;
`src/endpoint_resolver.py:78-152, 267-408` resolves provider transport,
owner-visible endpoints, model lists, and chat URLs; and
`src/foreground_model_routing.py:1-180` applies an explicit owner-scoped
foreground fallback policy with bounded candidates and availability statuses.
The webhook/chat route consumes these seams in
`routes/webhook/webhook_routes.py:237-369`. Relevant coverage includes
`tests/test_foreground_model_routing.py`, `tests/test_endpoint_resolver_models.py`,
`tests/test_model_routes.py`, and `tests/test_provider_endpoints_models.py`.

This is REAL as model routing/configuration, not evidence of a household
Finance budgeting capability or a model tournament.

## 6. Homelab operations — REAL for bounded configured operations

The runnable chain is:

`authenticated owner/tool request → routes and capability binding →
src/homelab_operations.py → bounded private-network/service runner and receipt
store → canonical observation/result`.

`src/homelab_operations.py:21-37, 249-429` bounds private targets, records
plans/observations, and rejects replayed discovery plans. Its operation surface
includes inspect/status, planned restart, bounded discovery, and service
enumeration; execution profiles and explicit plan receipts gate privileged
operations. `tests/test_homelab_workspace_surface.py` proves the owner surface
and identity-safe discovery presentation, while the network and homelab test
families exercise the bounded operations and scope rules.

This verdict is limited: it does not imply unrestricted shell access, broad
host authority, or a household Finance/Kitchen integration.
