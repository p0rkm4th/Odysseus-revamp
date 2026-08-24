# Hades Runtime Truth / Deployment Provenance Gate

Status: IN_PROGRESS — candidate source/build verified; deployment/browser gate pending  
Audited source: `23abf48e22cd2af574544df3324533d8ae73c3e1`  
Branch: `recovery/live-candidate-20260823`  
Observed: 2026-08-24

This is a deployment/runtime evidence record. It does not promote source-only
or synthetic feature rows to live acceptance.

## Current evidence

| Area | Evidence | Level | Status |
|---|---|---:|---|
| Checkout identity | `git rev-parse HEAD` = `23abf48e...` | E1 | VERIFIED |
| Git integrity | `git fsck --full` reports no integrity errors; dangling objects remain | E1 | VERIFIED |
| Test residue | empty ignored `tmp_pytest_probe/` directory; no files found | E1 | SAFE_RESIDUE |
| Running image | `sha256:c09af676...` | E4 | SOURCE_MISMATCH |
| Running backend | `/app/app.py` hash differs from checkout; `/api/version` only returns `1.0.2` | E4 | SOURCE_MISMATCH |
| Runtime build identity | no source/build environment values in running container | E4 | BROKEN |
| Broker | `/run/odysseus-privd.sock` exists inside `odysseus-odysseus-1`, mode `srw-rw----`, owned by `odysseus:odysseus`; app is PID 1 under that identity | E5 | VERIFIED |
| Ollama | host bridge `172.18.0.1:11434` returns version `0.31.1` and lists `qwen3:8b`; loopback refusal is expected from container namespace | E5 | VERIFIED_BRIDGE |
| Hades → Ollama | container probe to `host.docker.internal:11434/api/version` succeeds | E5 | VERIFIED |
| Vector/memory | not yet re-probed against a source-matched candidate | E0 | PENDING |
| Frontend architecture | intentionally unbundled static assets; canonical `npm run test:frontend` now runs Node syntax/static checks | E2 | VERIFIED_SOURCE |
| Playwright | not yet reproduced in repo-scoped environment | E0 | PENDING |
| Candidate image | `odysseus:candidate-23abf48`, digest `sha256:2655cb3e...` | E4 | VERIFIED_SOURCE_MATCHED_CANDIDATE |
| Candidate frontend | `frontend-23abf48e...-f58ebd...` | E4 | VERIFIED_SOURCE_MATCHED_CANDIDATE |
| Candidate migration head | `20260824_011_sandbox_v1`; fresh and rerun rehearsal each loaded 21 versions | E3 | VERIFIED |

## Remediation in this gate

- Docker candidates accept and embed source commit, build ID, build time,
  frontend build ID, and migration head as image environment and OCI labels.
- `/api/version` now exposes those non-secret identity fields plus the loaded
  migration head.
- Served HTML carries the frontend build ID in a meta marker.
- `scripts/build_candidate.sh` builds from the exact current Git checkout and
  prints the resulting local image ID without deploying it.
- `npm run test:frontend` is the canonical verification command for the
  unbundled frontend.

## Acceptance still required

The running service must be recreated from the candidate built from the audited
source, then `/api/version`, container labels, backend hashes, and frontend
marker must agree. A candidate build alone is not deployment acceptance.
Broker negative tests, vector/memory health, browser acceptance, and the
post-gate independent audit remain pending.
