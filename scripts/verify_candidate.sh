#!/usr/bin/env bash
# Read-only provenance check for an exact Hades candidate.
# Usage: scripts/verify_candidate.sh <full-or-short-source-sha>
# Optional: HADES_VERIFY_BASE_URL=http://127.0.0.1:7000
set -u

EXPECTED_SHA="${1:-}"
if [[ -z "$EXPECTED_SHA" ]]; then
  echo "usage: $0 <source-sha>" >&2
  exit 2
fi

repo_value() {
  git "$@" 2>/dev/null || echo unavailable
}

LOCAL_SHA="$(repo_value rev-parse HEAD)"
BRANCH="$(repo_value branch --show-current)"
REMOTE_SHA="$(repo_value rev-parse origin/hades-v1-productization)"
WORKTREE="$(git status --porcelain 2>/dev/null | if read -r _; then echo dirty; else echo clean; fi)"
SHORT_SHA="${EXPECTED_SHA:0:12}"
IMAGE_TAG="${HADES_VERIFY_IMAGE_TAG:-odysseus:candidate-${SHORT_SHA}}"

printf 'EXPECTED_SOURCE=%s\nBRANCH=%s\nLOCAL_SOURCE=%s\nREMOTE_SOURCE=%s\nWORKTREE=%s\nIMAGE_TAG=%s\n' \
  "$EXPECTED_SHA" "$BRANCH" "$LOCAL_SHA" "$REMOTE_SHA" "$WORKTREE" "$IMAGE_TAG"

if docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
  IMAGE_ID="$(docker image inspect "$IMAGE_TAG" --format '{{.Id}}')"
  IMAGE_REVISION="$(docker image inspect "$IMAGE_TAG" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')"
  IMAGE_BRANCH="$(docker image inspect "$IMAGE_TAG" --format '{{index .Config.Labels "org.odysseus.source.branch"}}')"
  printf 'IMAGE_ID=%s\nIMAGE_REVISION=%s\nIMAGE_BRANCH=%s\n' "$IMAGE_ID" "$IMAGE_REVISION" "$IMAGE_BRANCH"
  MARKER="$(docker run --rm --entrypoint sh "$IMAGE_TAG" -c 'cat /app/.odysseus-source-commit' 2>/dev/null || echo unavailable)"
  printf 'IMAGE_MARKER=%s\n' "$MARKER"
else
  echo 'IMAGE_ID=unavailable'
  echo 'IMAGE_REVISION=unavailable'
  echo 'IMAGE_MARKER=unavailable'
fi

FOUND_RUNNING=0
while IFS='|' read -r NAME IMAGE ID; do
  [[ -n "$NAME" ]] || continue
  FOUND_RUNNING=1
  REVISION="$(docker inspect "$NAME" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' 2>/dev/null || echo unavailable)"
  SOURCE="$(docker exec "$NAME" sh -c 'cat /app/.odysseus-source-commit' 2>/dev/null || echo unavailable)"
  ENDPOINT="$(docker inspect "$NAME" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | sed -n 's/^HADES_OLLAMA_ENDPOINT=//p' | head -n1)"
  [[ -n "$ENDPOINT" ]] || ENDPOINT=unknown
  printf 'RUNNING_CONTAINER=%s\nRUNNING_IMAGE=%s\nRUNNING_IMAGE_ID=%s\nRUNNING_REVISION=%s\nRUNNING_SOURCE=%s\nOLLAMA_ENDPOINT=%s\n' \
    "$NAME" "$IMAGE" "$ID" "$REVISION" "$SOURCE" "$ENDPOINT"
  QWEN="$(docker exec "$NAME" sh -c 'curl -fsS --max-time 5 "$HADES_OLLAMA_ENDPOINT/api/tags"' 2>/dev/null \
    | sed -n 's/.*"name":"\(qwen3:8b\)".*"digest":"\([^"]*\)".*/model=\1 digest=\2/p' | head -n1)"
  printf 'QWEN_STATUS=%s\n' "${QWEN:-unavailable}"
done < <(docker ps --format '{{.Names}}|{{.Image}}|{{.ID}}' 2>/dev/null | while IFS='|' read -r name image id; do
  revision="$(docker inspect "$name" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' 2>/dev/null || true)"
  [[ "$revision" == "$EXPECTED_SHA"* ]] && printf '%s|%s|%s\n' "$name" "$image" "$id"
done)
[[ "$FOUND_RUNNING" -eq 1 ]] || echo 'RUNNING_CONTAINER=none-matching-expected-source'

if [[ -n "${HADES_VERIFY_BASE_URL:-}" ]]; then
  HEALTH="$(curl -fsS --max-time 5 "${HADES_VERIFY_BASE_URL%/}/api/health" 2>/dev/null || echo unavailable)"
  printf 'HEALTH=%s\n' "$HEALTH"
else
  echo 'HEALTH=not-probed (set HADES_VERIFY_BASE_URL to probe explicitly)'
fi
