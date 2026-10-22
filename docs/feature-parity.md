# Feature parity vs Amperity

Legend: ✅ implemented (scaffold-grade) · 🟡 partial / stub · ❌ not started. References as in `architecture.md`.

## Identity resolution (Stitch)

| Amperity behaviour | Status | Notes |
|---|---|---|
| Semantic tagging per feed (given-name, surname, email, phone, address group, birthdate, loy_id, fk-*, pk, ck) | ✅ | `ingestion/semantics.py`; mapping per source in pipeline YAML |
| Preprocessing: email canonicalisation, junk local parts, phone last-10, address abbreviations, nicknames | ✅ | address parsing (unit/suite, PO Box, compound directionals) behind `normalize.address_parsing` (off: output-changing); nickname table = built-in dict + `normalize.nickname_file` CSV. No libpostal-style probabilistic tokenisation |
| Blocking strategies + size limits + persisted blocking keys | ✅ | documented strategies (e-mail, phone, name+postal, name+birthdate, loyalty, ck, fk) + a name-prefix key; limit 100 / fk 1000 define *oversized*, nothing is skipped |
| Oversized (hot-key) blocks | ✅ | compared in full within `max_pairs_per_block`, else sub-blocked on composite secondary keys + sorted-neighbourhood sweep; `records_dropped_by_blocking == 0` asserted every run; `stitch_oversized_blocks` QA table |
| Learned DNF blocking | ✅ (off by default) | Bilenko-style learner in `stitch/dnf.py` (unary predicates → conjunctions, exhaustive or `beam_width`-bounded → greedy red-blue cover under a pair budget), label-free positives from the deterministic rules; `tools/learn_dnf.py` (corpus / CSV / DuckDB input) writes the strategies YAML; `blocking.strategy_source: fixed \| learned \| union` with logged fallback to the fixed list. Default stays `fixed`: on held-out seed 7 the learned disjunction reached PC 0.68 (self labels) / 0.79 (truth) vs 0.90 for the fixed strategies (`reports/2026-10-22/dnf-*`) |
| Pairwise scoring 0–5 with weak/moderate/high/excellent/exact bands, threshold 3.0 | ✅ | bands + threshold reproduced |
| Ordinal-regression classifier trained without ground truth | ✅ (off by default) | `matcher.scorer: ordinal` (`stitch/ordinal.py`): all-threshold logistic ordinal regression on the base + extended feature families, positives/negatives self-labelled from the rules, hard conflicts and hard negatives, self-training rounds; model persisted to `matcher.ordinal.model_file` (`tools/train_ordinal.py` or in-run), reused with `retrain: never`; falls back to the rules scorer with a reason. `matcher.ordinal.monotone` (off) sign-constrains the fit so more agreement never lowers the score. Default `rules` is byte-identical to before (`tests/test_scoring_frozen.py`); held-out evaluation of the ordinal scorer is still in progress (`reports/2026-10-22/small-ordinal*`) |
| Rules Editor (ordered deterministic rules, first match wins) | 🟡 | fixed rule order in `matcher.py`, scores/thresholds configurable; operator overrides via persisted Stitch labels |
| Hard conflicts with explicit refuse-to-merge | ✅ | pairwise (birthdate) + cluster-time per-attribute tolerances checked at every union: birthdate (Levenshtein ≤ 2), given name (JW ≥ 0.6, swept on held-out seeds), optional set-valued contact (`any_overlap`); forced merge labels outrank inferred conflicts |
| Connected components → conflict-aware hierarchical clustering | ✅ | `cluster.linkage: fusion`: tiered, evidence-gated fusion with per-attribute hard conflicts (birthdate, given name, set-valued contact) checked at every union; `single` = conflict-aware single link |
| Supersized / blackhole components (BFS partition) | ✅ | BFS partition of oversized components before fusion + `cluster.carve` trimming weak tiers of oversized clusters after it (members surfaced as `carved_records`) |
| Trivial duplicate groups | ✅ | identical records collapse to a representative for blocking/scoring and expand back in `stitch_scores`; `match_type = trivial_duplicate` |
| Bad-value blocklist with automatic detection + manual blocklist | ✅ | thresholds from docs; `blocklist.manual {email, phone, address}` values (raw or normalised) are NULLed before blocking and listed in `stitch_blocklist_values` with reason `manual` (config, not a tenant table) |
| Stitch labels (forced merge / split) | ✅ | CSV overlay (`labels.file`) **and** persisted `stitch_labels` table (`aurora labels add|import|list|remove`, survive runs); merge → score-5 `label_merge` edge that outranks attribute conflicts, split → scored edge dropped + transitive pair veto; group-id label form not reproduced (pairs only) |
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
| Email AmpID Assignment (many-to-many narrowed to 1:1) | ✅ | `gold_email_ampid` (SCD2) written at profile build (`identity.email_ampid_assignment`); `identity.ampid_mode` adds `amperity_id` to exports and accepts it as a previous-assignment column |
| Customer 360 with behavioural attributes | 🟡 | order_count / total_spend / last_order_ts only |
| Households | ✅ | owned entity (`profile/households.py`): persistent `household_id`, evidence edges (shared address, surname+postal, phone, explicit relationships) with first/last-seen and a TTL so moves do not churn, hot values excluded, stable ids by max-overlap; built by `aurora profile` / the pipeline, `aurora household build|show|add-relationship` |
| Table/database versioning & rollback | 🟡 | SCD2 on ledger and merged customers; `*_as_of` helpers |

