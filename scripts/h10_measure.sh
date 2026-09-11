#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:-.}"
run_label="${2:?usage: h10_measure.sh PROJECT_DIR RUN_LABEL}"
cd "$project_dir"

contract="contracts/h10-storage-recall.json"
raw_dir="results/raw/h10/${run_label}"
if [[ -e "$raw_dir" ]]; then
  echo "raw run directory ${raw_dir} already exists; measurements are never overwritten" >&2
  exit 1
fi
git_dirty="$(git status --porcelain | wc -l | tr -d ' ')"

read -r repetitions catalog_prefix < <(python3 -c '
import json
contract = json.load(open("'"$contract"'"))
print(contract["protocol"]["repetitions"], contract["protocol"]["catalog_uri_prefix"])
')
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
apply_scripts=()
while read -r treatment script; do
  apply_scripts+=("${treatment} ${script}")
done < <(python3 -c '
import json
contract = json.load(open("'"$contract"'"))
for treatment, script in contract["protocol"]["apply_scripts"].items():
    print(treatment, script)
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
    echo "H10 Spark SQL ${label} failed with status ${spark_status}" >&2
    exit "$spark_status"
  fi
}

wait_for_catalog() {
  for _ in $(seq 1 60); do
    if curl -fsS http://127.0.0.1:8181/v1/config >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Iceberg REST catalog did not become ready" >&2
  exit 1
}

catalog_uri="$("${compose[@]}" exec -T iceberg-rest printenv CATALOG_URI </dev/null | tr -d '\r')"
if [[ "$catalog_uri" != "${catalog_prefix}"* ]]; then
  echo "H10 requires a persistent catalog under ${catalog_prefix}; found ${catalog_uri}" >&2
  exit 1
fi

mkdir -p "$raw_dir"
{
  echo "run_label=${run_label}"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "git_dirty_entries=${git_dirty}"
  echo "hostname=$(hostname)"
  echo "host_nproc=$(nproc)"
  echo "host_mem_total_bytes=$(awk '/MemTotal/ {print $2 * 1024}' /proc/meminfo)"
  echo "host_disk_total_bytes=$(df -B1 --output=size / | tail -1 | tr -d ' ')"
  echo "host_disk_free_bytes_before=$(df -B1 --output=avail / | tail -1 | tr -d ' ')"
  echo "spark_container_nproc=$("${compose[@]}" exec -T spark nproc </dev/null | tr -d '\r')"
  echo "catalog_uri=${catalog_uri}"
  echo "spark_defaults_sha256=$(sha256sum infra/spark/spark-defaults.conf | cut -d' ' -f1)"
  echo "versions_env_sha256=$(sha256sum infra/docker/versions.env | cut -d' ' -f1)"
  echo "compose_sha256=$(sha256sum docker-compose.yml | cut -d' ' -f1)"
  for service in minio iceberg-rest spark; do
    echo "image_${service}=$(docker inspect --format '{{.Image}}' "$("${compose[@]}" ps -q "$service")")"
  done
  echo "repetitions=${repetitions}"
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$raw_dir/environment.txt"

for rep in $(seq 1 "$repetitions"); do
  purge_sql=""
  for entry in "${treatment_tables[@]}"; do
    purge_sql+="DROP TABLE IF EXISTS ${entry#* } PURGE;"
  done
  run_spark "purge ${rep}" "$purge_sql"

  for entry in "${apply_scripts[@]}"; do
    treatment="${entry%% *}"
    script="${entry#* }"
    set +e
    apply_output="$(bash "$script" . 2>&1)"
    apply_status=$?
    set -e
    if (( apply_status != 0 )); then
      printf '%s\n' "$apply_output" >&2
      echo "H10 ${treatment} apply failed in repetition ${rep}" >&2
      exit "$apply_status"
    fi
    marker="$(printf '%s\n' "$apply_output" | grep -E '^H[0-9A-Z]+_VERIFY\|' | tail -1)"
    echo "${rep}|${treatment}|${marker}" >> "$raw_dir/apply-markers.txt"
  done

  for entry in "${treatment_tables[@]}"; do
    treatment="${entry%% *}"
    table="${entry#* }"
    sql="
SELECT concat_ws('|', 'H10F', '${rep}', '${treatment}', '${table}', 'data', file_path,
  CAST(file_size_in_bytes AS STRING), CAST(record_count AS STRING))
FROM (SELECT DISTINCT file_path, file_size_in_bytes, record_count FROM ${table}.all_data_files) files;
SELECT concat_ws('|', 'H10F', '${rep}', '${treatment}', '${table}', 'delete', file_path,
  CAST(file_size_in_bytes AS STRING), CAST(record_count AS STRING))
FROM (SELECT DISTINCT file_path, file_size_in_bytes, record_count FROM ${table}.all_delete_files) files;
SELECT concat_ws('|', 'H10F', '${rep}', '${treatment}', '${table}', 'manifest', path,
  CAST(length AS STRING), '')
FROM (SELECT DISTINCT path, length FROM ${table}.all_manifests) manifests;
SELECT concat_ws('|', 'H10F', '${rep}', '${treatment}', '${table}', 'manifest_list', manifest_list, '', '')
FROM (SELECT DISTINCT manifest_list FROM ${table}.snapshots) lists;
SELECT concat_ws('|', 'H10F', '${rep}', '${treatment}', '${table}', 'metadata_json', file, '', '')
FROM (SELECT DISTINCT file FROM ${table}.metadata_log_entries) entries;
SELECT concat_ws('|', 'H10S', '${rep}', '${treatment}', '${table}',
  CAST((SELECT count(*) FROM ${table}.snapshots) AS STRING),
  CAST((SELECT count(*) FROM ${table}) AS STRING));
"
    run_spark "footprint ${rep} ${table}" "$sql"
    printf '%s\n' "$output" | grep -E '^H10[FS]\|' >> "$raw_dir/footprint.txt"

    location="$(printf '%s\n' "$output" | grep -E '^H10F\|' | grep '|metadata_json|' | head -1 | cut -d'|' -f6 | sed -E 's#/metadata/[^/]+$##')"
    if [[ "$location" != s3://* ]]; then
      echo "H10 could not resolve the location of ${table}" >&2
      exit 1
    fi
    bucket_path="${location#s3://}"
    "${compose[@]}" exec -T minio sh -c \
      "mc alias set h10 http://localhost:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc ls --recursive --json h10/${bucket_path}/" </dev/null \
      | python3 -c '
import json
import sys
rep, treatment, table, location = sys.argv[1:5]
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    item = json.loads(line)
    if item.get("status") != "success" or item.get("type") != "file":
        raise SystemExit("unexpected MinIO listing entry: " + line)
    print("|".join(["H10L", rep, treatment, table, location + "/" + item["key"], str(item["size"])]))
' "$rep" "$treatment" "$table" "$location" >> "$raw_dir/listing.txt"
  done
done

"${compose[@]}" restart iceberg-rest >/dev/null 2>&1
wait_for_catalog

b3_store="$(printf '%s\n' "${treatment_tables[@]}" | awk '$1 == "B3" && $2 ~ /observation_vintages$/ {print $2}')"
b1_table="$(printf '%s\n' "${treatment_tables[@]}" | awk '$1 == "B1" {print $2}')"
b0_table="$(printf '%s\n' "${treatment_tables[@]}" | awk '$1 == "B0" {print $2}')"
b2_table="$(printf '%s\n' "${treatment_tables[@]}" | awk '$1 == "B2" {print $2}')"

run_spark "b1 snapshots after restart" "SELECT concat('H10SNAP|', CAST(snapshot_id AS STRING)) FROM ${b1_table}.snapshots ORDER BY committed_at, snapshot_id;"
snapshot_ids=()
while read -r line; do
  snapshot_ids+=("${line#H10SNAP|}")
done < <(printf '%s\n' "$output" | grep -E '^H10SNAP\|')
if (( ${#snapshot_ids[@]} == 0 )); then
  echo "H10 found no B1 snapshots after the catalog restart" >&2
  exit 1
fi
history_sql=""
for index in "${!snapshot_ids[@]}"; do
  [[ -n "$history_sql" ]] && history_sql+=" UNION ALL "
  history_sql+="SELECT $((index + 1)) AS snapshot_order, observation_id, value_lexeme FROM ${b1_table} VERSION AS OF ${snapshot_ids[$index]}"
done

recall_sql="
CREATE OR REPLACE TEMPORARY VIEW h10_requests USING csv OPTIONS (
  path '/home/iceberg/results/processed/h6-indicator-observations.csv', header 'true', inferSchema 'false');
CREATE OR REPLACE TEMPORARY VIEW h10_b1_history AS ${history_sql};
SELECT concat_ws('|', 'H10R', 'B0', r.observation_id, coalesce(c.observation_id, ''), coalesce(c.value_lexeme, ''), 'current')
FROM h10_requests r LEFT JOIN ${b0_table} c ON c.observation_id = r.observation_id;
SELECT concat_ws('|', 'H10R', 'B2', r.observation_id, coalesce(c.observation_id, ''), coalesce(c.value_lexeme, ''), 'current')
FROM h10_requests r LEFT JOIN ${b2_table} c ON c.observation_id = r.observation_id;
SELECT concat_ws('|', 'H10R', 'B3', r.observation_id, coalesce(s.observation_id, ''), coalesce(s.value_lexeme, ''), 'vintage_key')
FROM h10_requests r LEFT JOIN ${b3_store} s ON s.cell_id = r.cell_id AND s.vintage_id = r.vintage_id;
SELECT concat_ws('|', 'H10R', 'B1', r.observation_id, coalesce(max(h.observation_id), ''),
  coalesce(max(h.value_lexeme), ''),
  concat('snapshot_orders=', concat_ws(';', sort_array(collect_set(CAST(h.snapshot_order AS STRING))))))
FROM h10_requests r LEFT JOIN h10_b1_history h ON h.observation_id = r.observation_id
GROUP BY r.observation_id;
"
run_spark "recall after restart" "$recall_sql"
printf '%s\n' "$output" | grep -E '^H10R\|' > "$raw_dir/recall.txt"
printf 'H10SNAPCOUNT|%s\n' "${#snapshot_ids[@]}" >> "$raw_dir/recall.txt"

{
  echo "host_disk_free_bytes_after=$(df -B1 --output=avail / | tail -1 | tr -d ' ')"
  echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$raw_dir/environment.txt"

echo "H10_RAW|${run_label}|${repetitions}|$(wc -l < "$raw_dir/footprint.txt")|$(wc -l < "$raw_dir/listing.txt")|$(grep -c '^H10R|' "$raw_dir/recall.txt")"
