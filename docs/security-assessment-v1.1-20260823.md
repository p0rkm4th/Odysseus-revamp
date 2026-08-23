# Security Assessment V1.1

This release integrates trusted CMDB context and reviewed Homelab observations
into the bounded Security Assessment domain. It does not add exploit,
credential-attack, arbitrary-shell, or autonomous scanning capability.

## Scope

- Canonical CMDB asset targets resolve to read-only context snapshots.
- Missing, retired, or stale canonical targets cannot be planned for runs.
- Homelab observations can be ingested as provenance-rich evidence only from
  authorized bounded runs, with idempotent replay protection.
- Evidence can produce a proposed finding candidate; confirmation is an
  explicit operator transition and is never automatic.
- Evidence freshness is surfaced and revalidation is explicit.
- Security UI distinguishes observed, inferred, stale, and confirmed material.

Migration: `20260823_004_security_assessment_context_v1`.

## Hardware-fit classification

The 16 historical failures were stale catalog fixtures: the referenced
historical Phi, Gemma 4, Qwen 3.5, NVFP4, and AWQ catalog rows are absent from
the current hardware-fit catalog. They are explicit conditional skips; the
hardware-fit implementation was not weakened. The full suite result is
recorded with the acceptance handoff.

## Security invariants

Capability -> ActionSpec -> ToolBinding, `tool_policy`, `disabled_tools`, exact
approval sealing, owner isolation, SO_PEERCRED, CMDB strong-identity rules,
IP-only non-merge, and external-content taint handling remain authoritative.

Runtime image and source/tag lineage are recorded in the release handoff.
