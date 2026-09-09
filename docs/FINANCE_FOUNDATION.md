# Finance foundation

This slice provides synthetic/fixture-backed Finance truth. It does not
connect Plaid or access live financial data.

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

The future Plaid adapter belongs in front of this seam. It should normalize
provider data here rather than change canonical Finance truth.

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

The next campaign is **Plaid Sync + Read-Only Budgeting Conversation**.
Deferred work includes Plaid credentials/Link/sync, budgeting conversation,
forecasting, settle-up allocation/payment execution, and any unrelated
Kitchen, Telegram, or Homelab expansion.