## Activation & operations

| Amperity behaviour | Status | Notes |
|---|---|---|
| Segments over Customer 360 | ✅ | filter-list → parameterised SQL |
| Destinations | ✅ / 🟡 | CSV, JSONL and Parquet file connectors; JSON webhook with batching, retries/backoff, auth/custom headers (`dry_run` default, failures logged in `destination_runs`); no SFTP/S3/ad-platform catalogue ❌ |
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
3. **Conflict-aware clustering** is HC_fusion-style: edges applied in score tiers, formed entities fuse only with corroborating cross edges below `strong_edge_score`, hard conflicts checked at every union, oversized clusters carved by trimming weak tiers (`cluster.linkage: fusion`; `single` keeps the old behaviour).
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
15. **Stitch labels are pair-level.** A label names two records; a split is enforced as a clustering veto
    (checked on cluster roots, so it also blocks transitive merges). Amperity's labels are cluster group ids.
16. **Manual blocklist lives in config** (`blocklist.manual`), normalised like the records on load, not in a
    tenant `BlocklistValues` table; entries are logged per run with the number of records they blanked.
17. **Learned scorer monotonicity** (`matcher.ordinal.monotone`) is a projected-gradient sign constraint on the
    feature weights; it is off by default so the unconstrained fit used in the ordinal evaluation runs stays
    reproducible.
