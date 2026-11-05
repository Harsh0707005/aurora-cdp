# Changelog

All notable changes to the `aurora_cdp` platform. Local-only history; one entry per milestone commit.

## [Unreleased]

### 2026-11-05 — Reproducing the documented Stitch surface: Rules Editor, one-to-one mode, ordinal model completion (model: Claude Fable 5.1 via Claude Code)

- **Rules Editor** (`matcher.rules`): the ordered deterministic rules are now data, not code — a list of
  `{name, when: {feature-or-predicate: condition}, score[, category]}` evaluated first-match-wins before the
  probabilistic score, in both the per-pair reference and the vectorised scorer. Conditions: scalar equality,
  booleans for the predicates `names_agree` / `names_missing`, or `{eq|ne|gt|gte|lt|lte|present: value}`.
  `null` keeps the built-in list (`ck_exact, loy_exact, email_with_name, phone_with_name, email_no_name[, phone_no_name]`)
  driven by `matcher.deterministic.*`, so the frozen snapshot and every report stay byte-identical. Invalid rules
  fail at load. `tests/test_rules_editor.py`.
- **One-to-one Stitch** (`matcher.one_to_one`): records with the same customer key always merge, records with
  different customer keys never do (ck joins the hard-conflict attributes with an exact tolerance).
- **Ordinal scorer** (`stitch/ordinal.py`): `levels: 5` now reproduces Amperity's five ordered labels
  (hard-conflict < non-conflict < weak < moderate < strong) with the learned thresholds anchoring the 0–5 band
  floors; the Γ **cost matrix** (`ordinal.cost_matrix {"p,q": γ}`, cost of predicting p when the truth is q) weights
  the all-threshold loss exactly as the SIGMOD 2020 paper describes; **client-key labelling**
  (`ordinal.authoritative_keys`, `hard_negative_features`, `hard_negative_min_disagreements`) infers non-match labels
  from disagreeing trusted keys (US12499132) instead of only e-mail/phone.
- **Ground-truth-free evaluation** (`tools/signature_samples.py`, US10509809): `sample` groups a run's scored pairs
  by feature signature and writes a bounded, PII-bearing sample per signature for human labelling; `evaluate`
  rolls the labels up by signature frequency into estimated precision / recall of the merge decision and the
  P(match) of every score band. On the small synthetic tier 3,286 labels over 1,322 signatures estimate precision
  0.991 (harness: 0.998) — the method works without labelling the pair space.

### 2026-10-29 — EDAP-shaped end-to-end test (Williams-Sonoma feed contract) and identifier-only matching rules (model: Claude Fable 5.1 via Claude Code)

- **`tools/wsi_edap_sim.py` / `tools/wsi_edap_eval.py`**: synthetic EDAP → Amperity feeds in the shared DDL shapes
  (ORDER_HEADER bill-to, ORDER_LINE ship-to, RETAIL_STORE_ESTIMATE_HEADER) with ground truth, seven concepts, three
  channels with channel-specific PII capture (POS receipts carry only an e-mail, a phone, a loyalty id or nothing),
  OMS account ids, loyalty ids, employees, gift recipients, clienteling estimates, households, moves, nicknames,
  typos; the evaluator maps the feeds to identity records, runs `resolve_records` + households, builds the
  Amperity → EDAP `CUSTOMER` rows (survivorship + FIRST/SECOND/LATEST order, LIFETIME/L12M/L6M/L3M/L30D aggregates,
  RFM, flags) and scores identity, every CUSTOMER attribute, gift contamination and household pairs against the truth.
  Reports in `reports/2026-10-29/wsi-edap-*`.
- **Identifier-only deterministic rules** (`matcher.deterministic.email_exact_no_name_score: 4.0`,
  `phone_exact_no_name_score: null`): an exact e-mail between a record with no name (POS receipt e-mail) and one with
  a name was scored by the logistic model at 3.1, under the 3.25 threshold, so receipt-e-mail orders never joined the
  account that owns the e-mail. The rule fires only when at least one side carries no name (no name evidence either
  way); shared e-mails with two different names stay with the probabilistic model and the blocklist. 3k-person
  EDAP corpus: recall 0.811 → 0.922, F1 0.894 → 0.958, false merges 0.32 % → 0.37 %; bill-to ↔ bill-to recall
  0.747 → 0.873. Synthetic small tier: P 0.998 unchanged, R 0.872 → 0.869, false merges 0.75 % → 0.78 % (a handful
  of name-less synthetic records now link; reported as measured). Phone-only rule kept off by default (household
  phones). `tests/test_identifier_only_rules.py`.

