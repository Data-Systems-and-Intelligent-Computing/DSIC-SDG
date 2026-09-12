#!/usr/bin/env bash
# Shared SQL for the H11 main sweep: the baseline loader and the measurement driver
# must issue exactly the same treatment mechanisms, so both source this library.
#
# Every treatment keeps the mechanism frozen at H7-H9:
#   B0 overwrites the cell in place with MERGE;
#   B1 stores one complete state per release and rewrites the table with INSERT OVERWRITE;
#   B2 recomputes the whole single-source selection with the frozen H6B score;
#   B3 appends the vintage and recomputes only the cells the lineage marks dirty.

h11_results_dir="/home/iceberg/results/processed"
h11_b0_table="kkciv.sweep.b0_panel_current"
h11_b1_table="kkciv.sweep.b1_panel_full_snapshots"
h11_b2_table="kkciv.sweep.b2_panel_selected"
h11_b3_store="kkciv.sweep.b3_panel_observation_vintages"
h11_b3_serving="kkciv.sweep.b3_panel_current"

h11_load_manifest() {
  local manifest="${1:-data/manifests/h11-main-sweep-payload.json}"
  read -r h11_arrivals h11_selection_contract h11_selection_run < <(python3 -c '
import hashlib
import json

manifest = json.load(open("'"$manifest"'"))
if manifest["stage"] != "H11" or manifest["payload_status"] != "prepared":
    raise SystemExit("H11 payload manifest is not prepared")
for item in manifest["outputs"]:
    digest = hashlib.sha256(open(item["path"], "rb").read()).hexdigest()
    if digest != item["sha256"]:
        raise SystemExit("checksum mismatch for " + item["path"])
print(manifest["arrivals"], manifest["selection"]["contract_version"], manifest["selection"]["run_id"])
')
}

h11_csv_view() {
  printf "CREATE OR REPLACE TEMPORARY VIEW %s USING csv OPTIONS (path '%s/%s', header 'true', inferSchema 'false');\n" \
    "$1" "$h11_results_dir" "$2"
}

h11_observation_projection() {
  local prefix="${1:-}"
  cat <<SQL
  ${prefix}observation_id, ${prefix}cell_id, ${prefix}vintage_id, ${prefix}domain,
  ${prefix}indicator_key, ${prefix}series_key, ${prefix}observed_period,
  ${prefix}period_granularity, ${prefix}geo_level, ${prefix}geo_code, ${prefix}geo_name,
  ${prefix}unit, CAST(${prefix}value_decimal AS DECIMAL(38,10)) AS value_decimal,
  ${prefix}value_lexeme, CAST(${prefix}published_decimal_places AS INT) AS published_decimal_places,
  ${prefix}producer, ${prefix}methodology_version, ${prefix}source_artifact_path,
  ${prefix}source_artifact_sha256, ${prefix}source_record_id, ${prefix}ingestion_batch_id,
  ${prefix}transformation_run_id, ${prefix}transformation_version, ${prefix}trace_id,
  ${prefix}cause_family, ${prefix}evidence_level
SQL
}

h11_observation_columns() {
  cat <<'SQL'
  observation_id, cell_id, vintage_id, domain, indicator_key, series_key,
  observed_period, period_granularity, geo_level, geo_code, geo_name, unit,
  value_decimal, value_lexeme, published_decimal_places, producer,
  methodology_version, source_artifact_path, source_artifact_sha256,
  source_record_id, ingestion_batch_id, transformation_run_id,
  transformation_version, trace_id, cause_family, evidence_level
SQL
}

# The staging views. Without a scenario the payload stays out, which is the state
# every repetition starts from; with a scenario the payload joins as the fifth arrival.
h11_views() {
  local scenario="${1:-}"
  h11_csv_view h11_panel_csv h11-panel-observations.csv
  h11_csv_view h11_vintages_csv h11-panel-vintages.csv
  h11_csv_view h11_b1_keys_csv h11-b1-state-catalog.csv
  h11_csv_view h11_scores_csv h6b-source-trust-scores.csv
  h11_csv_view h11_edges_csv h11-panel-impact-edges.csv
  h11_csv_view h11_payload_csv h11-sweep-synthetic-observations.csv
  h11_csv_view h11_synthetic_vintages_csv h11-sweep-vintages.csv
  h11_csv_view h11_dirty_csv h11-b3-dirty-cells.csv
  cat <<SQL
CREATE OR REPLACE TEMPORARY VIEW h11_vintages AS
SELECT vintage_id, source_id, CAST(vintage_date AS DATE) AS vintage_date,
  CAST(retrieved_at AS TIMESTAMP) AS vintage_retrieved_at,
  CAST(arrival_order AS INT) AS arrival_order
FROM h11_vintages_csv;
CREATE OR REPLACE TEMPORARY VIEW h11_scores AS
SELECT source_id, CAST(trust_score AS DECIMAL(7,6)) AS trust_score, CAST(rank AS INT) AS rank
FROM h11_scores_csv;
CREATE OR REPLACE TEMPORARY VIEW h11_panel AS
SELECT
$(h11_observation_projection "panel."),
  vintage.source_id AS scoring_source_id, vintage.source_id AS source_id,
  vintage.vintage_date, vintage.vintage_retrieved_at, vintage.arrival_order
FROM h11_panel_csv panel
JOIN h11_vintages vintage ON vintage.vintage_id = panel.vintage_id;
SQL
  if [[ -z "$scenario" ]]; then
    cat <<SQL
CREATE OR REPLACE TEMPORARY VIEW h11_candidates AS SELECT * FROM h11_panel;
CREATE OR REPLACE TEMPORARY VIEW h11_b1_keys AS
SELECT CAST(snapshot_order AS INT) AS snapshot_order, state_snapshot_key, applied_vintage_id
FROM h11_b1_keys_csv;
SQL
  else
    cat <<SQL
CREATE OR REPLACE TEMPORARY VIEW h11_candidates AS
SELECT * FROM h11_panel
UNION ALL
SELECT
$(h11_observation_projection "payload."),
  payload.revised_source_id AS scoring_source_id,
  payload.source_id AS source_id,
  CAST(payload.vintage_date AS DATE) AS vintage_date,
  CAST(payload.vintage_retrieved_at AS TIMESTAMP) AS vintage_retrieved_at,
  CAST(payload.arrival_order AS INT) AS arrival_order
FROM h11_payload_csv payload
WHERE payload.scenario_id = '${scenario}';
CREATE OR REPLACE TEMPORARY VIEW h11_b1_keys AS
SELECT CAST(snapshot_order AS INT) AS snapshot_order, state_snapshot_key, applied_vintage_id
FROM h11_b1_keys_csv
UNION ALL
SELECT CAST(snapshot_order AS INT) AS snapshot_order, state_snapshot_key,
  vintage_id AS applied_vintage_id
FROM h11_synthetic_vintages_csv
WHERE scenario_id = '${scenario}';
CREATE OR REPLACE TEMPORARY VIEW h11_dirty AS
SELECT dirty.cell_id, dirty.synthetic_observation_id, dirty.lineage_edge_id
FROM h11_dirty_csv dirty
WHERE dirty.scenario_id = '${scenario}';
SQL
  fi
}

# Independent expectations for the cells a scenario does not revise: the panel state
# every treatment must still serve. They never read the statement under measurement.
h11_expectation_views() {
  cat <<SQL
CREATE OR REPLACE TEMPORARY VIEW h11_panel_latest AS
SELECT cell_id, observation_id, value_lexeme FROM (
  SELECT cell_id, observation_id, value_lexeme,
    row_number() OVER (PARTITION BY cell_id ORDER BY arrival_order DESC) AS resolution_rank
  FROM h11_panel
) resolved WHERE resolution_rank = 1;
CREATE OR REPLACE TEMPORARY VIEW h11_panel_selection AS
SELECT cell_id, observation_id, value_lexeme FROM (
  SELECT panel.cell_id, panel.observation_id, panel.value_lexeme,
    row_number() OVER (
      PARTITION BY panel.cell_id
      ORDER BY score.trust_score DESC, panel.vintage_date DESC,
               panel.scoring_source_id ASC, panel.observation_id ASC
    ) AS selection_rank
  FROM h11_panel panel
  JOIN h11_scores score ON score.source_id = panel.scoring_source_id
) selected WHERE selection_rank = 1;
SQL
}

# B0: one MERGE per arrival, exactly the frozen H7 statement.
h11_b0_merge() {
  local source_sql="$1" applied_order="$2"
  cat <<SQL
MERGE INTO ${h11_b0_table} AS current
USING (
${source_sql}
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
  applied_order = ${applied_order},
  replaced_observation_id = current.observation_id
WHEN NOT MATCHED THEN INSERT (
$(h11_observation_columns),
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
  incoming.evidence_level, ${applied_order}, NULL
);
SQL
}

h11_arrival_source() {
  local arrival="$1"
  cat <<SQL
  SELECT
$(h11_observation_columns)
  FROM h11_candidates WHERE arrival_order = ${arrival}
SQL
}

# B1: write every state up to the given arrival. States are resolved from the staging
# view because Iceberg cannot overwrite a table from a select on that same table.
h11_b1_overwrite() {
  local upto="$1"
  cat <<SQL
INSERT OVERWRITE ${h11_b1_table}
SELECT
$(h11_observation_projection "state."),
  CAST(state.snapshot_order AS INT) AS snapshot_order,
  keys.state_snapshot_key, keys.applied_vintage_id
FROM (
  SELECT candidate.*, orders.snapshot_order,
    row_number() OVER (
      PARTITION BY orders.snapshot_order, candidate.cell_id
      ORDER BY candidate.arrival_order DESC
    ) AS resolution_rank
  FROM h11_candidates candidate
  JOIN (SELECT explode(sequence(1, ${upto})) AS snapshot_order) orders
    ON candidate.arrival_order <= orders.snapshot_order
) state
JOIN h11_b1_keys keys ON keys.snapshot_order = state.snapshot_order
WHERE state.resolution_rank = 1;
SQL
}

# B2: recompute the whole selection. The score reads registry facts only, never a value.
h11_b2_overwrite() {
  cat <<SQL
INSERT OVERWRITE ${h11_b2_table}
SELECT
$(h11_observation_projection "selection."),
  selection.scoring_source_id AS selected_source_id,
  selection.trust_score,
  selection.source_rank,
  CAST(selection.candidate_count AS INT) AS candidate_count,
  CAST(selection.candidate_count - 1 AS INT) AS discarded_candidate_count,
  selection.arrival_order = selection.latest_arrival AS selected_is_latest_vintage,
  '${h11_selection_contract}' AS selection_contract_version,
  '${h11_selection_run}' AS selection_run_id
FROM (
  SELECT candidate.*, score.trust_score, score.rank AS source_rank,
    count(*) OVER (PARTITION BY candidate.cell_id) AS candidate_count,
    max(candidate.arrival_order) OVER (PARTITION BY candidate.cell_id) AS latest_arrival,
    row_number() OVER (
      PARTITION BY candidate.cell_id
      ORDER BY score.trust_score DESC, candidate.vintage_date DESC,
               candidate.scoring_source_id ASC, candidate.observation_id ASC
    ) AS selection_rank
  FROM h11_candidates candidate
  JOIN h11_scores score ON score.source_id = candidate.scoring_source_id
) selection
WHERE selection.selection_rank = 1;
SQL
}

# B3 store: append the arriving vintage, never overwrite an earlier one.
h11_b3_insert() {
  local arrival="$1"
  cat <<SQL
INSERT INTO ${h11_b3_store}
SELECT
$(h11_observation_columns),
  source_id, vintage_date, vintage_retrieved_at, arrival_order
FROM h11_candidates WHERE arrival_order = ${arrival};
SQL
}

# Resolve the latest stored vintage of every cell the filter selects; identical to H9A.
h11_resolution() {
  local cell_filter="$1"
  cat <<SQL
SELECT
$(h11_observation_columns),
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
    FROM ${h11_b3_store} stored
    WHERE ${cell_filter}
  ) revised
) ranked
WHERE resolution_rank = 1
SQL
}

# B3 serving: recompute only the cells the lineage edges mark dirty.
h11_b3_merge() {
  local cell_filter="$1" arrival="$2"
  cat <<SQL
MERGE INTO ${h11_b3_serving} AS serving
USING (
  SELECT resolved_rows.*, CAST(${arrival} AS INT) AS recomputed_at_arrival
  FROM (
$(h11_resolution "$cell_filter")
  ) resolved_rows
) AS resolved
ON serving.cell_id = resolved.cell_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
SQL
}

h11_expire() {
  local table="$1"
  cat <<SQL
CALL kkciv.system.expire_snapshots(
  table => '${table#kkciv.}',
  older_than => TIMESTAMP '9999-12-31 00:00:00',
  retain_last => 1
);
SQL
}
