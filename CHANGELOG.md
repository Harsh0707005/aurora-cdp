# Changelog

All notable changes to the `aurora_cdp` platform. Local-only history; one entry per milestone commit.

## [Unreleased]

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