### 2026-10-22 — Performance: quadratic blocking accounting removed, scoring/ingestion vectorised (model: Claude Fable 5.1 via Claude Code)

Output is byte-identical (116 tests incl. the frozen score snapshot; small tier through the harness: `assignments.csv`
and `pairs.csv` identical to `small-v5`, every non-timing metric unchanged). Measured on the 200k medium corpus,
final window, laptop (`cProfile`, same 2,676,111 blocked / 6,737,512 scored pairs before and after):

| stage | before | after |
|---|---|---|
| blocking | 156.6 s | 0.6 s |
| scoring | 69.8 s | 21.3 s |
| whole `resolve_records` | 280.8 s | 51.8 s |

- **`blocking.coverage_stats`**: the zero-discard check used `NOT EXISTS (SELECT 1 FROM _pairs p WHERE p.l = idx OR p.r = idx)`;
  the `OR` prevents a hash anti-join, so DuckDB scanned the whole pair table once per blocking-key row (quadratic;
  156 of the 157 blocking seconds at 200k, and the reason the "blocking" stage looked O(N²) in every report). The set
  of paired representatives is now materialised once (`_paired`) and anti-joined.
- **`features.features_frame`**: column sanitisation (`_nn`) ran as a Python loop over every element of every column,
  ~100 M calls per 200k run; now vectorised (`pd.isna` + `str.strip`), memoised per call (columns are reused by
  several features), and the element-wise equality loops (`_exact_vec`, birthdate, house number, trivial dupe) use
  array comparisons. The memo is keyed by `id(frame)` rather than stored in `DataFrame.attrs` (pandas deep-copies
  `attrs` into every derived Series, which cost 200 s on its own).
- **Dupe-group collapse requires an identifier** (`blocking.dupe_group_requires_identifier: true`,
  `dupe_group_identifier_fields`). The blocking-stage trivial-duplicate collapse grouped records that agreed on every
  key field *including when every field but the name was blank*, so name-only records ("James", "John Smith") were
  forced into one score-5 cluster before scoring ever ran; the scorer's own `trivial_dupe.requires_identifier` rule
  could not undo it. First visible at 1M records (`reports/2026-10-22/large`: the 25 worst over-merged clusters,
  up to 158 persons each, all `trivial_duplicate`). A group now needs a shared e-mail, phone, address, loyalty id
  or ck. Held-out seed-42 confirmation (harness, every window):

  | tier | before (`small-v5` / `medium-v3`) | after (`small-v8-dupefix` / `medium-v4-dupefix`) |
  |---|---|---|
  | small 20k | P 0.998 / F1 0.931 / B³ 0.937 / false merges 1.04 % | P 0.998 / F1 0.931 / B³ 0.937 / **0.75 %** |
  | medium 200k | P 0.994 / F1 0.923 / B³ 0.932 / false merges 2.22 % ❌ | P 0.996 / F1 0.923 / B³ 0.934 / **0.83 %** ✅ (all five gates) |

  Medium wall 708 s → 120 s on the laptop (perf fixes above). Recall and churn unchanged.
- **Stable-ID tie-break (memo R3)**: `stable_id.tie_break` (`stable`, default | `documented`). Equal-overlap ties were
  broken by the previous id *string*, i.e. randomly with uuid4 ids; `stable` prefers the previous id minted first
  (`id_ledger` `MIN(valid_from)`), then the larger current cluster, then the documented order. Small tier through the
  harness: every metric identical (churn 1.53 % / 2.19 %), only the surviving id in exact ties differs
  (`reports/2026-10-22/small-v7-tiebreak`). `tests/test_stable_id_tiebreak.py`.
- **`ingestion.semantics`**: `update_dt` parsing takes the pandas fast path (datetime columns: `to_pydatetime`;
  strings: `to_datetime(format="ISO8601")` with a dateutil fallback for anything it cannot parse); the per-row
  `iterrows` for foreign keys runs only when the mapping declares fk columns.

### 2026-10-22 — Amperity parity gaps: labels, manual blocklist, address parsing, webhook; learned DNF and ordinal completion (model: Claude Fable 5.1 via Claude Code)

