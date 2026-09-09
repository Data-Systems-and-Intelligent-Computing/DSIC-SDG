#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:-.}"
cd "$project_dir"

read -r expected_input expected_batches expected_snapshots expected_snapshot_rows expected_final expected_success expected_failure < <(
  python3 -c '
import hashlib
import json

manifest = json.load(open("data/manifests/h8-b1-full-snapshot.json"))
if manifest["stage"] != "H8" or manifest["track"] != "A" or manifest["implementation_status"] != "implemented":
    raise SystemExit("H8A manifest is not implemented")
for item in manifest["outputs"]:
    digest = hashlib.sha256(open(item["path"], "rb").read()).hexdigest()
    if digest != item["sha256"]:
        raise SystemExit("checksum mismatch for " + item["path"])
workload = manifest["workload"]
print(
    workload["input_rows"],
    workload["vintage_batches"],
    workload["snapshot_count"],
    workload["logical_full_copy_rows"],
    workload["final_rows"],
    workload["reproduction_successes"],
    workload["reproduction_failures"],
)
'
)

compose=(docker compose --env-file infra/docker/versions.env)
"${compose[@]}" cp infra/spark/h8-b1.sql spark:/tmp/h8-b1.sql
"${compose[@]}" exec -T spark \
  /opt/spark/bin/spark-sql --silent -f /tmp/h8-b1.sql

snapshot_ids=()
while IFS=, read -r snapshot_order _snapshot_key applied_vintage_id _rest; do
  if [[ ! "$snapshot_order" =~ ^[1-9][0-9]*$ || ! "$applied_vintage_id" =~ ^[0-9a-f]{20}$ ]]; then
    echo "invalid H8 snapshot catalog row" >&2
    exit 1
  fi
  sql="
CREATE OR REPLACE TEMPORARY VIEW h8_snapshot_states_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h8-b1-snapshot-states.csv',
  header 'true',
  inferSchema 'false'
);
INSERT OVERWRITE kkciv.experiments.b1_indicator_full_snapshots
SELECT
  observation_id, cell_id, vintage_id, domain, indicator_key, series_key,
  observed_period, period_granularity, geo_level, geo_code, geo_name, unit,
  CAST(value_decimal AS DECIMAL(38,10)) AS value_decimal, value_lexeme,
  CAST(published_decimal_places AS INT) AS published_decimal_places,
  producer, methodology_version, source_artifact_path, source_artifact_sha256,
  source_record_id, ingestion_batch_id, transformation_run_id,
  transformation_version, trace_id, cause_family, evidence_level,
  CAST(snapshot_order AS INT) AS snapshot_order, state_snapshot_key,
  applied_vintage_id
FROM h8_snapshot_states_csv
WHERE snapshot_order = '${snapshot_order}';
SELECT concat(
  'H8_WRITE|${snapshot_order}|',
  CAST((SELECT snapshot_id FROM kkciv.experiments.b1_indicator_full_snapshots.snapshots
        ORDER BY committed_at DESC, snapshot_id DESC LIMIT 1) AS STRING), '|',
  (SELECT count(*) FROM kkciv.experiments.b1_indicator_full_snapshots), '|',
  (SELECT count(DISTINCT cell_id) FROM kkciv.experiments.b1_indicator_full_snapshots), '|',
  (SELECT count(*) FROM kkciv.experiments.b1_indicator_full_snapshots.snapshots)
);
"
  set +e
  output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql --silent -e "$sql" </dev/null 2>&1)"
  spark_status=$?
  set -e
  printf '%s\n' "$output"
  if (( spark_status != 0 )); then
    echo "H8 Spark SQL write ${snapshot_order} failed with status ${spark_status}" >&2
    exit "$spark_status"
  fi
  marker="$(printf '%s\n' "$output" | grep -E "^H8_WRITE\|${snapshot_order}\|[0-9]+\|${expected_final}\|${expected_final}\|${snapshot_order}$" | tail -1 || true)"
  if [[ -z "$marker" ]]; then
    echo "H8 snapshot write marker ${snapshot_order} not found" >&2
    exit 1
  fi
  IFS='|' read -r _tag _order snapshot_id _rows _cells _count <<< "$marker"
  snapshot_ids+=("$snapshot_id")
done < <(tail -n +2 results/processed/h8-b1-snapshot-catalog.csv)

