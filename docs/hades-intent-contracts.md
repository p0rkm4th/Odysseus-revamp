# IntentFrame and domain-contract layer

Hades now records a bounded `IntentFrame` for each agent turn before provider
tool projection. The frame contains operation class, domain concept, target,
entity/run references, filters/scope, depth, constraints, and desired output.
It is a semantic routing artifact; raw wording is not an execution identity.

Resolution is:

`Natural language → IntentFrame → DomainContract → existing Capability →
ActionSpec → ToolBinding → policy/result`

`src/intent_contracts.py` is a resolver layer, not a second executor or
capability registry. Its contract entries reference existing capability IDs,
ActionSpec IDs, and ToolBindings. `validate_contracts()` fails on missing
capabilities/actions/bindings, missing result contracts, and approval on a
declared read.

Current registered semantic contracts:

| Concept | Canonical capability/action | Result contract | Status |
|---|---|---|---|
| `TECHNICAL_ASSET` | `inventory.manage/list` via `manage_assets` | technical asset list | implemented/source-tested |
| `NETWORK` | `homelab.manage/read_network_observations` or bounded discovery plan | network observations/discovery | implemented/source-tested |
| `SECURITY_FINDING` | `security.assessment.read/list_findings` | finding list | implemented/source-tested |
| `OSINT_CASE` | `research.public_sources/list_cases` or `plan` via `manage_osint` | Owner-scoped case read or OSINT plan | implemented/source-tested |
| `MEMORY` | `memory.read/summarize_owner_memory` via `read_memory` | explicit memory read | implemented/source-tested |
| `WORK` | `work.read/overview` via `read_work` | Work overview | implemented/source-tested |
| `HOUSEHOLD_ITEM` | `household.read/overview` via `read_household` | Household overview | implemented/source-tested |
| `INTEGRATION` | `setup.read/state` via `read_setup` | Setup/configuration state | implemented/source-tested |
| `CAREER_PROFILE` | `career.read/overview` via `read_career` | Work-scoped Career profile and provider posture | implemented/source-tested |
| `JOB_SEARCH` | `career.read/overview` or `provider_status` via `read_career` | Saved search/provider contract | implemented/source-tested; provider not configured |
| `JOB_OPPORTUNITY` | `career.read/saved_opportunities` via `read_career` | Owner-saved normalized opportunities | implemented/source-tested |
| `APPLICATION` | `career.read/applications` via `read_career` | Application lifecycle projection | implemented/source-tested |
| `INTERVIEW` | `career.read/interviews` via `read_career` | Interview/follow-up projection | implemented/source-tested |

Richer Network reads remain an explicit gap until additional owner-scoped
service/actions can be referenced without inventing a side registry. Setup’s
`read_setup` adapter reuses the existing secret-free SetupCenterService and
never grants authority. Memory’s `read_memory`, Work’s `read_work`, Household’s
`read_household`, Setup’s `read_setup`, and OSINT case reads are deliberately read-only;
legacy mutation actions
remain on their compatibility path until they can be migrated without
broadening this contract.

Result classification distinguishes success, empty, invalid, unavailable, and
failed shapes. Explicit technical-asset and network reads use canonical
bindings, return structured data, require no approval for read actions, and
prohibit filesystem fallback. Contract validation also checks the read effect,
executor, binding, and explicit transport applicability. The legacy technical
asset CLI remains deployment-scoped storage; the Hades binding is owner-aware,
but multi-owner row-level CMDB isolation remains an explicit migration gap
rather than an invented claim of completion.
