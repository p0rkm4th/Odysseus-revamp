# Hades capability/action exposure matrix

This matrix records canonical authority separately from provider tool choice.
The same owner, Run, intent, policy, and capability state must produce the
same canonical ActionSpec availability for Qwen, Luna, Sol, and other routes.
Models may differ in whether they select an exposed action; they do not create
or remove authority.

| Domain | Capability | ActionSpec | MODEL | API | WORK | UI | AUTOMATION | Execution | Approval | Policy |
|---|---|---|---|---|---|---|---|---|---|---|
| Infrastructure / Network | `homelab.manage` | `discovery_status` | yes | yes | yes | yes | no | application + broker health | none | owner/private scope |
| Infrastructure / Network | `homelab.manage` | `read_network_observations` | yes | yes | yes | yes | no | application projection | none | owner/private scope |
| Infrastructure / Network | `homelab.manage` | `plan_network_discovery` | yes | yes | yes | yes | no | application precheck | none | private IPv4, max /24 |
| Infrastructure / Network | `homelab.manage` | `execute_network_discovery` | yes | yes | yes | yes | no | host broker / Nmap | exact | private IPv4, max 256 |
| Infrastructure / Network | `homelab.manage` | `plan_network_service_enumeration` | yes | yes | yes | yes | no | application precheck | none | discovered private targets only |
| Infrastructure / Network | `homelab.manage` | `execute_network_service_enumeration` | yes | yes | yes | yes | no | host broker / safe Nmap `-sV` | exact | discovered private targets only; no exploitation |
| Infrastructure / Homelab | `homelab.manage` | `plan_service_restart` | yes | yes | yes | yes | no | application precheck | none | owner-scoped service |
| Infrastructure / Homelab | `homelab.manage` | `execute_service_restart` | yes | yes | yes | yes | no | trusted host operation | exact | protected-unit and profile policy |
| Infrastructure / Homelab | `homelab.manage` | `plan_diagnostic_install` | yes | yes | yes | yes | no | application precheck | none | declared capability remediation |
| Infrastructure / Homelab | `homelab.manage` | `execute_diagnostic_install` | yes | yes | yes | yes | no | host broker allowlist | exact | package allowlist; no model package guessing |
| Hades / Memory | `memory.read` | `summarize_owner_memory` | yes | yes | yes | yes | no | application / canonical Brain store | none | authenticated owner scope; no Skills/filesystem fallback |
| Hades / Memory | `memory.read` | `search_memory` | yes | yes | yes | yes | no | application / canonical Brain store | none | authenticated owner scope; no Skills/filesystem fallback |
| Hades / Memory | `memory.read` | `inspect_memory` | yes | yes | yes | yes | no | application / canonical Brain store | none | authenticated owner scope; no Skills/filesystem fallback |
| Work | `work.read` | `overview` | yes | yes | yes | yes | no | application / Work Engine | none | authenticated owner scope; canonical Work state only |
| Work | `work.read` | `review` | yes | yes | yes | yes | no | application / Work Engine | none | authenticated owner scope; canonical Work state only |
| Work | `work.read` | `context` | yes | yes | yes | yes | no | application / Work Engine | none | authenticated owner scope; canonical Work state only |
| Work | `work.read` | `list_goals` / `list_projects` / `list_tasks` / `list_runs` / `list_commitments` / `list_missions` / `list_watches` | yes | yes | yes | yes | no | application / Work Engine, MissionService, Monitor projection | none | authenticated owner scope; canonical Work state only |
| Home / Household | `household.read` | `overview` | yes | yes | yes | yes | no | application / InventoryService | none | authenticated owner scope; physical household state; CMDB remains separate |
| Home / Household | `household.read` | `list_items` / `search_items` / `get_item` | yes | yes | yes | yes | no | application / InventoryService | none | authenticated owner scope; physical household state; CMDB remains separate |
| System / Setup | `setup.read` | `state` | yes | yes | yes | yes | no | application / SetupCenterService | none | authenticated owner scope; secret-free configuration state; authority unchanged |
| System / Integrations | `setup.read` | `integrations` | yes | yes | yes | yes | no | application / SetupCenterService | none | authenticated owner scope; secret-free connectivity projection; configuration is not health proof |
| System / Permissions | `setup.read` | `permissions` | yes | yes | yes | yes | no | application / SetupCenterService | none | authenticated owner scope; projection only; canonical policy/approval remains authoritative |
| Research / OSINT | `research.public_sources` | `list_cases` / `get_case` | yes | yes | yes | yes | no | application / durable OSINT case store | none | authenticated owner scope; external report content remains tainted and non-authoritative |
| Work / Career | `career.read` | `overview` / `provider_status` | yes | yes | yes | yes | no | application / Career service | none | authenticated owner scope; provider status is explicit |
| Work / Career | `career.read` | `saved_opportunities` / `applications` / `follow_ups` / `interviews` | yes | yes | yes | yes | no | application / Career service | none | authenticated owner scope; provider records are not canonical lifecycle state |
| Work / Career | `career.provider` | `submit_application` / `send_message` / `book_interview` | no | adapter-dependent | Work/UI where explicitly initiated | no | no | provider adapter | exact | never autonomous; owner approval and provider policy required |

“MODEL: yes” means the canonical binding contract may be projected when the
intent and policy select the capability. Native function schemas and strict
textual contracts are transport projections of the same binding; a provider
that cannot call a tool must report that limitation and use the deterministic
repair/continuation path where supported. This does not grant model authority
outside policy.

Network deep-dive trajectory:

`plan_network_discovery` → `execute_network_discovery` →
`plan_network_service_enumeration` → `execute_network_service_enumeration` →
CMDB evidence normalization → inferred-only role hypotheses → grounded report.

The service target list is inherited from the completed discovery Result in
the same owner-scoped Work Run. Role hypotheses carry `INFERRED`, evidence,
and confidence metadata and never become canonical identity automatically.
