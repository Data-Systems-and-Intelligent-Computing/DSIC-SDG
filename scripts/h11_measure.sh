#!/usr/bin/env bash
# H11 main sweep: for every frozen revision size, rebuild the four treatments on the
# province panel, inject the revision through each treatment's own write mechanism, and
# measure the statement time, the byte growth, the recall and the propagation.
#
# Run this on the stack host with a clean working tree and a persistent catalog.
set -euo pipefail

project_dir="${1:-.}"
run_label="${2:?usage: h11_measure.sh PROJECT_DIR RUN_LABEL}"
cd "$project_dir"
# shellcheck source=scripts/h11_sql.sh
source scripts/h11_sql.sh

contract="contracts/h11-main-sweep.json"
raw_dir="results/raw/h11/${run_label}"
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
scenarios=()
while read -r scenario; do
  scenarios+=("$scenario")
done < <(python3 -c '
import json
contract = json.load(open("'"$contract"'"))
for scenario in sorted(contract["scenarios"], key=lambda row: row["scenario_order"]):
    print(scenario["scenario_id"])
')

# Smoke overrides. A run that uses them cannot pass aggregation, which checks the
# frozen repetition count and scenario list, and environment.txt records that it was
# limited, so a partial run can never be mistaken for the main sweep.
limited="no"
if [[ -n "${H11_LIMIT_SCENARIOS:-}" ]]; then
  IFS=';' read -r -a scenarios <<< "$H11_LIMIT_SCENARIOS"
  limited="yes"
fi
if [[ -n "${H11_LIMIT_REPETITIONS:-}" ]]; then
  repetitions="$H11_LIMIT_REPETITIONS"
  limited="yes"
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
    echo "H11 Spark SQL ${label} failed with status ${spark_status}" >&2
    exit "$spark_status"
  fi
}

# Same session, but the CLI keeps its "Time taken" lines so each statement can be timed
# without the JVM start-up of a fresh session.
run_spark_timed() {
  local label="$1" sql="$2"
  set +e
  output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql -e "$sql" </dev/null 2>&1)"
  spark_status=$?
  set -e
  if (( spark_status != 0 )); then
    printf '%s\n' "$output" >&2
    echo "H11 Spark SQL ${label} failed with status ${spark_status}" >&2
    exit "$spark_status"
  fi
  timings=()
  while read -r seconds; do
    timings+=("$seconds")
  done < <(printf '%s\n' "$output" | sed -nE 's/^Time taken: ([0-9.]+) seconds.*$/\1/p')
}

# The staging views come first in every timed session and are pure harness cost, so the
# treatment statements are labeled from the end of the session backwards.
record_timings() {
  local rep="$1" scenario="$2" treatment="$3"
  shift 3
  local labels=("$@")
  local total="${#timings[@]}"
  local tail_count="${#labels[@]}"
  if (( total < tail_count )); then
    echo "H11 ${treatment} produced ${total} statement timings for ${tail_count} treatment statements" >&2
    exit 1
  fi
  local harness=0 index=0
  for (( index = 0; index < total - tail_count; index++ )); do
    harness=$(python3 -c "print(f'{${harness} + ${timings[$index]}:.3f}')")
  done
  printf 'H11T|%s|%s|%s|0|staging_views|harness|%s\n' "$rep" "$scenario" "$treatment" "$harness" \
    >> "$raw_dir/timing.txt"
  local position=1
  for entry in "${labels[@]}"; do
    printf 'H11T|%s|%s|%s|%s|%s|%s|%s\n' \
      "$rep" "$scenario" "$treatment" "$position" "${entry%% *}" "${entry##* }" \
      "${timings[$((total - tail_count + position - 1))]}" >> "$raw_dir/timing.txt"
    position=$((position + 1))
  done
}

list_location() {
  local location="$1"
  local bucket_path="${location#s3://}"
  "${compose[@]}" exec -T minio sh -c \
    "mc alias set h11 http://localhost:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc ls --recursive --json h11/${bucket_path}/" </dev/null \
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

# One session measures every table of a phase; the MinIO listing then sizes the objects.
measure_phase() {
  local rep="$1" scenario="$2" phase="$3"
  local sql=""
  for entry in "${treatment_tables[@]}"; do
    local treatment="${entry%% *}" table="${entry#* }"
    sql+="
SELECT concat_ws('|', 'H11F', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}', 'data', file_path,
  CAST(file_size_in_bytes AS STRING), CAST(record_count AS STRING))
FROM (SELECT DISTINCT file_path, file_size_in_bytes, record_count FROM ${table}.all_data_files) files;
SELECT concat_ws('|', 'H11F', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}', 'delete', file_path,
  CAST(file_size_in_bytes AS STRING), CAST(record_count AS STRING))
