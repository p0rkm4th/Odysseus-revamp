# Hades productization roadmap

## Current checkpoint

- V2 baseline source: `120e4afa9d0cd60fff3f6225c42d131837c6c260`.
- Accepted baseline image: `sha256:b3f65991b7c59ed77118e15ed3e3faae2eea1d02d01169aa20b566ca19f06e97`.
- Accepted regression: `5890 passed, 3 skipped, 174 warnings, 0 failed`.
- Canonical network discovery: `homelab.manage` → `execute_network_discovery` → `manage_homelab` → `host_broker`.
- Fresh Luna and Qwen broker executions, exact approval continuation, CMDB
  observations, Network Map update, reconnect/model-switch/browser/container
  continuity, and immediate referent coverage are accepted stabilization
  evidence. Do not repeat that archaeology unless a regression appears.

## Dependency-ordered batches

1. **P0 baseline freeze:** preserve the accepted stabilization as rollback state and keep network/continuity invariants in regression.
2. **Tier 1 census and grammar:** make capability ownership, module states, authority, intake, dossiers, timelines, provenance, search, and window behavior inspectable and uniform.
3. **Tier 1 self/memory/Life:** unify identity, runtime health, Work state, capabilities, commitments, Attention, memory diagnostics, Episodes/Lessons, reviews, habits, and deterministic briefs on existing stores.
4. **Tier 2 communications:** productize Telegram continuity/voice and Email/Calendar/Contacts/Documents bridges.
5. **P2 local operations:** expand the existing bounded Homelab operation catalog and capability dependency health; then productize Household, IT/CMDB, Network history/change detection.
6. **P3 security/OSINT:** complete authorized assessment and public-source case workflows with evidence-linked reports.
7. **P4 communications/business:** expose Telegram cross-channel continuity, voice, Email/Calendar/Contacts links, and Work-based CRM.
8. **P5/P6 integrations and polish:** Home Assistant, PWA/share intake, multimodal/documents, Improvement/Model Lab/Developer surfaces, accessibility, and final uniformity.

Every batch must update the feature matrix, run focused tests, preserve policy
invariants, and leave a deployable commit. Schema changes require fresh,
rerun, and copied-database rehearsal before promotion. A partial backend or
sidebar entry is not a productized domain.

## V2 continuation checkpoint

The first active batch is the census/grammar boundary. Existing canonical
owners are sufficient for the initial Self, Attention, Work/Life, memory, and
window work; new tables are not justified until a focused gap is demonstrated.

## Completed V2 batches

- Updated the bounded existing-capability census and cross-cutting ownership map.
- Corrected the matrix/roadmap to the accepted `120e4afa…` baseline and made
  Tier 1 acceptance gates explicit.
- Added `PersistentAgent.operating_brief()` and `/api/hades/brief`, a
  deterministic daily/weekly projection over Self, Work review, Attention,
  capabilities, activity, and Episodes. It creates no new canonical state,
  model claims, or action claims.
- Added daily/weekly brief switching to the existing Hades window and focused
  tests for bounded horizon and grounding metadata.
- Extended the existing Ctrl+K conversation search surface with canonical
  module commands. Commands invoke existing module controls only; they do not
  create a UI-only execution path or bypass policy.
- Began the early UI standardization gate: added shared tokens and reusable
  header/state/badge/intake/provenance primitives, made OSINT explicit in the
  primary sidebar and command palette, and added an OSINT workspace with the
  required investigation tabs and review-oriented intake over the existing
  public-source research service.
- Made research intake seeds durable at start in the existing owner-scoped
  research store (`case_stage=intake`, `review_required=true`), so an OSINT
  investigation is recoverable before asynchronous results complete.

## Completed batches in this continuation

- Persisted `AssistantInstance.last_seen_at` and made `/api/hades/while-away`
  default to the persisted marker.
- Added `/api/hades/attention`, projecting unread notifications, blocked or
  awaiting Work runs, and open commitments without duplicating canonical state.
- Preserved notification source entity/run references for overdue commitments.
- Added a Hades workspace Attention Queue section.
- Added a deterministic Work Life Review projection for focus goals, due-soon
  and overdue commitments, due tasks, blocked tasks, and waiting runs.
