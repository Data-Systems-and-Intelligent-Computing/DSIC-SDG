#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:-.}"
cd "$project_dir"

read -r expected_input expected_arrivals expected_store expected_final expected_success expected_failure expected_asof < <(
  python3 -c '
import hashlib
import json

manifest = json.load(open("data/manifests/h9-b3-vintage-aware.json"))
if manifest["stage"] != "H9" or manifest["track"] != "A" or manifest["implementation_status"] != "implemented":
    raise SystemExit("H9A manifest is not implemented")
for item in manifest["outputs"]:
    digest = hashlib.sha256(open(item["path"], "rb").read()).hexdigest()
    if digest != item["sha256"]:
        raise SystemExit("checksum mismatch for " + item["path"])
workload = manifest["workload"]
print(
    workload["input_rows"],
    workload["arrival_batches"],
    workload["store_rows"],
    workload["final_rows"],
    workload["reproduction_successes"],
    workload["reproduction_failures"],
    workload["asof_rows"],
)
'
)

store_table="kkciv.experiments.b3_observation_vintages"
serving_table="kkciv.experiments.b3_indicator_current"
results_dir="/home/iceberg/results/processed"

csv_view() {
  printf "CREATE OR REPLACE TEMPORARY VIEW %s USING csv OPTIONS (path '%s/%s', header 'true', inferSchema 'false');\n" \
    "$1" "$results_dir" "$2"
}

# Resolve the latest stored vintage of every cell selected by the filter.
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
    FROM ${store_table} stored
    WHERE ${cell_filter}
  ) revised
) ranked
WHERE resolution_rank = 1
SQL
}

run_spark() {
  local label="$1"
  local sql="$2"
  set +e
  output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql --silent -e "$sql" </dev/null 2>&1)"
  spark_status=$?
  set -e
  printf '%s\n' "$output"
  if (( spark_status != 0 )); then
    echo "H9 Spark SQL ${label} failed with status ${spark_status}" >&2
    exit "$spark_status"
  fi
}

compose=(docker compose --env-file infra/docker/versions.env)
"${compose[@]}" cp infra/spark/h9-b3.sql spark:/tmp/h9-b3.sql
"${compose[@]}" exec -T spark \
  /opt/spark/bin/spark-sql --silent -f /tmp/h9-b3.sql </dev/null

full_mismatch_sql="
(SELECT count(*) FROM (
  SELECT observation_id, cell_id, vintage_id, value_lexeme, vintage_count, value_revision_count
  FROM ${serving_table}
  EXCEPT
  SELECT observation_id, cell_id, vintage_id, value_lexeme, vintage_count, value_revision_count
  FROM h9_full_resolution
) serving_only) + (SELECT count(*) FROM (
  SELECT observation_id, cell_id, vintage_id, value_lexeme, vintage_count, value_revision_count
  FROM h9_full_resolution
  EXCEPT
  SELECT observation_id, cell_id, vintage_id, value_lexeme, vintage_count, value_revision_count
  FROM ${serving_table}
) full_only)"

arrivals=0
while IFS=, read -r arrival_order vintage_id _source _date _input dirty_cells recomputed_cells _untouched _full _inserted _changed _value _provenance _unchanged store_after serving_after _rest; do
  if [[ ! "$arrival_order" =~ ^[1-9][0-9]*$ || ! "$vintage_id" =~ ^[0-9a-f]{20}$ ]]; then
    echo "invalid H9 arrival catalog row" >&2
    exit 1
  fi
  sql="$(csv_view h9_store_csv h9-b3-observation-store.csv)
$(csv_view h9_impact_csv h9-b3-impact.csv)
INSERT INTO ${store_table}
SELECT
  observation_id, cell_id, vintage_id, domain, indicator_key, series_key,
  observed_period, period_granularity, geo_level, geo_code, geo_name, unit,
  CAST(value_decimal AS DECIMAL(38,10)) AS value_decimal, value_lexeme,
  CAST(published_decimal_places AS INT) AS published_decimal_places,
  producer, methodology_version, source_artifact_path, source_artifact_sha256,
  source_record_id, ingestion_batch_id, transformation_run_id,
  transformation_version, trace_id, cause_family, evidence_level,
  source_id, CAST(vintage_date AS DATE) AS vintage_date,
  CAST(vintage_retrieved_at AS TIMESTAMP) AS vintage_retrieved_at,
  CAST(arrival_order AS INT) AS arrival_order
FROM h9_store_csv
WHERE arrival_order = '${arrival_order}' AND vintage_id = '${vintage_id}';
MERGE INTO ${serving_table} AS serving
USING (
  SELECT resolved_rows.*, CAST(${arrival_order} AS INT) AS recomputed_at_arrival
  FROM (
$(resolution_sql "stored.cell_id IN (SELECT DISTINCT cell_id FROM h9_impact_csv WHERE arrival_order = '${arrival_order}')")
  ) resolved_rows
) AS resolved
ON serving.cell_id = resolved.cell_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
CREATE OR REPLACE TEMPORARY VIEW h9_full_resolution AS
$(resolution_sql "true");
SELECT concat(
  'H9_ARRIVAL|${arrival_order}|',
  (SELECT count(*) FROM ${store_table}), '|',
  (SELECT count(*) FROM ${serving_table}), '|',
  (SELECT count(*) FROM ${serving_table} WHERE recomputed_at_arrival = ${arrival_order}), '|',
  (SELECT count(DISTINCT cell_id) FROM h9_impact_csv WHERE arrival_order = '${arrival_order}'), '|',
  ${full_mismatch_sql}
);
"
  run_spark "arrival ${arrival_order}" "$sql"
  expected_marker="H9_ARRIVAL|${arrival_order}|${store_after}|${serving_after}|${recomputed_cells}|${dirty_cells}|0"
  if ! printf '%s\n' "$output" | grep -Fxq "$expected_marker"; then
    echo "H9 arrival marker ${expected_marker} not found" >&2
    exit 1
  fi
  arrivals=$((arrivals + 1))
