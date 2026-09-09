#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:-.}"
cd "$project_dir"

manifest="data/manifests/h4-ingestion-classification.json"
batch_id="$(python3 -c 'import json; print(json.load(open("data/manifests/h4-ingestion-classification.json"))["batch_id"])')"
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
  mc mb --ignore-existing local/kkciv-warehouse >/dev/null
  mc cp --recursive "/tmp/'"$batch_id"'/" "local/kkciv-warehouse/ingest/h4/'"$batch_id"'/" >/dev/null
  mc ls --recursive "local/kkciv-warehouse/ingest/h4/'"$batch_id"'/"
'
