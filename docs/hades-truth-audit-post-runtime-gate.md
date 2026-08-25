# Hades truth audit — post-runtime-gate comparison

Observed: 2026-08-24  
Source candidate: `98dbb0368a9e6e83a089ec8384b20f145ad80ca2`  
Candidate image: `odysseus:candidate-26444587`  
Candidate digest: `sha256:9518d18e01b590a6346a6894817b9861def94d014fc17c13484a755edaf03167`

This is a bounded rerun of the independent truth-audit methodology. It does
not overwrite the historical `docs/hades-truth-audit.md`, and it does not
promote the currently running service to source-matched acceptance.

## Before / after

| Area | Before | After | Evidence |
|---|---|---|---|
| Source/build identity | running `/app` differed from checkout; no identity API | candidate `sha256:9518d18e...` is running; `/api/version` source/build/frontend/migration IDs match | E4/E5; API image_id remains unknown but external digest is recorded |
| Frontend identity | no build marker or canonical verification command | static marker plus `npm run test:frontend` | E2/E4 candidate |
| Compact navigation | separate hard-coded legacy rail omitted newer modules | workspace registry projects the same nine workspaces into grouped sidebar and compact rail | source/focused E2; synthetic browser E4 |
| Architecture convergence | duplicate paths were documented informally | module parity, workspace IA, and convergence artifacts recorded | E1/E2 |
| Full regression | historical counts varied 6063/6064 | current run: 6076 passed, 3 skipped, 186 warnings | E3; deterministic within this run |
| Migrations | prior audit reported fresh/rerun/copied passes | fresh and rerun loaded 21 registered versions | E3 |
| Broker | host namespace check falsely suggested missing socket | socket verified inside application container with owner/mode and SO_PEERCRED boundary preserved | E5 current deployment |
| Ollama | prior loopback probe failed | bridge endpoint responds, lists `qwen3:8b`, and container reaches `/api/version` | E5 bridge; inference request pending |
| Vector/memory | degraded/unverified | ChromaDB heartbeat succeeds; VectorRAG and MemoryVectorStore startup logs report healthy local FastEmbed fallback; HTTP embedding lane unavailable | partial/healthy-fallback |
| Browser | Playwright unavailable | repo-scoped Chromium and canonical window/realistic OSINT suites pass | E3/E4 synthetic |
| Action execution parity | weak Qwen network request ended in prose and grounding safeguard | one bounded deterministic `manage_homelab` plan repair now precedes approval/execution; exact-scope/broker path unchanged | E2/E4 synthetic; owner retest pending |
| Agent-to-Work provenance | detached agent stream had no durable Run proof | owner/session actionable turns now create/reuse one Work Run and project registered ToolBinding actions/results with exact approval references | E2 focused; owner-live continuation pending |

## Remaining discrepancies

1. HTTP embedding remains unavailable; VectorRAG and MemoryVectorStore are
   healthy through the explicit local FastEmbed fallback. Fresh owner-memory
   dogfood remains auth-gated.
2. Broker negative tests and authenticated runtime `/api/version` verification
   against the candidate remain deployment-gated.
3. Owner-live network/action and visual acceptance remain distinct from the
   synthetic suites.
4. Durable Work projection is focused-tested but the deployed candidate and
   owner-live “Continue” behavior still require acceptance.
5. The 186-warning set remains classified but not broadly reduced; SQLAlchemy,
   UTC datetime, Pydantic, and third-party warnings should be handled in a
   separate debt batch.

## Evidence boundary

Source and focused tests are E1/E2; the full regression and migration rehearsal
are E3; the candidate image is E4 source-attributable. Runtime E4/E5 applies
only after deployment from the recorded digest. Owner browser/dogfood remains
E6-blocked because no owner-authenticated session is available to this agent.
