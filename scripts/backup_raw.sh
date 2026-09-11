#!/usr/bin/env bash
set -euo pipefail

# Archive the local-only source payloads in data/raw with a checksum list.
# The archive stays in backups/ (ignored by Git); copy both files to a second location.
project_dir="${1:-.}"
cd "$project_dir"

stamp="$(date +%Y%m%d)"
archive="backups/data-raw-${stamp}.tar.gz"
sums="backups/data-raw-${stamp}.SHA256SUMS"
mkdir -p backups
if [[ -e "$archive" ]]; then
  echo "${archive} already exists; remove it or wait for a new date" >&2
  exit 1
fi

python3 - "$sums" <<'PY'
import glob
import hashlib
import json
import sys
from pathlib import Path

recorded = {}
def walk(node):
    if isinstance(node, dict):
        path = node.get("path") or node.get("raw_path")
        digest = node.get("sha256")
        if isinstance(path, str) and path.startswith("data/raw/") and isinstance(digest, str):
            recorded.setdefault(path, set()).add(digest)
        for value in node.values():
            walk(value)
    elif isinstance(node, list):
        for value in node:
            walk(value)
for manifest in sorted(glob.glob("data/manifests/*.json")):
    walk(json.load(open(manifest, encoding="utf-8")))

files = sorted(p for p in Path("data/raw").rglob("*") if p.is_file() and p.name != ".gitkeep")
lines, unrecorded = [], []
for path in files:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = recorded.get(str(path))
    if expected is None:
        unrecorded.append(str(path))
    elif expected != {digest}:
        sys.exit(f"{path} differs from the checksum recorded in its manifest")
    lines.append(f"{digest}  {path}")
if missing := sorted(set(recorded) - {str(p) for p in files}):
    sys.exit(f"manifested raw files are missing: {missing}")
Path(sys.argv[1]).write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"verified {len(files) - len(unrecorded)} manifested raw files; {len(unrecorded)} without a manifest checksum")
PY

tar -czf "$archive" data/raw
echo "RAW_BACKUP|${archive}|${sums}|$(wc -l < "$sums" | tr -d ' ')|$(du -h "$archive" | cut -f1)"
echo "Verify later with: shasum -a 256 -c ${sums}   (run from the repository root after extracting)"
