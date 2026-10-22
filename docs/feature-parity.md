# Feature parity vs Amperity

Legend: ✅ implemented (scaffold-grade) · 🟡 partial / stub · ❌ not started. References as in `architecture.md`.

## Identity resolution (Stitch)

| Amperity behaviour | Status | Notes |
|---|---|---|
| Semantic tagging per feed (given-name, surname, email, phone, address group, birthdate, loy_id, fk-*, pk, ck) | ✅ | `ingestion/semantics.py`; mapping per source in pipeline YAML |
| Preprocessing: email canonicalisation, junk local parts, phone last-10, address abbreviations, nicknames | ✅ / 🟡 | address parsing is a stub with TODOs; nickname table is a small built-in dict |
| Blocking strategies + size limits + persisted blocking keys | ✅ | documented strategies (e-mail, phone, name+postal, name+birthdate, loyalty, ck, fk) + a name-prefix key; limit 100 / fk 1000 define *oversized*, nothing is skipped |
| Oversized (hot-key) blocks | ✅ | compared in full within `max_pairs_per_block`, else sub-blocked on composite secondary keys + sorted-neighbourhood sweep; `records_dropped_by_blocking == 0` asserted every run; `stitch_oversized_blocks` QA table |
| Learned DNF blocking | 🟡 | strategy set and refinement cascade are configured (DNF of exact keys); budgets swept on held-out seeds (`tools/sweep_blocking.py`), not learned |
| Pairwise scoring 0–5 with weak/moderate/high/excellent/exact bands, threshold 3.0 | ✅ | bands + threshold reproduced |
| Ordinal-regression classifier trained without ground truth | ❌ | hand-set logistic weights + deterministic rules; see Assumptions |
| Rules Editor (ordered deterministic rules, first match wins) | 🟡 | fixed rule order in `matcher.py`, scores configurable |
| Hard conflicts (birthdate) with explicit refuse-to-merge | ✅ | pairwise label + cluster-time check |
| Connected components → conflict-aware hierarchical clustering | 🟡 | deterministic conflict-free single-link; not the full HC_fusion |
| Supersized / blackhole components (BFS partition) | ✅ | `cluster.py::_bfs_partition` |
| Trivial duplicate groups | ✅ | identical records collapse to a representative for blocking/scoring and expand back in `stitch_scores`; `match_type = trivial_duplicate` |
| Bad-value blocklist with automatic detection | ✅ | thresholds from docs; manual blocklist table ❌ |
| Stitch labels (forced merge / split CSV) | ❌ | planned |
| One-to-one (ck) Stitch mode | 🟡 | `ck_exact` is a deterministic rule; dedicated mode ❌ |
| Incremental clustering | 🟡 | changed-record pair filtering + carried edges; correctness equivalence not verified |
| Stable ID assignment (greedy max-overlap, ties by ascending id) | ✅ | `stable_id.py` |
| Unified Changes PKs / Clusters (added/deleted/updated + run id) | ✅ | `unified_changes_pk`, `unified_changes_clusters` |
| Jitter metric + 2% alert | ✅ | `jitter_reports` |
| Stitch QA tables (blocking keys, scores incl. non-merges, skipped blocks, cluster size distribution) | ✅ / 🟡 | several QA queries still to add (weakest match, many semantic values, FK validation) |

## Data model & profiles

| Amperity behaviour | Status | Notes |
|---|---|---|
| Immutable, versioned substrate (prior generations kept) | 🟡 | bronze keeps every row (`is_current`); stitch results keyed by run_id; silver is rebuilt per source |
| Unified Preprocessed Raw / Unified Coalesced / Identity Graph | ✅ | tables + views |
| Merged Customers with Source/Field priority, 999 default, recency | ✅ | provenance per attribute |
| Email AmpID Assignment (many-to-many narrowed to 1:1) | ❌ | |
| Customer 360 with behavioural attributes | 🟡 | order_count / total_spend / last_order_ts only |
| Households | ❌ | |
| Table/database versioning & rollback | 🟡 | SCD2 on ledger and merged customers; `*_as_of` helpers |

## Activation & operations

| Amperity behaviour | Status | Notes |
|---|---|---|
| Segments over Customer 360 | ✅ | filter-list → parameterised SQL |
| Destinations | 🟡 | CSV ✅, webhook stub (dry-run default) |
| Workflows / scheduling | 🟡 | YAML DAG + interval loop |
| Profile API (read-only lookup) | ✅ | FastAPI |
| Real-time streaming layer | ❌ | out of scope for now |
| Predictive models (CLV, propensity) | ❌ | |
| Snowflake/Databricks bridge | 🟡 | DDL kept Snowflake-compatible; no connector |

## Assumptions (things we invented or chose; not documented Amperity behaviour)

1. **Scoring model.** Score = `5 · sigmoid(bias + Σ wᵢ fᵢ)` with hand-set weights in `defaults.yaml`, plus
   deterministic rules (ck / loyalty exact → 5.0, email+name → 4.5, phone+name → 4.2). Amperity uses a learned
   ordinal-regression model. Weights are tuned only via the threshold sweep (`aurora tune`).
2. **Birthdate typo tolerance.** Birthdates within Levenshtein ≤ 2 count as a typo (0.5 agreement), not a conflict.
3. **Conflict-aware clustering** is deterministic single-link with a hard-conflict veto, not Amperity's HC_fusion.
4. **Incremental mode** carries previous clusters as score-5 "carried" edges and scores only pairs touching
   changed records (changed = ingested after the last run, or not yet in the ledger).
5. **Cluster ids** are sha1 prefixes of the smallest member record id; tie-breaks therefore follow that hash order.
6. **Silver rebuild.** Semantic tagging rebuilds the silver rows of a source from its current bronze rows on every
   ingest; bronze rows are never deleted (full loads flip `is_current`).
7. **Blocklist** is applied as "value → NULL for matching" in memory per run and logged; there is no tenant
   `BlocklistValues` table yet.
8. **Gmail dot folding** is an optional normalisation (default off); Amperity does not document it.
9. **Segments** are a filter list (field / op / value) over `customer_360`, not full SQL.
10. **Supersized threshold** defaults to 500 (docs are inconsistent between 64 and 500).
13. **Oversized-block handling** (`max_pairs_per_block`, per-strategy budgets, `refine_target`, `sn_window`, the
    `refine_keys` cascade and the `name` prefix strategy) is ours; Amperity skips such blocks. Defaults were chosen
    by the held-out sweep in `reports/<date>/tuning/` and are evaluated on seeds the sweep never saw.
14. **Memory bounds** (`storage.duckdb.*`, chunked scoring, integer union-find) are implementation choices with no
    documented Amperity counterpart.
11. **Adapter export** `(source_record_id, unified_id, run_date)` exists for the external scoring harness.
12. **Jitter** is computed over records present in both runs (`records_changed / records_compared`), matching the
    docs' "percent of customer records assigned an updated ID".

## Gaps / TODO (next steps)

- Learned scorer (ordinal regression on labelled signatures) and learned blocking.
- Stitch labels (forced merge/split), manual blocklist table, nickname table loader.
- Email AmpID Assignment, households, richer Customer 360 attributes.
- QA queries: weakest match, split clusters, many semantic values, FK validation.
- Snowflake deployment of the DDL and a Postgres serving store (see `deploy/DEPLOY.md`).
