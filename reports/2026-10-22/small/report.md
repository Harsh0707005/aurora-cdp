# Evaluation report — `small`

_Generated 2026-10-22T11:05:36 · dataset `small` · resolver `aurora_cdp` · threshold 0.6 (engine scale 3.0) · block cap 100 · seed 20261022_

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
  "dataset": "/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/small",
  "run_at": "2026-10-22T05:35:17+00:00",
  "host": {
    "platform": "macOS",
    "platform_release": "25.5.0",
    "machine": "arm64",
    "python": "3.11.11",
    "cpu_count": 8,
    "mem_total_gb": 8.59,
    "hostname": "Harshs-Macbook-Air"
  },
  "run_name": "small",
  "input_hash": "78760074ab1a77b34fd4",
  "dataset_manifest_fingerprint": 1314847783426890627,
  "dataset_seed": 42,
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
  "windows": "replay",
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

## Key metrics

```
pairwise P=0.980 R=0.649 F1=0.781 | B3 F1=0.931 | false-merge clusters=1.75% (profiles 4.54%) | split persons=36.20% | ID churn/30d mean=1.65% max=2.10% | AUC-ROC=0.919 AP=0.997 blocking-recall=0.537
```

| Metric | Value |
|---|---|
| Pairwise precision / recall / F1 | 0.980 / 0.649 / 0.781 |
| Pairs: TP / FP / FN | 194,139 / 3,888 / 105,107 |
| B-cubed precision / recall / F1 | 0.987 / 0.881 / 0.931 |
| Clusters predicted / truth persons (ratio) | 3,323 / 2,000 (1.661) |
| Exact-match clusters | 1,217 (60.85% of persons) |
| **False-merge rate** (clusters / profiles / pairs) | 1.75% / 4.54% / 1.96% |
| Over-merged clusters (max persons in one) | 58 (4) |
| Split persons (profiles) | 724 = 36.20% (52.07% of profiles) |
| **ID churn per 30-day window** mean / max | 1.65% / 2.10% |
| Harmful share of churn (purity dropped) | 9.75% |
| AUC-ROC / average precision (candidate pairs) | 0.919 / 0.997 |
| Blocking recall (true pairs reaching scoring) | 0.537 |
| Operating point P / R-in-candidates / effective R | 0.987 / 0.997 / 0.535 |
| Scored candidate pairs (stored fraction) | 166,297 (100.00%) |

> **Notes**
> - Engine scores are normalised from the 0–5 band scale to [0, 1] (score/5); the operating threshold 0.60 is the engine's 3.0 on its own scale.
> - The threshold sweep re-clusters engine pair scores with plain connected components, so it approximates (does not reproduce) the engine's conflict-aware clustering at other thresholds.

## Dataset

| | |
|---|---|
| persons | 2,000 |
| persons_with_profiles | 2,000 |
| profiles | 20,000 |
| months | 6 |
| true_pairs | 299,246 |
| households | 131 |
| movers | 198 |
| exact_duplicates | 1,864 |
| profiles_per_person_max | 368 |

Regenerate: `python scripts/generate.py --tier small --seed 42`

## Resolver run

| | |
|---|---|
| time: engine_load | 0.87s |
| time: engine_blocking | 0.31s |
| time: engine_scoring | 6.49s |
| time: engine_clustering | 1.12s |
| time: engine_stable_id | 0.12s |
| time: engine_persist | 0.93s |
| time: resolve_windows | 16.97s |
| time: wall_total | 17.75s |
| candidate pairs | 166,297 |
| block `engine (final snapshot)` | 166,297 pairs, 5,860 groups, 5 over cap (n/a) |

Engine snapshots (one engine run per replayed window; `previous=` carries stable ids forward):

| window | run_date | records | pairs scored | edges | clusters | skipped blocks | jitter % | ids minted | ids retired | engine s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2026-01-31 | 3,213 | 5,684 | 5,499 | 1,499 | 0 | 0.0 | 1499 | 0 | 0.9 |
| 1 | 2026-03-02 | 6,614 | 22,937 | 22,266 | 2,117 | 0 | 1.6807 | 660 | 42 | 1.21 |
| 2 | 2026-04-01 | 9,981 | 51,598 | 49,954 | 2,469 | 1 | 2.1016 | 413 | 61 | 2.05 |
| 3 | 2026-05-01 | 13,381 | 84,033 | 81,167 | 2,741 | 3 | 2.0639 | 358 | 86 | 3.1 |
| 4 | 2026-05-31 | 16,720 | 119,960 | 117,221 | 3,051 | 4 | 1.3228 | 359 | 49 | 4.6 |
| 5 | 2026-06-30 | 20,000 | 166,297 | 162,231 | 3,323 | 5 | 1.0945 | 320 | 48 | 5.11 |

