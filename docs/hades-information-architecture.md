# Hades information architecture

Status: **converging — source/test evidence only until a source-matched browser deployment is verified**

## Product rule

Odysseus separates backend domains, user-facing modules, and top-level
workspaces. A workspace is a user mental context; a module is a focused
projection; canonical persistence and policy remain domain-owned. The frontend
registry in `static/js/workspaceRegistry.js` is navigation metadata, not a
database or authority layer.

## Primary workspaces

| Workspace | Modules/projections | Canonical boundaries preserved |
|---|---|---|
| Hades | Hades, Memory, Attention, Automations, Models, Improvements | Memory, notification, model, and improvement stores remain separate |
| Today | Calendar, Tasks, Attention | Calendar events, Work tasks, and notifications remain distinct |
| Research | OSINT, Deep Research, sources, evidence, reports | OSINT cases/claims are distinct from reusable research jobs and source indexes |
| Infrastructure | Assets, Network, Homelab, Security, World Model, Incidents, Changes | CMDB, observations, operations, security findings, graph projections, incidents, and changes remain distinct |
| Home | Household, Smart Home, recipes, shopping | Household/Inventory remains distinct from technical CMDB and Home Assistant |
| Communications | Email, Calendar, Contacts, Telegram, Notifications | Provider state and canonical Work/Notification projections remain distinct |
| Work | Work, Goals, Projects, Tasks, Missions, Business, Commitments | Work/Run/Mission semantics are not merged with calendar or provider stores |
| Knowledge | Documents, Notes, Gallery, Library, Compare, Cookbook, Search | Document/artifact, note, media, model, and recipe semantics remain explicit |
| System | Setup, Integrations, Permissions, Control Center, Developer, Appearance, Settings | Policy, health, setup, and control-plane views remain projections of canonical services |

The compact rail now projects these same workspace definitions as icons. Long-
tail modules remain discoverable through the expanded workspace groups and
should be added to search/command navigation as their command contracts land.

## Routing and compatibility

Existing module routes such as `/osint`, `/network`, `/homelab`, and `/security`
remain compatibility entry points. Canonical workspace-aware routes may be
introduced incrementally; restoring a saved window must retain the module and
entity identity rather than forcing a new backend route.

## Cross-projection identity

Infrastructure dossiers retain one entity reference while projecting hardware,
network, services, containers, storage, security, relationships, incidents,
changes, and history. The same rule applies to OSINT cases, household items,
contacts, documents, and Work entities. A workspace changes the projection, not
the canonical owner.

## Setup, permissions, and attention

Setup Center groups module contracts by workspace. Permissions groups
capability/action authority by workspace without changing policy ownership.
Attention aggregates cross-workspace items into one owner-facing projection;
transport-specific notifications do not become separate alert truth.

## Responsive contract

Desktop and mobile navigation use the same workspace registry. On narrow
screens, workspace navigation may collapse into the existing responsive sidebar
pattern; it must not maintain an independently curated module list.

