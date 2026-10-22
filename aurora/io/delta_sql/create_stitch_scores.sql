-- Aurora CDP :: Delta Lake (spark.sql) — Stitch_Scores. Largest table; partition by job_id if you keep history.
CREATE TABLE IF NOT EXISTS stitch_scores (
  rid_l BIGINT, rid_r BIGINT, datasource_l STRING, pk_l STRING, datasource_r STRING, pk_r STRING,
  strategies ARRAY<STRING>,
  email_exact FLOAT, email_sim FLOAT, phone_exact FLOAT, phone_prefix FLOAT, given_jw FLOAT, surname_jw FLOAT,
  name_exact FLOAT, nickname_match FLOAT, postal_eq FLOAT, house_eq FLOAT, street_sim FLOAT, dob_eq FLOAT,
  dob_near FLOAT, fk_match FLOAT, name_conflict FLOAT, given_conflict FLOAT, dob_conflict FLOAT,
  raw_score DOUBLE, category INT, score DOUBLE, match_category STRING, match_type STRING, job_id STRING NOT NULL
) USING DELTA LOCATION 'data/lake/Stitch_Scores'
TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true');
-- OPTIMIZE stitch_scores ZORDER BY (datasource_l, pk_l);