Every new capability is opt-in; the default configuration produces byte-identical scores (frozen snapshot in
`tests/fixtures/handset_scores_frozen.json`) and the same blocking / clustering as before.

- **Stitch labels** (`labels.file`, `stitch/labels.py`): CSV of record pairs labelled `merge` / `split`. Merges
  become score-5 `label_merge` edges; splits drop the scored edge and install a pair-level veto in the
  conflict-aware clustering (`cluster_indices(..., forbidden=)`), so even transitive merges through other
  records are refused (`edges_rejected_by_label`). Rows are kept in `stitch_scores`; metrics `labels_merge`,
  `labels_split`, `labels_unmatched`, `edges_removed_by_label`. Malformed label files fail the run.
- **Manual blocklist** (`blocklist.manual {email, phone, address}`): values (raw or normalised form) NULLed
  before blocking, logged in `stitch_blocklist_values` with reason `manual` and the records affected.
- **Normalisation**: `normalize.nickname_file` (CSV merged over the built-in nickname dict, cached per path);
  `normalize.address_parsing` (off) canonicalises unit/suite designators (`APT 4B`, `#4B`, `STE 200` →
  `UNIT …`), PO Boxes and compound directionals (`NW` → `NORTHWEST`) via `parse_address()`.
- **Webhook destination**: per-destination `batch_size`, `max_retries` + exponential backoff
  (`backoff_base`, `backoff_max`), `headers`, `auth_token_env` (token from the environment, never logged),
  `timeout`; 429/5xx/connection errors retried, failures logged (`destination_runs.status = failed`) and raised
  as `WebhookDeliveryError`. Defaults unchanged (dry run; single legacy payload of ≤ 1000 profiles).
- **Learned DNF blocking completed**: `blocking.dnf.beam_width` bounds the conjunction search; the learned
  strategies YAML has a schema (`schema_version: 1`) with a validating loader; `blocking.strategy_source`
  falls back to the fixed strategies with a *logged warning* on an unset / missing / empty / malformed file,
  resolves relative paths (cwd, workspace parent, repo root) and rejects unknown sources; `tools/learn_dnf.py`
  accepts `--csv` and `--duckdb --table` inputs next to evaluation corpora, `--seed`, `--config`, and writes an
  absolute `learned_strategies_file` (the relative path had made the small-dnf smoke fall back silently).
- **Ordinal scorer hardening**: `matcher.ordinal.monotone` (off) sign-constrains the fit so more agreement
  never lowers the score; `tests/test_scoring_frozen.py` pins the hand-set scorer; new tests for monotone
  scores in 0–5, identical category bands / threshold, rule precedence, model file round trip and reuse.
- Docs: `docs/feature-parity.md` status table, assumptions, precise gaps list and audit resolution;
  `docs/interfaces.md` v1.2 additive metrics and `label_*` match types.
- Tests: `tests/test_normalize.py`, `tests/test_labels.py`, `tests/test_destinations.py`,
  `tests/test_scoring_frozen.py`; extended `tests/test_dnf.py`, `tests/test_ordinal.py`.

### 2026-10-22 — Zero-discard blocking + memory-bounded stitch (model: Claude Fable 5.1 via Claude Code)

- **Blocking never drops a block** (`stitch/blocking.py`, now DuckDB-backed). A block over
  `blocking.block_size_limit` is *oversized*, not skipped: it is compared in full when its pair count fits
  `max_pairs_per_block` (500k), otherwise refined on a cascade of composite secondary keys (`refine_keys`
  per strategy type) down to `refine_target`, plus a sorted-neighbourhood sweep (`sn_window`) across the whole
  block. Identical records collapse into trivial-dupe groups scored once via a representative and expanded
  back at export. New metrics: `oversized_blocks`, `oversized_handling`, `records_without_any_blocking_key`,
  `records_in_candidate_pairs`, `records_dropped_by_blocking` (asserted `== 0` every run); `skipped_blocks`
  is kept in the contract and is always 0. New QA table `stitch_oversized_blocks` (migration V2).
- **Vectorised scoring** (`features_frame` / `score_frame`, rapidfuzz `cpdist`): identical results to the
  per-pair reference (`tests/test_scoring_vectorised.py`), ~5x faster; pairs are streamed from DuckDB in
  `matcher.score_chunk_size` chunks; `features_json` persisted only with `matcher.persist_features`.
