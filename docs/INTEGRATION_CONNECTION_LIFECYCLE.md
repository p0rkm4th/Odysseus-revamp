# HADES integration connection lifecycle

HADES owns the authenticated, owner-scoped lifecycle for external connections.
Plaid supplies provider authorization, item identifiers, encrypted-token-backed
API calls, synchronization, and provider errors; it does not define HADES
capability or completion state.

The first reusable seam is the `FinanceConnection` record. Its canonical states
are `NOT_CONFIGURED`, `AUTHORIZATION_REQUIRED`, `AUTHORIZATION_IN_PROGRESS`,
`CONNECTED`, `SYNCING`, `HEALTHY`, `DEGRADED`, and `RECONNECT_REQUIRED`.
`PlaidItem` remains provider detail and points to exactly one connection. Link
sessions are short-lived, owner/connection-bound, state-hashed, expiring, and
single-use. Their continuation records the original connection operation so a
completed Link flow does not require a second owner command.

Permanent Plaid credentials enter encrypted server-side secret storage and are
never projected to the browser, tools, model context, or logs. A connection is
`HEALTHY` only after the existing bounded Plaid sync reconciles and verifies
canonical Finance state. `ITEM_LOGIN_REQUIRED`-class failures become
`RECONNECT_REQUIRED`; Plaid update-mode Link repairs the same connection and
reuses its access token.

Capability availability is a deterministic projection of the owner’s canonical
connection state. It grants no additional Finance authority and does not share
private Finance with a household. Finance reads remain owner-scoped,
read-only, currency-qualified, and freshness-aware.

Generalization review: Google Calendar, Gmail, and Home Assistant can use the
same HADES lifecycle with provider-specific authorization/credential/health
adapters and domain-specific canonical ingestion. No Plaid `item_id`, public
token, transaction cursor, or Plaid error code is required in the generic
lifecycle contract.

The design also preserves the AEGIS reference boundary used during this slice:
human authorization is a continuation point, policy precedes provider action,
verification precedes completion, capability state is structured, and secrets
remain outside model cognition. AEGIS runtime code is not imported.
