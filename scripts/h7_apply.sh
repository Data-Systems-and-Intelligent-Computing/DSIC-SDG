#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:-.}"
cd "$project_dir"

read -r expected_input expected_batches expected_final expected_overwritten expected_success expected_failure < <(
  python3 -c '
import hashlib
import json
import re

manifest = json.load(open("data/manifests/h7-b0-overwrite.json"))
if manifest["stage"] != "H7" or manifest["implementation_status"] != "implemented":
    raise SystemExit("H7 manifest is not implemented")
for item in manifest["outputs"]:
    digest = hashlib.sha256(open(item["path"], "rb").read()).hexdigest()
    if digest != item["sha256"]:
        raise SystemExit("checksum mismatch for " + item["path"])
workload = manifest["workload"]
print(
    workload["input_rows"],
    workload["vintage_batches"],
    workload["final_rows"],
    workload["overwritten_rows"],
    workload["reproduction_successes"],
    workload["reproduction_failures"],
)
'
)

compose=(docker compose --env-file infra/docker/versions.env)
"${compose[@]}" cp infra/spark/h7-b0.sql spark:/tmp/h7-b0.sql
"${compose[@]}" exec -T spark \
  /opt/spark/bin/spark-sql --silent -f /tmp/h7-b0.sql

sql="
CREATE OR REPLACE TEMPORARY VIEW h7_observations_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h6-indicator-observations.csv',
  header 'true',
  inferSchema 'false'
);
CREATE OR REPLACE TEMPORARY VIEW h7_expected_state_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h7-b0-final-state.csv',
  header 'true',
  inferSchema 'false'
);
CREATE OR REPLACE TEMPORARY VIEW h7_reproducibility_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h7-b0-reproducibility.csv',
  header 'true',
  inferSchema 'false'
);
DELETE FROM kkciv.experiments.b0_indicator_current;
"

while IFS=, read -r operation_order vintage_id _rest; do
  if [[ ! "$operation_order" =~ ^[1-9][0-9]*$ || ! "$vintage_id" =~ ^[0-9a-f]{20}$ ]]; then
    echo "invalid H7 operation row" >&2
    exit 1
  fi
  sql+="
MERGE INTO kkciv.experiments.b0_indicator_current AS current
USING (
  SELECT
    observation_id, cell_id, vintage_id, domain, indicator_key, series_key,
    observed_period, period_granularity, geo_level, geo_code, geo_name, unit,
    CAST(value_decimal AS DECIMAL(38,10)) AS value_decimal, value_lexeme,
    CAST(published_decimal_places AS INT) AS published_decimal_places,
    producer, methodology_version, source_artifact_path, source_artifact_sha256,
    source_record_id, ingestion_batch_id, transformation_run_id,
    transformation_version, trace_id, cause_family, evidence_level
  FROM h7_observations_csv
  WHERE vintage_id = '${vintage_id}'
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
  applied_order = ${operation_order},
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
  incoming.evidence_level, ${operation_order}, NULL
);
"
done < <(tail -n +2 results/processed/h7-b0-operations.csv)

sql+="
CALL kkciv.system.expire_snapshots(
  table => 'experiments.b0_indicator_current',
  older_than => current_timestamp(),
  retain_last => 1
);
SELECT concat(
  'H7_VERIFY|',
  (SELECT count(*) FROM kkciv.experiments.b0_indicator_current), '|',
  (SELECT count(DISTINCT cell_id) FROM kkciv.experiments.b0_indicator_current), '|',
  (SELECT count(*) FROM h7_reproducibility_csv WHERE result = 'current_available'), '|',
  (SELECT count(*) FROM h7_reproducibility_csv WHERE result = 'historical_overwritten'), '|',
  (SELECT count(*) FROM kkciv.experiments.b0_indicator_current.snapshots), '|',
  (SELECT count(*) FROM kkciv.experiments.b0_indicator_current.files), '|',
  (SELECT count(*) FROM (
    SELECT cell_id FROM kkciv.experiments.b0_indicator_current
    GROUP BY cell_id HAVING count(*) > 1
  ) duplicate_cells), '|',
  (SELECT count(*) FROM (
    SELECT observation_id, cell_id, vintage_id, value_lexeme,
           CAST(applied_order AS STRING) AS applied_order,
           coalesce(replaced_observation_id, '') AS replaced_observation_id
    FROM kkciv.experiments.b0_indicator_current
    EXCEPT
    SELECT observation_id, cell_id, vintage_id, value_lexeme,
           applied_order, replaced_observation_id
    FROM h7_expected_state_csv
  ) state_mismatches), '|',
  (SELECT count(*)
   FROM h7_reproducibility_csv r
   LEFT JOIN kkciv.experiments.b0_indicator_current c ON r.cell_id = c.cell_id
   WHERE
     (r.result = 'current_available' AND
       (c.observation_id IS NULL OR c.observation_id != r.requested_observation_id))
     OR
     (r.result = 'historical_overwritten' AND
       (c.observation_id IS NULL OR c.observation_id = r.requested_observation_id))
  ) audit_mismatches
);
"

output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql --silent -e "$sql" 2>&1)"
printf '%s\n' "$output"

verification="H7_VERIFY|${expected_final}|${expected_final}|${expected_success}|${expected_failure}|1|"
if ! printf '%s\n' "$output" | grep -Eq "^${verification}[1-9][0-9]*\|0\|0\|0$"; then
  echo "H7 Iceberg verification marker not found" >&2
  exit 1
fi

echo "verified H7 B0 overwrite: ${expected_input} inputs, ${expected_batches} batches, ${expected_overwritten} overwritten, ${expected_final} current rows"
