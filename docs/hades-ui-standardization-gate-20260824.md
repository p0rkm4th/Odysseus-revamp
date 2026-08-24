# Hades early UI standardization / OSINT visibility gate

Checkpoint source before this batch: `374c400b`.

## Implemented

- Added shared Hades UI grammar in `static/js/ui-components.js`: module
  headers, status badges, empty/loading/error/success states, intake fields,
  provenance badges, and a stable line-icon family.
- Added shared design tokens and responsive component classes to
  `static/style.css`.
- Added OSINT directly to primary Tools navigation and the Ctrl+K command
  surface.
- Added `static/js/osint.js`, a workspace window with Overview, New
  Investigation, Cases, Targets, Research, Sources, Facts, Inferences,
  Relationships, Timeline, Evidence, and Reports sections.
- New Investigation accepts Person, Company, Organization, and Domain targets;
  free-form known information; structured clues; URLs/files/images; and Quick,
  Standard, or Deep Dive depth.
- Intake uses the existing owner-scoped `/api/research/start` path and
  `research.public_sources`/`manage_osint` policy boundary. It does not create
  a second crawler or UI-only execution path.
- Existing research JSON is seeded at intake (`case_stage=intake`,
  `review_required=true`, owner/provenance stamped) and replaced by the
  completed sourced report, making the investigation recoverable immediately.

## Browser evidence

Host-side Playwright acceptance against `http://127.0.0.1:7001` passed:

- visible `#tool-osint-btn`
- OSINT workspace header
- all 12 required tabs
- all required New Investigation fields
- desktop rendering
- 375px mobile header/layout fit

Screenshot captured at `/tmp/osint-ui-gate.png` during acceptance.

## Verification

- JavaScript syntax checks passed for shared components, OSINT, search, and app
  shell.
- Focused Python tests: `17 passed, 1 warning`.
- Prior full regression before this batch: `5894 passed, 3 skipped, 180
  warnings, 0 failed`.

## Remaining gate work

The OSINT UI is visible and intake-complete, but dossier/detail, graph,
timeline, correction/review, and an authenticated live provider-backed
investigation remain productization work. A provider-backed run should be
dogfooded when the configured research endpoint is available.
