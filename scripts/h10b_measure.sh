#!/usr/bin/env bash
# H10 track B: physically inject one frozen revision scenario into every treatment,
# time the statements each treatment needs, and measure the bytes that revision adds.
#
# Run this on the stack host with a clean working tree and a persistent catalog.
set -euo pipefail

project_dir="${1:-.}"
run_label="${2:?usage: h10b_measure.sh PROJECT_DIR RUN_LABEL}"
cd "$project_dir"

contract="contracts/h10b-injected-revision-physical.json"
raw_dir="results/raw/h10b/${run_label}"
if [[ -e "$raw_dir" ]]; then
  echo "raw run directory ${raw_dir} already exists; measurements are never overwritten" >&2
  exit 1
fi
git_dirty="$(git status --porcelain | wc -l | tr -d ' ')"
results_dir="/home/iceberg/results/processed"

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
for scenario in sorted(contract["scenarios"], key=lambda row: row["physical_order"]):
    print(scenario["scenario_id"])
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

b0_table="$(printf '%s\n' "${treatment_tables[@]}" | awk '$1 == "B0" {print $2}')"
b1_table="$(printf '%s\n' "${treatment_tables[@]}" | awk '$1 == "B1" {print $2}')"
b2_table="$(printf '%s\n' "${treatment_tables[@]}" | awk '$1 == "B2" {print $2}')"
b3_store="$(printf '%s\n' "${treatment_tables[@]}" | awk '$1 == "B3" && $2 ~ /observation_vintages$/ {print $2}')"
b3_serving="$(printf '%s\n' "${treatment_tables[@]}" | awk '$1 == "B3" && $2 ~ /indicator_current$/ {print $2}')"

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
    echo "H10B Spark SQL ${label} failed with status ${spark_status}" >&2
    exit "$spark_status"
  fi
}

# Same session, but the CLI keeps its "Time taken" lines so each statement can be timed
# without the JVM start-up of a fresh session.
run_spark_timed() {
  local label="$1"
  local sql="$2"
  set +e
  output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql -e "$sql" </dev/null 2>&1)"
  spark_status=$?
  set -e
  if (( spark_status != 0 )); then
    printf '%s\n' "$output" >&2
    echo "H10B Spark SQL ${label} failed with status ${spark_status}" >&2
    exit "$spark_status"
  fi
  timings=()
  while read -r seconds; do
    timings+=("$seconds")
  done < <(printf '%s\n' "$output" | sed -nE 's/^Time taken: ([0-9.]+) seconds.*$/\1/p')
}

