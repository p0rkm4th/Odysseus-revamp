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
| `OSINT_CASE` | `research.public_sources/plan` | OSINT plan | implemented/source-tested |
| `MEMORY` | `memory.read/summarize_owner_memory` via `read_memory` | explicit memory read | implemented/source-tested |

Work, Setup/Integration, Household, and richer Network reads remain explicit
gaps until an existing owner-scoped service/action can be referenced without
inventing a side registry. Their absence is surfaced as an unresolved contract,
never repaired with filesystem or shell access. Memory’s `read_memory` binding
is deliberately read-only; legacy mutation actions remain on their compatibility
path until they can be migrated without broadening this contract.

Result classification distinguishes success, empty, invalid, unavailable, and
failed shapes. Explicit technical-asset and network reads use canonical
bindings, return structured data, require no approval for read actions, and
prohibit filesystem fallback. Contract validation also checks the read effect,
executor, binding, and explicit transport applicability. The legacy technical
asset CLI remains deployment-scoped storage; the Hades binding is owner-aware,
but multi-owner row-level CMDB isolation remains an explicit migration gap
rather than an invented claim of completion.
