# Hades consolidated baseline acceptance

Accepted candidate: `odysseus-odysseus:latest`

Digest: `sha256:f47c43367aa14df28af83917997664ce98bd5e1de462a06ff44a9000a4331339`

Rollback retained: `odysseus-odysseus:rollback-live-candidate-20260823`

Rollback digest: `sha256:aebd73fc09bec66b43084affcde704462577b13e4300ed1959204209b729fb7f`

## Test acceptance

- Broad suite: **5842 passed, 4 skipped, 0 failed**.
- Critical consolidation/security subset: **261 passed**.
- The four skips are existing explicitly skipped tests; no new skip was added.

The eight original failures were all stale tests, not implementation
regressions. They assumed shell/tool execution could proceed from a model
emission without accounting for the current tainted-skill provenance gate.
The tests now suppress automatic skill injection only in transport/routing
fixtures, so they test their stated seam while production retains exact
approval behavior.

| Test area | Old expectation | Current behavior | Classification |
|---|---|---|---|
| Native function-call execution | Native `bash` call executes immediately | Editable skill context is tainted; shell requires exact approval | STALE TEST |
| Non-native fenced execution | Fenced `bash` executes immediately | Same exact-approval boundary applies | STALE TEST |
| Selected-model multi-round routing | Tool round followed by another model round | First tool is held for approval unless the fixture supplies a clean context | STALE TEST |
| Later-round HTTP 400/429 handling (2 cases) | Second provider request occurs after the tool | Approval gate stops before the second request in the old fixture | STALE TEST |
| Pinned fallback force-answer recovery (2 cases) | Five pinned fallback rounds occur | First shell proposal is held for exact approval | STALE TEST |
| Tool cancellation on generator close | Long-running tool starts before disconnect | Old fixture was stopped by approval before creating the task | STALE TEST |

## Authenticated live acceptance

Authenticated live checks passed against the deployed container:

- Inventory UI shell loaded with Inventory surface and served inventory
  JavaScript.
- All/IT/household/kitchen inventory queries and search returned 200.
- Temporary IT asset was created, structured hostname/serial/IP fields were
  persisted and reloaded, then retired.
- Reviewable household intake draft was created, explicitly confirmed, and
  replayed with `replayed: true`.
- Temporary acceptance items and drafts were removed/archived after testing.
- CMDB summary loaded: 8 assets, 10 observations, 1 active relationship.
- IP-only CMDB identity matching remained false.
- Bounded homelab host status and private-network discovery planning passed.
- Public OSINT query returned data, was marked tainted, and private-target
  validation rejected loopback access.
- Telegram status and pairing-code issue/revoke lifecycle passed; polling was
  not enabled.
- Economic status loaded and reported `external_execution_available: false`.
- Improvement candidate/history surfaces loaded authenticated.

## Runtime lineage

- Source HEAD before freeze: `85297cee44f8c5b3aa4bbf54ab482f5f7513baa5`.
- Source commit: the commit referenced by the immutable source tag
  `hades-baseline-20260823` (the final SHA is recorded in the freeze handoff).
- Source tag: `hades-baseline-20260823`.
- Worktree: clean; preserved recovery artifacts remain ignored and local-only.
- Running Compose service image: `odysseus-odysseus:latest` at the accepted
  digest above.
- Migration registry:
  `20260822_001_inventory_v1`, `20260822_002_economic_work_v1`,
  `20260822_003_telegram_v1`, `20260822_004_safe_improvement_v1`,
  `20260823_002_inventory_network_discovery`.
- Database backup: `data/app.db.consolidation-backup-20260823-161451`.
- Auth backup: `data/auth.json.consolidation-backup-20260823-161451`.
- Verification rebuild from the clean source commit: image
  `odysseus-hades-source-verify:8d3c18a4`, digest
  `sha256:0a9d274410e624c5e0f0091cfc697391693f14bc1e8ac9289d56be6910ae674b`.
  It imported the application and exposed the accepted capability and
  Inventory schema. Build metadata differs from the accepted live image, so
  byte identity is not expected; runtime source content was verified.

The immutable acceptance tag is `odysseus-odysseus:hades-baseline-20260823`.
The rollback image is intentionally retained.
