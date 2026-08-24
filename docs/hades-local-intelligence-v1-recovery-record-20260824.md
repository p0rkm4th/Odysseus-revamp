# Hades Local Intelligence V1 recovery record

Status: candidate validated and promoted.

## Lineage

- Branch: `recovery/live-candidate-20260823`
- Source: final promotion commit (see annotated tag)
- Promoted image: final image digest recorded at promotion
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
- Systemd override survived an Ollama restart with `OLLAMA_HOST=172.18.0.1:11434`,
  `OLLAMA_KV_CACHE_TYPE=q8_0`, CUDA device 0, and 8192 context.

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
- Explicit approved discovery of `192.168.10.0/24` completed through Hades,
  returning 9 live candidates. Candidates were persisted as provenance-bearing
  unidentified CMDB observations; no IP-only canonical assets were created.
- Network Map now projects canonical CMDB assets plus clearly marked
  `unidentified` observation nodes.
- The final weak-model execution recovery converts explicit bounded network
  execution text into the first-class action when qwen emits non-native tool
  markup; approval and result grounding remain authoritative.

## Tests

Full suite before the final runtime-boundary fixes: **5872 passed, 4 skipped**.
Final source syntax and live smoke checks passed; the host does not have a
working repository pytest interpreter after the reboot, so a post-fix full
pytest rerun could not be started locally.

The live explicit-CIDR weak-model retest produced and executed:

```json
{"action":"plan_network_discovery","cidr":"192.168.10.0/24"}
```

It stopped at exact approval until the user-approved action was applied. The
approved scan then completed successfully with exit code 0.

## Promotion

The previous accepted Work Engine image and database/auth/settings backups are
retained. Ollama remains bridge-only and is not exposed on normal LAN/WAN
interfaces.
