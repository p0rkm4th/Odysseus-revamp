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

## Deferred

This bounded campaign does not implement Plaid Link UI, paid real-time balance
refresh, FX, categorization AI, forecasting, liabilities, recurring-bill
automation, automatic sharing, settle-up allocation/payment execution, or any
unrelated Kitchen, Telegram, or Homelab expansion. A live sync requires a
legitimate HADES Plaid authorization and is not faked when absent.
