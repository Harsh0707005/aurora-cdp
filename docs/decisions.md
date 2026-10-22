# Design decisions

Format: context → decision → consequences. Dated 2026-10-22 unless noted.

## D1. DuckDB as the local engine, Snowflake-leaning DDL
Context: must run on a laptop CPU, but the organisation's warehouse is Snowflake-shaped.
Decision: one DuckDB file per workspace; DDL in versioned `.sql` files using VARCHAR(n)/TIMESTAMP/DOUBLE/BOOLEAN
and JSON stored as VARCHAR. Views use `QUALIFY`, supported by both engines.
Consequences: single-writer. The API uses short-lived read-only connections; pipeline runs take the write lock.
Snowflake port needs VARIANT for JSON columns and a loader for `write_df`.

## D2. Reproduce Amperity's *interfaces* before its *models*
Context: the research documents score bands, thresholds, change tables and the stable-ID algorithm precisely,
but the learned classifier and learned blocking cannot be reproduced without labelled data.
Decision: implement the exact table shapes, score scale (0–5), threshold semantics, hard-conflict label,
blocking caps and stable-ID algorithm now; use a hand-weighted logistic scorer behind the same interface.
Consequences: the matcher can be swapped for a trained model without changing storage, QA or downstream code.

## D3. Stable IDs by greedy max-overlap, exactly as documented
Decision: shared-PK-weighted edges, sort desc by weight then asc by (previous id, cluster id), take greedily,
mint UUIDs for the rest, retire orphaned ids; persist an SCD2 `id_ledger` and the two Unified_Changes tables.
Consequences: a 1→N split necessarily mints N−1 ids (documented Amperity behaviour, called jitter, not a bug).

## D4. Immutable bronze, derived silver
Decision: bronze keeps every landed row forever (`is_current` flips on full loads, row-hash dedupe on
incremental loads); silver rows for a source are rebuilt from current bronze rows on each ingest.
Consequences: cheap and simple; prior silver generations are not retained (stitch results are, by run_id).

## D5. Conflict-aware single-link clustering
Decision: within each connected component, union edges in descending score and refuse unions that would put
incompatible birthdates in one cluster. Supersized components are first BFS-partitioned.
Consequences: deterministic, linear-ish, prevents the documented transitive over-merge class; weaker than
Amperity's hierarchical HC_fusion for subtle cases.

## D6. Incremental mode as pair filtering plus carried edges
Decision: score only pairs touching changed records; carry previous cluster membership as score-5 edges.
Consequences: fast re-runs; previous over-merges are only split if a hard conflict appears. Flagged as an
assumption; full-mode correctness is the reference.

## D7. Configuration overlay order
Decision: `defaults.yaml` → `./aurora.yaml` → `<workspace>/last_best.yaml` (written by `aurora tune`) → CLI overrides.
Consequences: the tuner can change the default threshold without editing source; `use_last_best=False` for
reproducible sweeps.

## D8. Scoring harness adapter is a thin export, not a metrics suite
Context: a separate repo owns scoring. Decision: `aurora stitch run --input --out` and `aurora stitch export`
emit `(source_record_id, unified_id, run_date, …)` plus optional pair scores; `evaluation.py` exists only to
let the tuner pick a threshold.

## D9. Shared repository with the Spark-based `aurora/` package
Context: a parallel worker builds a PySpark/Delta variant in `aurora/` in this repository.
Decision: keep all DuckDB platform code under `aurora_cdp/`, root-level docs/tests/Makefile/docker/deploy for
this package, `pyproject.toml` covers both packages with Spark deps under the optional `[spark]` extra.
