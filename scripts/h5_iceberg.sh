#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:-.}"
cd "$project_dir"

read -r expected_rows expected_traces < <(
  python3 -c '
import json
manifest = json.load(open("data/manifests/h5-gate1.json"))
outputs = {item["path"]: item for item in manifest["outputs"]}
print(
    outputs["results/processed/h5-revision-traces.csv"]["rows"],
    manifest["gate_g1"]["criterion_3_total_frozen_traces"],
)
'
)

compose=(docker compose --env-file infra/docker/versions.env)
sql="
CREATE NAMESPACE IF NOT EXISTS kkciv.gate1;
CREATE OR REPLACE TEMPORARY VIEW h5_revision_trace_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h5-revision-traces.csv',
  header 'true',
  inferSchema 'false'
);
CREATE TABLE IF NOT EXISTS kkciv.gate1.h5_revision_trace (
  trace_id STRING,
  event_id STRING,
  trace_type STRING,
  domain STRING,
  indicator_key STRING,
  series_key STRING,
  observed_period STRING,
  geo_level STRING,
  geo_code STRING,
  geo_name STRING,
  unit STRING,
  cause_family STRING,
  evidence_level STRING,
  vintage_order STRING,
  source_id STRING,
  release_date STRING,
  value STRING,
  producer STRING,
  methodology_version STRING,
  source_record_id STRING,
  evidence_note STRING
) USING iceberg
TBLPROPERTIES ('format-version'='2');
INSERT OVERWRITE kkciv.gate1.h5_revision_trace
SELECT
  trace_id, event_id, trace_type, domain, indicator_key, series_key,
  observed_period, geo_level, geo_code, geo_name, unit, cause_family,
  evidence_level, vintage_order, source_id, release_date, value, producer,
  methodology_version, source_record_id, evidence_note
FROM h5_revision_trace_csv;
SELECT concat(
  'H5_VERIFY|',
  count(*), '|',
  count(DISTINCT trace_id), '|',
  min(CAST(vintage_order AS INT)), '|',
  max(CAST(vintage_order AS INT)), '|',
  (SELECT count(*) FROM kkciv.gate1.h5_revision_trace.files)
) FROM kkciv.gate1.h5_revision_trace;
"

output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql --silent -e "$sql" 2>&1)"
printf '%s\n' "$output"

verification="H5_VERIFY|${expected_rows}|${expected_traces}|1|3|"
if ! printf '%s\n' "$output" | grep -Eq "^${verification}[1-9][0-9]*$"; then
  echo "Iceberg verification marker not found: ${verification}<positive data-file count>" >&2
  exit 1
fi

echo "verified Iceberg write-read: ${expected_rows} rows, ${expected_traces} traces"

