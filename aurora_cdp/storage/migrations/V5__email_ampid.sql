-- AmpID compatibility: one external id per e-mail (Amperity "Email AmpID Assignment": many-to-many narrowed to 1:1).
CREATE TABLE IF NOT EXISTS gold_email_ampid (
    email        VARCHAR(320) NOT NULL,
    aurora_id    VARCHAR(36)  NOT NULL,     -- the single customer this e-mail resolves to
    candidates   BIGINT       NOT NULL,     -- customers that carried the e-mail (narrowed to 1)
    rule         VARCHAR(32)  NOT NULL,     -- most_records | most_recent
    run_id       VARCHAR(64)  NOT NULL,
    valid_from   TIMESTAMP    NOT NULL,
    valid_to     TIMESTAMP,
    is_current   BOOLEAN      NOT NULL
);
