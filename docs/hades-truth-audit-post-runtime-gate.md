# Hades truth audit — post-runtime-gate comparison

Observed: 2026-08-24  
Source candidate: `febbfdbeeb8944830eaad0f62ea8f429fd4457c9`  
Candidate image: `odysseus:candidate-febbfdbe`  
Candidate digest: `sha256:f8f04bc8e50c6e7cf2c6f2d60d00590e88c0e606c927624029fc57685b576a4c`

This is a bounded rerun of the independent truth-audit methodology. It does
not overwrite the historical `docs/hades-truth-audit.md`, and it does not
promote the currently running service to source-matched acceptance.

## Before / after

| Area | Before | After | Evidence |
|---|---|---|---|
| Source/build identity | running `/app` differed from checkout; no identity API | candidate `sha256:f8f04bc8...` is running; `/api/version` source/build/frontend/migration IDs match | E4/E5; API image_id remains unknown but external digest is recorded |
| Frontend identity | no build marker or canonical verification command | static marker plus `npm run test:frontend` | E2/E4 candidate |
| Compact navigation | separate hard-coded legacy rail omitted newer modules | workspace registry projects the same nine workspaces into grouped sidebar and compact rail | source/focused E2; browser pending |
| Architecture convergence | duplicate paths were documented informally | module parity, workspace IA, and convergence artifacts recorded | E1/E2 |
| Full regression | historical counts varied 6063/6064 | current run: 6074 passed, 3 skipped, 186 warnings | E3; repeat run still desirable |
| Migrations | prior audit reported fresh/rerun/copied passes | fresh and rerun loaded 21 registered versions | E3 |
| Broker | host namespace check falsely suggested missing socket | socket verified inside application container with owner/mode and SO_PEERCRED boundary preserved | E5 current deployment |
| Ollama | prior loopback probe failed | bridge endpoint responds, lists `qwen3:8b`, and container reaches `/api/version` | E5 bridge; inference request pending |
| Vector/memory | degraded/unverified | ChromaDB heartbeat succeeds; VectorRAG and MemoryVectorStore startup logs report healthy local FastEmbed fallback; HTTP embedding lane unavailable | partial/healthy-fallback |
| Browser | Playwright unavailable | still unavailable in repo-scoped environment | blocked_external/tooling |

## Remaining discrepancies

1. VectorRAG, embedding provider, and MemoryVectorStore need a fresh health and
   synthetic grounding probe.
2. Playwright is not installed in the canonical environment; realistic OSINT,
   workspace, compact/mobile, theme, and multi-window acceptance cannot yet be
   claimed.
3. Broker negative tests and authenticated runtime `/api/version` verification
   against the candidate remain deployment-gated.
4. The 186-warning set remains classified but not broadly reduced; SQLAlchemy,
   UTC datetime, Pydantic, and third-party warnings should be handled in a
   separate debt batch.

## Evidence boundary

Source and focused tests are E1/E2; the full regression and migration rehearsal
are E3; the candidate image is E4 source-attributable. Runtime E4/E5 applies
only after deployment from the recorded digest. Owner browser/dogfood remains
E6-blocked because no owner-authenticated session is available to this agent.
