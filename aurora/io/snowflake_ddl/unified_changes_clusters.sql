-- Aurora CDP :: Unified_Changes_Clusters (Snowflake) — cluster-level CDC, append-only across runs.
CREATE TABLE IF NOT EXISTS UNIFIED_CHANGES_CLUSTERS (
  CURRENT_ID    VARCHAR        COMMENT 'aurora_id after this run (NULL when deleted)',
  PREVIOUS_ID   VARCHAR        COMMENT 'aurora_id before this run (NULL when added)',
  CHANGE_TYPE   VARCHAR NOT NULL COMMENT 'added|deleted|merged|recognized|split|split_merged',
  OVERLAP       NUMBER(19,0)   COMMENT 'shared (datasource,pk) count with the predecessor',
  NEW_SIZE      NUMBER(19,0), PREVIOUS_SIZE NUMBER(19,0),
  FRAGMENTS     NUMBER(10,0)   COMMENT 'other new clusters fed by the same predecessor',
  ABSORBED      NUMBER(10,0)   COMMENT 'other predecessors absorbed by this cluster',
  JOB_ID        VARCHAR NOT NULL, TS TIMESTAMP_TZ NOT NULL,
  LINEAGE       VARCHAR        COMMENT 'lineage:<job_id>:<id> pointer into LINEAGE'
) CLUSTER BY (JOB_ID) COMMENT = 'Per-run cluster change log (jitter)';
