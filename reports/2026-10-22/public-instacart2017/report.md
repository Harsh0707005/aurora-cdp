# Evaluation report — `public-instacart2017`

_Generated 2026-10-22T11:10:13 · dataset `sample-50000` · resolver `aurora_cdp` · threshold 0.6 (engine scale 3.0) · block cap 100 · seed 20261022_

## Provenance

```json
{
  "adapter": "aurora_cdp",
  "aurora_cdp_commit": "08be538f5996b0a909a71b047d33d5b696b470b3",
  "aurora_cdp_commit_source": "git",
  "aurora_cdp_dirty_worktree": true,
  "aurora_cdp_path": "/Users/harshmaster/Desktop/Projects/aurora-cdp",
  "aurora_cdp_version": "0.1.0",
  "harness_commit": "01795d854517e2c3a1540f4f0290be9ec53bf450",
  "harness_version": "0.1.0",
  "seed": 20261022,
  "dataset": "/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/public/instacart2017/sample-50000",
  "run_at": "2026-10-22T05:39:28+00:00",
  "host": {
    "platform": "macOS",
    "platform_release": "25.5.0",
    "machine": "arm64",
    "python": "3.11.11",
    "cpu_count": 8,
    "mem_total_gb": 8.59,
    "hostname": "Harshs-Macbook-Air"
  },
  "run_name": "public-instacart2017",
  "input_hash": "f1b484a7e469e95895ae",
  "dataset_manifest_fingerprint": 10527857023365178332,
  "dataset_seed": null,
  "sample": null
}
```

<details><summary><code>adapter config</code></summary>

```json
{
  "cdp_path": null,
  "config": null,
  "threshold": 0.6,
  "datasource_column": "source",
  "datasource": "input",
  "windows": 4,
  "deterministic_ids": true,
  "seed": 20261022,
  "isolate_windows": false,
  "max_stored_pairs": 20000000,
  "epoch": "2026-01-01",
  "window_days": 30,
  "retries": 1,
  "timeout_s": null,
  "threshold_raw": 3.0,
  "score_scale": 5.0,
  "engine_path": "/Users/harshmaster/Desktop/Projects/aurora-cdp"
}
```

</details>

<details><summary><code>aurora_cdp_config (resolved / expanded)</code></summary>

```json
{
  "workspace": ".aurora",
  "outputs_dir": "outputs",
  "db_file": "aurora.duckdb",
  "normalize": {
    "default_region": "US",
    "phone_use_last10_for_match": true,
    "email_strip_plus_tag": true,
    "email_strip_gmail_dots": false,
    "email_junk_local_parts": [
      "test",
      "no",
      "none",
      "reservation",
      "admin",
      "contact",
      "guest",
      "info",
      "noreply",
      "no-reply",
      "donotreply",
      "unknown"
    ],
    "address_abbreviations": {
      "ST": "STREET",
      "AVE": "AVENUE",
      "RD": "ROAD",
      "BLVD": "BOULEVARD",
      "DR": "DRIVE",
      "LN": "LANE",
      "CT": "COURT",
      "STE": "SUITE",
      "APT": "APARTMENT",
      "N": "NORTH",
      "S": "SOUTH",
      "E": "EAST",
      "W": "WEST",
      "1ST": "FIRST",
      "2ND": "SECOND",
      "3RD": "THIRD"
    }
  },
  "blocklist": {
    "email_max_given_names": 20,
    "email_max_surnames": 20,
    "phone_max_given_names": 20,
    "address_max_given_names": 40
  },
  "blocking": {
    "block_size_limit": 100,
    "fk_block_size_limit": 1000,
    "strategies": [
      {
        "name": "email_exact",
        "type": "email"
      },
      {
        "name": "phone_exact",
        "type": "phone"
      },
      {
        "name": "name_postal",
        "type": "name_postal"
      },
      {
        "name": "name_birthdate",
        "type": "name_birthdate"
      },
      {
        "name": "loy_id_exact",
        "type": "loy_id"
      },
      {
        "name": "ck_exact",
        "type": "ck"
      },
      {
        "name": "fk",
        "type": "fk"
      }
    ]
  },
  "matcher": {
    "match_threshold": 3.0,
    "deterministic": {
      "ck_exact_score": 5.0,
      "loy_exact_score": 5.0,
      "email_exact_with_name_score": 4.5,
      "phone_exact_with_name_score": 4.2,
      "name_agreement_min": 0.85
    },
    "weights": {
      "bias": -2.5,
      "given_sim": 1.0,
      "surname_sim": 1.2,
      "email_exact": 3.0,
      "email_sim": 0.5,
      "email_sim_min": 0.92,
      "phone_exact": 2.5,
      "address_sim": 1.2,
      "postal_exact": 0.6,
      "birthdate_exact": 1.5,
      "fk_shared": 1.0,
      "name_mismatch_penalty": -1.5,
      "birthdate_conflict": -3.0
    },
    "hard_conflicts": {
      "birthdate": true,
      "birthdate_typo_tolerance": 2
    }
  },
  "cluster": {
    "supersized_min_size": 500,
    "conflict_attributes": [
      "birthdate"
    ]
  },
  "stable_id": {
    "enabled": true,
    "jitter_alert_pct": 2.0
  },
  "survivorship": {
    "source_priority": {
      "loyalty": 1,
      "crm": 2,
      "ecommerce": 3,
      "pos": 4
    },
    "field_priority": {},
    "recency_field": "update_dt",
    "attributes": [
      "given_name",
      "surname",
      "email",
      "phone",
      "address",
      "address2",
      "city",
      "state",
      "postal",
      "country",
      "birthdate"
    ]
  },
  "sources": {},
  "tuning": {
    "thresholds": [
      2.0,
      2.5,
      3.0,
      3.5,
      4.0
    ],
    "min_precision": 0.98
  }
}
```

