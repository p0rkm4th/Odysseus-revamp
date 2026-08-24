# Hades Local Intelligence V1 recovery record

Status: candidate validated; promotion intentionally held.

## Lineage

- Branch: `recovery/live-candidate-20260823`
- Source: `0f1b56d4`
- Running candidate image: `sha256:28bfe99e7c81fc1fd6852dadf4561873bd8f39d0005ef0bc0d191fa21e7782df`
- Previous accepted image: `sha256:0618472b03fb2b5512e0364b472577fec355777f1c16a7470267fe96b16431e7`
- Migration: `20260823_006_local_intelligence_developer_v1`
- Database/auth/settings backups: `data/*.20260823-local-intel-v1`

## Runtime

- GPU: RTX 3080 Ti Laptop, 16 GiB; loaded/userspace NVIDIA `610.57.04`; NVML operational.
- Ollama: host systemd service, version `0.31.1`.
- Intended endpoint: `http://host.docker.internal:11434/v1`.
- Actual listener: `172.18.0.1:11434`; no LAN/WAN listener observed.
- Model discovery: host and Hades both return `qwen3:8b` from `/v1/models`.
- Primary/weak local model: `qwen3:8b`, Q4_K_M, approximately 5.2 GiB.
- Hades local context cap: 8192; direct generation measurements were approximately 15–24 tok/s.

The boot journal contains the separate PRH thermal-limit assertion; no Xid or
NVML mismatch is currently observed.

## Verified implementation

- Conversation, Work context, recent tool results, and memory are reconstructed by Hades; provider sessions are disposable.
- Action and read-result claims require persisted successful evidence; fabricated inventory reports are rejected.
- Local weak-model prose receives one bounded repair; explicitly scoped network prose becomes `manage_homelab`.
- Dependency registry maps `nmap -> nmap` and `ip/ss -> iproute2` for the host platform.
- Host Nmap execution uses the existing privileged broker, fixed ping-scan arguments, private IPv4 CIDR, and a maximum of 256 addresses.
- Browser window dogfood passed reuse, cross-open, snap, minimize/restore, maximize, reload restoration, and mobile fallback.
- Fresh migration, rerun, and copied production database rehearsals passed.

## Tests

Full suite: **5872 passed, 4 skipped**.

The live explicit-CIDR weak-model retest produced:

```json
{"action":"plan_network_discovery","cidr":"192.168.10.0/24"}
```

It stopped at exact approval; no scan occurred without approval.

## Promotion holds

1. The root-owned Ollama override is malformed. The administrator repair is
   `scripts/repair_ollama_systemd_override.sh`; it must be run with authorized
   root access, followed by GPU/inference/restart validation.
2. The real bounded discovery requires the explicit approval surfaced by Hades.

No source tag or promoted image is created until both holds are cleared.
