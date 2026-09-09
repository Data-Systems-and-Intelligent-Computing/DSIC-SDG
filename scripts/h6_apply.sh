#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:-.}"
cd "$project_dir"

read -r expected_vintages expected_observations expected_cells < <(
  python3 -c '
import hashlib
import json

manifest = json.load(open("data/manifests/h6-vintage-schema.json"))
for item in manifest["outputs"]:
    digest = hashlib.sha256(open(item["path"], "rb").read()).hexdigest()
    if digest != item["sha256"]:
        raise SystemExit("checksum mismatch for " + item["path"])
fixture = manifest["fixture"]
print(fixture["vintage_rows"], fixture["observation_rows"], fixture["cell_count"])
'
)

compose=(docker compose --env-file infra/docker/versions.env)
"${compose[@]}" cp infra/spark/h6-vintage-schema.sql spark:/tmp/h6-vintage-schema.sql
"${compose[@]}" exec -T spark \
  /opt/spark/bin/spark-sql --silent -f /tmp/h6-vintage-schema.sql

sql="
CREATE OR REPLACE TEMPORARY VIEW h6_vintages_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h6-release-vintages.csv',
  header 'true',
  inferSchema 'false'
);
CREATE OR REPLACE TEMPORARY VIEW h6_observations_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h6-indicator-observations.csv',
  header 'true',
  inferSchema 'false'
);
INSERT OVERWRITE kkciv.research.release_vintages
SELECT
  vintage_id, source_id, source_channel, CAST(vintage_date AS DATE),
  vintage_basis, CAST(retrieved_at AS TIMESTAMP), release_label,
  source_manifest_path, source_manifest_sha256
FROM h6_vintages_csv;
INSERT OVERWRITE kkciv.research.indicator_observations
SELECT
  observation_id, cell_id, vintage_id, domain, indicator_key, series_key,
  observed_period, period_granularity, geo_level, geo_code, geo_name, unit,
  CAST(value_decimal AS DECIMAL(38,10)), value_lexeme,
  CAST(published_decimal_places AS INT), producer, methodology_version,
  source_artifact_path, source_artifact_sha256, source_record_id,
  ingestion_batch_id, transformation_run_id, transformation_version,
  trace_id, cause_family, evidence_level
FROM h6_observations_csv;
SELECT concat(
  'H6_VERIFY|',
  (SELECT count(*) FROM kkciv.research.release_vintages), '|',
  (SELECT count(*) FROM kkciv.research.indicator_observations), '|',
  (SELECT count(DISTINCT cell_id) FROM kkciv.research.indicator_observations), '|',
  min(vintage_count), '|',
  max(vintage_count), '|',
  (SELECT count(*) FROM kkciv.research.release_vintages.files), '|',
  (SELECT count(*) FROM kkciv.research.indicator_observations.files), '|',
  (SELECT count(*) FROM kkciv.research.indicator_observations o
     LEFT ANTI JOIN kkciv.research.release_vintages v ON o.vintage_id = v.vintage_id), '|',
  (SELECT count(*) FROM kkciv.research.indicator_observations
     WHERE CAST(value_lexeme AS DECIMAL(38,10)) != value_decimal)
)
FROM (
  SELECT cell_id, count(*) AS vintage_count
  FROM kkciv.research.indicator_observations
  GROUP BY cell_id
);
"

output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql --silent -e "$sql" 2>&1)"
printf '%s\n' "$output"

verification="H6_VERIFY|${expected_vintages}|${expected_observations}|${expected_cells}|2|3|"
if ! printf '%s\n' "$output" | grep -Eq "^${verification}[1-9][0-9]*\|[1-9][0-9]*\|0\|0$"; then
  echo "H6 Iceberg verification marker not found" >&2
  exit 1
fi

echo "verified H6 Iceberg schema: ${expected_vintages} vintages, ${expected_observations} observations, ${expected_cells} cells"
