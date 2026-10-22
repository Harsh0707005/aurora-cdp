-- Aurora CDP :: Delta Lake (spark.sql) — Unified tables.
-- Paths are relative to storage.lake_root (default data/lake). Partitioning: the lake is rewritten per run,
-- so we recommend NO partitioning for the Unified tables at <10M rows; above that partition by DATASOURCE and
-- Z-ORDER BY (aurora_id) after each run (OPTIMIZE ... ZORDER BY (aurora_id)).
CREATE TABLE IF NOT EXISTS unified_preprocessed_raw USING DELTA LOCATION 'data/lake/Unified_Preprocessed_Raw' AS
SELECT * FROM delta.`data/lake/Unified_Preprocessed_Raw` WHERE 1 = 0;

CREATE TABLE IF NOT EXISTS unified_coalesced (
  datasource STRING NOT NULL, pk STRING NOT NULL, rid BIGINT,
  aurora_id STRING NOT NULL, cluster_id BIGINT NOT NULL, component_id BIGINT,
  is_supersized BOOLEAN, supersized_id BIGINT, rep_ds STRING, rep_pk STRING, has_blv BOOLEAN,
  given_name STRING, surname STRING, full_name STRING, email STRING, phone STRING, address STRING,
  city STRING, state STRING, postal STRING, country STRING, birthdate STRING, loyalty_id STRING,
  gender STRING, updated_at STRING, truth_id STRING,
  email_std STRING, email_canon STRING, phone_std STRING, given_std STRING, surname_std STRING,
  given_nick STRING, street_std STRING, house_no STRING, postal_std STRING, dob_std STRING,
  job_id STRING NOT NULL
) USING DELTA LOCATION 'data/lake/Unified_Coalesced'
TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true', 'delta.logRetentionDuration' = 'interval 30 days');

CREATE TABLE IF NOT EXISTS unified_customer (
  datasource STRING NOT NULL, pk STRING NOT NULL, aurora_id STRING NOT NULL, cluster_id BIGINT NOT NULL,
  truth_id STRING, job_id STRING NOT NULL,
  given_name STRING, surname STRING, full_name STRING, email STRING, phone STRING, address STRING,
  city STRING, state STRING, postal STRING, country STRING, birthdate STRING, loyalty_id STRING,
  gender STRING, updated_at STRING,
  email_std STRING, email_canon STRING, phone_std STRING, given_std STRING, surname_std STRING,
  given_nick STRING, street_std STRING, house_no STRING, postal_std STRING, dob_std STRING,
  is_supersized BOOLEAN, has_blv BOOLEAN
) USING DELTA LOCATION 'data/lake/Unified_Customer';

CREATE TABLE IF NOT EXISTS merged_customers (
  aurora_id STRING NOT NULL, rep_ds STRING, rep_pk STRING,
  given_name STRING, surname STRING, full_name STRING, email STRING, phone STRING, address STRING,
  city STRING, state STRING, postal STRING, country STRING, birthdate STRING, loyalty_id STRING,
  gender STRING, updated_at STRING,
  email_std STRING, email_canon STRING, phone_std STRING, given_std STRING, surname_std STRING,
  given_nick STRING, street_std STRING, house_no STRING, postal_std STRING, dob_std STRING,
  record_count BIGINT, sources ARRAY<STRING>
) USING DELTA LOCATION 'data/lake/Merged_Customers';

CREATE TABLE IF NOT EXISTS customer360 (
  aurora_id STRING NOT NULL, rep_ds STRING, rep_pk STRING,
  given_name STRING, surname STRING, full_name STRING, email STRING, phone STRING, address STRING,
  city STRING, state STRING, postal STRING, country STRING, birthdate STRING, loyalty_id STRING,
  gender STRING, updated_at STRING,
  email_std STRING, email_canon STRING, phone_std STRING, given_std STRING, surname_std STRING,
  given_nick STRING, street_std STRING, house_no STRING, postal_std STRING, dob_std STRING,
  record_count BIGINT, sources ARRAY<STRING>, first_seen STRING, last_seen STRING,
  loyalty_ids ARRAY<STRING>, emails ARRAY<STRING>, phones ARRAY<STRING>, is_supersized BOOLEAN, has_blv BOOLEAN
) USING DELTA LOCATION 'data/lake/Customer360';
