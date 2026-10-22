# Aurora CDP — developer guide

Aurora CDP is an in-house, local-first replacement for Amperity: identity resolution ("Stitch") with
stable IDs, golden-record profiles, segments and exports, running on CPU with DuckDB. Every behaviour maps
back to the Amperity research in `docs/research/` (see `architecture.md`); anything invented is listed in
`feature-parity.md` under *Assumptions*.

## Install

```bash
make install            # creates .venv and installs aurora-cdp[dev]
# or
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

Python 3.11+ is required. DuckDB is embedded; nothing else needs to be running.

## Run tests

```bash
make test               # pytest -q, CPU-only, < 30 s
```

## Run the demo

```bash
make demo               # == .venv/bin/aurora demo
```

The demo synthesises a few thousand rows across four sources (crm, ecommerce, loyalty, pos) plus an orders
feed, then runs: ingestion → schema init → semantic tagging + normalisation → Stitch (full) → profiles →
segment → CSV export, then ingests a second "late" batch incrementally and re-runs Stitch so the stable-ID
mapping and the jitter report are exercised. Outputs:

| artefact | path |
|---|---|
| DuckDB database | `.aurora/aurora.duckdb` |
| synthetic sources + labels | `.aurora/demo/*.csv`, `.aurora/demo/labels.csv` |
| pipeline specs | `.aurora/pipeline.yaml`, `.aurora/pipeline_batch2.yaml` |
| run history | `.aurora/runs.jsonl` |
| audience export | `outputs/engaged_buyers.csv` (+ timestamped copy) |

## CLI

```
aurora init-db                         create/upgrade the DuckDB schema
aurora ingest FILE -s SRC -f FEED [--mode full|incremental] [-m mapping.yaml]
aurora stitch [--mode full|incremental] [--threshold 3.0]
aurora stitch run --input records.csv --out assignments.csv [--scores-out scores.csv]   # harness adapter
aurora stitch export --out outputs/assignments.csv
aurora profile                         survivorship → gold_merged_customers + events
aurora segment NAME [-d segment.yaml]  evaluate/save a segment, export CSV
aurora report                          QA metrics table + outputs/report_<run>.md
aurora demo [--fast] [--people N]
aurora tune --quick                    threshold sweep → docs/tuning.md + .aurora/last_best.yaml
aurora pipeline pipeline.yaml          run a YAML DAG
aurora schedule pipeline.yaml --interval 300
aurora serve                           FastAPI + UI on http://127.0.0.1:8000
```

Every command prints a one-line summary and the path of anything it wrote. `--workspace` / `AURORA_WORKSPACE`
relocate state; `--config aurora.yaml` overlays `aurora_cdp/config/defaults.yaml`.

## API

```bash
make run    # uvicorn aurora_cdp.api.main:app --reload
```

| endpoint | purpose |
|---|---|
| `GET /health` | liveness + db path |
| `POST /runs/pipeline` `{pipeline?, mode?}` | run a pipeline YAML (defaults to `.aurora/pipeline.yaml`) |
| `GET /metrics?run_id=` | QA metrics + jitter for a Stitch run |
| `GET /runs` | run list |
| `GET /profiles?limit=&offset=&email=&surname=` | Customer 360 rows |
| `GET /profiles/{aurora_id}` | golden record + provenance + member records + events + id history |
| `GET /clusters/{aurora_id}` | cluster members + pairwise scores (cluster review) |
| `GET /changes?level=pk|clusters` | Unified_Changes_* change feed |
| `GET /segments` | saved segments and member counts |
| `GET /ui`, `GET /ui/clusters/{id}` | identity dashboard and cluster review page |

## Docker / deployment

See `docker/README.md` for the compose stack (`docker compose -f docker/docker-compose.yml up`) and
`deploy/DEPLOY.md` for the AWS material (EC2 + compose, S3 landing, RDS).

## Layout

See `architecture.md`. Configuration lives in `aurora_cdp/config/defaults.yaml`; DDL in
`aurora_cdp/storage/schema.sql` (+ `migrations/`).
