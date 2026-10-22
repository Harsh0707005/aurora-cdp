# Changelog

All notable changes to the `aurora_cdp` platform. Local-only history; one entry per milestone commit.

## [Unreleased]

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
