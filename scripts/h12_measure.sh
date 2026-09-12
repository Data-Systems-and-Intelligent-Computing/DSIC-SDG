#!/usr/bin/env bash
# H12: apply the four real BPS releases of the frozen panel to every treatment, one
# arrival at a time, and measure what each real revision costs that treatment.
#
# The mechanisms and the maintenance are the ones frozen at H7-H9, applied per arrival,
# so these numbers can be read next to the injected-revision numbers of H10B and H11.
# Run this on the stack host with a clean working tree and a persistent catalog.
set -euo pipefail

project_dir="${1:-.}"
run_label="${2:?usage: h12_measure.sh PROJECT_DIR RUN_LABEL}"
cd "$project_dir"
# shellcheck source=scripts/h11_sql.sh
source scripts/h11_sql.sh

contract="contracts/h12-real-revision-cost.json"
raw_dir="results/raw/h12/${run_label}"
if [[ -e "$raw_dir" ]]; then
  echo "raw run directory ${raw_dir} already exists; measurements are never overwritten" >&2
  exit 1
fi
h11_load_manifest
git_dirty="$(git status --porcelain | wc -l | tr -d ' ')"

read -r repetitions catalog_prefix < <(python3 -c '
import json
contract = json.load(open("'"$contract"'"))
print(contract["protocol"]["repetitions"], contract["protocol"]["catalog_uri_prefix"])
')
if [[ -n "${H12_LIMIT_REPETITIONS:-}" ]]; then
  repetitions="$H12_LIMIT_REPETITIONS"
  limited="yes"
else
  limited="no"
fi

treatment_tables=(
  "B0 ${h11_b0_table}"
  "B1 ${h11_b1_table}"
  "B2 ${h11_b2_table}"
  "B3 ${h11_b3_store}"
  "B3 ${h11_b3_serving}"
)

compose=(docker compose --env-file infra/docker/versions.env)

run_spark() {
  local label="$1" sql="$2"
  set +e
  output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql --silent -e "$sql" </dev/null 2>&1)"
  spark_status=$?
  set -e
  if (( spark_status != 0 )); then
    printf '%s\n' "$output" >&2
    echo "H12 Spark SQL ${label} failed with status ${spark_status}" >&2
    exit "$spark_status"
  fi
}

run_spark_timed() {
  local label="$1" sql="$2"
  set +e
  output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql -e "$sql" </dev/null 2>&1)"
  spark_status=$?
  set -e
  if (( spark_status != 0 )); then
    printf '%s\n' "$output" >&2
    echo "H12 Spark SQL ${label} failed with status ${spark_status}" >&2
    exit "$spark_status"
  fi
  timings=()
  while read -r seconds; do
    timings+=("$seconds")
  done < <(printf '%s\n' "$output" | sed -nE 's/^Time taken: ([0-9.]+) seconds.*$/\1/p')
}

# One session per treatment applies every arrival, so the statements of one arrival are
# a contiguous block; the staging views in front of them are harness cost.
record_arrival_timings() {
  local rep="$1" treatment="$2" per_arrival="$3"
  shift 3
  local labels=("$@")
  local total="${#timings[@]}"
  local expected=$(( per_arrival * h11_arrivals ))
  if (( total < expected )); then
    echo "H12 ${treatment} produced ${total} timings for ${expected} treatment statements" >&2
    exit 1
  fi
  local harness=0 index=0
  for (( index = 0; index < total - expected; index++ )); do
    harness=$(python3 -c "print(f'{${harness} + ${timings[$index]}:.3f}')")
  done
  printf 'H12T|%s|%s|0|0|staging_views|harness|%s\n' "$rep" "$treatment" "$harness" \
    >> "$raw_dir/timing.txt"
  local offset=$(( total - expected ))
  local arrival position entry
  for (( arrival = 1; arrival <= h11_arrivals; arrival++ )); do
    position=1
    for entry in "${labels[@]}"; do
      printf 'H12T|%s|%s|%s|%s|%s|%s|%s\n' \
        "$rep" "$treatment" "$arrival" "$position" "${entry%% *}" "${entry##* }" \
        "${timings[$(( offset + (arrival - 1) * per_arrival + position - 1 ))]}" \
        >> "$raw_dir/timing.txt"
      position=$(( position + 1 ))
    done
  done
}

