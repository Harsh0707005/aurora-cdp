# Docker stack

```bash
docker compose -f docker/docker-compose.yml up --build      # api :8000, runner, db :5432, seed (one-shot)
open http://localhost:8000/ui                               # dashboard;  /docs for OpenAPI
docker compose -f docker/docker-compose.yml run --rm -e AURORA_RESEED=1 seed   # regenerate demo data
docker compose -f docker/docker-compose.yml down -v         # stop and drop volumes
```

Services: `api` (FastAPI + UI), `runner` (scheduler re-running `pipeline_batch2.yaml` every `AURORA_INTERVAL`
seconds, default 900), `seed` (demo data + full pipeline, idempotent), `db` (Postgres 16).

Running the CLI inside the stack:

```bash
docker compose -f docker/docker-compose.yml run --rm api aurora report
docker compose -f docker/docker-compose.yml run --rm -v "$PWD":/work api \
    aurora resolve --input /work/records.csv --output /work/assignments.csv
```

## Notes and limits

- **State** lives in DuckDB at `/data/aurora/aurora.duckdb` on the `aurora-data` volume; exports in `/data/outputs`.
- **Single writer.** DuckDB allows one writing process. The runner and `POST /runs/pipeline` take the lock during
  a run; read endpoints use read-only connections and answer `503 database busy` while a run holds it.
  Keep `AURORA_INTERVAL` well above the run duration (seconds for the demo).
- **Postgres** is provisioned to match the AWS layout (RDS) and is the intended serving/metadata store; syncing
  `customer_360` / `identity_graph` / change feeds into it is a TODO (`deploy/DEPLOY.md`, "Serving layer").
- Images are built from the repo root context; only `aurora_cdp/` is installed (the sibling Spark package has its
  own images under `aurora/docker/`).