18. **Webhook legacy payload.** Without `batch_size` the webhook still sends a single payload with the first
    1000 profiles (the original stub's behaviour); batching delivers every profile.
19. **Address parsing is rule-based** (designators, PO Box, directionals), not probabilistic, and changes
    `address_norm` only when `normalize.address_parsing` is on.
12. **Jitter** is computed over records present in both runs (`records_changed / records_compared`), matching the
    docs' "percent of customer records assigned an updated ID".

## Defaults in force (measured on the small tier, seed 42, `reports/2026-10-22/small-v5`)

`matcher.scorer: rules`, `match_threshold: 3.25`, `blocking.strategy_source: fixed` + zero-discard sub-blocking,
`cluster.linkage: fusion` with birthdate + given-name hard conflicts and carve, `matcher.trivial_dupe.requires_identifier: true`,
labels, households and AmpID mode on. Result: P/R/F1 0.998/0.872/0.931, B³ F1 0.937, blocking recall 0.878,
false-merge clusters 1.04 % (baseline engine `08be538`: 0.980/0.649/0.781, B³ 0.931, 0.537, 1.75 %).

## Gaps / TODO (next steps)

Precise list of what is still partial or absent (everything above marked ✅ has tests in `tests/`):

- **Learned DNF blocking is implemented but not adopted**: the learned disjunction under-covers the fixed
  strategies on held-out data (PC 0.68/0.79 vs 0.90). Likely causes to investigate: the predicate space lacks the
  composite keys the fixed list uses (`given₃+surname+postal`, `given₃+surname₁+birthdate`) and the pair budget
  (`pairs_per_record_budget`) is tighter than the fixed list's cost. `beam_width` is `null` (exhaustive) by default.
- **Ordinal scorer** evaluated on seed-42 small (`reports/2026-10-22/small-ordinal*`): F1 0.955 but precision 0.952–0.957 and false merges 6.75–8.66 % — no operating point meets P ≥ 0.98, so `rules` stays the default.
  `tools/train_ordinal.py` reads evaluation corpora only (no CSV/DuckDB input yet).
- **Rules Editor**: deterministic rule *order* is fixed in `matcher.py` (ck → loyalty → e-mail+name → phone+name);
  only the scores and the name-agreement floor are configurable.
- **Clustering**: HC_fusion in place (`cluster.linkage: fusion`, default); the medium-tier false-merge ceiling (2.0 %) is the remaining open gate — see `docs/tuning.md`.
- **Stitch labels** are pair-level (no group-id form); a split between two members of the same trivial-dupe
  group separates the member from its representative (unenforceable in the group-id sense).
- **Manual blocklist** is config-only (no `BlocklistValues` table / UI).
- **Nickname table** ships ~70 built-in entries; a full table must be supplied via `normalize.nickname_file`.
- **Address parsing**: no libpostal-style tokenisation, no secondary-unit ranges, no non-US formats beyond
  uppercasing; hyphens inside PO Box numbers become spaces.
- **Connectors**: CSV/JSONL/Parquet files and the webhook exist; no SFTP/S3/ad-platform catalogue, no OAuth refresh, no idempotency keys.
- `api/templates/cluster.html` still carries the "approve / split actions TODO" placeholder: the API has no
  write endpoints; labels are applied through `aurora labels …` / `labels.file` instead.
- Richer Customer 360 attributes, one-to-one (ck) Stitch mode; device graph and real-time streaming are deliberately out of scope.
- QA queries: weakest match, split clusters, many semantic values, FK validation.
- Snowflake deployment of the DDL and a Postgres serving store (see `deploy/DEPLOY.md`).

## Audit 2026-10-22 (historical snapshot, taken before the gap work — superseded by the tables above)

> This section is kept as history. Everything it lists as missing was re-assessed the same day; the
> "Resolution" table below is the authoritative outcome and matches the status tables at the top of this file.

Scope: case-insensitive grep for `amperity` across code, tests, docs and `git log`; grep for
TODO / FIXME / NotImplemented / skip / xfail across `aurora_cdp/`, `tests/` and `tools/`. "Amperity" in this repo
is the *reference product* being reproduced, not a third-party integration: there is no Amperity API client,
auth, pagination or export payload code anywhere, so the parity surface is the semantic-tagging → preprocessing →
blocking → scoring → clustering → survivorship → activation chain documented in `architecture.md`.

Found missing or incomplete at the time of the audit (precise):

- `stitch/matcher.py`: hand-set logistic weights + fixed-order deterministic rules; `stitch/ordinal.py` existed
  but was not wired, had no config keys and no tests.
- `stitch/dnf.py` + `tools/learn_dnf.py`: learner existed; CLI parquet-only, relative strategies path, silent
  fallback, exhaustive conjunction search, no wiring tests.
- `ingestion/normalize.py`: TODOs for unit/suite parsing, PO Box and directional suffixes; ~70-entry nickname dict.
- `audiences/destinations.py::send_webhook`: stub (single payload truncated to 1000 profiles, no retries/auth).
- `stitch/run.py::apply_blocklist_sql`: automatic detection only, no manual blocklist.
- Stitch labels absent; `cluster.py` had no pair-level veto, only the birthdate conflict.
- `api/templates/cluster.html`: "approve / split actions TODO" placeholder (UI only).
- Not started at audit time: Email AmpID Assignment, households, one-to-one (ck) Stitch mode, QA queries,
  HC_fusion clustering, streaming layer, predictive models, Snowflake/Databricks connector.
- No `pytest.mark.skip` / `xfail` / `NotImplementedError` anywhere in `aurora_cdp/` or `tests/`.

### Resolution of the audit items (final state at HEAD)

| Audit item | Outcome |
|---|---|
| Ordinal scorer not wired / no config / no tests | **wired** as `matcher.scorer: rules \| ordinal` + `matcher.ordinal.*` (label-free self-training, hard negatives, rules fallback); tests in `tests/test_ordinal.py`, `tests/test_scoring_frozen.py`. **Not default**: no operating point reaches P ≥ 0.98 on seed-42 small (`reports/2026-10-22/small-ordinal*`) |
| DNF CLI parquet-only, relative path, silent fallback, exhaustive search, no wiring tests | `--csv` / `--duckdb --table`, absolute strategies path, validated loader with logged warning, `beam_width`, learned/union/fallback + CLI→run tests. **Not default**: held-out PC 0.68/0.79 vs 0.90 for the fixed list |
| Address parsing TODOs, nickname dict TODO | `normalize.address_parsing` (opt-in) + `normalize.nickname_file` |
| Webhook stub | batching / retries / auth / timeout (opt-in; dry-run default); JSONL and Parquet file connectors added |
| No manual blocklist | `blocklist.manual` |
| No Stitch labels / pair veto | **done**: `labels.file` overlay + persisted `stitch_labels` table (`aurora labels …`), forced merges outrank attribute conflicts, splits are transitive vetoes |
| HC_fusion clustering not started | **done and default**: `cluster.linkage: fusion` (tiered evidence-gated fusion, per-attribute hard conflicts incl. given name and optional contact sets, supersized carve) |
| Households not started | **done and default**: owned entity with persistent ids, evidence edges + TTL, relationships; built with `aurora profile` / pipeline |
| Email AmpID Assignment not started | **done and default**: `gold_email_ampid` (1:1, SCD2) + `identity.ampid_mode` (`amperity_id` export / previous-assignment alias) |
| `cluster.html` placeholder | left (UI only; see gaps) |
| Still deliberately unbuilt | one-to-one (ck) Stitch mode; QA query catalogue (weakest match / many semantic values / FK validation); SFTP/S3/ad-platform connectors; device graph; real-time streaming; predictive models; Snowflake/Databricks connector |
