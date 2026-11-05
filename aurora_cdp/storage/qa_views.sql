-- Views applied by init_schema after every migration (CREATE OR REPLACE, so always current).

-- [AMP: Customer 360] merged PII + interaction rollups + the Customer Attributes family (customer_attributes, V7)
CREATE OR REPLACE VIEW customer_360 AS
SELECT b.*, a.* EXCLUDE (aurora_id, run_id, built_at)
FROM customer_360_base b LEFT JOIN customer_attributes a USING (aurora_id);

-- ---------------------------------------------------------------------------------------------- Stitch QA views
-- [AMP: Stitch QA tables] all over the latest succeeded run (internals §5). Read-only diagnostics; recreated on init.
CREATE OR REPLACE VIEW stitch_latest_run AS
SELECT run_id FROM stitch_runs WHERE status = 'succeeded' ORDER BY started_at DESC, run_id DESC LIMIT 1;

CREATE OR REPLACE VIEW qa_cluster_scores AS                -- pairwise scores inside clusters (direct + transitive)
SELECT u.* FROM unified_scores u WHERE u.run_id = (SELECT run_id FROM stitch_latest_run);

CREATE OR REPLACE VIEW qa_weakest_match AS                 -- the weakest direct edge holding each cluster together
SELECT aurora_id, MIN(score) AS weakest_score, COUNT(*) AS direct_edges,
       arg_min(left_datasource || '|' || left_pk || ' ~ ' || right_datasource || '|' || right_pk, score) AS weakest_pair
FROM unified_scores WHERE run_id = (SELECT run_id FROM stitch_latest_run) AND match_type <> 'scored_transitive'
GROUP BY aurora_id ORDER BY weakest_score, aurora_id;

CREATE OR REPLACE VIEW qa_split_clusters AS                -- components the conflict-aware clustering split
SELECT component_id, COUNT(DISTINCT aurora_id) AS ids, COUNT(*) AS records, string_agg(DISTINCT aurora_id, ',') AS aurora_ids
FROM stitch_clusters WHERE run_id = (SELECT run_id FROM stitch_latest_run)
GROUP BY component_id HAVING COUNT(DISTINCT aurora_id) > 1 ORDER BY records DESC;

CREATE OR REPLACE VIEW qa_cluster_size_distribution AS
SELECT CASE WHEN n = 1 THEN '1' WHEN n = 2 THEN '2' WHEN n <= 5 THEN '3-5' WHEN n <= 10 THEN '6-10' WHEN n <= 50 THEN '11-50' ELSE '50+' END AS size_bucket,
       COUNT(*) AS clusters, SUM(n) AS records
FROM (SELECT aurora_id, COUNT(*) AS n FROM stitch_clusters WHERE run_id = (SELECT run_id FROM stitch_latest_run) GROUP BY 1)
GROUP BY 1 ORDER BY MIN(n);

CREATE OR REPLACE VIEW qa_dedupe_keys_per_id AS            -- several records of one source in one id (dedupe inside a source)
SELECT aurora_id, datasource, COUNT(*) AS records, string_agg(pk, ',' ORDER BY pk) AS pks
FROM stitch_clusters WHERE run_id = (SELECT run_id FROM stitch_latest_run)
GROUP BY 1, 2 HAVING COUNT(*) > 1 ORDER BY records DESC;

CREATE OR REPLACE VIEW qa_connections_across_sources AS    -- which source pairs get stitched together, how often
SELECT a.datasource AS source_a, b.datasource AS source_b, COUNT(DISTINCT a.aurora_id) AS shared_ids
FROM stitch_clusters a JOIN stitch_clusters b ON a.run_id = b.run_id AND a.aurora_id = b.aurora_id AND a.datasource < b.datasource
WHERE a.run_id = (SELECT run_id FROM stitch_latest_run) GROUP BY 1, 2 ORDER BY shared_ids DESC;

CREATE OR REPLACE VIEW qa_source_cluster_distribution AS   -- ids by number of distinct sources
SELECT sources, COUNT(*) AS ids FROM (
  SELECT aurora_id, COUNT(DISTINCT datasource) AS sources FROM stitch_clusters WHERE run_id = (SELECT run_id FROM stitch_latest_run) GROUP BY 1)
