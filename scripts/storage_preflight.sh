#!/bin/sh
# Conservative guardrail for source-attributable Odysseus image builds.
# This reports Docker usage and refuses large builds when the host cannot
# safely absorb another candidate image. It never performs cleanup.
set -eu

min_free_gib="${ODYSSEUS_MIN_FREE_GIB:-30}"
max_used_percent="${ODYSSEUS_MAX_ROOT_USED_PERCENT:-80}"

set -- $(df -Pk / | awk 'NR==2 {gsub("%", "", $5); print $4, $5}')
free_kib="$1"
used_percent="$2"
free_gib=$((free_kib / 1024 / 1024))

docker_report="$(docker system df --format 'TYPE={{.Type}} TOTAL={{.TotalCount}} ACTIVE={{.Active}} SIZE={{.Size}} RECLAIMABLE={{.Reclaimable}}' 2>/dev/null || true)"
candidate_count="$(docker images --format '{{.Repository}}:{{.Tag}}' | awk '/^odysseus:candidate-/ {count++} END {print count+0}')"
rollback_count="$(docker images --format '{{.Repository}}:{{.Tag}}' | awk '/^odysseus:rollback-/ {count++} END {print count+0}')"

printf 'STORAGE_PREFLIGHT root_free_gib=%s root_used_percent=%s min_free_gib=%s max_used_percent=%s candidate_images=%s rollback_images=%s\n' \
  "$free_gib" "$used_percent" "$min_free_gib" "$max_used_percent" "$candidate_count" "$rollback_count"
printf '%s\n' "$docker_report"

if [ "$free_gib" -lt "$min_free_gib" ] || [ "$used_percent" -gt "$max_used_percent" ]; then
  printf '%s\n' "STORAGE_PREFLIGHT_BLOCKED: reclaim safe, positively identified build artifacts before a large image build." >&2
  exit 2
fi
