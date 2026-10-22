-- Aurora CDP schema, version 1.
-- Conventions: Snowflake-compatible DDL where reasonable (VARCHAR(n), TIMESTAMP, DOUBLE, BOOLEAN, BIGINT).
-- JSON payloads are stored as VARCHAR (Snowflake: VARIANT; DuckDB: parse with json_extract_* on read).
-- SCD2 tables carry valid_from / valid_to / is_current. Every mutable artefact is keyed by run_id so
-- prior generations are preserved (Amperity: immutable information model, docs/research internals §2.11).

CREATE TABLE IF NOT EXISTS schema_version (
    version      INTEGER      NOT NULL,
    applied_at   TIMESTAMP    NOT NULL,
    description  VARCHAR(255)
);

-- ---------------------------------------------------------------------------------------------
-- BRONZE: schema-on-read landing zone (Amperity: feeds -> domain tables)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze_batches (
    batch_id     VARCHAR(64)  NOT NULL,
    source       VARCHAR(128) NOT NULL,
    feed         VARCHAR(128) NOT NULL,
    file_path    VARCHAR(1024),
    load_mode    VARCHAR(16)  NOT NULL,       -- full | incremental
    rows_read    BIGINT       NOT NULL,
    rows_loaded  BIGINT       NOT NULL,       -- after exact-dedupe on row_hash
    rows_deduped BIGINT       NOT NULL,
    loaded_at    TIMESTAMP    NOT NULL
);

CREATE TABLE IF NOT EXISTS bronze_landing (
    row_hash     VARCHAR(64)  NOT NULL,       -- sha256 over the canonicalised raw row (exact dedupe key)
    source       VARCHAR(128) NOT NULL,
    feed         VARCHAR(128) NOT NULL,
    batch_id     VARCHAR(64)  NOT NULL,
    payload      VARCHAR      NOT NULL,       -- JSON document of the raw row (schema-on-read)
    ingested_at  TIMESTAMP    NOT NULL,
    is_current   BOOLEAN      NOT NULL DEFAULT TRUE  -- full loads retire prior rows of the same feed
);

-- ---------------------------------------------------------------------------------------------
-- SILVER: semantically tagged + preprocessed records (Amperity: Unified Preprocessed Raw / Unified Coalesced)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver_unified_raw (
    datasource   VARCHAR(128) NOT NULL,
    pk           VARCHAR(255) NOT NULL,
    ck           VARCHAR(255),                -- customer key (deterministic / one-to-one stitch)
    given_name   VARCHAR(255),
    surname      VARCHAR(255),
    email        VARCHAR(320),
    phone        VARCHAR(64),
    address      VARCHAR(512),
    address2     VARCHAR(255),
    city         VARCHAR(128),
    state        VARCHAR(64),
    postal       VARCHAR(32),
    country      VARCHAR(64),
    birthdate    VARCHAR(32),
    loy_id       VARCHAR(255),
    fk_json      VARCHAR,                     -- {"fk-<namespace>": "value", ...}
    update_dt    TIMESTAMP,
    row_hash     VARCHAR(64)  NOT NULL,
    batch_id     VARCHAR(64)  NOT NULL,
    tagged_at    TIMESTAMP    NOT NULL
);

CREATE TABLE IF NOT EXISTS silver_unified_preprocessed (
    datasource        VARCHAR(128) NOT NULL,
    pk                VARCHAR(255) NOT NULL,
    ck                VARCHAR(255),
    given_name_norm   VARCHAR(255),
    given_name_canon  VARCHAR(255),           -- nickname-canonicalised given name
    surname_norm      VARCHAR(255),
    email_norm        VARCHAR(320),
    phone_e164        VARCHAR(32),
    phone_match       VARCHAR(16),            -- last 10 digits used for matching
    address_norm      VARCHAR(512),
    postal_norm       VARCHAR(16),
    birthdate_norm    VARCHAR(10),            -- YYYY-MM-DD
    loy_id_norm       VARCHAR(255),
    fk_json           VARCHAR,
    update_dt         TIMESTAMP,
    batch_id          VARCHAR(64)  NOT NULL,
    preprocessed_at   TIMESTAMP    NOT NULL
);

