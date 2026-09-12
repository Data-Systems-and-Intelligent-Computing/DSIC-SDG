-- H11 main sweep: the four treatments on the frozen province panel.
-- Schemas are identical to the H7-H9 fixture tables; only the namespace and the
-- table names differ, so the evidence fixture in kkciv.experiments is never touched.
CREATE NAMESPACE IF NOT EXISTS kkciv.sweep;

DROP TABLE IF EXISTS kkciv.sweep.b0_panel_current;
DROP TABLE IF EXISTS kkciv.sweep.b1_panel_full_snapshots;
DROP TABLE IF EXISTS kkciv.sweep.b2_panel_selected;
DROP TABLE IF EXISTS kkciv.sweep.b3_panel_observation_vintages;
DROP TABLE IF EXISTS kkciv.sweep.b3_panel_current;

CREATE TABLE kkciv.sweep.b0_panel_current (
  observation_id STRING NOT NULL,
  cell_id STRING NOT NULL,
  vintage_id STRING NOT NULL,
  domain STRING NOT NULL,
  indicator_key STRING NOT NULL,
  series_key STRING NOT NULL,
  observed_period STRING NOT NULL,
  period_granularity STRING NOT NULL,
  geo_level STRING NOT NULL,
  geo_code STRING NOT NULL,
  geo_name STRING NOT NULL,
  unit STRING NOT NULL,
  value_decimal DECIMAL(38,10) NOT NULL,
  value_lexeme STRING NOT NULL,
  published_decimal_places INT NOT NULL,
  producer STRING NOT NULL,
  methodology_version STRING NOT NULL,
  source_artifact_path STRING NOT NULL,
  source_artifact_sha256 STRING NOT NULL,
  source_record_id STRING NOT NULL,
  ingestion_batch_id STRING NOT NULL,
  transformation_run_id STRING NOT NULL,
  transformation_version STRING NOT NULL,
  trace_id STRING,
  cause_family STRING,
  evidence_level STRING,
  applied_order INT NOT NULL,
  replaced_observation_id STRING
) USING iceberg
PARTITIONED BY (domain)
TBLPROPERTIES (
  'format-version'='2',
  'write.format.default'='parquet'
);

CREATE TABLE kkciv.sweep.b1_panel_full_snapshots (
  observation_id STRING NOT NULL,
  cell_id STRING NOT NULL,
  vintage_id STRING NOT NULL,
  domain STRING NOT NULL,
  indicator_key STRING NOT NULL,
  series_key STRING NOT NULL,
  observed_period STRING NOT NULL,
  period_granularity STRING NOT NULL,
  geo_level STRING NOT NULL,
  geo_code STRING NOT NULL,
  geo_name STRING NOT NULL,
  unit STRING NOT NULL,
  value_decimal DECIMAL(38,10) NOT NULL,
  value_lexeme STRING NOT NULL,
  published_decimal_places INT NOT NULL,
  producer STRING NOT NULL,
  methodology_version STRING NOT NULL,
  source_artifact_path STRING NOT NULL,
  source_artifact_sha256 STRING NOT NULL,
  source_record_id STRING NOT NULL,
  ingestion_batch_id STRING NOT NULL,
  transformation_run_id STRING NOT NULL,
  transformation_version STRING NOT NULL,
  trace_id STRING,
  cause_family STRING,
  evidence_level STRING,
  snapshot_order INT NOT NULL,
  state_snapshot_key STRING NOT NULL,
  applied_vintage_id STRING NOT NULL
) USING iceberg
PARTITIONED BY (domain)
TBLPROPERTIES (
  'format-version'='2',
  'write.format.default'='parquet'
);

