-- Oversized blocks are no longer skipped; this table records how each one was handled (QA / audit).
CREATE TABLE IF NOT EXISTS stitch_oversized_blocks (
    run_id       VARCHAR(64)  NOT NULL,
    strategy     VARCHAR(64)  NOT NULL,
    bk           VARCHAR(512) NOT NULL,
    block_size   BIGINT       NOT NULL,
    size_limit   BIGINT       NOT NULL,
    handling     VARCHAR(16)  NOT NULL,   -- full | refined
    sub_blocks   BIGINT       NOT NULL,
    pairs        BIGINT       NOT NULL
);
