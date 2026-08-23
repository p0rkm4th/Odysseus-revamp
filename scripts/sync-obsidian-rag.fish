#!/usr/bin/env fish
# sync-obsidian-rag.fish
#
# Synchronize approved Obsidian knowledge into Odysseus Personal Docs / RAG.
#
# Workflow:
#   1. Copy approved source folders into a sanitized staging tree.
#   2. Apply explicit exclusions for known-sensitive / low-value notes.
#   3. Abort if staged files appear to contain credential assignments.
#   4. Add searchable source-path metadata to staged Markdown files.
#   5. Remove stale vectors for each staged knowledge domain.
#   6. Reindex the domains into Odysseus Chroma/FastEmbed RAG.
#   7. Print RAG health and a small retrieval smoke test.
#
# Intended installation:
#   <odysseus repo>/scripts/sync-obsidian-rag.fish
#
# Run from anywhere:
#   ./scripts/sync-obsidian-rag.fish
#
# The original Obsidian vault is NEVER modified.

# ---------- Configuration ----------

set -l owner "scotty"

set -l source_house "/home/scootz/Documents/Obsidian/House of Hades/House of Hades SOP"
set -l source_hckrslsh "/home/scootz/Documents/Obsidian/Vault Archive/hckrslsh"
set -l source_linuxplus "/home/scootz/Documents/Obsidian/Vault Archive/Linux+"

# Resolve the Odysseus repository from the script location.
# This assumes the script lives in <repo>/scripts/.
set -l script_path (realpath (status --current-filename))
set -l script_dir (dirname "$script_path")
set -l repo_root (realpath "$script_dir/..")
set -l stage_root "$repo_root/data/personal_docs/obsidian"

set -l stage_house "$stage_root/house-of-hades"
set -l stage_hckrslsh "$stage_root/hckrslsh"
set -l stage_linuxplus "$stage_root/linuxplus"

# Stronger than merely searching for words such as "password":
# this looks for credential-like labels followed by ":" or "=" and
# then a non-trivial value.
set -l credential_pattern '(api[_ -]?key|client[_ -]?secret|password|passwd|token|authorization|bearer)[[:space:]]*[:=][[:space:]]*"?[^[:space:]"]{8,}'

# ---------- Helpers ----------

function fail
    printf '\nERROR: %s\n' "$argv" >&2
    exit 1
end

function banner
    printf '\n=== %s ===\n' "$argv"
end

# ---------- Preconditions ----------

banner "PRECHECK"

for cmd in rsync rg docker python realpath find grep mktemp
    command -q "$cmd"; or fail "Required command not found: $cmd"
end

test -d "$repo_root"; or fail "Could not resolve Odysseus repository root."
test -f "$repo_root/docker-compose.yml"; or fail "docker-compose.yml not found at $repo_root"

for src in "$source_house" "$source_hckrslsh" "$source_linuxplus"
    test -d "$src"; or fail "Source directory not found: $src"
    test -r "$src"; or fail "Source directory is not readable: $src"
end

cd "$repo_root"; or fail "Could not enter repository: $repo_root"

docker compose ps odysseus >/dev/null 2>&1; or fail "docker compose is unavailable for this repository."

printf 'Repository: %s\n' "$repo_root"
printf 'Staging:    %s\n' "$stage_root"
printf 'Owner:      %s\n' "$owner"

# ---------- Stage sanitized copies ----------

banner "SYNC APPROVED OBSIDIAN CONTENT"

mkdir -p "$stage_house" "$stage_hckrslsh" "$stage_linuxplus"; or fail "Could not create staging directories."

rsync -a --delete \
    --exclude='.obsidian/' \
    --exclude='07 chatgpt ramblings.md' \
    --exclude='99 chatgpt ramblings.md' \
    --exclude='Nodes/98 Router setup.md' \
    --exclude='2024/07 Lampades.md' \
    --exclude='2024/06.02 Cloudflare DDNS.md' \
    --exclude='2024/04 Physical Boxes.md' \
    --exclude='2024/06.01 Kemp Load Balancer.md' \
    --exclude='2024/05 Kronos.md' \
    --exclude='2024/06 Ostium.md' \
    "$source_house/" "$stage_house/"
or fail "House of Hades rsync failed."

