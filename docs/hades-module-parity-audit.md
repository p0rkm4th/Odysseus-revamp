# Hades module parity audit

Status: **source audit / E2 structural remediation**

## Root cause

The expanded sidebar was composed from `static/index.html` module rows and
grouped at runtime by `groupToolDestinations()` in `static/app.js`. The compact
desktop rail was a separate hard-coded set of legacy `rail-*` buttons in the
HTML. New module rows had no corresponding compact representation, so
Household, IT Assets, Network, Developer, and Hades could be present when
expanded and absent when compact. This is `SEPARATE_NAV_ARRAY` plus
`MISSING_COMPACT_RENDERER`, not a CSS-only failure.

The first convergence step adds `static/js/workspaceRegistry.js`, projects
expanded groups and compact workspace icons from the same workspace definitions,
and leaves existing module IDs/click handlers as explicit compatibility
bindings.

## Registry contract

`WorkspaceDefinition` owns user-facing destination identity: id, label, icon,
order, default module, and module IDs. `ModuleDefinition` owns module label,
semantic icon, and legacy DOM binding. Backend services, routes, ActionSpecs,
SetupContracts, and permissions remain independently canonical and are linked
by explicit references rather than inferred from UI metadata.

## Mature vs newer path

| Concern | Mature/original path | Newer Hades path | Finding |
|---|---|---|---|
| Expanded navigation | static module rows and direct handlers | grouped Hades rows and semantic icon hydration | Same shell, but newer grouping was appended around legacy rows |
| Compact navigation | hard-coded `rail-*` launchers | no new-module rail projection | Confirmed parity defect; workspace rail now supplies common compact identity |
| Mobile | sidebar layout and responsive CSS | Hades windows/modules | Shared shell exists; browser verification still pending |
| Window launch | modal managers and routed modules | `workspaceWindowManager.js` and `registerView()` | Compose; preserve one view/entity identity |
| Icons/theme | inline SVGs plus theme CSS | `ui-components.js` semantic icons | Registry should be the source for first-class workspace/module icons; live browser pass pending |
| Backend | mature provider/domain services | Hades projections and control-plane services | Reuse original services; newer policy/action contracts own consequential authority |

## Module completeness sample

| Module | Canonical id | Expanded | Compact | Mobile | Window | Backend/service | Evidence/gap |
|---|---|---:|---:|---:|---:|---|---|
| Hades | hades | yes | workspace icon | shared sidebar | yes | persistent-agent routes | E2; live browser pending |
| Household | household | yes | workspace icon | shared sidebar | yes | inventory routes/service | E2; health/browser pending |
| IT Assets | assets | yes | workspace icon | shared sidebar | yes | CMDB/asset service | E2; browser pending |
| Network | network | yes | workspace icon | shared sidebar | yes | network/CMDB service | E2; broker/runtime evidence separate |
| Homelab | homelab | yes | workspace icon | shared sidebar | yes | intelligence/Homelab projection | E2; browser pending |
| World Model | worldModel | yes | workspace icon | shared sidebar | yes | `WorldModelService` | E2; browser pending |
| Control Center | controlCenter | yes | workspace icon | shared sidebar | yes | control-center routes | E2; runtime provenance pending |
| OSINT | osint | yes | workspace icon | shared sidebar | yes | OSINT routes/case store | UI layout source fix E2; realistic browser pending |
| Setup Center | setupCenter | yes | workspace icon | shared sidebar | yes | setup routes/contracts | health gaps remain explicit |

## Legacy reconciliation

Tools/Brain/Compare/Cookbook/Inventory/Work/Gallery/Library/Notes/Tasks/Theme
remain compatibility module identities for now. The information architecture
maps them into Hades, Today, Knowledge, Home, Work, or System rather than
deleting functionality. The next migration should move command/search and
window launchers to workspace/module metadata before removing legacy DOM IDs.

## Shared component audit

New Hades modules use `moduleHeader`, `statusBadge`, `emptyState`,
`loadingState`, `errorState`, provenance helpers, and the shared window manager
where applicable. Original modules retain mature modal-specific components.
This is intentional composition, but the shared responsive card, tabs, window
chrome, and realistic-content browser acceptance remain incomplete until a
repo-scoped Playwright environment is restored.

## Evidence levels

Source/structural findings are E1/E2. The candidate image built from the
provenance commit is attributable, but the running deployment has not yet been
replaced, so these findings are not E4/E5. Owner live visual acceptance remains
E6-blocked by the lack of owner-authenticated browser access.