-- ---------------------------------------------------------------------------------------------
-- STITCH: diagnostics + results per run (Amperity: Stitch Blocking Keys / Stitch Scores / Unified Scores)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stitch_runs (
    run_id       VARCHAR(64)  NOT NULL,
    mode         VARCHAR(16)  NOT NULL,       -- full | incremental
    started_at   TIMESTAMP    NOT NULL,
    finished_at  TIMESTAMP,
    status       VARCHAR(16)  NOT NULL,       -- running | succeeded | failed
    config_json  VARCHAR,
    metrics_json VARCHAR
);

CREATE TABLE IF NOT EXISTS stitch_blocking_keys (
    run_id       VARCHAR(64)  NOT NULL,
    bk           VARCHAR(512) NOT NULL,
    datasource   VARCHAR(128) NOT NULL,
    pk           VARCHAR(255) NOT NULL,
    strategy     VARCHAR(64)  NOT NULL
);

CREATE TABLE IF NOT EXISTS stitch_skipped_blocks (
    run_id       VARCHAR(64)  NOT NULL,
    strategy     VARCHAR(64)  NOT NULL,
    bk           VARCHAR(512) NOT NULL,
    block_size   BIGINT       NOT NULL,
    size_limit   BIGINT       NOT NULL
);

CREATE TABLE IF NOT EXISTS stitch_blocklist_values (
    run_id       VARCHAR(64)  NOT NULL,
    semantic     VARCHAR(32)  NOT NULL,
    value        VARCHAR(512) NOT NULL,
    reason       VARCHAR(255) NOT NULL,
    distinct_count BIGINT     NOT NULL
);

CREATE TABLE IF NOT EXISTS stitch_scores (
    run_id            VARCHAR(64)  NOT NULL,
    left_datasource   VARCHAR(128) NOT NULL,
    left_pk           VARCHAR(255) NOT NULL,
    right_datasource  VARCHAR(128) NOT NULL,
    right_pk          VARCHAR(255) NOT NULL,
    score             DOUBLE       NOT NULL,  -- 0.0 .. 5.0
    match_category    VARCHAR(32)  NOT NULL,  -- hard_conflict | non_conflict | weak | moderate | high | excellent | exact
    match_type        VARCHAR(32)  NOT NULL,  -- scored | scored_transitive | trivial_duplicate | deterministic | carried
    is_edge           BOOLEAN      NOT NULL,  -- score >= threshold and not a hard conflict
    features_json     VARCHAR
);