GROUP BY 1 ORDER BY 1;

CREATE OR REPLACE VIEW qa_many_amperity_ids AS             -- one semantic value spread over several ids (missed merges / shared values)
SELECT 'email' AS semantic, p.email_norm AS value, COUNT(DISTINCT l.aurora_id) AS ids, COUNT(*) AS records
FROM silver_unified_preprocessed p JOIN id_ledger l ON l.datasource = p.datasource AND l.pk = p.pk AND l.is_current
WHERE p.email_norm IS NOT NULL GROUP BY 1, 2 HAVING COUNT(DISTINCT l.aurora_id) > 1
UNION ALL
SELECT 'phone', p.phone_match, COUNT(DISTINCT l.aurora_id), COUNT(*)
FROM silver_unified_preprocessed p JOIN id_ledger l ON l.datasource = p.datasource AND l.pk = p.pk AND l.is_current
WHERE p.phone_match IS NOT NULL GROUP BY 1, 2 HAVING COUNT(DISTINCT l.aurora_id) > 1
ORDER BY ids DESC, records DESC;

CREATE OR REPLACE VIEW qa_many_semantic_values AS          -- one id carrying many distinct e-mails / phones (over-merge signal)
SELECT l.aurora_id, COUNT(DISTINCT p.email_norm) AS emails, COUNT(DISTINCT p.phone_match) AS phones,
       COUNT(DISTINCT p.given_name_canon) AS given_names, COUNT(DISTINCT p.surname_norm) AS surnames, COUNT(*) AS records
FROM silver_unified_preprocessed p JOIN id_ledger l ON l.datasource = p.datasource AND l.pk = p.pk AND l.is_current
GROUP BY 1 HAVING COUNT(DISTINCT p.email_norm) > 3 OR COUNT(DISTINCT p.phone_match) > 3 OR COUNT(DISTINCT p.given_name_canon) > 2
ORDER BY records DESC;

CREATE OR REPLACE VIEW qa_unmatched_semantic_values AS     -- values seen on exactly one record (no partner anywhere)
SELECT 'email' AS semantic, email_norm AS value, MIN(datasource || '|' || pk) AS record
FROM silver_unified_preprocessed WHERE email_norm IS NOT NULL GROUP BY 1, 2 HAVING COUNT(*) = 1
UNION ALL
SELECT 'phone', phone_match, MIN(datasource || '|' || pk) FROM silver_unified_preprocessed WHERE phone_match IS NOT NULL GROUP BY 1, 2 HAVING COUNT(*) = 1;

CREATE OR REPLACE VIEW qa_null_amperity_ids AS             -- current records without an id in the ledger
SELECT p.datasource, p.pk FROM silver_unified_preprocessed p
LEFT JOIN id_ledger l ON l.datasource = p.datasource AND l.pk = p.pk AND l.is_current
WHERE l.aurora_id IS NULL;

CREATE OR REPLACE VIEW qa_bad_foreign_keys AS              -- fk-<namespace> values that point at no record of that namespace
WITH fks AS (
  SELECT p.datasource, p.pk, k AS namespace, json_extract_string(p.fk_json, '$.' || k) AS fk_value
  FROM silver_unified_preprocessed p, UNNEST(json_keys(p.fk_json)) AS t(k) WHERE p.fk_json IS NOT NULL AND json_valid(p.fk_json))
SELECT f.datasource, f.pk, f.namespace, f.fk_value
FROM fks f LEFT JOIN silver_unified_preprocessed t ON t.datasource = replace(f.namespace, 'fk-', '') AND t.pk = f.fk_value
WHERE t.pk IS NULL;

CREATE OR REPLACE VIEW qa_fk_validation AS                 -- interaction events whose foreign key resolved / did not resolve to an id
SELECT datasource, fk_namespace, event_type, COUNT(*) AS events, SUM(CASE WHEN aurora_id IS NULL THEN 1 ELSE 0 END) AS unresolved
FROM gold_profile_events GROUP BY 1, 2, 3 ORDER BY unresolved DESC;
