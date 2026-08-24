# Hades Runtime Truth / Deployment Provenance Gate

Status: IN_PROGRESS — source-matched candidate deployed; browser/vector/owner gates pending  
Audited source: `febbfdbeeb8944830eaad0f62ea8f429fd4457c9`  
Branch: `recovery/live-candidate-20260823`  
Observed: 2026-08-24

This is a deployment/runtime evidence record. It does not promote source-only
or synthetic feature rows to live acceptance.

## Current evidence

| Area | Evidence | Level | Status |
|---|---|---:|---|
| Checkout identity | `git rev-parse HEAD` = `febbfdbe...` | E1 | VERIFIED |
| Git integrity | `git fsck --full` reports no integrity errors; dangling objects remain | E1 | VERIFIED |
| Test residue | empty ignored `tmp_pytest_probe/` directory; no files found | E1 | SAFE_RESIDUE |
| Running image | `sha256:f8f04bc8...` (`odysseus:candidate-febbfdbe`) | E4 | SOURCE_MATCHED |
| Running backend | `/app/app.py` hash `d32c9178...`; `/api/version` source commit matches `febbfdbe...` | E4/E5 | VERIFIED |
| Runtime build identity | source/build/frontend/migration values present; Docker digest recorded outside container; API `image_id` remains `unknown` | E4 | VERIFIED_WITH_DIGEST_NOTE |
| Broker | `/run/odysseus-privd.sock` exists inside `odysseus-odysseus-1`, mode `srw-rw----`, owned by `odysseus:odysseus`; app is PID 1 under that identity | E5 | VERIFIED |
| Ollama | host bridge `172.18.0.1:11434` returns version `0.31.1` and lists `qwen3:8b`; loopback refusal is expected from container namespace | E5 | VERIFIED_BRIDGE |
| Hades → Ollama | source-matched container probe to `host.docker.internal:11434/api/version` succeeds | E5 | VERIFIED |
| ChromaDB | source-matched container heartbeat succeeds | E5 | VERIFIED_ENDPOINT |
| Vector/memory | ChromaDB heartbeat and source-matched startup logs show VectorRAG and MemoryVectorStore healthy via local FastEmbed; HTTP embedding lane unavailable | E5 | HEALTHY_FALLBACK |
| Frontend architecture | intentionally unbundled static assets; canonical `npm run test:frontend` now runs Node syntax/static checks | E2 | VERIFIED_SOURCE |
| Playwright | not yet reproduced in repo-scoped environment | E0 | PENDING |
| Candidate image | `odysseus:candidate-febbfdbe`, digest `sha256:f8f04bc8...` | E4 | VERIFIED_SOURCE_MATCHED_CANDIDATE |
| Candidate frontend | `frontend-febbfdbe...-fe7841...` | E4 | VERIFIED_SOURCE_MATCHED_CANDIDATE |
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

The running service has been recreated from the candidate built from the
audited source. `/api/version`, container labels, backend hash, and recorded
container digest agree on source/build identity. The image digest is recorded
outside the container because Docker does not inject it into image environment
automatically.
Broker negative tests, browser acceptance, and owner-live visual acceptance
remain pending; vector/memory is healthy through the explicit local fallback.