if (( ${#snapshot_ids[@]} != expected_snapshots )); then
  echo "H8 expected ${expected_snapshots} Iceberg snapshots, got ${#snapshot_ids[@]}" >&2
  exit 1
fi

history_sql=""
for index in "${!snapshot_ids[@]}"; do
  order=$((index + 1))
  snapshot_id="${snapshot_ids[$index]}"
  if [[ -n "$history_sql" ]]; then
    history_sql+=" UNION ALL "
  fi
  history_sql+="SELECT ${order} AS actual_snapshot_order, observation_id, cell_id, vintage_id, value_lexeme, snapshot_order, state_snapshot_key, applied_vintage_id FROM kkciv.experiments.b1_indicator_full_snapshots VERSION AS OF ${snapshot_id}"
done

verify_sql="
CREATE OR REPLACE TEMPORARY VIEW h8_expected_states_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h8-b1-snapshot-states.csv',
  header 'true',
  inferSchema 'false'
);
CREATE OR REPLACE TEMPORARY VIEW h8_expected_current_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h8-b1-current-state.csv',
  header 'true',
  inferSchema 'false'
);
CREATE OR REPLACE TEMPORARY VIEW h8_reproducibility_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h8-b1-reproducibility.csv',
  header 'true',
  inferSchema 'false'
);
CREATE OR REPLACE TEMPORARY VIEW h8_actual_history AS
${history_sql};
SELECT concat(
  'H8_VERIFY|',
  (SELECT count(*) FROM kkciv.experiments.b1_indicator_full_snapshots.snapshots), '|',
  (SELECT count(*) FROM h8_actual_history), '|',
  (SELECT count(*) FROM kkciv.experiments.b1_indicator_full_snapshots), '|',
  (SELECT count(DISTINCT r.requested_observation_id)
   FROM h8_reproducibility_csv r
   JOIN h8_actual_history a ON r.requested_observation_id = a.observation_id), '|',
  (SELECT count(*) FROM h8_reproducibility_csv r
   LEFT ANTI JOIN h8_actual_history a ON r.requested_observation_id = a.observation_id), '|',
  (SELECT count(*) FROM kkciv.experiments.b1_indicator_full_snapshots.snapshots), '|',
  (SELECT count(*) FROM (
    SELECT actual_snapshot_order, cell_id FROM h8_actual_history
    GROUP BY actual_snapshot_order, cell_id HAVING count(*) > 1
  ) duplicate_cells), '|',
  (SELECT count(*) FROM (
    SELECT CAST(actual_snapshot_order AS STRING), observation_id, cell_id, vintage_id,
           value_lexeme, CAST(snapshot_order AS STRING), state_snapshot_key, applied_vintage_id
    FROM h8_actual_history
    EXCEPT
    SELECT snapshot_order, observation_id, cell_id, vintage_id,
           value_lexeme, snapshot_order, state_snapshot_key, applied_vintage_id
    FROM h8_expected_states_csv
  ) state_mismatches), '|',
  (SELECT count(*) FROM (
    SELECT observation_id, cell_id, vintage_id, value_lexeme,
           CAST(snapshot_order AS STRING), state_snapshot_key, applied_vintage_id
    FROM kkciv.experiments.b1_indicator_full_snapshots
    EXCEPT
    SELECT observation_id, cell_id, vintage_id, value_lexeme,
           snapshot_order, state_snapshot_key, applied_vintage_id
    FROM h8_expected_current_csv
  ) current_mismatches), '|',
  (SELECT count(*) FROM h8_reproducibility_csv r
   LEFT ANTI JOIN h8_actual_history a
     ON r.requested_observation_id = a.observation_id
     AND array_contains(split(r.matching_snapshot_orders, ';'), CAST(a.actual_snapshot_order AS STRING)))
);
"

set +e
output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql --silent -e "$verify_sql" 2>&1)"
spark_status=$?
set -e
printf '%s\n' "$output"
if (( spark_status != 0 )); then
  echo "H8 Spark SQL verification failed with status ${spark_status}" >&2
  exit "$spark_status"
fi

verification="H8_VERIFY|${expected_snapshots}|${expected_snapshot_rows}|${expected_final}|${expected_success}|${expected_failure}|${expected_snapshots}|0|0|0|0"
if ! printf '%s\n' "$output" | grep -Fxq "$verification"; then
  echo "H8 Iceberg verification marker not found" >&2
  exit 1
fi

echo "verified H8A B1 full snapshots: ${expected_input} inputs, ${expected_batches} releases, ${expected_snapshot_rows} retained row appearances, ${expected_success}/${expected_input} historical reads"
