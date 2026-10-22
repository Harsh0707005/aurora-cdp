-- Operator-owned Stitch labels persisted in the workspace (survive across runs; see stitch/labels.py).
CREATE TABLE IF NOT EXISTS stitch_labels (
    label_id         VARCHAR(36)  NOT NULL,
    left_datasource  VARCHAR(128) NOT NULL,
    left_pk          VARCHAR(255) NOT NULL,
    right_datasource VARCHAR(128) NOT NULL,
    right_pk         VARCHAR(255) NOT NULL,
    label            VARCHAR(8)   NOT NULL,   -- merge | split
    created_at       TIMESTAMP    NOT NULL,
    created_by       VARCHAR(128),
    note             VARCHAR,
    active           BOOLEAN      NOT NULL DEFAULT TRUE
);