## Score quality (candidate pairs)

![ROC](plots/roc.png) ![PR](plots/pr.png)

![score histogram](plots/score_hist.png)

## Threshold sweep (final window)

| threshold | precision | recall | F1 | B³ F1 | false-merge clusters | split persons | clusters |
|---|---|---|---|---|---|---|---|
| 0.30 | 0.914 | 0.655 | 0.763 | 0.919 | 2.45% | 34.35% | 3,187 |
| 0.35 | 0.914 | 0.655 | 0.763 | 0.919 | 2.45% | 34.35% | 3,187 |
| 0.40 | 0.914 | 0.655 | 0.763 | 0.919 | 2.45% | 34.35% | 3,187 |
| 0.45 | 0.914 | 0.655 | 0.763 | 0.919 | 2.35% | 34.35% | 3,191 |
| 0.50 | 0.914 | 0.655 | 0.763 | 0.919 | 2.35% | 34.45% | 3,193 |
| 0.55 | 0.917 | 0.655 | 0.764 | 0.921 | 2.12% | 34.60% | 3,212 |
| 0.60 | 0.919 | 0.655 | 0.765 | 0.921 | 2.08% | 34.60% | 3,217 |
| 0.65 | 0.923 | 0.655 | 0.766 | 0.922 | 2.01% | 34.75% | 3,232 |
| 0.70 | 0.922 | 0.654 | 0.766 | 0.922 | 2.01% | 34.85% | 3,236 |
| 0.75 | 0.923 | 0.651 | 0.764 | 0.919 | 1.98% | 36.40% | 3,284 |
| 0.80 | 0.924 | 0.640 | 0.756 | 0.913 | 1.87% | 39.70% | 3,423 |
| 0.85 | 0.930 | 0.534 | 0.678 | 0.813 | 1.13% | 68.35% | 5,153 |
| 0.90 | 0.974 | 0.377 | 0.544 | 0.622 | 0.29% | 87.55% | 8,627 |
| 0.95 | 0.984 | 0.268 | 0.421 | 0.505 | 0.17% | 91.35% | 9,971 |

Best F1 on this grid: threshold **0.65** (F1 0.766). Run `scripts/tune.py` for finer grids, precision-constrained objectives and weight search.

![sweep](plots/sweep.png)

## Clusters

![cluster sizes](plots/cluster_sizes.png)

| | predicted | truth |
|---|---|---|
| mean | 6.02 | 10.00 |
| p50 | 2.00 | 6.00 |
| p90 | 15.00 | 21.00 |
| p99 | 42.78 | 55.02 |
| max | 129 | 368 |
| singletons | 1,430 | 113 |

## Over-merge detector

58 predicted clusters conflate ≥2 persons, covering 907 profiles and 124 persons. 2,082 accepted edges cross a person boundary.

Which agreeing feature carried the bad edges (an edge can count in several columns; `only` = that feature was the sole agreement):

| feature | bad edges agreeing | sole agreement |
|---|---|---|
| engine_scored | 1,993 | 1,993 |
| engine_deterministic | 89 | 89 |
| email | 0 | 0 |
| phone | 0 | 0 |
| dob | 0 | 0 |
| postal | 0 | 0 |
| name | 0 | 0 |
| addr | 0 | 0 |
| engine_trivial_duplicate | 0 | 0 |

Worst clusters (full list in `overmerge_clusters.json`, edges in `overmerge_edges.parquet`):

