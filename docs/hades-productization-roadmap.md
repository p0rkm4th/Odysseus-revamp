# Hades productization roadmap

## Current checkpoint

- Stabilization source: `6f36a0bb12d6bb35d40555b5e842bc95fb1c1df7`.
- Canonical network discovery: `homelab.manage` → `execute_network_discovery` → `manage_homelab` → `host_broker`.
- Full regression after the preceding continuity checkpoint: `5885 passed, 3 skipped`.
- Three unrelated pre-existing files remain modified and are intentionally not included in the stabilization commits.
- Fresh Luna and Qwen broker executions each returned 9 bounded candidates; 9 `homelab_nmap` observations are visible in CMDB and Network Map.

## Dependency-ordered batches

1. **P0 stabilization:** preserve the network evidence, finish explicit model-switch/browser/reconnect evidence, and keep weak-model referents bounded and diagnosable.
2. **P1 continuity/self:** unify identity, runtime health, Work state, capabilities, commitments, attention, working-memory diagnostics, and durable Episodes/Lessons.
3. **P1 Life/attention:** productize Goals/Projects/Tasks/Commitments, reviews, deterministic monitors, notifications, and daily briefs on existing Work primitives.
4. **P2 shared shell:** audit and consolidate icons, module navigation, window behavior, global search, command palette, entity headers, timelines, provenance, and responsive states.
5. **P2 local operations:** expand the existing bounded Homelab operation catalog and capability dependency health; then productize Household, IT/CMDB, Network history/change detection.
6. **P3 security/OSINT:** complete authorized assessment and public-source case workflows with evidence-linked reports.
7. **P4 communications/business:** expose Telegram cross-channel continuity, voice, Email/Calendar/Contacts links, and Work-based CRM.
8. **P5/P6 integrations and polish:** Home Assistant, PWA/share intake, multimodal/documents, Improvement/Model Lab/Developer surfaces, accessibility, and final uniformity.

Every batch must update the feature matrix, run focused tests, preserve policy
invariants, and leave a deployable commit. Schema changes require fresh,
rerun, and copied-database rehearsal before promotion.

## Completed batches in this continuation

- Persisted `AssistantInstance.last_seen_at` and made `/api/hades/while-away`
  default to the persisted marker.
- Added `/api/hades/attention`, projecting unread notifications, blocked or
  awaiting Work runs, and open commitments without duplicating canonical state.
- Preserved notification source entity/run references for overdue commitments.
- Added a Hades workspace Attention Queue section.
- Added a deterministic Work Life Review projection for focus goals, due-soon
  and overdue commitments, due tasks, blocked tasks, and waiting runs.
