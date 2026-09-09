#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:-.}"
cd "$project_dir"

read -r expected_input expected_selected expected_discarded expected_older expected_success expected_failure expected_selected_sources < <(
  python3 -c '
import csv
import hashlib
import json

manifest = json.load(open("data/manifests/h7b-b2-single-source.json"))
if (
    manifest["stage"] != "H7"
    or manifest["track"] != "B"
    or manifest["treatment_id"] != "B2"
    or manifest["implementation_status"] != "implemented"
):
    raise SystemExit("H7B manifest is not implemented")
for item in manifest["outputs"]:
    digest = hashlib.sha256(open(item["path"], "rb").read()).hexdigest()
    if digest != item["sha256"]:
        raise SystemExit("checksum mismatch for " + item["path"])
workload = manifest["workload"]
with open("results/processed/h7b-b2-selected-state.csv", newline="") as handle:
    selected_sources = {row["selected_source_id"] for row in csv.DictReader(handle)}
print(
    workload["input_rows"],
    workload["selected_rows"],
    workload["discarded_rows"],
    workload["older_selected"],
    workload["reproduction_successes"],
    workload["reproduction_failures"],
    len(selected_sources),
)
'
)

compose=(docker compose --env-file infra/docker/versions.env)
"${compose[@]}" cp infra/spark/h7b-b2.sql spark:/tmp/h7b-b2.sql
"${compose[@]}" exec -T spark \
  /opt/spark/bin/spark-sql --silent -f /tmp/h7b-b2.sql

sql="
CREATE OR REPLACE TEMPORARY VIEW h7b_selected_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h7b-b2-selected-state.csv',
  header 'true',
  inferSchema 'false'
);
CREATE OR REPLACE TEMPORARY VIEW h7b_reproducibility_csv
USING csv
OPTIONS (
  path '/home/iceberg/results/processed/h7b-b2-reproducibility.csv',
  header 'true',
  inferSchema 'false'
);
INSERT OVERWRITE kkciv.experiments.b2_indicator_selected
SELECT
  observation_id, cell_id, vintage_id, domain, indicator_key, series_key,
  observed_period, period_granularity, geo_level, geo_code, geo_name, unit,
  CAST(value_decimal AS DECIMAL(38,10)), value_lexeme,
  CAST(published_decimal_places AS INT), producer, methodology_version,
  source_artifact_path, source_artifact_sha256, source_record_id,
  ingestion_batch_id, transformation_run_id, transformation_version,
  trace_id, cause_family, evidence_level, selected_source_id,
  CAST(trust_score AS DECIMAL(7,6)), CAST(source_rank AS INT),
  CAST(candidate_count AS INT), CAST(discarded_candidate_count AS INT),
  CAST(selected_is_latest_vintage AS BOOLEAN), selection_contract_version,
  selection_run_id
FROM h7b_selected_csv;
CALL kkciv.system.expire_snapshots(
  table => 'experiments.b2_indicator_selected',
  older_than => TIMESTAMP '9999-12-31 00:00:00',
  retain_last => 1
);
SELECT concat(
  'H7B_VERIFY|',
  (SELECT count(*) FROM kkciv.experiments.b2_indicator_selected), '|',
  (SELECT count(DISTINCT cell_id) FROM kkciv.experiments.b2_indicator_selected), '|',
  (SELECT count(DISTINCT selected_source_id) FROM kkciv.experiments.b2_indicator_selected), '|',
  (SELECT count(*) FROM kkciv.experiments.b2_indicator_selected
    WHERE selected_is_latest_vintage = false), '|',
  (SELECT count(*) FROM h7b_reproducibility_csv WHERE result = 'selected_available'), '|',
  (SELECT count(*) FROM h7b_reproducibility_csv
    WHERE result = 'discarded_by_source_selection'), '|',
  (SELECT count(*) FROM kkciv.experiments.b2_indicator_selected.snapshots), '|',
  (SELECT count(*) FROM kkciv.experiments.b2_indicator_selected.files), '|',
  (SELECT count(*) FROM (
    SELECT cell_id FROM kkciv.experiments.b2_indicator_selected
    GROUP BY cell_id HAVING count(*) > 1
  ) duplicate_cells), '|',
  (SELECT count(*) FROM (
    SELECT observation_id, cell_id, vintage_id, value_lexeme,
           selected_source_id, CAST(trust_score AS STRING) AS trust_score,
           CAST(source_rank AS STRING) AS source_rank,
           CAST(selected_is_latest_vintage AS STRING) AS selected_is_latest_vintage
    FROM kkciv.experiments.b2_indicator_selected
    EXCEPT
    SELECT observation_id, cell_id, vintage_id, value_lexeme,
           selected_source_id, trust_score, source_rank, selected_is_latest_vintage
    FROM h7b_selected_csv
  ) state_mismatches), '|',
  (SELECT count(*)
   FROM h7b_reproducibility_csv r
   LEFT JOIN kkciv.experiments.b2_indicator_selected s ON r.cell_id = s.cell_id
   WHERE
     (r.result = 'selected_available' AND
       (s.observation_id IS NULL OR s.observation_id != r.requested_observation_id))
     OR
     (r.result = 'discarded_by_source_selection' AND
       (s.observation_id IS NULL OR s.observation_id = r.requested_observation_id))
  )
);
"

set +e
output="$("${compose[@]}" exec -T spark /opt/spark/bin/spark-sql --silent -e "$sql" 2>&1)"
spark_status=$?
set -e
printf '%s\n' "$output"
if (( spark_status != 0 )); then
  echo "H7B Spark SQL execution failed with status ${spark_status}" >&2
  exit "$spark_status"
fi

verification="H7B_VERIFY|${expected_selected}|${expected_selected}|${expected_selected_sources}|${expected_older}|${expected_success}|${expected_failure}|1|"
if ! printf '%s\n' "$output" | grep -Eq "^${verification}[1-9][0-9]*\|0\|0\|0$"; then
  echo "H7B Iceberg verification marker not found" >&2
  exit 1
fi

echo "verified H7B B2 selection: ${expected_input} candidates, ${expected_selected} selected, ${expected_discarded} discarded"