</details>

## Limitations

- Public-corpus sanity check on a 50,000-profile sample (whole customers sampled, seed 20261022); the full corpus was not evaluated locally. See aurora-eval-harness/datasets/public/instacart2017/README.md for the mapping and the pseudonymous loy_id assumption (recall ceiling ~0.64).

## Key metrics

```
pairwise P=1.000 R=0.639 F1=0.780 | B3 F1=0.796 | false-merge clusters=0.00% (profiles 0.00%) | split persons=85.45% | ID churn/30d mean=0.00% max=0.00%
```

| Metric | Value |
|---|---|
| Pairwise precision / recall / F1 | 1.000 / 0.639 / 0.780 |
| Pairs: TP / FP / FN | 495,406 / 0 / 279,739 |
| B-cubed precision / recall / F1 | 1.000 / 0.660 / 0.796 |
| Clusters predicted / truth persons (ratio) | 13,157 / 3,106 (4.236) |
| Exact-match clusters | 452 (14.55% of persons) |
| **False-merge rate** (clusters / profiles / pairs) | 0.00% / 0.00% / 0.00% |
| Over-merged clusters (max persons in one) | 0 (1) |
| Split persons (profiles) | 2,654 = 85.45% (94.69% of profiles) |
| **ID churn per 30-day window** mean / max | 0.00% / 0.00% |
| Harmful share of churn (purity dropped) | 0.00% |

> **Notes**
> - Engine scores are normalised from the 0–5 band scale to [0, 1] (score/5); the operating threshold 0.60 is the engine's 3.0 on its own scale.
> - The threshold sweep re-clusters engine pair scores with plain connected components, so it approximates (does not reproduce) the engine's conflict-aware clustering at other thresholds.

## Dataset

| | |
|---|---|
| profiles | 50,017 |
| persons | 3,106 |
| true_pairs | 775,145 |
| profiles_per_person_max | 100 |
| singleton_persons | 0 |

## Resolver run

| | |
|---|---|
| time: engine_load | 1.25s |
| time: engine_blocking | 0.59s |
| time: engine_scoring | 18.31s |
| time: engine_clustering | 3.14s |
| time: engine_stable_id | 0.37s |
| time: engine_persist | 1.56s |
| time: resolve_windows | 40.4s |
| time: wall_total | 42.61s |
| candidate pairs | 495,406 |
| block `engine (final snapshot)` | 495,406 pairs, 3,093 groups, 0 over cap (n/a) |