CREATE TABLE kkciv.sweep.b2_panel_selected (
  observation_id STRING NOT NULL,
  cell_id STRING NOT NULL,
  vintage_id STRING NOT NULL,
  domain STRING NOT NULL,
  indicator_key STRING NOT NULL,
  series_key STRING NOT NULL,
  observed_period STRING NOT NULL,
  period_granularity STRING NOT NULL,
  geo_level STRING NOT NULL,
  geo_code STRING NOT NULL,
  geo_name STRING NOT NULL,
  unit STRING NOT NULL,
  value_decimal DECIMAL(38,10) NOT NULL,
  value_lexeme STRING NOT NULL,
  published_decimal_places INT NOT NULL,
  producer STRING NOT NULL,
  methodology_version STRING NOT NULL,
  source_artifact_path STRING NOT NULL,
  source_artifact_sha256 STRING NOT NULL,
  source_record_id STRING NOT NULL,
  ingestion_batch_id STRING NOT NULL,
  transformation_run_id STRING NOT NULL,
  transformation_version STRING NOT NULL,
  trace_id STRING,
  cause_family STRING,
  evidence_level STRING,
  selected_source_id STRING NOT NULL,
  trust_score DECIMAL(7,6) NOT NULL,
  source_rank INT NOT NULL,
  candidate_count INT NOT NULL,
  discarded_candidate_count INT NOT NULL,
  selected_is_latest_vintage BOOLEAN NOT NULL,
  selection_contract_version STRING NOT NULL,
  selection_run_id STRING NOT NULL
) USING iceberg
PARTITIONED BY (domain)
TBLPROPERTIES (
  'format-version'='2',
  'write.format.default'='parquet'
);

CREATE TABLE kkciv.sweep.b3_panel_observation_vintages (
  observation_id STRING NOT NULL,
  cell_id STRING NOT NULL,
  vintage_id STRING NOT NULL,
  domain STRING NOT NULL,
  indicator_key STRING NOT NULL,
  series_key STRING NOT NULL,
  observed_period STRING NOT NULL,
  period_granularity STRING NOT NULL,
  geo_level STRING NOT NULL,
  geo_code STRING NOT NULL,
  geo_name STRING NOT NULL,
  unit STRING NOT NULL,
  value_decimal DECIMAL(38,10) NOT NULL,
  value_lexeme STRING NOT NULL,
  published_decimal_places INT NOT NULL,
  producer STRING NOT NULL,
  methodology_version STRING NOT NULL,
  source_artifact_path STRING NOT NULL,
  source_artifact_sha256 STRING NOT NULL,
  source_record_id STRING NOT NULL,
  ingestion_batch_id STRING NOT NULL,
  transformation_run_id STRING NOT NULL,
  transformation_version STRING NOT NULL,
  trace_id STRING,
  cause_family STRING,
  evidence_level STRING,
  source_id STRING NOT NULL,
  vintage_date DATE NOT NULL,
  vintage_retrieved_at TIMESTAMP NOT NULL,
  arrival_order INT NOT NULL
) USING iceberg
PARTITIONED BY (domain)
TBLPROPERTIES (
  'format-version'='2',
  'write.format.default'='parquet'
);

CREATE TABLE kkciv.sweep.b3_panel_current (
  observation_id STRING NOT NULL,
  cell_id STRING NOT NULL,
  vintage_id STRING NOT NULL,
  domain STRING NOT NULL,
  indicator_key STRING NOT NULL,
  series_key STRING NOT NULL,
  observed_period STRING NOT NULL,
  period_granularity STRING NOT NULL,
  geo_level STRING NOT NULL,
  geo_code STRING NOT NULL,
  geo_name STRING NOT NULL,
  unit STRING NOT NULL,
  value_decimal DECIMAL(38,10) NOT NULL,
  value_lexeme STRING NOT NULL,
  published_decimal_places INT NOT NULL,
  producer STRING NOT NULL,
  methodology_version STRING NOT NULL,
  source_artifact_path STRING NOT NULL,
  source_artifact_sha256 STRING NOT NULL,
  source_record_id STRING NOT NULL,
  ingestion_batch_id STRING NOT NULL,
  transformation_run_id STRING NOT NULL,
  transformation_version STRING NOT NULL,
  trace_id STRING,
  cause_family STRING,
  evidence_level STRING,
  source_id STRING NOT NULL,
  vintage_date DATE NOT NULL,
  vintage_retrieved_at TIMESTAMP NOT NULL,
  arrival_order INT NOT NULL,
  vintage_count INT NOT NULL,
  value_revision_count INT NOT NULL,
  recomputed_at_arrival INT NOT NULL
) USING iceberg
PARTITIONED BY (domain)
TBLPROPERTIES (
  'format-version'='2',
  'write.format.default'='parquet'
);
