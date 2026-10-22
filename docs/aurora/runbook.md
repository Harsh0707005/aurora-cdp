# Aurora identity engine — runbook

Everything here is local: Spark `local[*]`, Delta (or Parquet) under `data/lake`,
CDC under `data/cdc`. No cloud resources are touched.

Targets live in `aurora/Makefile`. Run them as `make -f aurora/Makefile <target>`
(or `make <target>` if the root Makefile includes it). `python -m …` equivalents
are shown everywhere so nothing depends on make.

## 1. Quickstart

### Without Docker

```bash
cd ~/Desktop/Projects/aurora-cdp
python3 -m venv .venv && .venv/bin/pip install -U pip
.venv/bin/pip install -e ".[spark,dev]"           # make -f aurora/Makefile setup-spark

# 100k synthetic customers (~160k source rows) + a drifted copy for the second run
.venv/bin/python -m aurora.synth.generator --size 100000 --out data/raw/run1 --drift-out data/raw/run2

# first identity pass
.venv/bin/python -m aurora.pipeline.runner --config configs/tenants/demo.yaml --raw data/raw/run1
#  -> prints:  JITTER SUMMARY: added=… deleted=… merged=… recognized=… split=… split_merged=… percent=…%

# second pass over the drifted data: stable IDs are inherited, CDC events emitted
.venv/bin/python -m aurora.pipeline.runner --config configs/tenants/demo.yaml --raw data/raw/run2

# metrics vs planted truth, churn vs the previous run
.venv/bin/python -m aurora.pipeline.eval --config configs/tenants/demo.yaml

# API + UI
.venv/bin/uvicorn aurora.api.main:app --port 8000        # http://localhost:8000
```

Requirements: Java 17 (`java -version`), Python ≥ 3.11. The first Delta run
downloads the Delta jars through Ivy (needs network once); afterwards they are
cached in `~/.ivy2`. If the download fails the run **falls back to Parquet**
automatically and the summary says so (`delta_error`). Force a format with
`--format parquet|delta`.

### With Docker Compose

```bash
docker compose -f aurora/docker/docker-compose.yml up --build -d      # API on :8000, Spark local[*]
docker compose -f aurora/docker/docker-compose.yml exec api \
  python -m aurora.pipeline.runner --raw data/raw/run1
# optional single-node Spark cluster
docker compose -f aurora/docker/docker-compose.yml --profile cluster up -d
AURORA_SPARK_MASTER=spark://spark:7077 docker compose -f aurora/docker/docker-compose.yml up -d api
```

The repo is bind-mounted, so outputs land in the same `data/` folders.

## 2. Where outputs land

| Path | What |
|---|---|
| `data/raw/run1/records.parquet` | synthetic input (with `truth_id`) |
| `data/raw/run2/records.parquet` | drifted input for run 2 |
| `data/lake/<Table>/` | Delta (or Parquet) tables, see `docs/aurora/data-model.md` |
| `data/lake/Unified_Changes_*` | CDC tables, append-only across runs |
| `data/lake/Stable_Id_Mapping`, `Lineage` | per-run id inheritance and record lineage |
| `data/cdc/<job_id>.jsonl` | CDC event stream |
| `data/runs/<job_id>/summary.json`, `jitter.csv` | run summary + jitter events; `data/runs/LATEST` holds the last job id |
| `data/eval/<job_id>.json`, `docs/aurora/evaluation.md` | evaluation report |

Browse without Spark:

```python
from aurora.io.deltaio import read_table_pandas
df = read_table_pandas("data/lake", "Merged_Customers")
```

or via the API (`/health` lists tables). Tail CDC with
`python scripts/cdc_consumer.py --follow`.

## 3. Stable IDs

`aurora_id` is a UUIDv5 of `(tenant namespace, cluster seed)`; the seed of a
brand-new cluster is its smallest `(datasource, pk)`. On every later run,
`aurora.graph.stable_id.assign_stable_ids` compares the new clusters with the
previous `Unified_Customer` assignment:

