#!/bin/sh
# Canonical verification for the intentionally unbundled static frontend.
# This checks the shipped JavaScript/CSS assets without inventing a bundler.
set -eu

command -v node >/dev/null 2>&1 || {
  echo "frontend verification requires node" >&2
  exit 2
}

find static/js -type f -name '*.js' -print0 \
  | xargs -0 -r -n1 node --check
test -s static/index.html
test -s static/style.css
test -s static/app.js
printf '%s\n' "frontend static verification passed"
