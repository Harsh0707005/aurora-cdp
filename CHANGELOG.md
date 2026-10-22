# Changelog

All notable changes to the `aurora_cdp` platform. Local-only history; one entry per milestone commit.

## [Unreleased]

### 2026-10-22 — Step 1 scaffold (model: Claude Fable 5.1 via Claude Code)

- Repo skeleton: `pyproject.toml` (DuckDB/FastAPI/Typer stack), `Makefile`, `.gitignore`, research docs under `docs/research/`.
- Core packages: `config`, `storage` (versioned DDL + DuckDB helpers), `ingestion` (landing, semantics, normalize),
  `stitch` (blocking, features, matcher, conflict-aware clustering, stable IDs, run orchestration),
  `profile` (survivorship + golden records + events), `audiences` (segments + CSV/webhook destinations),
  `orchestration` (YAML pipeline DAG + loop scheduler).
