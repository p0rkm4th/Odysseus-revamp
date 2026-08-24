# Hades Local Intelligence V1 live validation — 2026-08-24

This is the post-reboot recovery record for the current clean branch
`recovery/live-candidate-20260823` at source `5759a861c2e85016a9ebcfa9cb1137c69fb186a7`.

## Host and runtime

- NVIDIA userspace, loaded kernel module, and DKMS module: `610.57.04`.
- GPU: NVIDIA GeForce RTX 3080 Ti Laptop GPU, 16 GiB.
- Ollama: host systemd service, version `0.31.1`.
- Ollama binding: `172.18.0.1:11434`; no LAN/WAN listener observed.
- Hades endpoint: `http://host.docker.internal:11434/v1`.
- Hades container restart preserved database, owner state, model discovery, and
  Ollama reachability.

The boot journal contains the previously observed NVIDIA PRH thermal-limit
assertion once after module load. It is separate from the resolved NVML
userspace/kernel mismatch; no Xid or NVML mismatch was observed.

## Local model

- Primary local general / weak test model: `qwen3:8b`, GGUF Q4_K_M, 5.2 GiB.
- No separate coder model is installed or selected.
- Ollama reported 100% GPU processing, 8192 requested context, and about
  10.98 GiB VRAM resident after Hades inference.
- Direct bridge measurements were approximately 15–24 generated tokens/sec on
  short runs; Hades structured inference returned valid JSON.
- Hades model discovery lists `qwen3:8b` from `/v1/models` without requiring
  `/api/ps` residency.

## Acceptance evidence

- Focused local/routing/model/Work/YOLO/window/network suite:
  `240 passed, 1 skipped`.
- Full suite: `5859 passed, 4 skipped, 0 failed`.
- Authenticated Hades checks passed for local profiles, work-status routing,
  structured inference, model discovery, and Network Map projection.
- YOLO ran as UID 1000 in the workspace; sudo and Docker were blocked; revoke
  blocked subsequent execution.
- Discovery planning accepted private `/29`, rejected public and over-256
  targets, and required exact approval plus the existing Homelab/Nmap path.

## Promotion hold

The root-owned systemd drop-in still contains a malformed escaped
`OLLAMA_KV_CACHE_TYPE` entry and `OLLAMA_CONTEXT_LENGTH=4096`. `OLLAMA_HOST`
is persistent and correct, but the KV-cache entry is absent from the effective
service environment. Correct the drop-in with operator root access, reload and
restart Ollama, then repeat the GPU and inference checks before promotion.