1. count shared `(datasource, pk)` between every old id and new cluster;
2. split the bipartite overlap graph into connected blocks;
3. per block, solve maximum-weight matching — SciPy Hungarian
   (`linear_sum_assignment`) when `old + new ≤ stable_id.hungarian_max_nodes`,
   otherwise greedy largest-overlap-first;
4. a matched new cluster inherits the old id; unmatched new clusters mint a new
   id; unmatched old ids are retired.

Consequences: a **split** keeps the old id on the largest fragment only; a
**merge** keeps the id of the largest-overlap predecessor. Both are *jitter*
and are reported per run. Mapping tables: `Stable_Id_Mapping` (cluster →
id → previous id → change type, per job) and `Unified_Changes_Clusters`.

## 4. Tuning thresholds

Everything is in the tenant YAML (`configs/tenants/demo.yaml`, layered on
`aurora/config/defaults.yaml`; see `docs/aurora/config.md`):

- `scoring.weights` / `scoring.bias` — linear weights per pairwise feature;
- `scoring.thresholds` — five increasing cut points → categories 0..5;
- `scoring.edge_keep_threshold` — minimum continuous score for an edge (default 3.0 = "high");
- `scoring.deterministic_keys` — features that short-circuit to `exact`;
- `scoring.hard_conflicts` — features that cap a pair at `moderate` (never merge).

Data-driven tuning on labelled pairs (`truth_id` on synthetic data, or a
reviewed sample in production):

```python
from aurora.scoring.ordinal import tune_thresholds, fit_learned
best = tune_thresholds(X, y, cfg.scoring)      # grid search keep threshold + a few weight scalings
learned = fit_learned(X, y, cfg.scoring); learned.save("models/demo.joblib")
# then: scoring.mode: learned / scoring.model_path: models/demo.joblib
```

`docs/aurora/evaluation.md` shows pair precision/recall at several keep
thresholds — pick the one with the best F1 (or the precision you need) and set
`edge_keep_threshold`. Blocking recall problems show up as a gap between the
"candidate" and "global" pair recall.

## 5. Re-running safely and reading CDC

- Runs are idempotent for the serving tables (`Unified_*`, `Merged_Customers`,
  `Customer360`, `Stitch_Scores`, `Blocking_Stats` are overwritten); the CDC and
  lineage tables are append-only and keyed by `job_id`.
- The previous assignment is read from `Unified_Customer` *before* it is
  overwritten, so re-running on identical input yields `recognized` for every
  cluster and `percent=0.0%` jitter.
- To start from scratch: `make -f aurora/Makefile clean-spark` (removes the
  lake, CDC, run summaries and `.tmp`).
- CDC event types: `identity_assigned` (new id), `id_reissued` (a record moved
  ids), `cluster_split`, `cluster_merge`, `identity_retired`. Each carries
  `job_id`, `ts`, `current_id`, `previous_id`, an optional `(datasource, pk)`
  and a `lineage` pointer `lineage:<job_id>:<id>` resolvable in `Lineage`.
- A jitter `percent` above ~2% on a routine daily load usually means a
  threshold or blocking change moved many records, or a big bulk load — compare
  `Unified_Changes_Clusters` for `split`/`merged` rows and inspect them in the
  UI (`/ui/cluster/<aurora_id>` shows the edges that formed the cluster).

## Troubleshooting

- `ModuleNotFoundError: distutils` — Python 3.12 + PySpark 3.5: `pip install setuptools` (included in the `[spark]` extra).
- `Java gateway process exited` — install JDK 17 and make sure `java` is on PATH.
- Delta jar download hangs — set `storage.format: parquet` or pass `--format parquet`.
- Slow runs — lower `blocking.*.max_block_size`, raise `spark.shuffle_partitions`, or run a smaller `--size`.
