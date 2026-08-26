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
running_images="$(docker ps --format '{{.Image}}' | sort -u | tr '\n' ' ' | sed 's/[[:space:]]*$//' || true)"
candidate_tags="$(docker images --format '{{.Repository}}:{{.Tag}}' | awk '/^odysseus:candidate-/ {print}' | sort || true)"
rollback_tags="$(docker images --format '{{.Repository}}:{{.Tag}}' | awk '/^odysseus:rollback-/ {print}' | sort || true)"
obsolete_candidates=""
if [ -n "$candidate_tags" ]; then
  while IFS= read -r tag; do
    [ -n "$tag" ] || continue
    case " $running_images " in
      *" $tag "*) continue ;;
    esac
    obsolete_candidates="${obsolete_candidates}${tag} "
  done <<EOF
$candidate_tags
EOF
fi

printf 'STORAGE_PREFLIGHT root_free_gib=%s root_used_percent=%s min_free_gib=%s max_used_percent=%s candidate_images=%s rollback_images=%s\n' \
  "$free_gib" "$used_percent" "$min_free_gib" "$max_used_percent" "$candidate_count" "$rollback_count"
printf '%s\n' "$docker_report"
printf 'STORAGE_PREFLIGHT running_images=%s\n' "${running_images:-none}"
printf 'STORAGE_PREFLIGHT candidate_tags=%s\n' "${candidate_tags:-none}"
printf 'STORAGE_PREFLIGHT rollback_tags=%s\n' "${rollback_tags:-none}"
printf 'STORAGE_PREFLIGHT obsolete_unreferenced_candidates=%s\n' "${obsolete_candidates:-none}"

if [ "$free_gib" -lt "$min_free_gib" ] || [ "$used_percent" -gt "$max_used_percent" ]; then
  printf '%s\n' "STORAGE_PREFLIGHT_BLOCKED: reclaim safe, positively identified build artifacts before a large image build." >&2
  exit 2
fi
