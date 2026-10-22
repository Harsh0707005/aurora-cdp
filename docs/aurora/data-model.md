# Data model

All tables are written under `storage.lake_root` (default `data/lake`) as Delta
(fallback Parquet). DDL: `aurora/io/snowflake_ddl/*.sql` (Snowflake) and
`aurora/io/delta_sql/*.sql` (spark.sql). Pydantic API models live in
`aurora/api/models.py`; shared column lists in `aurora/data/schemas.py`.

| Table | Grain | Purpose |
|---|---|---|
| `Unified_Preprocessed_Raw` | source row | standardised input (`*_std` columns), `has_blv` when a blocklisted value was stripped |
| `Blocking_Stats` | strategy | blocks, keyed records, skipped (over-sized) blocks, candidate pairs |
| `Stitch_Scores` | candidate pair | every feature, raw score, category 0..5, continuous score, `match_type ∈ {scored, deterministic, hard_conflict}`; includes pairs that did *not* become edges |
| `Unified_Coalesced` | source row | row + `cluster_id`, `component_id`, `is_supersized`, `supersized_id`, representative `rep_ds/rep_pk`, `aurora_id` |
| `Unified_Customer` | source row | slim serving projection keyed by `aurora_id` |
| `Merged_Customers` | aurora_id | golden record (survivorship policy below) |
| `Customer360` | aurora_id | golden record + cross-source rollups (`sources`, `emails`, `phones`, `loyalty_ids`, first/last seen, flags) |
| `Stable_Id_Mapping` | cluster × job | which id each cluster received, inherited from which, with the change type |
| `Unified_Changes_Clusters` | cluster event × job | CDC at cluster level (`added / deleted / merged / recognized / split / split_merged`) |
| `Unified_Changes_PKs` | record × job | CDC at record level (`added / removed / moved`) |
| `Lineage` | record × job | `(aurora_id, datasource, pk, cluster_id, supersized_id)` with a `lineage:<job>:<id>` pointer |

## Survivorship (Merged_Customers)

Rows of a cluster are ordered by completeness (count of non-null
`email_std, phone_std, given_std, surname_std, street_std, postal_std, dob_std`),
then most recent `updated_at`, then `(datasource, pk)` for determinism. The
first row is the representative; every field takes the first non-null value in
that order (coalescing survivorship). Change the policy in
`aurora.pipeline.runner.merged_customers`.

## Match categories

| category | label | meaning |
|---|---|---|
| 0 | non_match | below first threshold |
| 1 | weak | |
| 2 | moderate | also the cap applied to hard-conflict pairs |
| 3 | high | default `edge_keep_threshold` |
| 4 | excellent | |
| 5 | exact | deterministic key hit (email / phone / loyalty id) |

## Mapping to Amperity's documented tables (conceptual)

| Aurora | Amperity |
|---|---|
| Unified_Preprocessed_Raw | Unified Preprocessed Raw |
| Stitch_Scores | Stitch Scores |
| Unified_Coalesced | Unified Coalesced |
| Merged_Customers | Merged Customers |
| Customer360 | Customer 360 |
| Unified_Changes_Clusters / PKs | Unified Changes Clusters / PKs |
| Blocking_Stats | Stitch Blocking Keys (aggregate only) |
