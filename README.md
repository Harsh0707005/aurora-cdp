# Aurora CDP

In-house customer data platform. This repository hosts two packages:

- **`aurora/`** — the Spark/Delta identity engine (Stitch-like): blocking →
  pairwise features → ordinal scoring → connected components + hygiene →
  stable `aurora_id` assignment by max-overlap matching → CDC, plus a
  FastAPI profile API and a small Jinja/HTMX explorer. Quickstart:
  `docs/aurora/runbook.md`; targets in `aurora/Makefile`
  (`make -f aurora/Makefile setup-spark generate-data run-pipeline eval api-spark`).
- **`aurora_cdp/`** — the local-first DuckDB platform package (CLI `aurora`,
  ingestion, profiles, audiences). See the root `Makefile` and `CHANGELOG.md`.

## Spark engine in 60 seconds

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[spark,dev]"
.venv/bin/python -m aurora.synth.generator --size 100000          # data/raw/run1 (+ drifted run2)
.venv/bin/python -m aurora.pipeline.runner --raw data/raw/run1     # prints JITTER SUMMARY: ...
.venv/bin/python -m aurora.pipeline.runner --raw data/raw/run2     # stable IDs inherited, CDC emitted
.venv/bin/python -m aurora.pipeline.eval                           # docs/aurora/evaluation.md
.venv/bin/uvicorn aurora.api.main:app --port 8000                  # http://localhost:8000
```

Docs: `docs/aurora/{runbook,architecture,data-model,config,evaluation}.md`,
build history in `docs/build-log.md`. License: MIT.
