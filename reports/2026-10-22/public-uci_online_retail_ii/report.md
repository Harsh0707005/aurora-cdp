# Evaluation report — `public-uci_online_retail_ii`

_Generated 2026-10-22T11:03:41 · dataset `sample-50000` · resolver `aurora_cdp` · threshold 0.6 (engine scale 3.0) · block cap 100 · seed 20261022_

## Provenance

```json
{
  "adapter": "aurora_cdp",
  "aurora_cdp_commit": "08be538f5996b0a909a71b047d33d5b696b470b3",
  "aurora_cdp_commit_source": "git",
  "aurora_cdp_dirty_worktree": false,
  "aurora_cdp_path": "/Users/harshmaster/Desktop/Projects/aurora-cdp",
  "aurora_cdp_version": "0.1.0",
  "harness_commit": "2b160cb3d45caffe557202f1fc37b1e075118051",
  "harness_version": "0.1.0",
  "seed": 20261022,
  "dataset": "/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/public/uci_online_retail_ii/sample-50000",
  "run_at": "2026-10-22T05:33:11+00:00",
  "host": {
    "platform": "macOS",
    "platform_release": "25.5.0",
    "machine": "arm64",
    "python": "3.11.11",
    "cpu_count": 8,
    "mem_total_gb": 8.59,
    "hostname": "Harshs-Macbook-Air"
  },
  "run_name": "public-uci_online_retail_ii",
  "input_hash": "a6229f1c71867e8697a4",
  "dataset_manifest_fingerprint": 7481820924562800300,
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

- Public-corpus sanity check on a 50,000-profile sample (whole customers sampled, seed 20261022); the full corpus was not evaluated locally. See aurora-eval-harness/datasets/public/uci_online_retail_ii/README.md for the mapping and the pseudonymous loy_id assumption (recall ceiling ~0.64).

## Key metrics

```
pairwise P=1.000 R=0.291 F1=0.451 | B3 F1=0.773 | false-merge clusters=0.00% (profiles 0.00%) | split persons=51.14% | ID churn/30d mean=2.34% max=4.26%
```

| Metric | Value |
|---|---|
| Pairwise precision / recall / F1 | 1.000 / 0.291 / 0.451 |
| Pairs: TP / FP / FN | 263,699 / 0 / 641,136 |
| B-cubed precision / recall / F1 | 1.000 / 0.631 / 0.773 |
| Clusters predicted / truth persons (ratio) | 17,722 / 5,942 (2.982) |
| Exact-match clusters | 2,903 (48.86% of persons) |
| **False-merge rate** (clusters / profiles / pairs) | 0.00% / 0.00% / 0.00% |
| Over-merged clusters (max persons in one) | 0 (1) |
| Split persons (profiles) | 3,039 = 51.14% (84.97% of profiles) |
| **ID churn per 30-day window** mean / max | 2.34% / 4.26% |
| Harmful share of churn (purity dropped) | 0.00% |

> **Notes**
> - Engine scores are normalised from the 0–5 band scale to [0, 1] (score/5); the operating threshold 0.60 is the engine's 3.0 on its own scale.
> - The threshold sweep re-clusters engine pair scores with plain connected components, so it approximates (does not reproduce) the engine's conflict-aware clustering at other thresholds.

## Dataset

| | |
|---|---|
| profiles | 44,876 |
| persons | 5,942 |
| true_pairs | 904,835 |
| profiles_per_person_max | 510 |
| singleton_persons | 1,461 |
| raw_invoice_lines_with_customer | 824,364 |

## Resolver run

| | |
|---|---|
| time: engine_load | 0.84s |
| time: engine_blocking | 0.29s |
| time: engine_scoring | 8.02s |
| time: engine_clustering | 2.67s |
| time: engine_stable_id | 0.28s |
| time: engine_persist | 1.93s |
| time: resolve_windows | 23.11s |
| time: wall_total | 24.94s |
| candidate pairs | 263,699 |
| block `engine (final snapshot)` | 263,699 pairs, 4,081 groups, 19 over cap (n/a) |

Engine snapshots (one engine run per replayed window; `previous=` carries stable ids forward):

| window | run_date | records | pairs scored | edges | clusters | skipped blocks | jitter % | ids minted | ids retired | engine s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2009-12-31 | 1,900 | 1,321 | 1,321 | 1,307 | 0 | 0.0 | 1307 | 0 | 0.95 |
| 8 | 2010-08-28 | 14,812 | 67,683 | 67,683 | 6,254 | 1 | 0.5263 | 4947 | 0 | 2.93 |
| 16 | 2011-04-25 | 29,624 | 151,692 | 151,692 | 11,999 | 10 | 4.2601 | 5745 | 0 | 7.94 |
| 24 | 2011-12-21 | 44,876 | 263,699 | 263,699 | 17,722 | 19 | 2.2448 | 5723 | 0 | 11.29 |

## Threshold sweep (final window)

| threshold | precision | recall | F1 | B³ F1 | false-merge clusters | split persons | clusters |
|---|---|---|---|---|---|---|---|
| 0.30 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.35 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.40 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.45 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.50 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.55 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.60 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.65 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.70 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.75 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.80 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.85 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.90 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |
| 0.95 | 1.000 | 0.291 | 0.451 | 0.773 | 0.00% | 51.14% | 17,722 |

Best F1 on this grid: threshold **0.30** (F1 0.451). Run `scripts/tune.py` for finer grids, precision-constrained objectives and weight search.

![sweep](plots/sweep.png)

## Clusters

![cluster sizes](plots/cluster_sizes.png)

| | predicted | truth |
|---|---|---|
| mean | 2.53 | 7.55 |
| p50 | 1.00 | 4.00 |
| p90 | 5.00 | 17.00 |
| p99 | 26.00 | 56.59 |
| max | 100 | 510 |
| singletons | 13,641 | 1,461 |

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
| 0 | 1,900 | 1,307 | – | – | – | – | – | – | – | – |
| 8 | 14,812 | 6,254 | 12,912 | 1,900 | 10 | 0.53% | 0 | 10 | 0 | 10 |
| 16 | 29,624 | 11,999 | 14,812 | 14,812 | 631 | 4.26% | 0 | 631 | 0 | 631 |
| 24 | 44,876 | 17,722 | 15,252 | 29,624 | 665 | 2.24% | 0 | 665 | 0 | 665 |

Quality per window snapshot:

| window | profiles | precision | recall | F1 | false-merge clusters |
|---|---|---|---|---|---|
| 0 | 1,900 | 1.000 | 0.596 | 0.747 | 0.00% |
| 8 | 14,812 | 1.000 | 0.562 | 0.719 | 0.00% |
| 16 | 29,624 | 1.000 | 0.364 | 0.534 | 0.00% |
| 24 | 44,876 | 1.000 | 0.291 | 0.451 | 0.00% |

## Resources

Wall 28.1s · peak RSS 554 MB · mean CPU 87% (peak 98%, 8 cores) · 27 samples @ 1.0s

![resources](plots/resources.png)

| stage | wall s | peak RSS MB | mean CPU % |
|---|---|---|---|
| resolve:w0 | 1.1 | 192 | 53 |
| resolve:w8 | 3.2 | 379 | 95 |
| resolve:w16 | 8.4 | 363 | 84 |
| resolve:w24 | 12.1 | 554 | 92 |
| assemble | 0.3 | 335 | 97 |
| metrics | 2.3 | 173 | 70 |
| report | 0.0 | 270 | 85 |

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
# dataset: /Users/harshmaster/Documents/aanya/datasets/aurora-testdata/public/uci_online_retail_ii/sample-50000
python -m aurora_eval.cli run --adapter aurora_cdp --windows 4 --seed 20261022 --date 2026-10-22 --force --dataset /Users/harshmaster/Documents/aanya/datasets/aurora-testdata/public/uci_online_retail_ii/sample-50000 --run-name public-uci_online_retail_ii --limitation Public-corpus sanity check on a 50,000-profile sample (whole customers sampled, seed 20261022); the full corpus was not evaluated locally. See aurora-eval-harness/datasets/public/uci_online_retail_ii/README.md for the mapping and the pseudonymous loy_id assumption (recall ceiling ~0.64).
# resume after interruption: same command (checkpoints in /Users/harshmaster/Desktop/Projects/aurora-eval-harness/runs/public-uci_online_retail_ii/checkpoints)
```

## Files

- `metrics.json` — everything above, machine-readable (same shape as `aurora_eval.score()` output)
- `plots/` — PNGs embedded here
- `overmerge_clusters.json`, `overmerge_edges.parquet` — drill-down for the detector
- `provenance.json`, `resources.jsonl`, `events.jsonl`, `state.json` — provenance, resource samples, failure/retry log, stage state
