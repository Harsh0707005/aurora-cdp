# Changelog

All notable changes to the `aurora_cdp` platform. Local-only history; one entry per milestone commit.

## [Unreleased]

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
