-- Aurora CDP :: Delta Lake (spark.sql) — CDC tables (append-only; partition by job_id).
CREATE TABLE IF NOT EXISTS unified_changes_clusters (
  current_id STRING, previous_id STRING, change_type STRING NOT NULL, overlap BIGINT,
  new_size BIGINT, previous_size BIGINT, fragments BIGINT, absorbed BIGINT,
  job_id STRING NOT NULL, ts STRING NOT NULL, lineage STRING
) USING DELTA PARTITIONED BY (job_id) LOCATION 'data/lake/Unified_Changes_Clusters';

CREATE TABLE IF NOT EXISTS unified_changes_pks (
  datasource STRING NOT NULL, pk STRING NOT NULL, current_id STRING, previous_id STRING,
  change_type STRING NOT NULL, job_id STRING NOT NULL, ts STRING NOT NULL, lineage STRING
) USING DELTA PARTITIONED BY (job_id) LOCATION 'data/lake/Unified_Changes_PKs';

CREATE TABLE IF NOT EXISTS stable_id_mapping (
  cluster_id BIGINT, aurora_id STRING NOT NULL, previous_id STRING, change_type STRING, job_id STRING NOT NULL
) USING DELTA PARTITIONED BY (job_id) LOCATION 'data/lake/Stable_Id_Mapping';

CREATE TABLE IF NOT EXISTS lineage (
  aurora_id STRING NOT NULL, datasource STRING NOT NULL, pk STRING NOT NULL,
  cluster_id BIGINT, supersized_id BIGINT, job_id STRING NOT NULL, lineage STRING
) USING DELTA PARTITIONED BY (job_id) LOCATION 'data/lake/Lineage';