- **Clustering on integer union-find** (no networkx graph of the whole corpus); BFS partitioning only
  builds adjacency for supersized components.
- **Memory-bounded storage**: `storage.duckdb.{memory_limit, threads, temp_directory,
  preserve_insertion_order}` applied on every connection; assignment/score exports stream through
  `COPY` instead of pandas; run metrics report `peak_rss_mb` and the effective DuckDB settings.
- Tests: `tests/test_blocking_subblocks.py` (full comparison within budget, refinement keeps every record,
  duplicate-flood collapse, keyless records reported), `tests/test_scoring_vectorised.py` (reference
  equivalence, chunk invariance); the old "cap skips oversized blocks" test now asserts the opposite.
- `name` blocking strategy (given₃ + surname₃) with its own `max_pairs_per_block`: records carrying only a name
  (phone/birthdate are null on 51 % / 72 % of corpus rows) were unreachable by every other key.
- Config hygiene: `name_mismatch_floor`, `address_house_number_mismatch_cap` and the refine-key fallback moved
  into `defaults.yaml`; engine code carries no paths, seeds, tenant names or magic thresholds.
- `tools/sweep_blocking.py`: held-out sweep (tune seeds 7/11, confirm medium seed 7) with search space, trial
  count, noise band and confirmation; reported tiers (seed 42) are evaluated afterwards without re-tuning.
  (Sweep was started and stopped per the "no heavy local runs" instruction; 0 trials recorded.)
- Stitch labels persisted in the workspace (`stitch_labels`, `aurora labels add|import|list|remove`), applied
  together with the CSV overlay; forced merges outrank inferred attribute conflicts, split labels still win.
- Households as an owned entity (`profile/households.py`): persistent `household_id`, evidence edges with
  first/last-seen and a TTL, explicit relationships, stable ids by max-overlap; built by `aurora profile` and the
  pipeline (`household.build_with_profile`).
- AmpID compatibility (`identity.*`): `amperity_id` export column / previous-assignment alias and the 1:1
  e-mail → customer table `gold_email_ampid`.
- Destinations: JSONL and Parquet file connectors next to CSV and the webhook.
- **HC_fusion clustering** (`cluster.linkage: fusion`): edges are applied in score tiers (strong structure first);
  below `fusion.strong_edge_score` two formed clusters fuse only with corroborating cross edges
  (`min_cross_edges`, `min_cross_edge_ratio`); hard conflicts are checked at every union, including a set-valued
  `contact` (e-mail ∪ phone, `any_overlap`) conflict; clusters above `carve.max_cluster_size` lose their weakest
  tiers until the pieces fit and the separated members are surfaced (`carved_records`, `supersized_id`).
  Bookkeeping is numpy arrays + per-root value sets; `linkage: single` keeps the previous behaviour.
- Trivial dupes (`matcher.trivial_dupe`) now require an agreeing identifier and compare birthdate: name-only
  "trivial duplicates" had bridged different people with the same common name on the medium tier.
- Held-out sweep (tune small seeds 7/11, confirm medium seed 7; 20 trials) chose `match_threshold: 3.25` and a
  given-name hard conflict (`cluster.conflict_tolerances.given_name: jaro_winkler_min 0.6`) over the previous
  3.0 / birthdate-only defaults. Seed-42 confirmation: small passes all five gates (false merges 2.51 % → 1.01 %,
  P 0.999, F1 0.937, B³ 0.940, blocking recall 0.878); medium passes four and misses the false-merge ceiling
  (2.51 % vs 2.0 %; P 0.990, F1 0.926, B³ 0.934, blocking recall 0.893). Ordinal did not win (no operating point
  with P ≥ 0.98 and F1 ≥ 0.90) and stays selectable, not default. See `docs/tuning.md`.
- Ordinal-regression scorer wired as `matcher.scorer: ordinal` (default stays `rules` until the harness
  comparison says otherwise): label-free self-training on the run's own candidate pairs or a saved
  `matcher.ordinal.model_file`; insufficient data / `retrain: never` without a model fall back to the rules scorer
  with `scorer_fallback_reason` in the metrics. `tools/sweep_blocking.py` now sweeps scorer × threshold × name
  budget on held-out seeds 7/11 with per-corpus gates incl. B³ F1.
