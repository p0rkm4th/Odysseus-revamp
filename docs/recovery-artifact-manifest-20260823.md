# Recovery artifact manifest

The accepted Hades baseline intentionally does not commit the following
preserved local artifacts:

- `odysseus-hades.bundle` — local Git bundle used for recovery inspection.
- `odysseus_fasttrack_*.py`, `odysseus_install_authorization_*.py`,
  `odysseus_intent_fusion_*.py`, `odysseus_network_recon_intent_*.py`,
  `odysseus_orchestration_*.py`, `odysseus_privileged_broker_*.py`,
  `odysseus_route_policy_*.py`, and `odysseus_supervision_*.py` — historical
  self-applying patch artifacts. Their applied behavior is represented by the
  committed runtime source and tests; the original files remain locally for
  provenance.
- `BUNDLE_PIVOT.md` — earlier bundle-pivot note superseded by the consolidation
  and acceptance records.
- `static/app.js.pre-rag-default` — historical frontend snapshot, not a runtime
  source file.
- `docker-compose.override.raw-vault.disabled.yml` — local-only disabled
  Obsidian mount configuration containing machine-specific paths.

The following are also excluded by the repository's existing data/credential
rules and must never be committed: databases, database backups, auth files,
sessions, tokens, `.env` files, caches, logs, uploads, and generated artifacts.

Canonical recovery/consolidation evidence is retained in:

- `docs/consolidation-milestone-20260823.md`
- `docs/hades-baseline-acceptance-20260823.md`
- the committed runtime modules, migrations, frontend, tests, and Jarvis
  benchmark harness.