rsync -a --delete \
    --exclude='.obsidian/' \
    --exclude='docker-compose.yml' \
    --exclude='IT & Smart Home Side Business – Nashville, TN.md' \
    "$source_hckrslsh/" "$stage_hckrslsh/"
or fail "HckrSlsh rsync failed."

rsync -a --delete \
    --exclude='.obsidian/' \
    "$source_linuxplus/" "$stage_linuxplus/"
or fail "Linux+ rsync failed."

set -l staged_files (find "$stage_root" -type f)
set -l staged_count (count $staged_files)
printf 'Staged files: %s\n' "$staged_count"

# ---------- Credential safety gate ----------

banner "CREDENTIAL SAFETY SCAN"

set -l hits_file (mktemp)
or fail "Could not create temporary scan file."

rg -l -i "$credential_pattern" "$stage_root" >"$hits_file"
set -l scan_status $status

if test $scan_status -eq 0
    printf 'ABORT: possible credential assignments were detected in staged RAG content:\n' >&2
    cat "$hits_file" >&2
    rm -f "$hits_file"
    printf '\nNothing was reindexed. Review/sanitize the listed staged files first.\n' >&2
    exit 2
else if test $scan_status -eq 1
    printf 'Credential assignment scan: clean\n'
else
    rm -f "$hits_file"
    fail "ripgrep credential scan failed with status $scan_status"
end

rm -f "$hits_file"

set -l suspicious_names (find "$stage_root" -type f | grep -Ei '(secret|credential|password|passwd|api.?key|token|account)')
if test (count $suspicious_names) -gt 0
    printf '\nWARNING: suspicious staged filenames found:\n'
    printf '  %s\n' $suspicious_names
    printf 'Review these names if they are unexpected.\n'
else
    printf 'Suspicious filename scan: clean\n'
end

# ---------- Add searchable RAG context ----------

banner "ENRICH MARKDOWN CONTEXT"

python -c 'from pathlib import Path; root=Path("data/personal_docs/obsidian"); marker="<!-- odysseus-rag-context -->"; files=list(root.rglob("*.md")); [(lambda t,p=p: None if t.startswith(marker) else p.write_text(marker+"\nKnowledge base: "+p.relative_to(root).parts[0]+"\nSource path: "+p.relative_to(root).as_posix()+"\nFile name: "+p.name+"\n\n"+t,encoding="utf-8"))(p.read_text(encoding="utf-8",errors="replace")) for p in files]; print("Enriched Markdown files:",len(files))'
or fail "Markdown enrichment failed."

# ---------- Rebuild staged RAG domains ----------

banner "REINDEX CHROMA / FASTEMBED"

set -l reindex_code 'from src.rag_singleton import get_rag_manager
import sys

owner = sys.argv[1]
r = get_rag_manager()
dirs = [
    "/app/data/personal_docs/obsidian/house-of-hades",
    "/app/data/personal_docs/obsidian/hckrslsh",
    "/app/data/personal_docs/obsidian/linuxplus",
]

results = []
for directory in dirs:
    removed = r.remove_directory(directory)
    indexed = r.index_personal_documents(directory, owner=owner)
    results.append((directory, removed, indexed))
    print(f"\n{directory}")
    print("  removed:", removed)
    print("  indexed:", indexed)

stats = r.get_stats()
print("\n=== RAG HEALTH ===")
print(stats)

ok = all(
    indexed.get("success") is True and indexed.get("failed_count", 0) == 0
    for _, _, indexed in results
)
ok = ok and bool(stats.get("healthy"))

queries = [
    "What nodes exist in the House of Hades documentation?",
    "What services and pricing did I design for HckrSlsh?",
    "What Linux commands have I documented?",
]

print("\n=== RETRIEVAL SMOKE TEST ===")
for query in queries:
    print(f"\n{query}")
    hits = r.search(query, k=3, owner=owner)
    if not hits:
        print("  NO RESULTS")
        continue
    for hit in hits:
        filename = hit.get("metadata", {}).get("filename", "?")
        score = float(hit.get("similarity", 0) or 0)
        print(f"  - {filename} | {score:.3f}")

sys.exit(0 if ok else 1)
'

docker compose exec --user 1000:1000 odysseus python -c "$reindex_code" "$owner"
or fail "RAG reindex or health verification failed."

banner "SYNC COMPLETE"
printf 'Sanitized Obsidian knowledge has been synchronized and reindexed successfully.\n'
