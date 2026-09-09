#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:-.}"
cd "$project_dir"

manifest="data/manifests/h4-ingestion-classification.json"
read -r batch_id bucket object_prefix < <(
  python3 -c '
import json
data = json.load(open("data/manifests/h4-ingestion-classification.json"))
target = data["object_store_target"]
print(data["batch_id"], target["bucket"], target["prefix"])
'
)
compose=(docker compose --env-file infra/docker/versions.env)
files=(
  results/processed/h4-ingested-observations.csv
  results/processed/h4-ingestion-inventory.csv
  results/processed/h4-classified-events.csv
  results/processed/h4-classification-summary.csv
  "$manifest"
)

"${compose[@]}" exec -T minio mkdir -p "/tmp/$batch_id"
for file in "${files[@]}"; do
  "${compose[@]}" cp "$file" "minio:/tmp/$batch_id/$(basename "$file")"
done

"${compose[@]}" exec -T minio sh -c '
  set -e
  mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
  mc mb --ignore-existing "local/'"$bucket"'" >/dev/null
  mc cp --recursive "/tmp/'"$batch_id"'/" "local/'"$bucket"'/'"$object_prefix"'" >/dev/null
  for file in "/tmp/'"$batch_id"'"/*; do
    object="${file##*/}"
    set -- $(sha256sum "$file")
    expected="$1"
    set -- $(mc cat "local/'"$bucket"'/'"$object_prefix"'$object" | sha256sum)
    actual="$1"
    test "$actual" = "$expected"
    echo "verified $actual $object"
  done
  mc ls --recursive "local/'"$bucket"'/'"$object_prefix"'"
'