| cluster | persons | profiles | dominant feature | sample names by person |
|---|---|---|---|---|
| `w0-7b58aa4b1d968ec2` | 4 | 18 | engine_scored | ps_0001290: Steven, steven dvis; ps_0001220: James Davis, james davis; ps_0000858: Christopher Davis; ps_0000080: Frank Davis, f davis |
| `w0-58f11bbee4bf5646` | 3 | 104 | engine_scored | ps_0000762: james rodriguez; ps_0001010: Patrick Rodriguez, paddy rodriguez; ps_0001991: Jack Rodriguez, jack rodriguez |
| `w0-48a87a2e3d49ec6b` | 3 | 61 | engine_scored | ps_0000325: Alex Lin, alexander lin; ps_0000800: Betty Lin, betty; ps_0001987: trish lin |
| `w0-b95b440e1bac9f6d` | 3 | 27 | engine_scored | ps_0001095: matthew smith, matthew ssmith; ps_0000362: John Smith, john smith; ps_0001041: raymod smith, raymond smith |
| `w0-ad2d6dfb3f10e2ce` | 3 | 22 | engine_scored | ps_0001314: James Rodriguez; ps_0000640: Margaret Rodriguez; ps_0001237: anthony rodriguez, tony rodriguez |
| `w1-ca74b78d5cbfbfb3` | 3 | 19 | engine_scored | ps_0000140: Joshua Dunn, joshua dunn; ps_0000682: James Dunm, james dunn; ps_0001458: riya dunn |
| `w0-c147442332addb32` | 3 | 15 | engine_deterministic | ps_0001434: Bobby Smith, Robert Smith; ps_0000715: Robert Smith, robert smith; ps_0001974: Rob, rogert simth |
| `w3-18d8f3a26014d957` | 3 | 15 | engine_scored | ps_0001178: Michael, michael mith; ps_0000349: J SMITH, James Smiht; ps_0000697: nicholas smith |
| `w0-6c90db3ecdd0e6ea` | 3 | 13 | engine_scored | ps_0000617: Thomas Smith; ps_0000066: Jason Smith, jason smith; ps_0000128: James Smith |
| `w2-8614aa45e6fd236b` | 3 | 12 | engine_scored | ps_0000167: Shirley Huang; ps_0000306: Christopher Huang, c huang; ps_0000939: jsmes huang |
| `w0-b192a5e969176646` | 3 | 11 | engine_scored | ps_0000008: John Soctt, john scott; ps_0001502: Charles Scott; ps_0001336: Robert Csott, Robert Scoft |
| `w0-433fbc8805540270` | 3 | 10 | engine_scored | ps_0001516: John Cruz, john cruz; ps_0000653: Michael Cruz, Mike Cruz; ps_0000203: john cruz |

## ID churn per 30-day window

Churn = carried-over profiles whose stable cluster id changed vs the previous window. *merge* = the profile's whole previous cluster was absorbed; *split* = otherwise. *harmful* = the profile's new cluster is less pure for its true person than the old one.

![churn](plots/churn.png)

| window | profiles | clusters | new | carried | churned | churn rate | merge | split | harmful | justified |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 3,213 | 1,499 | – | – | – | – | – | – | – | – |
| 1 | 6,614 | 2,117 | 3,401 | 3,213 | 54 | 1.68% | 47 | 7 | 8 | 46 |
| 2 | 9,981 | 2,469 | 3,367 | 6,614 | 139 | 2.10% | 76 | 63 | 16 | 123 |
| 3 | 13,381 | 2,741 | 3,400 | 9,981 | 206 | 2.06% | 124 | 82 | 7 | 199 |
| 4 | 16,720 | 3,051 | 3,339 | 13,381 | 177 | 1.32% | 69 | 108 | 18 | 159 |
| 5 | 20,000 | 3,323 | 3,280 | 16,720 | 183 | 1.09% | 70 | 113 | 25 | 158 |

Quality per window snapshot:

| window | profiles | precision | recall | F1 | false-merge clusters |
|---|---|---|---|---|---|
| 0 | 3,213 | 0.989 | 0.865 | 0.923 | 0.93% |
| 1 | 6,614 | 0.992 | 0.889 | 0.938 | 1.42% |
| 2 | 9,981 | 0.986 | 0.850 | 0.913 | 1.66% |
| 3 | 13,381 | 0.985 | 0.752 | 0.853 | 1.64% |
| 4 | 16,720 | 0.982 | 0.681 | 0.804 | 1.57% |
| 5 | 20,000 | 0.980 | 0.649 | 0.781 | 1.75% |

## Resources

Wall 19.0s · peak RSS 865 MB · mean CPU 97% (peak 100%, 8 cores) · 19 samples @ 1.0s

![resources](plots/resources.png)

| stage | wall s | peak RSS MB | mean CPU % |
|---|---|---|---|
| resolve:w0 | 1.0 | 307 | 77 |
| resolve:w1 | 1.3 | 357 | 98 |
| resolve:w2 | 2.1 | 475 | 98 |
| resolve:w3 | 3.2 | 656 | 99 |
| resolve:w4 | 4.7 | 743 | 98 |
| resolve:w5 | 5.3 | 865 | 99 |
| metrics | 0.8 | 800 | 93 |
| report | 0.0 | 803 | 97 |

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
# dataset: /Users/harshmaster/Documents/aanya/datasets/aurora-testdata/small  (regenerate: python scripts/generate.py --tier small --seed 42)
python -m aurora_eval.cli run --adapter aurora_cdp --dataset small --seed 20261022 --run-name small --date 2026-10-22 --force
# resume after interruption: same command (checkpoints in /Users/harshmaster/Desktop/Projects/aurora-eval-harness/runs/small/checkpoints)
```

## Files

- `metrics.json` — everything above, machine-readable (same shape as `aurora_eval.score()` output)
- `plots/` — PNGs embedded here
- `overmerge_clusters.json`, `overmerge_edges.parquet` — drill-down for the detector
- `provenance.json`, `resources.jsonl`, `events.jsonl`, `state.json` — provenance, resource samples, failure/retry log, stage state
