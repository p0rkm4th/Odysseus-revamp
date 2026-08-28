# Cookbook dependency/runtime audit

Status: audit completed before migration.  No Cookbook installer or runtime
path was deleted by this audit.

## Current ownership

| Concern | Current implementation | Durable behavior to preserve | Migration risk |
|---|---|---|---|
| HF model download | `routes/cookbook_routes.py` `/api/model/download`, generated local/remote runners, `scripts/hf_download.py` | resumable HF cache, optional `hf_transfer`, token handling, retries, remote and Windows launch | high |
| Ollama pull | Cookbook download route and generated runner; local Docker sidecar fallback | native Ollama and supported sidecar behavior, retry/status markers | high |
| Pip/user dependency install | `routes/cookbook_helpers.py` pip fallback builders plus `/api/model/serve` and shell package paths | PEP-668 fallback, venv activation, user-site visibility, no-cache retries | high |
| OS package setup | `/api/cookbook/setup`, `routes/shell_routes.py` package matrix, privileged broker/homelab diagnostic install | platform mapping, broker allowlist, explicit approval, host-vs-container distinction | critical |
| Package/runtime probing | `/api/cookbook/packages`, `_package_probe_script`, local import metadata and remote SSH probes | local/remote target selection, venv-aware probes, actionable diagnosis | high |
| Background jobs | Cookbook task state plus `tmux`/detached Windows processes and `/api/cookbook/tasks/status` | reconnect, output tails, dedupe, retry, crash diagnosis, resumability | critical |
| Runtime launch | `/api/model/serve`, generated runners, platform/backend branches | vLLM/SGLang/llama.cpp/MLX/Ollama launch preflight and bounded port selection | critical |
| Endpoint lifecycle | `_auto_register_llm_endpoint`, image endpoint registration, `src/cookbook_serve_lifecycle.py` | endpoint provenance, stale endpoint removal, health/probe behavior | high |
| Remote SSH transport | Cookbook helpers/routes and shell routes | timeouts, remote platform handling, known-host behavior, venv/remote path handling | critical |
| Human projection | Cookbook UI modules and `/api/cookbook/*` routes | browse/install/inspect/repair/remove workflows and running-task visibility | medium |

## Duplicate or non-canonical control points

The audit found these independent control points that must converge behind the
existing Hades authority model:

1. Cookbook generates shell installers for HF dependencies, Ollama, pip
   runtimes, and system packages.
2. Shell routes independently expose package probing and generic shell/tmux
   execution.
3. Homelab diagnostic installation already has a bounded brokered path and a
   durable prerequisite handoff, but its small registry is separate from the
   Cookbook package matrix.
4. Cookbook state stores task identity/progress separately from durable Work
   Runs.  The UI state is useful as a projection/cache, but must not become a
   second execution truth.
5. Runtime endpoint registration is split between route-local launch logic and
   the serve lifecycle loop.

## Canonical extraction boundary

The migration target is one backend with typed contracts:

`DependencySpec` → `InstallerSpec` → `ArtifactSpec` → `RuntimeSpec` →
`VerificationSpec`

The backend owns declaration, target/platform resolution, provenance, bounded
execution delegation, verification, and resume identity.  It does not accept
model-provided shell, package names, repository URLs, credentials, or scopes as
authority.

Cookbook will remain the owner-facing projection over that backend.  Its
existing runner mechanics will be adapted incrementally; they are not to be
reimplemented in ACI or copied into a second manager.

## Safe migration order

1. Extract immutable contracts and normalize the existing Cookbook package,
   model, runtime, and verification metadata without changing execution.
2. Route read-only package/runtime inspection through the backend while keeping
   the existing probes as the first adapter.
3. Route HF/Ollama artifact planning and existing resumable runners through the
   backend; preserve task IDs and tmux/detached job behavior.
4. Route user-scoped pip, remote SSH setup, and host-package requests through
   backend adapters with the existing broker/policy/approval gates.
5. Project backend task status into Cookbook and durable Work identity; remove
   only duplicate state transitions after replay/restart tests pass.
6. Move endpoint registration/probe receipts behind the same runtime adapter.

No phase may replace a mature runner with a stub or claim live verification from
fixture execution.  Missing provider credentials remain `UNCONFIGURED`.

Security note: Cookbook setup, scheduled remote serve cleanup, shared remote
binary/adoption probes, GPU probes, and cancellation paths now use the shared
unattended SSH boundary with strict host-key verification. The central
transport rejects permissive host-key mode. Direct package/runtime runner
mechanics remain migration debt and are not treated as canonical execution.