Engine snapshots (one engine run per replayed window; `previous=` carries stable ids forward):

| window | run_date | records | pairs scored | edges | clusters | skipped blocks | jitter % | ids minted | ids retired | engine s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2017-01-31 | 9,003 | 9,461 | 9,461 | 4,700 | 0 | 0.0 | 4700 | 0 | 1.66 |
| 4 | 2017-05-31 | 32,585 | 158,925 | 158,925 | 9,671 | 0 | 0.0 | 4971 | 0 | 8.5 |
| 8 | 2017-09-28 | 45,395 | 369,040 | 369,040 | 12,217 | 0 | 0.0 | 2546 | 0 | 14.83 |
| 12 | 2018-01-26 | 50,017 | 495,406 | 495,406 | 13,157 | 0 | 0.0 | 940 | 0 | 15.41 |

## Threshold sweep (final window)

| threshold | precision | recall | F1 | B³ F1 | false-merge clusters | split persons | clusters |
|---|---|---|---|---|---|---|---|
| 0.30 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.35 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.40 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.45 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.50 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.55 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.60 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.65 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.70 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.75 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.80 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.85 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.90 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |
| 0.95 | 1.000 | 0.639 | 0.780 | 0.796 | 0.00% | 85.45% | 13,157 |

Best F1 on this grid: threshold **0.30** (F1 0.780). Run `scripts/tune.py` for finer grids, precision-constrained objectives and weight search.

![sweep](plots/sweep.png)

## Clusters

![cluster sizes](plots/cluster_sizes.png)

| | predicted | truth |
|---|---|---|
| mean | 3.80 | 16.10 |
| p50 | 1.00 | 10.00 |
| p90 | 10.00 | 36.00 |
| p99 | 41.00 | 85.95 |
| max | 87 | 100 |
| singletons | 10,064 | 0 |

## Over-merge detector

0 predicted clusters conflate ≥2 persons, covering 0 profiles and 0 persons. 0 accepted edges cross a person boundary.

Which agreeing feature carried the bad edges (an edge can count in several columns; `only` = that feature was the sole agreement):

| feature | bad edges agreeing | sole agreement |
|---|---|---|
| email | 0 | 0 |
| phone | 0 | 0 |
| dob | 0 | 0 |
| postal | 0 | 0 |
| name | 0 | 0 |
| addr | 0 | 0 |
| engine_deterministic | 0 | 0 |
| engine_scored | 0 | 0 |
| engine_trivial_duplicate | 0 | 0 |

## ID churn per 30-day window

Churn = carried-over profiles whose stable cluster id changed vs the previous window. *merge* = the profile's whole previous cluster was absorbed; *split* = otherwise. *harmful* = the profile's new cluster is less pure for its true person than the old one.

![churn](plots/churn.png)

| window | profiles | clusters | new | carried | churned | churn rate | merge | split | harmful | justified |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 9,003 | 4,700 | – | – | – | – | – | – | – | – |
| 4 | 32,585 | 9,671 | 23,582 | 9,003 | 0 | 0.00% | 0 | 0 | 0 | 0 |
| 8 | 45,395 | 12,217 | 12,810 | 32,585 | 0 | 0.00% | 0 | 0 | 0 | 0 |
| 12 | 50,017 | 13,157 | 4,622 | 45,395 | 0 | 0.00% | 0 | 0 | 0 | 0 |

Quality per window snapshot:

| window | profiles | precision | recall | F1 | false-merge clusters |
|---|---|---|---|---|---|
| 0 | 9,003 | 1.000 | 0.647 | 0.785 | 0.00% |
| 4 | 32,585 | 1.000 | 0.637 | 0.778 | 0.00% |
| 8 | 45,395 | 1.000 | 0.639 | 0.780 | 0.00% |
| 12 | 50,017 | 1.000 | 0.639 | 0.780 | 0.00% |

## Resources

Wall 44.4s · peak RSS 1,402 MB · mean CPU 99% (peak 112%, 8 cores) · 43 samples @ 1.0s

![resources](plots/resources.png)

