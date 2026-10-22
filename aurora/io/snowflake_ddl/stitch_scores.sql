-- Aurora CDP :: Stitch_Scores (Snowflake)
-- Every scored candidate pair, including pairs that did NOT become edges (non-merge diagnosis).
CREATE TABLE IF NOT EXISTS STITCH_SCORES (
  RID_L NUMBER(19,0), RID_R NUMBER(19,0),
  DATASOURCE_L VARCHAR NOT NULL, PK_L VARCHAR NOT NULL,
  DATASOURCE_R VARCHAR NOT NULL, PK_R VARCHAR NOT NULL,
  STRATEGIES      ARRAY                 COMMENT 'blocking strategies that produced the pair',
  EMAIL_EXACT FLOAT, EMAIL_SIM FLOAT, PHONE_EXACT FLOAT, PHONE_PREFIX FLOAT, GIVEN_JW FLOAT, SURNAME_JW FLOAT,
  NAME_EXACT FLOAT, NICKNAME_MATCH FLOAT, POSTAL_EQ FLOAT, HOUSE_EQ FLOAT, STREET_SIM FLOAT, DOB_EQ FLOAT,
  DOB_NEAR FLOAT, FK_MATCH FLOAT, NAME_CONFLICT FLOAT, DOB_CONFLICT FLOAT,
  RAW_SCORE       FLOAT                 COMMENT 'linear score z = b + w.x (or logistic decision value)',
  CATEGORY        NUMBER(1,0)           COMMENT '0 non,1 weak,2 moderate,3 high,4 excellent,5 exact',
  SCORE           FLOAT                 COMMENT 'continuous 0.0-5.0, comparable across the range',
  MATCH_CATEGORY  VARCHAR, MATCH_TYPE VARCHAR COMMENT 'scored | deterministic | hard_conflict',
  JOB_ID          VARCHAR NOT NULL
) CLUSTER BY (JOB_ID, DATASOURCE_L) COMMENT = 'All pairwise scores for a run';