FROM (SELECT DISTINCT file_path, file_size_in_bytes, record_count FROM ${table}.all_delete_files) files;
SELECT concat_ws('|', 'H11F', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}', 'manifest', path,
  CAST(length AS STRING), '')
FROM (SELECT DISTINCT path, length FROM ${table}.all_manifests) manifests;
SELECT concat_ws('|', 'H11F', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}', 'manifest_list', manifest_list, '', '')
FROM (SELECT DISTINCT manifest_list FROM ${table}.snapshots) lists;
SELECT concat_ws('|', 'H11F', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}', 'metadata_json', file, '', '')
FROM (SELECT DISTINCT file FROM ${table}.metadata_log_entries) entries;
SELECT concat_ws('|', 'H11S', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}',
  CAST((SELECT count(*) FROM ${table}.snapshots) AS STRING),
  CAST((SELECT count(*) FROM ${table}) AS STRING));
"
  done
  run_spark "footprint ${phase} ${rep} ${scenario}" "$sql"
  printf '%s\n' "$output" | grep -E '^H11[FS]\|' >> "$raw_dir/footprint.txt"

  for entry in "${treatment_tables[@]}"; do
    local treatment="${entry%% *}" table="${entry#* }"
    local location
    location="$(printf '%s\n' "$output" | grep -E "^H11F\|" | grep "|${table}|metadata_json|" | head -1 | cut -d'|' -f8 | sed -E 's#/metadata/[^/]+$##')"
    if [[ "$location" != s3://* ]]; then
      echo "H11 could not resolve the location of ${table}" >&2
      exit 1
    fi
    while IFS='|' read -r path size; do
      printf 'H11L|%s|%s|%s|%s|%s|%s|%s\n' "$rep" "$scenario" "$phase" "$treatment" "$table" "$path" "$size" \
        >> "$raw_dir/listing.txt"
    done < <(list_location "$location")
  done
}

served_state() {
  local treatment="$1"
  case "$treatment" in
    B0) echo "  SELECT cell_id, observation_id, value_lexeme FROM ${h11_b0_table}" ;;
    B1) echo "  SELECT cell_id, observation_id, value_lexeme FROM ${h11_b1_table} WHERE snapshot_order = $((h11_arrivals + 1))" ;;
    B2) echo "  SELECT cell_id, observation_id, value_lexeme FROM ${h11_b2_table}" ;;
    B3) echo "  SELECT cell_id, observation_id, value_lexeme FROM ${h11_b3_serving}" ;;
  esac
}

# The expected state of a treatment after the revision: the frozen prediction for the
# revised cells, and the untouched panel state for every other cell.
expected_state() {
  local treatment="$1" scenario="$2"
  local untouched="h11_panel_latest"
  if [[ "$treatment" == "B2" ]]; then
    untouched="h11_panel_selection"
  fi
  # The parentheses matter: EXCEPT and UNION ALL share precedence in Spark SQL, so an
  # unbracketed union inside a set operation would rewrite the comparison.
  cat <<SQL
  SELECT * FROM (
    SELECT cell_id, served_observation_id AS observation_id, served_value_lexeme AS value_lexeme
    FROM h11_expected_revised_csv
    WHERE scenario_id = '${scenario}' AND treatment_id = '${treatment}'
    UNION ALL
    SELECT cell_id, observation_id, value_lexeme FROM ${untouched}
    WHERE cell_id NOT IN (SELECT cell_id FROM h11_dirty)
  ) expected_rows
SQL
}

state_mismatch() {
  local treatment="$1" scenario="$2"
  cat <<SQL
(SELECT count(*) FROM (
  SELECT * FROM (
$(served_state "$treatment")
  ) served_rows
  EXCEPT
$(expected_state "$treatment" "$scenario")
) served_only) + (SELECT count(*) FROM (
$(expected_state "$treatment" "$scenario")
  EXCEPT
  SELECT * FROM (
$(served_state "$treatment")
  ) served_rows
) expected_only)
SQL
}

