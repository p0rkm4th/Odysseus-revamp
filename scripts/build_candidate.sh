#!/bin/sh
# Build a source-attributable candidate image from the current checkout.
# The script does not deploy, stop, or replace a running service.
set -eu

# Fail closed before Docker can create another multi-gigabyte candidate on a
# nearly full root filesystem. The preflight reports, but never performs,
# cleanup; retention decisions remain explicit and recoverable.
scripts/storage_preflight.sh

SOURCE_COMMIT="$(git rev-parse --verify HEAD)"
BUILD_TIME="${ODYSSEUS_BUILD_TIME:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
BUILD_ID="${ODYSSEUS_BUILD_ID:-${SOURCE_COMMIT}-${BUILD_TIME}}"
FRONTEND_HASH="$(git ls-files 'static/*' | sort | xargs sha256sum | sha256sum | cut -d' ' -f1)"
FRONTEND_BUILD_ID="${ODYSSEUS_FRONTEND_BUILD_ID:-frontend-${SOURCE_COMMIT}-${FRONTEND_HASH}}"
MIGRATION_HEAD="${ODYSSEUS_MIGRATION_HEAD:-$(venv/bin/python - <<'PY'
import importlib
from pathlib import Path
from core.schema_migrations import schema_migration_registry

for path in sorted(Path('core').glob('*_migrations.py')):
    importlib.import_module(f"core.{path.stem}")
migrations = schema_migration_registry.ordered()
print(migrations[-1].version if migrations else 'none')
PY
)}"
SOURCE_SHORT="$(printf '%s' "$SOURCE_COMMIT" | cut -c1-12)"
IMAGE_TAG="${ODYSSEUS_IMAGE_TAG:-odysseus:candidate-${SOURCE_SHORT}}"

docker build \
  --build-arg "ODYSSEUS_SOURCE_COMMIT=${SOURCE_COMMIT}" \
  --build-arg "ODYSSEUS_BUILD_ID=${BUILD_ID}" \
  --build-arg "ODYSSEUS_BUILD_TIME=${BUILD_TIME}" \
  --build-arg "ODYSSEUS_FRONTEND_BUILD_ID=${FRONTEND_BUILD_ID}" \
  --build-arg "ODYSSEUS_MIGRATION_HEAD=${MIGRATION_HEAD}" \
  --tag "${IMAGE_TAG}" .

IMAGE_ID="$(docker image inspect --format '{{.Id}}' "${IMAGE_TAG}")"
printf 'SOURCE_COMMIT=%s\nBUILD_ID=%s\nBUILD_TIME=%s\nFRONTEND_BUILD_ID=%s\nMIGRATION_HEAD=%s\nIMAGE_TAG=%s\nIMAGE_ID=%s\n' \
  "$SOURCE_COMMIT" "$BUILD_ID" "$BUILD_TIME" "$FRONTEND_BUILD_ID" "$MIGRATION_HEAD" "$IMAGE_TAG" "$IMAGE_ID"
