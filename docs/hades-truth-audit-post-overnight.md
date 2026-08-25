# Hades post-overnight truth audit

Date: 2026-08-25  
Branch: `recovery/live-candidate-20260823`  
Final source under audit: `38e3f984`

## What changed

- Preserved and committed the handoff IntentFrame/domain-contract, canonical
  IT-asset read, bounded network service-enumeration, target-propagation, and
  action-exposure work as `be1435f8`.
- Audited original/recovered Odysseus versus newer Hades ownership in
  `docs/hades-architecture-convergence-audit.md`.
- Converged expanded workspace grouping onto the existing
  `WorkspaceDefinition`/`ModuleDefinition` registry. Virtual/contextual
  modules now have explicit metadata instead of silently missing registration.
  Commits: `5163533d`, `12494174`.
- Kept legacy routes/DOM bindings and mature provider implementations as
  compatibility/adaptation paths; no backend databases were merged.
- Added a first-class read-only `memory.read` Capability and `read_memory`
  ToolBinding over the existing canonical Brain store. This is an adapter, not
  a second memory engine; legacy mutations remain compatibility-only.
- Added a first-class read-only `work.read` Capability and `read_work`
  ToolBinding over the existing durable WorkEngine. Overview, review, context,
  and typed list reads remain owner-scoped structured projections; no second
  Work store or filesystem fallback was introduced.
- Added a first-class read-only `household.read` Capability and
  `read_household` ToolBinding over the existing owner-scoped InventoryService
  for household overview, listing, search, and item reads. Household Inventory
  remains distinct from technical CMDB/IT Assets.
- Added a first-class read-only `setup.read` Capability and `read_setup`
  ToolBinding over existing secret-free SetupCenterService projections for
  state, integrations, and permissions. Setup metadata remains distinct from
  authority and never resolves secrets.
- Preserved the mature `api_call` integration routing rule pack while adding
  Setup/Integration guidance; the full regression caught and verified this
  convergence detail.
- Added owner-scoped OSINT case reads (`list_cases`/`get_case`) through the
  existing public-source capability and durable research case store. Report
  prose remains tainted and does not promote itself into canonical claims.
- Built and deployed `odysseus:candidate-90cc66b0` with image
  `sha256:7434e78a8e375a8a37f09bdeb21e54d43c75f3612ca30da18fe0cad4f904ac18`.
  Runtime `/api/version`, container source hash, and browser/static checks are
  attributable to this commit; rollback `odysseus:rollback-0c18805fe1d0` is
  retained.

## Evidence

| Area | Evidence | Truth status |
|---|---|---|
| Python regression | 6120 passed, 3 skipped, 186 warnings | E3 |
| Focused contract/network/asset tests | green; workspace/theme focused tests green | E2/E3 |
| Frontend static verification | `npm run test:frontend` | E3 |
| Browser/window/realistic acceptance | all three repo commands pass against final candidate | E4 |
| Runtime provenance | `/api/version`, checkout/container hash, image digest agree | E4/E5 |
| Broker | socket present, `odysseus:odysseus`, mode 660 | E4/E5 |
| Ollama | bridge `/api/version` responds; model inference was verified at prior gate | E4/E5 |
| Owner-live dogfood | no owner-authenticated session available overnight | pending E6 |
| Memory read convergence | `memory.read`/`read_memory`, focused and full regression green | E3/E4 |
| Work read convergence | `work.read`/`read_work`, focused and full regression green | E3/E4 |
| Household read convergence | `household.read`/`read_household`, focused and full regression green | E3/E4 |
| Setup/Integration read convergence | `setup.read`/`read_setup`, focused tests green and deployed source-matched | E2/E4 |
| OSINT case read convergence | `research.public_sources` case reads, focused/full regression green | E3 pending deployment |

## Reuse and convergence decisions

New control-plane primitives remain canonical for consequential authority:
Capability → ActionSpec → Policy → Approval → ToolBinding/trusted executor,
Work Run/journal, CMDB identity, epistemic evidence, and workspace registry.
Original Email, Calendar, Telegram, Cookbook, Compare, document/media,
research, and operation implementations remain reused through adapters or
projections where their provider/product behavior is stronger.

Composed boundaries remain intentional: Household versus technical CMDB,
Deep Research versus OSINT cases, Calendar versus Work/Missions, semantic
memory versus vector index, and domain documents versus evidence references.

## Remaining truth gaps

- Intent contracts are implemented for technical assets, network, security
  findings, OSINT planning, explicit Memory reads, Work reads, Household
  reads, Setup/Integration state, and OSINT case reads. Richer domain reads still require
  canonical binding/result-contract adapters; they are not claimed complete.
- The legacy technical asset CLI storage is deployment-scoped rather than
  row-owner keyed. Hades entry is owner-aware, but multi-owner CMDB isolation
  remains a migration gap.
- Consequential legacy tool paths still need a bounded call-graph audit and
  strangler migration; no generic shell authority was added.
- Owner-live Memory, theme/sidebar visual acceptance, Telegram, and provider
  dogfood remain pending owner authentication/credentials.
- Vector/memory health and optional provider availability must continue to be
  reported honestly; no degraded subsystem is promoted by UI wording.

## Classification rule

Synthetic tests and source-matched browser tests are not owner dogfood. E6 is
reserved for the owner’s manual verification on the deployed candidate.
