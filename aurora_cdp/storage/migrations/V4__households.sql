-- Households as an owned entity (persistent household id, explicit evidence edges); see profile/households.py.
CREATE TABLE IF NOT EXISTS households (
    household_id    VARCHAR(36)  NOT NULL,
    created_run_id  VARCHAR(64)  NOT NULL,
    created_at      TIMESTAMP    NOT NULL,
    status          VARCHAR(16)  NOT NULL DEFAULT 'active'   -- active | retired
);

CREATE TABLE IF NOT EXISTS household_members (          -- SCD2: which household a customer belongs to over time
    household_id    VARCHAR(36)  NOT NULL,
    aurora_id       VARCHAR(36)  NOT NULL,
    run_id          VARCHAR(64)  NOT NULL,
    valid_from      TIMESTAMP    NOT NULL,
    valid_to        TIMESTAMP,
    is_current      BOOLEAN      NOT NULL
);

CREATE TABLE IF NOT EXISTS household_evidence (         -- why two customers are in one household
    evidence_id     VARCHAR(36)  NOT NULL,
    kind            VARCHAR(32)  NOT NULL,     -- shared_address | shared_surname_postal | shared_phone | relationship | label
    left_aurora_id  VARCHAR(36)  NOT NULL,
    right_aurora_id VARCHAR(36)  NOT NULL,
    value           VARCHAR(512),              -- the shared key / relationship kind
    weight          DOUBLE       NOT NULL,
    first_seen_run  VARCHAR(64)  NOT NULL,
    last_seen_run   VARCHAR(64)  NOT NULL,
    first_seen      TIMESTAMP    NOT NULL,
    last_seen       TIMESTAMP    NOT NULL,
    active          BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS household_relationships (    -- explicit relationships (registry, gift, account owner...)
    left_datasource  VARCHAR(128) NOT NULL,
    left_pk          VARCHAR(255) NOT NULL,
    right_datasource VARCHAR(128) NOT NULL,
    right_pk         VARCHAR(255) NOT NULL,
    kind             VARCHAR(32)  NOT NULL,
    source           VARCHAR(128),
    created_at       TIMESTAMP    NOT NULL
);

CREATE TABLE IF NOT EXISTS household_runs (
    run_id            VARCHAR(64) NOT NULL,
    stitch_run_id     VARCHAR(64) NOT NULL,
    finished_at       TIMESTAMP   NOT NULL,
    metrics_json      VARCHAR
);
