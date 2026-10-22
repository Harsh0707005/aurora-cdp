# Evaluating the resolver with aurora-eval-harness

The sibling repository `aurora-eval-harness` owns the metrics; this repo owns the engine. The harness calls the
engine's stable entrypoint (`aurora_cdp.adapters.resolver.resolve_records`, see `docs/interfaces.md`) through its
`aurora_cdp` adapter and writes provenance-stamped reports **into this repo** under `reports/<YYYY-MM-DD>/<run>/`.

## Setup (once)

```bash
cd ../aurora-eval-harness
uv venv .venv --python 3.11 && uv pip install --python .venv/bin/python -e ".[dev]" -e ../aurora-cdp psutil hypothesis
#   (or: python3.11 -m venv .venv && .venv/bin/pip install -e ".[dev]" -e ../aurora-cdp)
.venv/bin/python -c "import aurora_cdp, aurora_eval; print('ok')"
```

The engine is found by import; alternatively `--cdp-path /path/to/aurora-cdp` or `$AURORA_CDP_PATH`. There is no
stub — if the engine cannot be imported the harness fails with instructions.

## Datasets

Seeded synthetic corpora live under `$AURORA_DATA_DIR` (default `~/Documents/aanya/datasets/aurora-testdata/`):

| tier | persons / profiles | regenerate |
|---|---|---|
| `small`  | 2k / 20k   | `python scripts/generate.py --tier small  --seed <SEED>` |
| `medium` | 20k / 200k | `python scripts/generate.py --tier medium --seed <SEED>` |
| `large`  | 100k / 1M  | `python scripts/generate.py --tier large  --seed <SEED>` |

Each directory holds `profiles.{parquet,csv}` (`profile_id, source, created_at, first_name, last_name, email, phone,
dob, address, city, postal_code`), `truth.{parquet,csv}` (`profile_id, person_id`) and `manifest.json` (generator
config incl. the dataset seed, counts, fingerprint). Public PII-free corpora (Instacart 2017, Olist, UCI Online
Retail II) are built by `datasets/public/<name>/build.py` in the harness — see `datasets/public/README.md` there.

## Running

```bash
cd ../aurora-eval-harness
# one tier -> ../aurora-cdp/reports/<today>/small/report.md (+ metrics.json, plots/, provenance.json, ...)
.venv/bin/aurora-eval run --adapter aurora_cdp --dataset small --seed 20261022 --run-name small

# the three tiers of the production-readiness memo (large runs its windows in child processes)
make eval-cdp-tiers EVAL_SEED=20261022 DATE=2026-10-22

# options
.venv/bin/aurora-eval run --adapter aurora_cdp --dataset medium --seed 20261022 --run-name medium \
    --windows replay            # replay | final | <k>: how many 30-day snapshots to resolve (default: every window)
    --threshold 3.0             # engine match_threshold on its 0-5 scale (report shows 0.60 on the harness' [0,1] scale)
    --cdp-config overlay.yaml   # or inline JSON; overlays aurora_cdp/config/defaults.yaml (recorded in provenance)
    --isolate-windows           # each snapshot in a fresh child process (memory returned between windows)
    --sample 50000              # seeded sample of profiles (sanity checks on big corpora; recorded as a limitation)
    --date 2026-10-22 --reports-root ../aurora-cdp/reports --runs-dir runs
    --no-deterministic-ids      # keep raw uuid4 ids (engine production behaviour; output is then not byte-reproducible)

# resume after a crash / kill: run the same command again (per-window checkpoints under runs/<run>/checkpoints/)
# re-running a finished run with identical inputs is a no-op that prints the existing report path
```

`aurora-eval resolve --resolver aurora_cdp ...` + `aurora-eval evaluate ...` is the two-step equivalent; the
file contract (`assignments.csv`, `pairs.csv`) is written in both paths.

## What the adapter does

