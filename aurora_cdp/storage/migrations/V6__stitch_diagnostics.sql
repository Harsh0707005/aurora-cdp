-- V6: Stitch diagnostic chain (dupe-group id, hierarchical cluster ids, per-tier partitions), Unified Scores
--     (pairwise scores within clusters incl. transitive pairs) and the persisted manual blocklist table.
ALTER TABLE stitch_clusters ADD COLUMN IF NOT EXISTS dupe_group_id VARCHAR(64);      -- trivial-dupe group (NULL = singleton group)
ALTER TABLE stitch_clusters ADD COLUMN IF NOT EXISTS hier_cluster_id VARCHAR(255);   -- cluster_id.tier2.tier3…: a prefix selects a lower-confidence tier

CREATE TABLE IF NOT EXISTS stitch_cluster_tiers (      -- hierarchy of nested clusterings, one row per record per tier
    run_id          VARCHAR(64)  NOT NULL,
    datasource      VARCHAR(128) NOT NULL,
    pk              VARCHAR(255) NOT NULL,
    tier            INTEGER      NOT NULL,              -- 1 = the match threshold (coarsest), higher = stronger floors
    min_score       DOUBLE       NOT NULL,              -- score floor of the tier
    tier_cluster_id VARCHAR(64)  NOT NULL
);

CREATE TABLE IF NOT EXISTS unified_scores (             -- [AMP: Unified Scores] pairwise scores within clusters
    run_id            VARCHAR(64)  NOT NULL,
    aurora_id         VARCHAR(36)  NOT NULL,
    left_datasource   VARCHAR(128) NOT NULL,
    left_pk           VARCHAR(255) NOT NULL,
    right_datasource  VARCHAR(128) NOT NULL,
    right_pk          VARCHAR(255) NOT NULL,
    score             DOUBLE,                           -- direct score, or the cluster's weakest direct edge for transitive pairs
    match_category    VARCHAR(32),
    match_type        VARCHAR(32)  NOT NULL             -- scored | deterministic | trivial_duplicate | carried | label_merge | scored_transitive
);

CREATE TABLE IF NOT EXISTS blocklist_values_manual (    -- [AMP: BlocklistValues] operator-maintained, survives runs
    semantic    VARCHAR(32)  NOT NULL,                  -- email | phone | address | given_name | surname
    value       VARCHAR(512) NOT NULL,
    created_at  TIMESTAMP    NOT NULL,
    created_by  VARCHAR(128),
    note        VARCHAR,
    PRIMARY KEY (semantic, value)
);