record_timings() {
  local rep="$1" scenario="$2" treatment="$3"
  shift 3
  local labels=("$@")
  if (( ${#timings[@]} != ${#labels[@]} )); then
    echo "H10B ${treatment} produced ${#timings[@]} statement timings for ${#labels[@]} statements" >&2
    exit 1
  fi
  local index=0
  for entry in "${labels[@]}"; do
    printf 'H10BT|%s|%s|%s|%s|%s|%s|%s\n' \
      "$rep" "$scenario" "$treatment" "$((index + 1))" "${entry%% *}" "${entry##* }" "${timings[$index]}" \
      >> "$raw_dir/timing.txt"
    index=$((index + 1))
  done
}

table_location() {
  local table="$1"
  run_spark "location ${table}" \
    "SELECT concat('H10BLOC|', file) FROM (SELECT file FROM ${table}.metadata_log_entries LIMIT 1) entry;"
  printf '%s\n' "$output" | grep -E '^H10BLOC\|' | head -1 | cut -d'|' -f2 | sed -E 's#/metadata/[^/]+$##'
}

list_location() {
  local location="$1"
  local bucket_path="${location#s3://}"
  "${compose[@]}" exec -T minio sh -c \
    "mc alias set h10b http://localhost:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc ls --recursive --json h10b/${bucket_path}/" </dev/null \
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

measure_table() {
  local rep="$1" scenario="$2" phase="$3" treatment="$4" table="$5"
  local sql="
SELECT concat_ws('|', 'H10F', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}', 'data', file_path,
  CAST(file_size_in_bytes AS STRING), CAST(record_count AS STRING))
FROM (SELECT DISTINCT file_path, file_size_in_bytes, record_count FROM ${table}.all_data_files) files;
SELECT concat_ws('|', 'H10F', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}', 'delete', file_path,
  CAST(file_size_in_bytes AS STRING), CAST(record_count AS STRING))
FROM (SELECT DISTINCT file_path, file_size_in_bytes, record_count FROM ${table}.all_delete_files) files;
SELECT concat_ws('|', 'H10F', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}', 'manifest', path,
  CAST(length AS STRING), '')
FROM (SELECT DISTINCT path, length FROM ${table}.all_manifests) manifests;
SELECT concat_ws('|', 'H10F', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}', 'manifest_list', manifest_list, '', '')
FROM (SELECT DISTINCT manifest_list FROM ${table}.snapshots) lists;
SELECT concat_ws('|', 'H10F', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}', 'metadata_json', file, '', '')
FROM (SELECT DISTINCT file FROM ${table}.metadata_log_entries) entries;
SELECT concat_ws('|', 'H10S', '${rep}', '${scenario}', '${phase}', '${treatment}', '${table}',
  CAST((SELECT count(*) FROM ${table}.snapshots) AS STRING),
  CAST((SELECT count(*) FROM ${table}) AS STRING));
"
  run_spark "footprint ${phase} ${rep} ${table}" "$sql"
  printf '%s\n' "$output" | grep -E '^H10[FS]\|' >> "$raw_dir/footprint.txt"

  local location
  location="$(printf '%s\n' "$output" | grep -E '^H10F\|' | grep '|metadata_json|' | head -1 | cut -d'|' -f8 | sed -E 's#/metadata/[^/]+$##')"
  if [[ "$location" != s3://* ]]; then
    echo "H10B could not resolve the location of ${table}" >&2
    exit 1
  fi
  while IFS='|' read -r path size; do
    printf 'H10L|%s|%s|%s|%s|%s|%s|%s\n' "$rep" "$scenario" "$phase" "$treatment" "$table" "$path" "$size" \
      >> "$raw_dir/listing.txt"
  done < <(list_location "$location")
}

csv_view() {
  printf "CREATE OR REPLACE TEMPORARY VIEW %s USING csv OPTIONS (path '%s/%s', header 'true', inferSchema 'false');\n" \
    "$1" "$results_dir" "$2"
}

observation_projection() {
  cat <<'SQL'
  observation_id, cell_id, vintage_id, domain, indicator_key, series_key,
  observed_period, period_granularity, geo_level, geo_code, geo_name, unit,
  CAST(value_decimal AS DECIMAL(38,10)) AS value_decimal, value_lexeme,
  CAST(published_decimal_places AS INT) AS published_decimal_places,
  producer, methodology_version, source_artifact_path, source_artifact_sha256,
  source_record_id, ingestion_batch_id, transformation_run_id,
  transformation_version, trace_id, cause_family, evidence_level
SQL
}

# Resolve the latest stored vintage of every cell the filter selects; identical to H9A.
resolution_sql() {
  local cell_filter="$1"
  cat <<SQL
SELECT
  observation_id, cell_id, vintage_id, domain, indicator_key, series_key,
  observed_period, period_granularity, geo_level, geo_code, geo_name, unit,
  value_decimal, value_lexeme, published_decimal_places, producer,
  methodology_version, source_artifact_path, source_artifact_sha256,
  source_record_id, ingestion_batch_id, transformation_run_id,
  transformation_version, trace_id, cause_family, evidence_level,
  source_id, vintage_date, vintage_retrieved_at, arrival_order,
  CAST(vintage_count AS INT) AS vintage_count,
  CAST(value_revision_count AS INT) AS value_revision_count
FROM (
  SELECT revised.*,
    row_number() OVER (
      PARTITION BY cell_id
      ORDER BY vintage_date DESC, vintage_retrieved_at DESC, vintage_id DESC
    ) AS resolution_rank,
    count(*) OVER (PARTITION BY cell_id) AS vintage_count,
    sum(value_revised) OVER (PARTITION BY cell_id) AS value_revision_count
  FROM (
    SELECT stored.*,
      CAST(coalesce(
        lag(value_decimal) OVER (
          PARTITION BY cell_id ORDER BY vintage_date, vintage_retrieved_at, vintage_id
        ) != value_decimal,
        false
      ) AS INT) AS value_revised
    FROM ${b3_store} stored
    WHERE ${cell_filter}
  ) revised
) ranked
WHERE resolution_rank = 1
SQL
}

expected_mismatch_sql() {
  local table="$1" scenario="$2" treatment="$3"
  cat <<SQL
(SELECT count(*) FROM (
  SELECT cell_id, observation_id, vintage_id, value_lexeme FROM ${table}
  EXCEPT
  SELECT cell_id, observation_id, vintage_id, value_lexeme FROM h10b_expected
  WHERE scenario_id = '${scenario}' AND treatment_id = '${treatment}'
) served_only) + (SELECT count(*) FROM (
  SELECT cell_id, observation_id, vintage_id, value_lexeme FROM h10b_expected
  WHERE scenario_id = '${scenario}' AND treatment_id = '${treatment}'
  EXCEPT
  SELECT cell_id, observation_id, vintage_id, value_lexeme FROM ${table}
) expected_only)
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
  echo "H10B requires a persistent catalog under ${catalog_prefix}; found ${catalog_uri}" >&2
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
  echo "host_disk_total_bytes=$(df -B1 --output=size / | tail -1 | tr -d ' ')"
  echo "host_disk_free_bytes_before=$(df -B1 --output=avail / | tail -1 | tr -d ' ')"
  echo "spark_container_nproc=$("${compose[@]}" exec -T spark nproc </dev/null | tr -d '\r')"
  echo "spark_driver_memory=$("${compose[@]}" exec -T spark printenv SPARK_DRIVER_MEMORY </dev/null | tr -d '\r')"
  echo "catalog_uri=${catalog_uri}"
  echo "spark_defaults_sha256=$(sha256sum infra/spark/spark-defaults.conf | cut -d' ' -f1)"
  echo "versions_env_sha256=$(sha256sum infra/docker/versions.env | cut -d' ' -f1)"
  echo "compose_sha256=$(sha256sum docker-compose.yml | cut -d' ' -f1)"
  for service in minio iceberg-rest spark; do
    echo "image_${service}=$(docker inspect --format '{{.Image}}' "$("${compose[@]}" ps -q "$service")")"
  done
  echo "repetitions=${repetitions}"
  echo "scenarios=$(IFS=';'; echo "${scenarios[*]}")"
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$raw_dir/environment.txt"

# Approved cleanup (h10b_orphan_cleanup): drop the objects the 2026-09-09 run left behind
# when the catalog lost its table registrations, so later listings only hold current objects.
cleanup_stamp="$(date -u +'%Y-%m-%d %H:%M:%S')"
for entry in "${treatment_tables[@]}"; do
  table="${entry#* }"
  short_table="${table#kkciv.}"
  location="$(table_location "$table")"
  if [[ "$location" != s3://* ]]; then
    echo "H10B could not resolve the location of ${table} before cleanup" >&2
    exit 1
  fi
  objects=0
  bytes=0
  while IFS='|' read -r _path size; do
    objects=$((objects + 1))
    bytes=$((bytes + size))
  done < <(list_location "$location")
  printf 'H10BC|%s|before|%s|%s\n' "$table" "$objects" "$bytes" >> "$raw_dir/orphan-cleanup.txt"

  run_spark "remove orphan files ${table}" "
CALL kkciv.system.remove_orphan_files(
  table => '${short_table}',
  older_than => TIMESTAMP '${cleanup_stamp}'
);"
  printf '%s\n' "$output" | grep -E '^s3://' | while read -r removed; do
    printf 'H10BO|%s|%s\n' "$table" "$removed" >> "$raw_dir/orphan-cleanup.txt"
  done

  objects=0
  bytes=0
  while IFS='|' read -r _path size; do
    objects=$((objects + 1))
    bytes=$((bytes + size))
  done < <(list_location "$location")
  printf 'H10BC|%s|after|%s|%s\n' "$table" "$objects" "$bytes" >> "$raw_dir/orphan-cleanup.txt"
done
echo "orphan_cleanup_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$raw_dir/environment.txt"

for rep in $(seq 1 "$repetitions"); do
  for scenario in "${scenarios[@]}"; do
    purge_sql=""
    for entry in "${treatment_tables[@]}"; do
      purge_sql+="DROP TABLE IF EXISTS ${entry#* } PURGE;"
    done
    run_spark "purge ${rep} ${scenario}" "$purge_sql"

    for entry in "${apply_scripts[@]}"; do
      treatment="${entry%% *}"
      script="${entry#* }"
      set +e
      apply_output="$(bash "$script" . 2>&1)"
      apply_status=$?
      set -e
      if (( apply_status != 0 )); then
        printf '%s\n' "$apply_output" >&2
        echo "H10B ${treatment} baseline apply failed in repetition ${rep} ${scenario}" >&2
        exit "$apply_status"
      fi
      marker="$(printf '%s\n' "$apply_output" | grep -E '^H[0-9A-Z]+_VERIFY\|' | tail -1)"
      echo "${rep}|${scenario}|${treatment}|${marker}" >> "$raw_dir/apply-markers.txt"
    done

    for entry in "${treatment_tables[@]}"; do
      measure_table "$rep" "$scenario" "baseline" "${entry%% *}" "${entry#* }"
    done

    # ---------- B0: overwrite the revised cells in place ----------
    b0_sql="$(csv_view h10b_payload h10b-synthetic-observations.csv)
$(csv_view h10b_expected h10b-expected-state.csv)
MERGE INTO ${b0_table} AS current
USING (
  SELECT
$(observation_projection)
  FROM h10b_payload WHERE scenario_id = '${scenario}'
) AS incoming
ON current.cell_id = incoming.cell_id
WHEN MATCHED THEN UPDATE SET
  observation_id = incoming.observation_id,
  vintage_id = incoming.vintage_id,
  domain = incoming.domain,
  indicator_key = incoming.indicator_key,
  series_key = incoming.series_key,
  observed_period = incoming.observed_period,
  period_granularity = incoming.period_granularity,
  geo_level = incoming.geo_level,
  geo_code = incoming.geo_code,
  geo_name = incoming.geo_name,
  unit = incoming.unit,
  value_decimal = incoming.value_decimal,
  value_lexeme = incoming.value_lexeme,
  published_decimal_places = incoming.published_decimal_places,
  producer = incoming.producer,
  methodology_version = incoming.methodology_version,
  source_artifact_path = incoming.source_artifact_path,
  source_artifact_sha256 = incoming.source_artifact_sha256,
  source_record_id = incoming.source_record_id,
  ingestion_batch_id = incoming.ingestion_batch_id,
  transformation_run_id = incoming.transformation_run_id,
  transformation_version = incoming.transformation_version,
  trace_id = incoming.trace_id,
  cause_family = incoming.cause_family,
  evidence_level = incoming.evidence_level,
  applied_order = 4,
  replaced_observation_id = current.observation_id
WHEN NOT MATCHED THEN INSERT (
  observation_id, cell_id, vintage_id, domain, indicator_key, series_key,
  observed_period, period_granularity, geo_level, geo_code, geo_name, unit,
  value_decimal, value_lexeme, published_decimal_places, producer,
  methodology_version, source_artifact_path, source_artifact_sha256,
  source_record_id, ingestion_batch_id, transformation_run_id,
  transformation_version, trace_id, cause_family, evidence_level,
  applied_order, replaced_observation_id
) VALUES (
  incoming.observation_id, incoming.cell_id, incoming.vintage_id,
  incoming.domain, incoming.indicator_key, incoming.series_key,
  incoming.observed_period, incoming.period_granularity, incoming.geo_level,
  incoming.geo_code, incoming.geo_name, incoming.unit, incoming.value_decimal,
  incoming.value_lexeme, incoming.published_decimal_places, incoming.producer,
  incoming.methodology_version, incoming.source_artifact_path,
  incoming.source_artifact_sha256, incoming.source_record_id,
  incoming.ingestion_batch_id, incoming.transformation_run_id,
  incoming.transformation_version, incoming.trace_id, incoming.cause_family,
  incoming.evidence_level, 4, NULL
);
CALL kkciv.system.expire_snapshots(
  table => 'experiments.b0_indicator_current',
  older_than => TIMESTAMP '9999-12-31 00:00:00',
  retain_last => 1
);
SELECT concat_ws('|', 'H10BI', '${rep}', '${scenario}', 'B0',
  CAST((SELECT count(*) FROM ${b0_table}) AS STRING),
  CAST((SELECT count(DISTINCT cell_id) FROM ${b0_table}) AS STRING),
  CAST((SELECT count(*) FROM ${b0_table}.snapshots) AS STRING),
  CAST($(expected_mismatch_sql "${b0_table}" "$scenario" "B0") AS STRING), '', '');
"
    run_spark_timed "B0 injection ${rep} ${scenario}" "$b0_sql"
    record_timings "$rep" "$scenario" "B0" \
      "view_payload harness" "view_expected harness" "merge_revision write" \
      "expire_snapshots maintenance" "verify_state verification"
    printf '%s\n' "$output" | grep -E '^H10BI\|' >> "$raw_dir/injection.txt"

    # ---------- B1: write the complete next state as a fourth snapshot ----------
    b1_sql="$(csv_view h10b_b1 h10b-b1-next-state.csv)
$(csv_view h10b_expected h10b-expected-state.csv)
INSERT OVERWRITE ${b1_table}
SELECT
$(observation_projection),
  CAST(snapshot_order AS INT) AS snapshot_order, state_snapshot_key, applied_vintage_id
FROM h10b_b1 WHERE scenario_id = '${scenario}';
SELECT concat_ws('|', 'H10BI', '${rep}', '${scenario}', 'B1',
  CAST((SELECT count(*) FROM ${b1_table}) AS STRING),
  CAST((SELECT count(DISTINCT cell_id) FROM ${b1_table}) AS STRING),
  CAST((SELECT count(*) FROM ${b1_table}.snapshots) AS STRING),
  CAST($(expected_mismatch_sql "${b1_table}" "$scenario" "B1") AS STRING), '', '');
"
    run_spark_timed "B1 injection ${rep} ${scenario}" "$b1_sql"
    record_timings "$rep" "$scenario" "B1" \
      "view_next_state harness" "view_expected harness" "insert_overwrite_snapshot write" \
      "verify_state verification"
    printf '%s\n' "$output" | grep -E '^H10BI\|' >> "$raw_dir/injection.txt"

    # ---------- B2: recompute the single-source selection and rewrite it ----------
    b2_sql="$(csv_view h10b_b2 h10b-b2-next-state.csv)
$(csv_view h10b_expected h10b-expected-state.csv)
INSERT OVERWRITE ${b2_table}
SELECT
$(observation_projection),
  selected_source_id, CAST(trust_score AS DECIMAL(7,6)), CAST(source_rank AS INT),
  CAST(candidate_count AS INT), CAST(discarded_candidate_count AS INT),
  CAST(selected_is_latest_vintage AS BOOLEAN), selection_contract_version,
  selection_run_id
FROM h10b_b2 WHERE scenario_id = '${scenario}';
CALL kkciv.system.expire_snapshots(
  table => 'experiments.b2_indicator_selected',
  older_than => TIMESTAMP '9999-12-31 00:00:00',
  retain_last => 1
);
SELECT concat_ws('|', 'H10BI', '${rep}', '${scenario}', 'B2',
  CAST((SELECT count(*) FROM ${b2_table}) AS STRING),
  CAST((SELECT count(DISTINCT cell_id) FROM ${b2_table}) AS STRING),
  CAST((SELECT count(*) FROM ${b2_table}.snapshots) AS STRING),
  CAST($(expected_mismatch_sql "${b2_table}" "$scenario" "B2") AS STRING), '', '');
"
    run_spark_timed "B2 injection ${rep} ${scenario}" "$b2_sql"
    record_timings "$rep" "$scenario" "B2" \
      "view_next_state harness" "view_expected harness" "insert_overwrite_selection write" \
      "expire_snapshots maintenance" "verify_state verification"
    printf '%s\n' "$output" | grep -E '^H10BI\|' >> "$raw_dir/injection.txt"

    # ---------- B3: append the vintage and recompute only the dirty cells ----------
    b3_sql="$(csv_view h10b_payload h10b-synthetic-observations.csv)
$(csv_view h10b_dirty h10b-b3-dirty-cells.csv)
$(csv_view h10b_expected h10b-expected-state.csv)
INSERT INTO ${b3_store}
SELECT
$(observation_projection),
  source_id, CAST(vintage_date AS DATE) AS vintage_date,
  CAST(vintage_retrieved_at AS TIMESTAMP) AS vintage_retrieved_at,
  CAST(arrival_order AS INT) AS arrival_order
FROM h10b_payload WHERE scenario_id = '${scenario}';
MERGE INTO ${b3_serving} AS serving
USING (
  SELECT resolved_rows.*, CAST(4 AS INT) AS recomputed_at_arrival
  FROM (
$(resolution_sql "stored.cell_id IN (SELECT DISTINCT cell_id FROM h10b_dirty WHERE scenario_id = '${scenario}')")
  ) resolved_rows
) AS resolved
ON serving.cell_id = resolved.cell_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
CALL kkciv.system.expire_snapshots(
  table => 'experiments.b3_observation_vintages',
  older_than => TIMESTAMP '9999-12-31 00:00:00',
  retain_last => 1
);
CALL kkciv.system.expire_snapshots(
  table => 'experiments.b3_indicator_current',
  older_than => TIMESTAMP '9999-12-31 00:00:00',
  retain_last => 1
);
SELECT concat_ws('|', 'H10BI', '${rep}', '${scenario}', 'B3',
  CAST((SELECT count(*) FROM ${b3_serving}) AS STRING),
  CAST((SELECT count(DISTINCT cell_id) FROM ${b3_serving}) AS STRING),
  CAST((SELECT count(*) FROM ${b3_serving}.snapshots) AS STRING),
  CAST($(expected_mismatch_sql "${b3_serving}" "$scenario" "B3") AS STRING),
  CAST((SELECT count(*) FROM ${b3_store}) AS STRING),
  CAST((SELECT count(*) FROM ${b3_store}.snapshots) AS STRING));
"
    run_spark_timed "B3 injection ${rep} ${scenario}" "$b3_sql"
    record_timings "$rep" "$scenario" "B3" \
      "view_payload harness" "view_dirty_cells harness" "view_expected harness" \
      "insert_store_rows write" "merge_serving_dirty_cells write" \
      "expire_snapshots_store maintenance" "expire_snapshots_serving maintenance" \
      "verify_state verification"
    printf '%s\n' "$output" | grep -E '^H10BI\|' >> "$raw_dir/injection.txt"

    for entry in "${treatment_tables[@]}"; do
      measure_table "$rep" "$scenario" "after_revision" "${entry%% *}" "${entry#* }"
    done

    # ---------- recall every official and synthetic observation ----------
    run_spark "b1 snapshots ${rep} ${scenario}" \
      "SELECT concat('H10BSNAP|', CAST(snapshot_id AS STRING)) FROM ${b1_table}.snapshots ORDER BY committed_at, snapshot_id;"
    snapshot_ids=()
    while read -r line; do
      snapshot_ids+=("${line#H10BSNAP|}")
    done < <(printf '%s\n' "$output" | grep -E '^H10BSNAP\|')
    if (( ${#snapshot_ids[@]} == 0 )); then
      echo "H10B found no B1 snapshots in repetition ${rep} ${scenario}" >&2
      exit 1
    fi
    printf 'H10BSNAPCOUNT|%s|%s|%s\n' "$rep" "$scenario" "${#snapshot_ids[@]}" >> "$raw_dir/recall.txt"

    history_sql=""
    for index in "${!snapshot_ids[@]}"; do
      [[ -n "$history_sql" ]] && history_sql+=" UNION ALL "
      history_sql+="SELECT $((index + 1)) AS snapshot_order, observation_id, value_lexeme FROM ${b1_table} VERSION AS OF ${snapshot_ids[$index]}"
    done

    recall_sql="$(csv_view h10b_payload h10b-synthetic-observations.csv)
CREATE OR REPLACE TEMPORARY VIEW h10b_official USING csv OPTIONS (
  path '${results_dir}/h6-indicator-observations.csv', header 'true', inferSchema 'false');
CREATE OR REPLACE TEMPORARY VIEW h10b_requests AS
SELECT observation_id, cell_id, vintage_id, value_lexeme FROM h10b_official
UNION ALL
SELECT observation_id, cell_id, vintage_id, value_lexeme FROM h10b_payload
WHERE scenario_id = '${scenario}';
CREATE OR REPLACE TEMPORARY VIEW h10b_b1_history AS ${history_sql};
SELECT concat_ws('|', 'H10BR', '${rep}', '${scenario}', 'B0', r.observation_id,
  coalesce(c.observation_id, ''), coalesce(c.value_lexeme, ''), 'current')
FROM h10b_requests r LEFT JOIN ${b0_table} c ON c.observation_id = r.observation_id;
SELECT concat_ws('|', 'H10BR', '${rep}', '${scenario}', 'B2', r.observation_id,
  coalesce(c.observation_id, ''), coalesce(c.value_lexeme, ''), 'current')
FROM h10b_requests r LEFT JOIN ${b2_table} c ON c.observation_id = r.observation_id;
SELECT concat_ws('|', 'H10BR', '${rep}', '${scenario}', 'B3', r.observation_id,
  coalesce(s.observation_id, ''), coalesce(s.value_lexeme, ''), 'vintage_key')
FROM h10b_requests r LEFT JOIN ${b3_store} s
  ON s.cell_id = r.cell_id AND s.vintage_id = r.vintage_id;
SELECT concat_ws('|', 'H10BR', '${rep}', '${scenario}', 'B1', r.observation_id,
  coalesce(max(h.observation_id), ''), coalesce(max(h.value_lexeme), ''),
  concat('snapshot_orders=', concat_ws(';', sort_array(collect_set(CAST(h.snapshot_order AS STRING))))))
FROM h10b_requests r LEFT JOIN h10b_b1_history h ON h.observation_id = r.observation_id
GROUP BY r.observation_id;
"
    run_spark "recall ${rep} ${scenario}" "$recall_sql"
    printf '%s\n' "$output" | grep -E '^H10BR\|' >> "$raw_dir/recall.txt"
  done
done

{
  echo "host_disk_free_bytes_after=$(df -B1 --output=avail / | tail -1 | tr -d ' ')"
  echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$raw_dir/environment.txt"

echo "H10B_RAW|${run_label}|${repetitions}|${#scenarios[@]}|$(wc -l < "$raw_dir/timing.txt")|$(wc -l < "$raw_dir/footprint.txt")|$(wc -l < "$raw_dir/listing.txt")|$(grep -c '^H10BR|' "$raw_dir/recall.txt")"