# The state a treatment holds after an arrival, with the bytes its metadata still
# references. The MinIO listing at the end of the cycle cross-checks these sizes.
arrival_marker() {
  local rep="$1" treatment="$2" table="$3" arrival="$4"
  cat <<SQL
SELECT concat_ws('|', 'H12A', '${rep}', '${treatment}', '${table}', '${arrival}',
  CAST((SELECT count(*) FROM ${table}) AS STRING),
  CAST((SELECT count(DISTINCT cell_id) FROM ${table}) AS STRING),
  CAST((SELECT count(*) FROM ${table}.snapshots) AS STRING),
  CAST((SELECT coalesce(sum(file_size_in_bytes), 0) FROM (
    SELECT DISTINCT file_path, file_size_in_bytes FROM ${table}.all_data_files) data_files) AS STRING),
  CAST((SELECT coalesce(sum(length), 0) FROM (
    SELECT DISTINCT path, length FROM ${table}.all_manifests) manifests) AS STRING));
SQL
}

list_location() {
  local location="$1"
  local bucket_path="${location#s3://}"
  "${compose[@]}" exec -T minio sh -c \
    "mc alias set h12 http://localhost:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc ls --recursive --json h12/${bucket_path}/" </dev/null \
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
    print(location + "/" + item["key"] + "|" + str(item["size"]))
' "$location"
}

