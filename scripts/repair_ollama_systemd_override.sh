#!/usr/bin/env bash
# Administrator-only repair for the host Ollama service. This intentionally
# does not run from Hades and never broadens the listener beyond the Docker
# bridge. Keep the file root-owned after installation.
set -euo pipefail

override='/etc/systemd/system/ollama.service.d/override.conf'
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

cat >"$tmp" <<'EOF'
[Service]
Environment="OLLAMA_HOST=172.18.0.1:11434"
Environment="OLLAMA_VULKAN=false"
Environment="CUDA_VISIBLE_DEVICES=0"
Environment="OLLAMA_NUM_PARALLEL=5"
Environment="OLLAMA_MAX_LOADED_MODELS=5"
Environment="OLLAMA_CONTEXT_LENGTH=8192"
Environment="OLLAMA_FLASH_ATTENTION=true"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
Environment="OLLAMA_KEEP_ALIVE=30m"
Environment="OLLAMA_MODELS=/home/scootz/.ollama/models"
EOF

sudo install -D -o root -g root -m 0644 "$tmp" "$override"
sudo systemctl daemon-reload
sudo systemctl restart ollama

environment="$(systemctl show ollama --property=Environment --value)"
grep -q 'OLLAMA_HOST=172.18.0.1:11434' <<<"$environment"
grep -q 'OLLAMA_CONTEXT_LENGTH=8192' <<<"$environment"
grep -q 'OLLAMA_KV_CACHE_TYPE=q8_0' <<<"$environment"
if grep -q 'OLLAMA_HOST=0.0.0.0' <<<"$environment"; then
  echo 'refusing: Ollama is configured for a public listener' >&2
  exit 1
fi

echo 'Ollama systemd override repaired and restarted.'
systemctl show ollama --property=Environment --no-pager
ss -ltnp | grep '172.18.0.1:11434'