- Stable-ID assignment, change feeds, jitter and the SCD2 ledger now run inside DuckDB (`stable_id.py`
  `assign_stable_ids_duck`): unambiguous 1-to-1 overlaps are assigned in SQL, only the split/merge subset goes
  through the greedy loop; `stitch_clusters` / `unified_changes_*` / `id_ledger` are `INSERT … SELECT`s, so no
  per-record Python dict survives the run (cluster ids are strings per cluster, integers per record).
  `tests/test_stable_id_sql.py` checks the SQL core against a brute-force greedy reference on random histories.
- Learned DNF blocking scaffold (`stitch/dnf.py`, `tools/learn_dnf.py`, `dnf` strategy type, config
  `blocking.strategy_source/learned_strategies_file/dnf.*`) and an ordinal-regression scorer module
  (`stitch/ordinal.py`, `tools/train_ordinal.py`, tests) — **handed over**: a separate worker now owns the
  Amperity-gap strand (DNF, ordinal, HC_fusion, labels, households). State at handover: DNF learner runs end to
  end on held-out seed 7 but its learned disjunction reaches PC 0.68 (self-labels) / 0.79 (truth labels) vs 0.90
  for the fixed strategies (`reports/2026-10-22/dnf-{self,truth}/`); `learn_dnf.py` writes a *relative*
  `learned_strategies_file` path, so the harness smoke (`reports/2026-10-22/small-dnf`) fell back to the fixed
  list (identical to small-v2). The ordinal module is unit-tested but not wired into `run_stitch`.

### 2026-10-22 — Step 1 scaffold (model: Claude Fable 5.1 via Claude Code)

- Repo skeleton: `pyproject.toml` (DuckDB/FastAPI/Typer stack), `Makefile`, `.gitignore`, research docs under `docs/research/`.
- Core packages: `config`, `storage` (versioned DDL + DuckDB helpers), `ingestion` (landing, semantics, normalize),
  `stitch` (blocking, features, matcher, conflict-aware clustering, stable IDs, run orchestration),
  `profile` (survivorship + golden records + events), `audiences` (segments + CSV/webhook destinations),
  `orchestration` (YAML pipeline DAG + loop scheduler).
- FastAPI service (`/health`, `/runs/pipeline`, `/metrics`, `/profiles`, `/clusters/{id}`, `/changes`, `/segments`)
  with a Jinja2 identity dashboard and cluster review page.
- Typer CLI: `init-db`, `ingest`, `stitch` (+ `run`/`export`), `resolve`, `profile`, `segment`, `report`, `demo`,
  `tune`, `pipeline`, `schedule`, `serve`.
- Synthetic multi-source demo (two batches: full + incremental) exercising stable IDs and jitter.
- Stable external interface for the scoring harness: `aurora resolve` / `python -m aurora_cdp.adapters.resolver` /
  `aurora_cdp.adapters.resolve_records()`; contract in `docs/interfaces.md` (+ `docs/adapter-contract.md`).
- Tests: `tests/test_smoke.py` (imports, demo fast mode, API, adapter), `tests/test_stitch_small.py`
  (labelled precision/recall > 0.8, hard conflicts, normalisation, blocking caps, greedy stable IDs). 47 passing.
- Docs: `docs/README.md`, `architecture.md`, `feature-parity.md` (with Assumptions), `decisions.md`, `tuning.md`.
- Fixes found while testing: YAML `no` parsed as boolean in junk-email list; NaN leaking into normalisers and
  features; Starlette `TemplateResponse` signature; missing loyalty-id / customer-key blocking strategies.
- Scorer hardening after the sweep exposed look-alike false merges: address similarity is centred (dissimilar
  addresses count against a match), a different house number caps address similarity, and email similarity
  only counts at typo level (≥ 0.92). Synthetic generator gained hard negatives (look-alikes, household members)
  and unique per-source ids (random ids had collided).
- Tuner: precision floor (`tuning.min_precision`, 0.98) before F1; ties → lowest churn → closest to 3.0.
  `aurora demo` preserves `.aurora/last_best.yaml` across resets.
- Docker: `docker/Dockerfile`, `docker/docker-compose.yml` (api + runner + seed + postgres), `docker/seed.sh`.
- AWS: `deploy/DEPLOY.md` and `deploy/aws/*.sh` (S3 landing bucket, EC2 + compose via systemd, RDS Postgres,
  code upload, feed sync, destroy). Credentials-gated; not executed against a live account.
- Root `README.md` gained an `aurora_cdp` section (additive; the file is shared with the sibling Spark package).
