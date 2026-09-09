CREATE NAMESPACE IF NOT EXISTS kkciv.experiments;

CREATE TABLE IF NOT EXISTS kkciv.experiments.b0_indicator_current (
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