CREATE TABLE IF NOT EXISTS stitch_clusters (
    run_id         VARCHAR(64)  NOT NULL,
    datasource     VARCHAR(128) NOT NULL,
    pk             VARCHAR(255) NOT NULL,
    cluster_id     VARCHAR(64)  NOT NULL,     -- temporary id for this run
    aurora_id      VARCHAR(36)  NOT NULL,     -- stable id after assignment
    component_id   VARCHAR(64),               -- connected component before conflict splitting
    supersized_id  VARCHAR(64),               -- set when the component was partitioned by BFS
    is_supersized  BOOLEAN      NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------------------------------------------
-- IDENTITY: stable ID ledger (SCD2) and change feeds (Amperity: Unified Changes PKs / Clusters)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS id_ledger (
    aurora_id    VARCHAR(36)  NOT NULL,
    datasource   VARCHAR(128) NOT NULL,
    pk           VARCHAR(255) NOT NULL,
    run_id       VARCHAR(64)  NOT NULL,       -- run that opened this row
    valid_from   TIMESTAMP    NOT NULL,
    valid_to     TIMESTAMP,
    is_current   BOOLEAN      NOT NULL
);

CREATE TABLE IF NOT EXISTS unified_changes_pk (
    run_id          VARCHAR(64)  NOT NULL,
    datasource      VARCHAR(128) NOT NULL,
    pk              VARCHAR(255) NOT NULL,
    aurora_id       VARCHAR(36),
    aurora_id_prev  VARCHAR(36),
    change_type     VARCHAR(16)  NOT NULL,    -- added | deleted | updated
    changed_at      TIMESTAMP    NOT NULL
);

CREATE TABLE IF NOT EXISTS unified_changes_clusters (
    run_id          VARCHAR(64)  NOT NULL,
    aurora_id       VARCHAR(36)  NOT NULL,
    aurora_id_prev  VARCHAR(36),
    change_type     VARCHAR(16)  NOT NULL,    -- added | deleted | updated
    pk_count        BIGINT       NOT NULL,
    pk_count_prev   BIGINT,
    changed_at      TIMESTAMP    NOT NULL
);

CREATE TABLE IF NOT EXISTS jitter_reports (
    run_id            VARCHAR(64) NOT NULL,
    prev_run_id       VARCHAR(64),
    records_total     BIGINT      NOT NULL,
    records_compared  BIGINT      NOT NULL,   -- records present in both runs
    records_changed   BIGINT      NOT NULL,   -- records whose aurora_id changed
    jitter_pct        DOUBLE      NOT NULL,
    ids_minted        BIGINT      NOT NULL,
    ids_retired       BIGINT      NOT NULL,
    alert             BOOLEAN     NOT NULL,
    created_at        TIMESTAMP   NOT NULL
);

-- ---------------------------------------------------------------------------------------------
-- GOLD: survivorship output and activation surfaces (Amperity: Merged Customers / Customer 360)
-- ---------------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold_merged_customers (
    aurora_id         VARCHAR(36)  NOT NULL,
    given_name        VARCHAR(255),
    surname           VARCHAR(255),
    email             VARCHAR(320),
    phone             VARCHAR(64),
    address           VARCHAR(512),
    address2          VARCHAR(255),
    city              VARCHAR(128),
    state             VARCHAR(64),
    postal            VARCHAR(32),
    country           VARCHAR(64),
    birthdate         VARCHAR(32),
    provenance_json   VARCHAR,                 -- {"email": {"datasource": "...", "pk": "...", "rule": "..."}}
    record_count      BIGINT       NOT NULL,
    datasources       VARCHAR(1024),           -- comma-separated list
    row_hash          VARCHAR(64)  NOT NULL,
    run_id            VARCHAR(64)  NOT NULL,
    valid_from        TIMESTAMP    NOT NULL,
    valid_to          TIMESTAMP,
    is_current        BOOLEAN      NOT NULL
);

CREATE TABLE IF NOT EXISTS gold_profile_events (
    event_id      VARCHAR(64)  NOT NULL,
    aurora_id     VARCHAR(36),
    datasource    VARCHAR(128) NOT NULL,
    fk_namespace  VARCHAR(128) NOT NULL,
    fk_value      VARCHAR(255) NOT NULL,
    event_type    VARCHAR(64)  NOT NULL,
    event_ts      TIMESTAMP,
    amount        DOUBLE,
    payload       VARCHAR,
    run_id        VARCHAR(64)  NOT NULL
);

CREATE TABLE IF NOT EXISTS segments (
    segment_name     VARCHAR(128) NOT NULL,
    definition_json  VARCHAR      NOT NULL,
    created_at       TIMESTAMP    NOT NULL,
    updated_at       TIMESTAMP    NOT NULL
);

CREATE TABLE IF NOT EXISTS segment_members (
    segment_name  VARCHAR(128) NOT NULL,
    run_id        VARCHAR(64)  NOT NULL,
    aurora_id     VARCHAR(36)  NOT NULL,
    evaluated_at  TIMESTAMP    NOT NULL
);

CREATE TABLE IF NOT EXISTS destination_runs (
    destination_id VARCHAR(64)  NOT NULL,
    segment_name   VARCHAR(128) NOT NULL,
    kind           VARCHAR(32)  NOT NULL,     -- csv | webhook
    target         VARCHAR(1024),
    row_count      BIGINT       NOT NULL,
    status         VARCHAR(16)  NOT NULL,
    created_at     TIMESTAMP    NOT NULL
);

-- ---------------------------------------------------------------------------------------------
-- VIEWS (point-in-time convenience over the SCD2 / run-keyed tables)
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW unified_coalesced AS
SELECT l.aurora_id, p.*
FROM silver_unified_preprocessed p
JOIN id_ledger l
  ON l.datasource = p.datasource AND l.pk = p.pk AND l.is_current;

CREATE OR REPLACE VIEW identity_graph AS
SELECT aurora_id, datasource, COALESCE(ck, pk) AS customer_key, pk
FROM unified_coalesced;

CREATE OR REPLACE VIEW customer_360 AS
SELECT m.*,
       COALESCE(e.order_count, 0)  AS order_count,
       COALESCE(e.total_spend, 0.0) AS total_spend,
       e.last_order_ts
FROM gold_merged_customers m
LEFT JOIN (
    SELECT aurora_id,
           COUNT(*)      AS order_count,
           SUM(amount)   AS total_spend,
           MAX(event_ts) AS last_order_ts
    FROM gold_profile_events
    WHERE event_type = 'order'
    GROUP BY aurora_id
) e ON e.aurora_id = m.aurora_id
WHERE m.is_current;