injection_marker() {
  local rep="$1" scenario="$2" treatment="$3" rows_sql="$4" snapshots_sql="$5" extra="$6"
  cat <<SQL
SELECT concat_ws('|', 'H11I', '${rep}', '${scenario}', '${treatment}',
  CAST(${rows_sql} AS STRING),
  CAST($(served_cells "$treatment") AS STRING),
  CAST(${snapshots_sql} AS STRING),
  CAST($(state_mismatch "$treatment" "$scenario") AS STRING),
  CAST($(propagated "$treatment") AS STRING),
  '${extra}');
SQL
}

served_cells() {
  local treatment="$1"
  case "$treatment" in
    B0) echo "(SELECT count(DISTINCT cell_id) FROM ${h11_b0_table})" ;;
    B1) echo "(SELECT count(DISTINCT cell_id) FROM ${h11_b1_table} WHERE snapshot_order = $((h11_arrivals + 1)))" ;;
    B2) echo "(SELECT count(DISTINCT cell_id) FROM ${h11_b2_table})" ;;
    B3) echo "(SELECT count(DISTINCT cell_id) FROM ${h11_b3_serving})" ;;
  esac
}

# Propagation: how many admitted revisions the serving state of a treatment returns.
propagated() {
  local treatment="$1"
  cat <<SQL
(SELECT count(*) FROM (
$(served_state "$treatment")
) served JOIN h11_dirty dirty
  ON dirty.cell_id = served.cell_id AND dirty.synthetic_observation_id = served.observation_id)
SQL
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
  echo "H11 requires a persistent catalog under ${catalog_prefix}; found ${catalog_uri}" >&2
  exit 1
fi
wait_for_catalog

mkdir -p "$raw_dir"
{
  echo "run_label=${run_label}"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "git_dirty_entries=${git_dirty}"
  echo "git_dirty_paths=$(git status --porcelain | awk '{print $2}' | head -10 | paste -sd';' -)"
  echo "hostname=$(hostname)"
  echo "host_nproc=$(nproc)"
  echo "host_mem_total_bytes=$(awk '/MemTotal/ {print $2 * 1024}' /proc/meminfo)"
  echo "host_disk_total_bytes=$(df -B1 --output=size / | tail -1 | tr -d ' ')"
  echo "host_disk_free_bytes_before=$(df -B1 --output=avail / | tail -1 | tr -d ' ')"
  echo "spark_container_nproc=$("${compose[@]}" exec -T spark nproc </dev/null | tr -d '\r')"
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
  echo "scenarios=$(IFS=';'; echo "${scenarios[*]}")"
  echo "limited_run=${limited}"
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$raw_dir/environment.txt"

for rep in $(seq 1 "$repetitions"); do
  for scenario in "${scenarios[@]}"; do
    cycle_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    set +e
    baseline_output="$(bash scripts/h11_baseline.sh . 2>&1)"
    baseline_status=$?
    set -e
    if (( baseline_status != 0 )); then
      printf '%s\n' "$baseline_output" >&2
      echo "H11 baseline rebuild failed in repetition ${rep} ${scenario}" >&2
      exit "$baseline_status"
    fi
    printf '%s|%s|%s\n' "$rep" "$scenario" \
      "$(printf '%s\n' "$baseline_output" | grep -E '^H11B_VERIFY\|' | tail -1)" \
      >> "$raw_dir/baseline-markers.txt"

    measure_phase "$rep" "$scenario" "baseline"

    views="$(h11_views "$scenario")
$(h11_expectation_views)
$(h11_csv_view h11_expected_revised_csv h11-expected-revised.csv)"

    # ---------- B0: overwrite the revised cells in place ----------
    b0_sql="${views}
$(h11_b0_merge "$(h11_arrival_source "$((h11_arrivals + 1))")" "$((h11_arrivals + 1))")
$(h11_expire "$h11_b0_table")
$(injection_marker "$rep" "$scenario" "B0" "(SELECT count(*) FROM ${h11_b0_table})" "(SELECT count(*) FROM ${h11_b0_table}.snapshots)" "")"
    run_spark_timed "B0 injection ${rep} ${scenario}" "$b0_sql"
    record_timings "$rep" "$scenario" "B0" \
      "merge_revision write" "expire_snapshots maintenance" "verify_state verification"
    printf '%s\n' "$output" | grep -E '^H11I\|' >> "$raw_dir/injection.txt"

    # ---------- B1: rewrite the whole table with one more full state ----------
    b1_sql="${views}
$(h11_b1_overwrite "$((h11_arrivals + 1))")
$(injection_marker "$rep" "$scenario" "B1" "(SELECT count(*) FROM ${h11_b1_table})" "(SELECT count(*) FROM ${h11_b1_table}.snapshots)" "")"
    run_spark_timed "B1 injection ${rep} ${scenario}" "$b1_sql"
    record_timings "$rep" "$scenario" "B1" \
      "insert_overwrite_all_states write" "verify_state verification"
    printf '%s\n' "$output" | grep -E '^H11I\|' >> "$raw_dir/injection.txt"

    # ---------- B2: recompute the single-source selection and rewrite it ----------
    b2_sql="${views}
$(h11_b2_overwrite)
$(h11_expire "$h11_b2_table")
$(injection_marker "$rep" "$scenario" "B2" "(SELECT count(*) FROM ${h11_b2_table})" "(SELECT count(*) FROM ${h11_b2_table}.snapshots)" "")"
    run_spark_timed "B2 injection ${rep} ${scenario}" "$b2_sql"
    record_timings "$rep" "$scenario" "B2" \
      "insert_overwrite_selection write" "expire_snapshots maintenance" "verify_state verification"
    printf '%s\n' "$output" | grep -E '^H11I\|' >> "$raw_dir/injection.txt"

    # ---------- B3: append the vintage and recompute only the dirty cells ----------
    b3_sql="${views}
$(h11_b3_insert "$((h11_arrivals + 1))")
$(h11_b3_merge "stored.cell_id IN (SELECT DISTINCT cell_id FROM h11_dirty)" "$((h11_arrivals + 1))")
$(h11_expire "$h11_b3_store")
$(h11_expire "$h11_b3_serving")
$(injection_marker "$rep" "$scenario" "B3" "(SELECT count(*) FROM ${h11_b3_store})" "(SELECT count(*) FROM ${h11_b3_serving}.snapshots)" "store_snapshots=")"
    run_spark_timed "B3 injection ${rep} ${scenario}" "$b3_sql"
    record_timings "$rep" "$scenario" "B3" \
      "insert_store_rows write" "merge_serving_dirty_cells write" \
      "expire_snapshots_store maintenance" "expire_snapshots_serving maintenance" \
      "verify_state verification"
    printf '%s\n' "$output" | grep -E '^H11I\|' >> "$raw_dir/injection.txt"

    measure_phase "$rep" "$scenario" "after_revision"

    # ---------- recall every panel and synthetic observation ----------
    run_spark "b1 snapshots ${rep} ${scenario}" \
      "SELECT concat('H11SNAP|', CAST(snapshot_id AS STRING)) FROM ${h11_b1_table}.snapshots ORDER BY committed_at, snapshot_id;"
    snapshot_ids=()
    while read -r line; do
      snapshot_ids+=("${line#H11SNAP|}")
    done < <(printf '%s\n' "$output" | grep -E '^H11SNAP\|')
    if (( ${#snapshot_ids[@]} != h11_arrivals + 1 )); then
      echo "H11 expected $((h11_arrivals + 1)) B1 snapshots in repetition ${rep} ${scenario}, found ${#snapshot_ids[@]}" >&2
      exit 1
    fi
    previous_snapshot="${snapshot_ids[$((h11_arrivals - 1))]}"

    recall_sql="${views}
CREATE OR REPLACE TEMPORARY VIEW h11_requests AS
SELECT observation_id, cell_id, vintage_id, value_lexeme, 'official' AS request_kind FROM h11_panel_csv
UNION ALL
SELECT observation_id, cell_id, vintage_id, value_lexeme, 'synthetic' AS request_kind
FROM h11_payload_csv WHERE scenario_id = '${scenario}';
SELECT concat_ws('|', 'H11R', '${rep}', '${scenario}', 'B0', request_kind,
  CAST(count(*) AS STRING), CAST(sum(addressable) AS STRING), CAST(sum(exact) AS STRING))
FROM (
  SELECT r.request_kind,
    CASE WHEN c.observation_id IS NOT NULL THEN 1 ELSE 0 END AS addressable,
    CASE WHEN c.observation_id IS NOT NULL AND c.value_lexeme = r.value_lexeme THEN 1 ELSE 0 END AS exact
  FROM h11_requests r LEFT JOIN ${h11_b0_table} c ON c.observation_id = r.observation_id
) b0 GROUP BY request_kind;
SELECT concat_ws('|', 'H11R', '${rep}', '${scenario}', 'B1', request_kind,
  CAST(count(*) AS STRING), CAST(sum(addressable) AS STRING), CAST(sum(exact) AS STRING))
FROM (
  SELECT r.request_kind,
    CASE WHEN s.observation_id IS NOT NULL THEN 1 ELSE 0 END AS addressable,
    CASE WHEN s.observation_id IS NOT NULL AND s.value_lexeme = r.value_lexeme THEN 1 ELSE 0 END AS exact
  FROM h11_requests r LEFT JOIN (
    SELECT DISTINCT observation_id, value_lexeme FROM ${h11_b1_table}
  ) s ON s.observation_id = r.observation_id
) b1 GROUP BY request_kind;
SELECT concat_ws('|', 'H11R', '${rep}', '${scenario}', 'B2', request_kind,
  CAST(count(*) AS STRING), CAST(sum(addressable) AS STRING), CAST(sum(exact) AS STRING))
FROM (
  SELECT r.request_kind,
    CASE WHEN c.observation_id IS NOT NULL THEN 1 ELSE 0 END AS addressable,
    CASE WHEN c.observation_id IS NOT NULL AND c.value_lexeme = r.value_lexeme THEN 1 ELSE 0 END AS exact
  FROM h11_requests r LEFT JOIN ${h11_b2_table} c ON c.observation_id = r.observation_id
) b2 GROUP BY request_kind;
SELECT concat_ws('|', 'H11R', '${rep}', '${scenario}', 'B3', request_kind,
  CAST(count(*) AS STRING), CAST(sum(addressable) AS STRING), CAST(sum(exact) AS STRING))
FROM (
  SELECT r.request_kind,
    CASE WHEN s.observation_id IS NOT NULL THEN 1 ELSE 0 END AS addressable,
    CASE WHEN s.observation_id IS NOT NULL AND s.value_lexeme = r.value_lexeme THEN 1 ELSE 0 END AS exact
  FROM h11_requests r LEFT JOIN ${h11_b3_store} s
    ON s.cell_id = r.cell_id AND s.vintage_id = r.vintage_id
) b3 GROUP BY request_kind;
SELECT concat_ws('|', 'H11V', '${rep}', '${scenario}', 'b1_previous_snapshot_rows',
  CAST((SELECT count(*) FROM ${h11_b1_table} VERSION AS OF ${previous_snapshot}) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b1_table} VERSION AS OF ${previous_snapshot}
        WHERE snapshot_order = $((h11_arrivals + 1))) AS STRING));
SELECT concat_ws('|', 'H11V', '${rep}', '${scenario}', 'b3_store_snapshots',
  CAST((SELECT count(*) FROM ${h11_b3_store}.snapshots) AS STRING),
  CAST((SELECT count(*) FROM ${h11_b3_serving}.snapshots) AS STRING));
"
    run_spark "recall ${rep} ${scenario}" "$recall_sql"
    printf '%s\n' "$output" | grep -E '^H11[RV]\|' >> "$raw_dir/recall.txt"
    printf 'H11C|%s|%s|%s|%s\n' "$rep" "$scenario" "$cycle_started" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$raw_dir/cycles.txt"
  done
done

{
  echo "host_disk_free_bytes_after=$(df -B1 --output=avail / | tail -1 | tr -d ' ')"
  echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$raw_dir/environment.txt"

echo "H11_RAW|${run_label}|${repetitions}|${#scenarios[@]}|$(wc -l < "$raw_dir/timing.txt")|$(wc -l < "$raw_dir/footprint.txt")|$(wc -l < "$raw_dir/listing.txt")|$(grep -c '^H11R|' "$raw_dir/recall.txt")"
