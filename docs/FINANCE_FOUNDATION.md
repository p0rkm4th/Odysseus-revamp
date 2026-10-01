# Finance foundation

This slice provides owner-scoped canonical Finance truth and a read-only Plaid
Transactions Sync adapter. Live authorization remains an environment/owner
concern; all provider behavior is also proven with mocked responses.

## Ownership and privacy

`FinanceAccount` and `FinanceTransaction` rows always have a non-null owner.
Private reads filter by the authenticated storage owner. Household membership
does not grant access to another member's private account or transaction.

`Household` and `HouseholdMembership` provide the smallest explicit household
boundary needed here, with `owner` and `member` roles. Finance never treats
`owner IS NULL` as shared authorization.

## Import seam

`src/finance_service.py` accepts normalized provider-neutral account and
transaction dictionaries. Provider/account/transaction identities are scoped
and replay-safe. Reimporting a known identity reconciles the canonical row;
malformed amount, currency, date, status, or merchant/description data is
rejected. Money is stored as decimal-safe, currency-qualified numeric data.

`src/plaid_transport.py` uses Plaid `/accounts/get`, `/item/get`, and
`/transactions/sync`. The access token is stored through the existing encrypted
secret type and is never returned to routes or model context. Sync fetches a
bounded complete page sequence, restarts from the original cursor on
`TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION`, then reconciles accounts,
added/modified/removed transactions, and the final cursor in one database
transaction. A failed page therefore cannot produce a false successful cursor.

Plaid's positive amounts are normalized to explicit `outflow` direction and
negative amounts to `inflow`; the canonical amount is non-negative. Pending
predecessors remain historical evidence when a posted transaction replaces
them, while current reads exclude provider-removed rows. Replays are
provider-identity upserts and are idempotent.

## Local CSV fallback

When Plaid is unavailable, an authenticated owner can import a bounded local
bank export from Integration Center. Common bank header variants are accepted:
date/transaction date/posted date, amount (or debit and credit), and
merchant/name/description/payee. Optional currency, direction, status,
category, and memo fields are preserved in canonical Finance fields. Dates in
ISO, US slash, and year-first slash formats plus ordinary currency formatting
are supported; rows that still lack an unambiguous date, identity, or amount
are rejected. Imports use the existing owner-scoped Finance account and transaction tables with
provider `csv`, are labeled `local_csv` and `live_provider: false`, and never
claim live balances or Plaid connectivity. Repeating the same file is
idempotent, duplicate rows remain distinct, and the entire snapshot commits
atomically so a malformed row leaves no partial ledger behind. CSV data follows
the same deterministic currency-separated spending, cash-flow, pending, and
coverage rules as Plaid.

Deterministic Finance reads are available through `finance.read`/
`read_finance`: coverage, bounded transactions, posted spending, currency-
separated cash flow, and explicit shared-expense projections. Pending rows are
not included in posted spending, currencies are never silently combined, and
coverage/as-of/sync health travels with the result. The model may explain
these facts but does not calculate authoritative totals or choose an owner.

## Explicit household projection

Sharing creates a `SharedExpense` relation from an owned private transaction
to one household. The source remains private and owned by its original user.
The household projection contains only coordination fields: payer, amount,
currency, date, merchant/label/note, source provider, and pending/posted
status. It does not expose account metadata, provider payloads, or credentials.

The source owner can revoke the projection without deleting the private
transaction. This slice does not execute payments, transfers, or settle-up.

## Authenticated seams

The `/api/finance` routes call `FinanceService` beneath presentation. They
support account/transaction reads and normalized imports, membership reads and
bounded household membership setup, explicit share/revoke, household shared
expense reads, and a bounded model-facing read projection. Models do not make
authorization decisions or receive unrestricted database access.

Plaid Link is owner-facing in Integration Center. HADES creates a short-lived
Link token for the authenticated owner, stores only its digest in
`finance_plaid_link_sessions`, and exchanges the one-time browser public token
server-side. The resulting permanent access token is encrypted in `PlaidItem`
and never enters browser payloads or model context. Successful exchange enters
the existing read-only sync seam; Link never grants financial mutation.

Pantry and grocery records use the existing owner-scoped inventory service.
Items can be edited, soft-archived, stocked, consumed, and explicitly marked
for the grocery list from the UI or the bounded `manage_assets` inventory
actions. Grocery membership is metadata/state only and does not alter stock
until a separately verified stock operation occurs.

## Deferred

This bounded campaign does not implement paid real-time balance refresh, FX,
categorization AI, forecasting, liabilities, recurring-bill
automation, automatic sharing, settle-up allocation/payment execution, or any
unrelated Kitchen, Telegram, or Homelab expansion. A live sync requires a
legitimate HADES Plaid authorization and is not faked when absent.