done < <(tail -n +2 results/processed/h9-b3-arrival-catalog.csv)

if (( arrivals != expected_arrivals )); then
  echo "H9 expected ${expected_arrivals} arrivals, applied ${arrivals}" >&2
  exit 1
fi

verify_sql="
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
$(csv_view h9_expected_current_csv h9-b3-current-state.csv)
$(csv_view h9_reproducibility_csv h9-b3-reproducibility.csv)
$(csv_view h9_b1_states_csv h8-b1-snapshot-states.csv)
CREATE OR REPLACE TEMPORARY VIEW h9_full_resolution AS
$(resolution_sql "true");
CREATE OR REPLACE TEMPORARY VIEW h9_vintage_rank AS
SELECT vintage_id,
  dense_rank() OVER (ORDER BY vintage_date, vintage_retrieved_at, vintage_id) AS vintage_rank
FROM (SELECT DISTINCT vintage_id, vintage_date, vintage_retrieved_at FROM ${store_table}) vintages;
CREATE OR REPLACE TEMPORARY VIEW h9_asof_actual AS
SELECT asof_order, observation_id, cell_id, vintage_id, value_lexeme
FROM (
  SELECT bound.vintage_rank AS asof_order, stored.observation_id, stored.cell_id,
    stored.vintage_id, stored.value_lexeme,
    row_number() OVER (
      PARTITION BY bound.vintage_rank, stored.cell_id ORDER BY eligible.vintage_rank DESC
    ) AS asof_rank
  FROM h9_vintage_rank bound
  CROSS JOIN ${store_table} stored
  JOIN h9_vintage_rank eligible
    ON stored.vintage_id = eligible.vintage_id AND eligible.vintage_rank <= bound.vintage_rank
) candidates
WHERE asof_rank = 1;
SELECT concat(
  'H9_VERIFY|',
  (SELECT count(*) FROM ${store_table}), '|',
  (SELECT count(*) FROM (SELECT DISTINCT cell_id, vintage_id FROM ${store_table}) keys), '|',
  (SELECT count(*) FROM ${serving_table}), '|',
  (SELECT count(DISTINCT cell_id) FROM ${serving_table}), '|',
  (SELECT count(*) FROM h9_reproducibility_csv r
   JOIN ${store_table} s
     ON r.cell_id = s.cell_id AND r.requested_vintage_id = s.vintage_id
     AND r.requested_observation_id = s.observation_id
     AND r.requested_value_lexeme = s.value_lexeme), '|',
  (SELECT count(*) FROM h9_reproducibility_csv r
   LEFT ANTI JOIN ${store_table} s
     ON r.cell_id = s.cell_id AND r.requested_vintage_id = s.vintage_id
     AND r.requested_observation_id = s.observation_id
     AND r.requested_value_lexeme = s.value_lexeme), '|',
  (SELECT count(*) FROM ${store_table}.snapshots), '|',
  (SELECT count(*) FROM ${serving_table}.snapshots), '|',
  (SELECT count(*) FROM (
    SELECT observation_id, cell_id, vintage_id, value_lexeme,
      CAST(vintage_count AS STRING), CAST(value_revision_count AS STRING),
      CAST(recomputed_at_arrival AS STRING)
    FROM ${serving_table}
    EXCEPT
    SELECT observation_id, cell_id, vintage_id, value_lexeme,
      vintage_count, value_revision_count, recomputed_at_arrival
    FROM h9_expected_current_csv
  ) serving_mismatches) + (SELECT count(*) FROM (
    SELECT observation_id, cell_id, vintage_id, value_lexeme,
      vintage_count, value_revision_count, recomputed_at_arrival
    FROM h9_expected_current_csv
    EXCEPT
    SELECT observation_id, cell_id, vintage_id, value_lexeme,
      CAST(vintage_count AS STRING), CAST(value_revision_count AS STRING),
      CAST(recomputed_at_arrival AS STRING)
    FROM ${serving_table}
  ) expected_only), '|',
  ${full_mismatch_sql}, '|',
  (SELECT count(*) FROM h9_asof_actual), '|',
  (SELECT count(*) FROM (
    SELECT CAST(asof_order AS STRING), observation_id, cell_id, vintage_id, value_lexeme
    FROM h9_asof_actual
    EXCEPT
    SELECT snapshot_order, observation_id, cell_id, vintage_id, value_lexeme
    FROM h9_b1_states_csv
  ) asof_only) + (SELECT count(*) FROM (
    SELECT snapshot_order, observation_id, cell_id, vintage_id, value_lexeme
    FROM h9_b1_states_csv
    EXCEPT
    SELECT CAST(asof_order AS STRING), observation_id, cell_id, vintage_id, value_lexeme
    FROM h9_asof_actual
  ) b1_only)
);
"
run_spark "verification" "$verify_sql"

verification="H9_VERIFY|${expected_store}|${expected_store}|${expected_final}|${expected_final}|${expected_success}|${expected_failure}|1|1|0|0|${expected_asof}|0"
if ! printf '%s\n' "$output" | grep -Fxq "$verification"; then
  echo "H9 Iceberg verification marker not found" >&2
  exit 1
fi

echo "verified H9A B3 vintage-aware store: ${expected_input} inputs, ${expected_arrivals} arrivals, ${expected_store} append-only rows, ${expected_success}/${expected_input} vintage-key reads after snapshot expiry"
