#!/usr/bin/env bash
# Approved stack maintenance (h10b_orphan_cleanup): remove the objects that earlier runs
# left in the experiment table locations, once, before the H10B measurement.
#
# The script is restartable. A table that already carries a recorded "after" line is
# skipped, so an interrupted cleanup can be completed without measuring anything twice.
set -euo pipefail

project_dir="${1:-.}"
run_label="${2:?usage: h10b_cleanup_orphans.sh PROJECT_DIR RUN_LABEL}"
cd "$project_dir"

contract="contracts/h10b-injected-revision-physical.json"
raw_dir="results/raw/h10b/cleanup-${run_label}"
mkdir -p "$raw_dir/file-lists"
record="$raw_dir/orphan-cleanup.txt"
touch "$record"

treatment_tables=()
while read -r treatment table; do
  treatment_tables+=("${treatment} ${table}")
done < <(python3 -c '
import json
contract = json.load(open("'"$contract"'"))
for treatment, tables in contract["tables"].items():
    for table in tables:
        print(treatment, table)
')

compose=(docker compose --env-file infra/docker/versions.env)

run_spark() {
  local label="$1"
  local sql="$2"
  set +e
  output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql --silent -e "$sql" </dev/null 2>&1)"
  spark_status=$?
  set -e
  if (( spark_status != 0 )); then
    printf '%s\n' "$output" >&2
    echo "H10B cleanup Spark SQL ${label} failed with status ${spark_status}" >&2
    exit "$spark_status"
  fi
}

list_location() {
  local location="$1"
  local bucket_path="${location#s3://}"
  "${compose[@]}" exec -T minio sh -c \
    "mc alias set h10bc http://localhost:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc ls --recursive --json h10bc/${bucket_path}/" </dev/null \
    | python3 -c '
import json
import sys
location = sys.argv[1]
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    item = json.loads(line)
    if item.get("status") != "success" or item.get("type") != "file":
        raise SystemExit("unexpected MinIO listing entry: " + line)
    modified = item["lastModified"].replace("T", " ")[:19]
    print(location + "/" + item["key"] + "|" + str(item["size"]) + "|" + modified)
' "$location"
}

# 25 hours back is the shortest interval the Iceberg procedure accepts. Nothing written
# today can fall inside it, and every leftover object is at least a day old.
cleanup_stamp="$(date -u -d '25 hours ago' +'%Y-%m-%d %H:%M:%S')"
{
  echo "run_label=cleanup-${run_label}"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "older_than=${cleanup_stamp}"
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$raw_dir/cleanup-environment.txt"

for entry in "${treatment_tables[@]}"; do
  table="${entry#* }"
  short_table="${table#kkciv.}"
  if grep -q "^H10BC|${table}|after|" "$record"; then
    echo "cleanup of ${table} already recorded; skipping"
    continue
  fi

  run_spark "location ${table}" \
    "SELECT concat('H10BLOC|', file) FROM (SELECT file FROM ${table}.metadata_log_entries LIMIT 1) entry;"
  location="$(printf '%s\n' "$output" | grep -E '^H10BLOC\|' | head -1 | cut -d'|' -f2 | sed -E 's#/metadata/[^/]+$##')"
  if [[ "$location" != s3://* ]]; then
    echo "H10B cleanup could not resolve the location of ${table}" >&2
    exit 1
  fi

  file_list="$raw_dir/file-lists/${table##*.}.csv"
  {
    echo "file_path,last_modified"
    while IFS='|' read -r path _size modified; do
      printf '%s,%s\n' "$path" "$modified"
    done < <(list_location "$location")
  } > "$file_list"

  objects=0
  bytes=0
  while IFS='|' read -r _path size _modified; do
    objects=$((objects + 1))
    bytes=$((bytes + size))
  done < <(list_location "$location")
  printf 'H10BC|%s|before|%s|%s\n' "$table" "$objects" "$bytes" >> "$record"

  # The Spark image has no Hadoop file system for the s3 scheme, so the procedure is
  # handed the MinIO listing instead of listing the location itself.
  run_spark "remove orphan files ${table}" "
CREATE OR REPLACE TEMPORARY VIEW h10b_file_list_csv USING csv OPTIONS (
  path '/home/iceberg/${file_list}', header 'true', inferSchema 'false');
CREATE OR REPLACE TEMPORARY VIEW h10b_file_list AS
SELECT file_path, CAST(last_modified AS TIMESTAMP) AS last_modified FROM h10b_file_list_csv;
CALL kkciv.system.remove_orphan_files(
  table => '${short_table}',
  older_than => TIMESTAMP '${cleanup_stamp}',
  file_list_view => 'h10b_file_list'
);"
  while read -r removed; do
    [[ -z "$removed" ]] && continue
    printf 'H10BO|%s|%s\n' "$table" "$removed" >> "$record"
  done < <(printf '%s\n' "$output" | grep -E '^s3://' || true)

  objects=0
  bytes=0
  while IFS='|' read -r _path size _modified; do
    objects=$((objects + 1))
    bytes=$((bytes + size))
  done < <(list_location "$location")
  printf 'H10BC|%s|after|%s|%s\n' "$table" "$objects" "$bytes" >> "$record"
done

echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$raw_dir/cleanup-environment.txt"
echo "H10B_CLEANUP|${run_label}|$(grep -c '^H10BO|' "$record" || true)|$(grep -c '^H10BC|' "$record")"
