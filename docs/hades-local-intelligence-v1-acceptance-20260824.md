# Hades Local Intelligence V1 acceptance

This record covers the local-intelligence, routing, YOLO, windowed-workspace,
inventory-split, and Network discovery candidate built from source commit
`a095bfc4f410efac091fab70103e899fd82b83ec`.

## Runtime lineage

- Source commit: `a095bfc4f410efac091fab70103e899fd82b83ec`
- Candidate image: `odysseus-odysseus:latest`
- Candidate image digest: `sha256:d8d6e7228a3e1a9fb49a6cf30b220c5d7a0e67ffad857738c16f37461760f19a`
- Compose service: `odysseus-odysseus-1`
- Migration: `20260823_006_local_intelligence_developer_v1`
- Previous rollback image: `sha256:0618472b03fb2b5512e0364b472577fec355777f1c16a7470267fe96b16431e7`
- Backups: `/home/scootz/Odysseus/hades-backups/local-intelligence-v1-20260824-0105/`

## GPU and local model

The host has an RTX 3080 Ti Mobile with 16 GiB VRAM. GPU validation is
reboot-blocked, not software-unknown: the loaded kernel module reports
610.43.03 while userspace NVML and the installed DKMS module report 610.57.04.
`nvidia-smi` consequently fails with an NVML API mismatch. No reboot was
performed during acceptance.

The accepted local profile is intentionally CPU-capable:

- profile: `hades-local-test`
- model: `qwen3:8b`, Q4_K_M, approximately 5.2 GiB on disk
- context: 8192
- Ollama: 0.31.1
- CPU-only operation, approximately 10 generation tokens/sec in benchmark
- structured JSON inference through Hades passed
- local profile is limited to safe/read-oriented routing; strong model remains
  required for consequential or security actions

## Host-only Ollama bridge

Ollama listens on `172.18.0.1:11434`, not on LAN/WAN interfaces. Compose uses
an explicit `172.18.0.0/16` network and maps `host.docker.internal` to
`HADES_HOST_GATEWAY` (default `172.18.0.1`). The whole Hades container does
not use host networking, privileged mode, or the Docker socket.

From the running Hades container:

- `GET http://host.docker.internal:11434/v1/models` returned HTTP 200 and
  OpenAI `data[].id = qwen3:8b`.
- `GET http://host.docker.internal:11434/api/tags` returned HTTP 200 and native
  Ollama `models[].name = qwen3:8b`.
- Hades model discovery used exactly `/v1/models`; no `/v1/v1/models` and no
  `/api/ps` residency dependency.
- A LAN probe to the host address was refused.

## Acceptance evidence

- Full suite: **5859 passed, 4 skipped, 0 failed**.
- Focused local/routing/Work/YOLO/provider suite: **131 passed**.
- Migration rehearsal passed on a fresh DB, rerun, and copied application DB;
  the second run applied zero migrations.
- Hades local inference returned structured JSON through `/api/intelligence/infer`.
- Safe Work, Household, IT Asset, and Homelab reads selected the local profile;
  security/mutation execution remained on `strong-default`.
- A durable action resumed after changing model/session, completed once, and a
  second completion returned replay protection without creating another action.
- A YOLO owner lease ran a workspace fixture as UID 1000, produced Work Engine
  audit action data, and failed closed after revocation.
- Browser automation opened Network, IT Assets, Work, Security, and Household
  windows; verified snap, minimize/restore, duplicate reuse, reload restoration,
  and 390x844 mobile full-screen fallback with no page errors.
- An explicitly approved private `172.18.0.0/29` Nmap host-discovery run
  completed with five review-only candidates and no intrusive scripts. The
  existing CMDB retained strong-identity/IP-only separation and provenance.

## Promotion note

The image is promotable as a CPU-capable local-intelligence baseline with the
GPU mismatch retained as a documented reboot follow-up. Do not claim GPU
offload until reboot and post-reboot `nvidia-smi`, container GPU, Ollama
offload, VRAM, and utilization checks pass.