| stage | wall s | peak RSS MB | mean CPU % |
|---|---|---|---|
| resolve:w0 | 1.9 | 333 | 99 |
| resolve:w4 | 8.9 | 743 | 98 |
| resolve:w8 | 15.4 | 989 | 99 |
| resolve:w12 | 16.0 | 1,383 | 100 |
| persist | 0.6 | 1,395 | 103 |
| metrics | 1.0 | 1,402 | 94 |
| report | 0.0 | 1,385 | 98 |

## Failures and retries

0 stage failure(s), 0 retry(ies). Full log: `events.jsonl`.

## Metric validation

17 golden/sanity cases, 91 hand-computed checks run through `aurora_eval.score` (the reports' own code path) — **ALL PASSED**. Metrics marked *untrusted* have no independent check and must not be used for gating.

| metric | status | basis |
|---|---|---|
| pairwise.precision/recall/f1 | ✅ validated | A: pairwise |
| pairwise.tp/fp/fn pairs | ✅ validated | A: pairwise |
| cluster.bcubed_precision/recall/f1 | ✅ validated | A: B-cubed |
| cluster.false_merge (cluster/profile/pair) | ✅ validated | A: false-merge |
| cluster.split (persons/profiles) | ✅ validated | A: split |
| cluster.exact_match_rate / cluster_count_ratio | ✅ validated | A: exact / ratio |
| cluster.pred_size_dist / truth_size_dist | ✅ validated | A: size distributions |
| churn.rate / merge vs split | ✅ validated | C: churn rate, merge vs split |
| churn.harmful vs justified | ✅ validated | C: harmful vs justified |
| curves.blocking_recall | ✅ validated | A: blocking recall |
| curves.auc_roc / average_precision | ✅ validated | A: ROC / PR |
| curves.operating_point | ✅ validated | A: operating point @0.75 |
| per_window quality | ✅ validated | C: per-window quality |
| sanity: perfect input | ✅ validated | perfect prediction |
| sanity: all-singleton input | ✅ validated | all singletons |
| sanity: all-merged input | ✅ validated | everything merged |
| sanity: disjoint prediction | ✅ validated | disjoint prediction |
| sanity: disjoint pairs file | ✅ validated | pairs file with no true pair |
| threshold_sweep | ≈ approximation | approximation — harness connected components over engine pair scores; not the engine's conflict-aware clustering |
| overmerge.dominant_feature | ⚠️ untrusted | untrusted — attribution by engine match_type only (engine pair features are not exported) |
| curves.score_hist | ⚠️ untrusted | untrusted — diagnostic histogram, no golden case |
| engine.metrics (pairs_blocked, skipped_blocks, cluster_size_distribution, timings) | ⚠️ untrusted | untrusted — reported verbatim from the engine, not independently recomputed |
| engine.jitter_pct per snapshot | ✅ cross-checked | engine jitter == harness churn rate per window |

## Reproduce

```bash
# dataset: /Users/harshmaster/Documents/aanya/datasets/aurora-testdata/public/instacart2017/sample-50000
python -m aurora_eval.cli run --adapter aurora_cdp --windows 4 --seed 20261022 --date 2026-10-22 --force --dataset /Users/harshmaster/Documents/aanya/datasets/aurora-testdata/public/instacart2017/sample-50000 --run-name public-instacart2017 --limitation Public-corpus sanity check on a 50,000-profile sample (whole customers sampled, seed 20261022); the full corpus was not evaluated locally. See aurora-eval-harness/datasets/public/instacart2017/README.md for the mapping and the pseudonymous loy_id assumption (recall ceiling ~0.64).
# resume after interruption: same command (checkpoints in /Users/harshmaster/Desktop/Projects/aurora-eval-harness/runs/public-instacart2017/checkpoints)
```

## Files

- `metrics.json` — everything above, machine-readable (same shape as `aurora_eval.score()` output)
- `plots/` — PNGs embedded here
- `overmerge_clusters.json`, `overmerge_edges.parquet` — drill-down for the detector
- `provenance.json`, `resources.jsonl`, `events.jsonl`, `state.json` — provenance, resource samples, failure/retry log, stage state