measure_final_footprint() {
  local rep="$1"
  local sql=""
  for entry in "${treatment_tables[@]}"; do
    local treatment="${entry%% *}" table="${entry#* }"
    sql+="
SELECT concat_ws('|', 'H12F', '${rep}', '${treatment}', '${table}', 'data', file_path,
  CAST(file_size_in_bytes AS STRING))
FROM (SELECT DISTINCT file_path, file_size_in_bytes FROM ${table}.all_data_files) files;
SELECT concat_ws('|', 'H12F', '${rep}', '${treatment}', '${table}', 'delete', file_path,
  CAST(file_size_in_bytes AS STRING))
FROM (SELECT DISTINCT file_path, file_size_in_bytes FROM ${table}.all_delete_files) files;
SELECT concat_ws('|', 'H12F', '${rep}', '${treatment}', '${table}', 'manifest', path,
  CAST(length AS STRING))
FROM (SELECT DISTINCT path, length FROM ${table}.all_manifests) manifests;
SELECT concat_ws('|', 'H12F', '${rep}', '${treatment}', '${table}', 'manifest_list', manifest_list, '')
FROM (SELECT DISTINCT manifest_list FROM ${table}.snapshots) lists;
SELECT concat_ws('|', 'H12F', '${rep}', '${treatment}', '${table}', 'metadata_json', file, '')
FROM (SELECT DISTINCT file FROM ${table}.metadata_log_entries) entries;
"
  done
  run_spark "final footprint ${rep}" "$sql"
  printf '%s\n' "$output" | grep -E '^H12F\|' >> "$raw_dir/footprint.txt"

  for entry in "${treatment_tables[@]}"; do
    local treatment="${entry%% *}" table="${entry#* }"
    local location
    location="$(printf '%s\n' "$output" | grep -E '^H12F\|' | grep "|${table}|metadata_json|" | head -1 | cut -d'|' -f6 | sed -E 's#/metadata/[^/]+$##')"
    if [[ "$location" != s3://* ]]; then
      echo "H12 could not resolve the location of ${table}" >&2
      exit 1
    fi
    while IFS='|' read -r path size; do
      printf 'H12L|%s|%s|%s|%s|%s\n' "$rep" "$treatment" "$table" "$path" "$size" \
        >> "$raw_dir/listing.txt"
    done < <(list_location "$location")
  done
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
  echo "H12 requires a persistent catalog under ${catalog_prefix}; found ${catalog_uri}" >&2
  exit 1
fi
wait_for_catalog

mkdir -p "$raw_dir"
{
  echo "run_label=${run_label}"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "git_dirty_entries=${git_dirty}"
  echo "hostname=$(hostname)"
  echo "host_nproc=$(nproc)"
  echo "host_mem_total_bytes=$(awk '/MemTotal/ {print $2 * 1024}' /proc/meminfo)"
  echo "host_disk_free_bytes_before=$(df -B1 --output=avail / | tail -1 | tr -d ' ')"
  echo "spark_driver_memory=$("${compose[@]}" exec -T spark printenv SPARK_DRIVER_MEMORY </dev/null | tr -d '\r')"
  echo "catalog_uri=${catalog_uri}"
  echo "spark_defaults_sha256=$(sha256sum infra/spark/spark-defaults.conf | cut -d' ' -f1)"
  echo "versions_env_sha256=$(sha256sum infra/docker/versions.env | cut -d' ' -f1)"
  echo "compose_sha256=$(sha256sum docker-compose.yml | cut -d' ' -f1)"
  echo "payload_manifest_sha256=$(sha256sum data/manifests/h11-main-sweep-payload.json | cut -d' ' -f1)"
  for service in minio iceberg-rest spark; do
    echo "image_${service}=$(docker inspect --format '{{.Image}}' "$("${compose[@]}" ps -q "$service")")"
  done
  echo "repetitions=${repetitions}"
  echo "arrivals=${h11_arrivals}"
  echo "limited_run=${limited}"
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$raw_dir/environment.txt"

purge_sql=""
for entry in "${treatment_tables[@]}"; do
  purge_sql+="DROP TABLE IF EXISTS ${entry#* } PURGE;"
done
views="$(h11_views)"

for rep in $(seq 1 "$repetitions"); do
  cycle_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  run_spark "purge and create ${rep}" "${purge_sql}
$(cat infra/spark/h11-sweep.sql)"

  # ---------- B0: overwrite the cell in place on every release ----------
  sql="${views}"
  for arrival in $(seq 1 "$h11_arrivals"); do
    sql+="
$(h11_b0_merge "$(h11_arrival_source "$arrival")" "$arrival")
$(h11_expire "$h11_b0_table")
$(arrival_marker "$rep" "B0" "$h11_b0_table" "$arrival")"
  done
  run_spark_timed "B0 arrivals ${rep}" "$sql"
  record_arrival_timings "$rep" "B0" 3 \
    "merge_arrival write" "expire_snapshots maintenance" "verify_state verification"
  printf '%s\n' "$output" | grep -E '^H12A\|' >> "$raw_dir/arrivals.txt"

  # ---------- B1: store one complete state per release ----------
  sql="${views}"
  for arrival in $(seq 1 "$h11_arrivals"); do
    sql+="
$(h11_b1_overwrite "$arrival")
$(arrival_marker "$rep" "B1" "$h11_b1_table" "$arrival")"
  done
  run_spark_timed "B1 arrivals ${rep}" "$sql"
  record_arrival_timings "$rep" "B1" 2 \
    "insert_overwrite_all_states write" "verify_state verification"
  printf '%s\n' "$output" | grep -E '^H12A\|' >> "$raw_dir/arrivals.txt"

  # ---------- B2: recompute the single-source selection on every release ----------
  sql="${views}"
  for arrival in $(seq 1 "$h11_arrivals"); do
    sql+="
CREATE OR REPLACE TEMPORARY VIEW h11_candidates AS
SELECT * FROM h11_panel WHERE arrival_order <= ${arrival};
$(h11_b2_overwrite)
$(h11_expire "$h11_b2_table")
$(arrival_marker "$rep" "B2" "$h11_b2_table" "$arrival")"
  done
  run_spark_timed "B2 arrivals ${rep}" "$sql"
  record_arrival_timings "$rep" "B2" 4 \
    "narrow_candidates harness" "insert_overwrite_selection write" \
    "expire_snapshots maintenance" "verify_state verification"
  printf '%s\n' "$output" | grep -E '^H12A\|' >> "$raw_dir/arrivals.txt"

  # ---------- B3: append the vintage and recompute only the dirty cells ----------
  sql="${views}"
  for arrival in $(seq 1 "$h11_arrivals"); do
    sql+="
$(h11_b3_insert "$arrival")
$(h11_b3_merge "stored.cell_id IN (SELECT DISTINCT cell_id FROM h11_edges_csv WHERE CAST(arrival_order AS INT) = ${arrival})" "$arrival")
$(h11_expire "$h11_b3_store")
$(h11_expire "$h11_b3_serving")
$(arrival_marker "$rep" "B3" "$h11_b3_store" "$arrival")
$(arrival_marker "$rep" "B3" "$h11_b3_serving" "$arrival")"
  done
  run_spark_timed "B3 arrivals ${rep}" "$sql"
  record_arrival_timings "$rep" "B3" 6 \
    "insert_store_rows write" "merge_serving_dirty_cells write" \
    "expire_snapshots_store maintenance" "expire_snapshots_serving maintenance" \
    "verify_store verification" "verify_serving verification"
  printf '%s\n' "$output" | grep -E '^H12A\|' >> "$raw_dir/arrivals.txt"

  measure_final_footprint "$rep"
  printf 'H12C|%s|%s|%s\n' "$rep" "$cycle_started" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >> "$raw_dir/cycles.txt"
done

{
  echo "host_disk_free_bytes_after=$(df -B1 --output=avail / | tail -1 | tr -d ' ')"
  echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$raw_dir/environment.txt"

echo "H12_RAW|${run_label}|${repetitions}|${h11_arrivals}|$(wc -l < "$raw_dir/timing.txt")|$(wc -l < "$raw_dir/arrivals.txt")|$(wc -l < "$raw_dir/footprint.txt")|$(wc -l < "$raw_dir/listing.txt")"