1. Maps profiles onto the engine's semantic columns (`given_name, surname, email, phone, birthdate, address, city,
   postal, update_dt`, `datasource` = `source`; extras `state, country, loy_id, ck, fk_*` pass through).
2. Replays the timeline: snapshot *w* resolves all records created in 30-day windows `0..w`, passing the previous
   snapshot's assignments as `previous=` so the engine's stable-ID inheritance and jitter report are exercised.
3. Normalises pair scores from the engine's 0–5 band scale to `[0, 1]` (`score / 5`) for ROC/PR and the sweep;
   raw score, `match_category` and `match_type` are kept.
4. Relabels every freshly minted uuid4 to `w<window>-<engine cluster_id>` at mint time (a bijection, so ids stay
   stable and jitter is unchanged) and feeds those labels back as `previous=`. Reason: the engine's equal-overlap
   tie-break sorts on the previous id string, so with raw uuids *which* id survives a 2-way equal merge is random.
   `--no-deterministic-ids` disables this.
5. Checkpoints each window; the runner resumes from the last good stage and never recomputes identical inputs.

## Run names in this repo

`reports/2026-10-22/{small,medium}` are the baseline (engine `08be538`, blocks over the cap skipped);
`small-v2` (`42bd18e`) and `small-v3` (`6d2cf9b`) are the zero-discard engine. Use a new run name per engine
revision so before/after stay side by side; the stress report's "throughput per window" section reads the runs
named `small`/`medium`/`large` only.

Known harness-side expectation that is now obsolete: `tests/test_edge_cases.py` asserts
`engine.skipped_blocks >= 1` for the supersized-cluster case; the engine never skips a block any more
(`skipped_blocks` is always 0, `oversized_blocks` / `records_dropped_by_blocking` report what happened instead).

## Metric validation and stress tests

```bash
.venv/bin/aurora-eval validate                       # 17 golden/sanity cases, 91 hand-computed checks; exit 1 on any failure
.venv/bin/aurora-eval stress --dataset large --seed 20261022 --date 2026-10-22 \
    --sizes 20000,50000,100000,200000,400000 --conc-levels 1,2,4 --max-parallel 4 --flood-scale 20000 --timeout-s 1800
#   -> reports/<date>/stress/{report.md,stress.json}: size ramp to the ceiling actually hit (wall limit / RSS budget),
#      concurrency + backpressure, malformed/partial + duplicate floods, timeout kill path, throughput per 30-day window
```

Every evaluation report embeds the validation result (section *Metric validation*): each reported metric is
**validated** (golden case reproduced through `aurora_eval.score`), **cross-checked** (engine jitter vs harness
churn on the same windows), an **approximation** (threshold sweep) or **untrusted** (no independent check). A failed
golden case puts a red UNTRUSTED banner at the top of the report. `--rebuild-report` recomputes metrics and report
from saved resolve outputs; `--timeout-s` (with `--isolate-windows`) kills and retries a window that exceeds the limit.

## Metrics in every report

Pairwise precision / recall / F1 (exact, via contingency arithmetic), B³ precision / recall / F1, false-merge rate
(cluster-, profile- and pair-weighted), split-person rate, ROC / PR / AP over the engine's scored candidate pairs,
**blocking recall** (true pairs that reached scoring — the engine's block-size limit shows up here), the operating
point at the engine threshold, a threshold sweep (harness connected components over engine pair scores, an
approximation of the engine's conflict-aware clustering), ID churn per 30-day window (harness view: merge vs split,
harmful vs justified) **and** the engine's own jitter report per snapshot (`jitter_pct`, ids minted / retired),
resource curves (CPU %, RSS, wall per stage) and the failure/retry log.

## Provenance

Top of every `report.md` and in `metrics.json` / `provenance.json`:

```json
{
  "adapter": "aurora_cdp",
  "aurora_cdp_commit": "<git rev-parse HEAD of this repo, or the package version if git is unavailable>",
  "aurora_cdp_dirty_worktree": false,
  "aurora_cdp_config": { "...fully expanded defaults.yaml + overlay + threshold..." },
  "seed": 20261022,
  "dataset": "/abs/path/to/the/dataset",
  "dataset_seed": 42,
  "run_at": "2026-10-22T05:30:00+00:00",
  "host": {"platform": "macOS", "python": "3.11.11", "cpu_count": 8, "mem_total_gb": 8.59}
}
```

`seed` is the evaluation seed (stored-pair sampling, public-corpus sampling, synthetic edge cases); the engine
itself is seedless and deterministic given the adapter's id relabelling. `dataset_seed` is the corpus generator's
seed from `manifest.json`.

## Tests that guard the integration (harness repo)

`tests/test_aurora_cdp_adapter.py` (contract, seeded repeatability, permutation invariance, uuid toggle, isolated
windows), `tests/test_runner_resilience.py` (SIGKILL mid-run → resume equals a clean run; idempotent re-run leaves
outputs untouched; retries logged), `tests/test_edge_cases.py` (null-heavy, extreme duplicates, supersized cluster,
adversarial strings) and `tests/test_properties.py` (Hypothesis: never drops keys, permutation-stable ids, no crash
on hostile Unicode). Run `make test` in the harness.
