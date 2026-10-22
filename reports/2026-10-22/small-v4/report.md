# Evaluation report — `small-v4`

_Generated 2026-10-22T16:04:44 · dataset `small` · resolver `aurora_cdp` · threshold 0.6 (engine scale 3.0) · block cap 100 · seed 20261022_

## Provenance

```json
{
  "adapter": "aurora_cdp",
  "aurora_cdp_commit": "26bea50c2f4f85b1f46073e1422dd9bb2032ea1f",
  "aurora_cdp_commit_source": "git",
  "aurora_cdp_dirty_worktree": false,
  "aurora_cdp_path": "/Users/harshmaster/Desktop/Projects/aurora-cdp",
  "aurora_cdp_version": "0.1.0",
  "harness_commit": "1211f2017a2dcaf198a4002f7323561ee6e8edca",
  "harness_version": "0.1.0",
  "seed": 20261022,
  "dataset": "/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/small",
  "run_at": "2026-10-22T10:34:26+00:00",
  "host": {
    "platform": "macOS",
    "platform_release": "25.5.0",
    "machine": "arm64",
    "python": "3.11.11",
    "cpu_count": 8,
    "mem_total_gb": 8.59,
    "hostname": "Harshs-Macbook-Air"
  },
  "run_name": "small-v4",
  "input_hash": "7f34a2678c0cdd7e43b0",
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
    "nickname_file": null,
    "address_parsing": false,
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
    "address_max_given_names": 40,
    "manual": {}
  },
  "blocking": {
    "block_size_limit": 100,
    "fk_block_size_limit": 1000,
    "max_pairs_per_block": 500000,
    "refine_target": 100,
    "sn_window": 25,
    "collapse_trivial_dupes": true,
    "persist_blocking_keys": true,
    "strategy_source": "fixed",
    "learned_strategies_file": null,
    "learned_keep_types": [
      "ck",
      "loy_id",
      "fk"
    ],
    "dnf": {
      "max_terms": 2,
      "min_positive_pairs": 200,
      "min_predicate_pc": 0.01,
      "target_pc": 0.95,
      "min_gain_pairs": 5,
      "pairs_per_record_budget": 20,
      "sample_records": 20000,
      "sample_positive_pairs": 5000,
      "sample_seed": 0,
      "labels": "self"
    },
    "refine_keys": {
      "email": [
        "name3",
        "postal",
        "birthdate",
        "update_month",
        "given3"
      ],
      "phone": [
        "name3",
        "postal",
        "birthdate",
        "update_month",
        "given3"
      ],
      "name_postal": [
        "email",
        "phone",
        "birthdate",
        "house_number",
        "update_month"
      ],
      "name_birthdate": [
        "email",
        "phone",
        "postal",
        "house_number",
        "update_month"
      ],
      "name": [
        "postal",
        "birthdate",
        "email",
        "phone",
        "house_number",
        "update_month"
      ],
      "loy_id": [
        "name3",
        "postal",
        "birthdate",
        "update_month"
      ],
      "ck": [
        "name3",
        "postal",
        "birthdate",
        "update_month"
      ],
      "fk": [
        "name3",
        "postal",
        "birthdate",
        "update_month"
      ],
      "dnf": [
        "postal",
        "birthdate",
        "email",
        "phone",
        "name3",
        "update_month"
      ]
    },
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
        "name": "name",
        "type": "name",
        "max_pairs_per_block": 50000
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
    "match_threshold": 3.25,
    "scorer": "rules",
    "ordinal": {
      "model_file": null,
      "retrain": "auto",
      "save_model": true,
      "apply_rules_first": true,
      "levels": 3,
      "self_train_rounds": 3,
      "confidence_margin": 1.0,
      "negatives_per_positive": 2.0,
      "hard_negative_min_disagreements": 2,
      "max_train_pairs": 40000,
      "min_positive_pairs": 300,
      "min_negative_pairs": 300,
      "l2": 0.001,
      "lr": 0.05,
      "epochs": 300,
      "sample_seed": 0,
      "monotone": false
    },
    "score_chunk_size": 250000,
    "persist_features": false,
    "export_expanded_dupe_pairs": true,
    "max_expanded_pairs": 50000000,
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
      "name_mismatch_floor": 0.6,
      "address_house_number_mismatch_cap": 0.3,
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
      "birthdate",
      "given_name"
    ],
    "conflict_tolerances": {
      "birthdate": {
        "measure": "levenshtein_max",
        "value": 2
      },
      "given_name": {
        "measure": "jaro_winkler_min",
        "value": 0.6
      }
    },
    "conflict_columns": {
      "birthdate": "birthdate_norm",
      "given_name": "given_name_canon",
      "surname": "surname_norm",
      "ck": "ck",
      "loy_id": "loy_id_norm"
    }
  },
  "labels": {
    "file": null
  },
  "storage": {
    "duckdb": {
      "memory_limit": "3GB",
      "threads": 4,
      "temp_directory": null,
      "preserve_insertion_order": false
    }
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
pairwise P=0.999 R=0.882 F1=0.937 | B3 F1=0.940 | false-merge clusters=1.01% (profiles 1.12%) | split persons=37.65% | ID churn/30d mean=1.46% max=2.02% | AUC-ROC=0.936 AP=0.977 blocking-recall=0.878
```

| Metric | Value |
|---|---|
| Pairwise precision / recall / F1 | 0.999 / 0.882 / 0.937 |
| Pairs: TP / FP / FN | 264,030 / 300 / 35,216 |
| B-cubed precision / recall / F1 | 0.997 / 0.889 / 0.940 |
| Clusters predicted / truth persons (ratio) | 2,972 / 2,000 (1.486) |
| Exact-match clusters | 1,230 (61.50% of persons) |
| **False-merge rate** (clusters / profiles / pairs) | 1.01% / 1.12% / 0.11% |
| Over-merged clusters (max persons in one) | 30 (3) |
| Split persons (profiles) | 753 = 37.65% (55.12% of profiles) |
| **ID churn per 30-day window** mean / max | 1.46% / 2.02% |
| Harmful share of churn (purity dropped) | 2.75% |
| AUC-ROC / average precision (candidate pairs) | 0.936 / 0.977 |
| Blocking recall (true pairs reaching scoring) | 0.878 |
| Operating point P / R-in-candidates / effective R | 0.990 / 0.813 / 0.713 |
| Scored candidate pairs (stored fraction) | 329,263 (100.00%) |

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
| time: engine_load | 0.35s |
| time: engine_blocking | 4.49s |
| time: engine_scoring | 3.02s |
| time: engine_clustering | 0.56s |
| time: engine_stable_id | 0.12s |
| time: engine_persist | 0.28s |
| time: resolve_windows | 15.18s |
| time: wall_total | 15.99s |
| candidate pairs | 329,263 |
| block `engine (final snapshot)` | 97,863 pairs, 6,896 groups, 0 over cap (n/a) |

Engine snapshots (one engine run per replayed window; `previous=` carries stable ids forward):

| window | run_date | records | pairs scored | edges | clusters | skipped blocks | jitter % | ids minted | ids retired | engine s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2026-01-31 | 3,213 | 8,798 | 3,410 | 1,510 | 0 | 0.0 | 1510 | 0 | 0.75 |
| 1 | 2026-03-02 | 6,614 | 35,373 | 11,484 | 2,141 | 0 | 1.5873 | 672 | 41 | 1.1 |
| 2 | 2026-04-01 | 9,981 | 83,412 | 22,645 | 2,463 | 0 | 1.7539 | 379 | 57 | 1.85 |
| 3 | 2026-05-01 | 13,381 | 149,235 | 35,253 | 2,652 | 0 | 2.0238 | 279 | 90 | 2.77 |
| 4 | 2026-05-31 | 16,720 | 229,027 | 48,318 | 2,834 | 0 | 1.2331 | 229 | 47 | 3.77 |
| 5 | 2026-06-30 | 20,000 | 329,263 | 62,124 | 2,972 | 0 | 0.7237 | 182 | 44 | 4.94 |

## Score quality (candidate pairs)

![ROC](plots/roc.png) ![PR](plots/pr.png)

![score histogram](plots/score_hist.png)

## Threshold sweep (final window)

| threshold | precision | recall | F1 | B³ F1 | false-merge clusters | split persons | clusters |
|---|---|---|---|---|---|---|---|
| 0.30 | 0.254 | 0.971 | 0.402 | 0.817 | 13.94% | 12.75% | 1,600 |
| 0.35 | 0.268 | 0.971 | 0.420 | 0.828 | 12.97% | 12.80% | 1,634 |
| 0.40 | 0.352 | 0.970 | 0.517 | 0.850 | 12.04% | 12.90% | 1,702 |
| 0.45 | 0.931 | 0.931 | 0.931 | 0.935 | 3.62% | 31.20% | 2,597 |
| 0.50 | 0.932 | 0.921 | 0.927 | 0.931 | 3.31% | 33.70% | 2,691 |
| 0.55 | 0.934 | 0.921 | 0.927 | 0.933 | 2.99% | 33.90% | 2,712 |
| 0.60 | 0.937 | 0.921 | 0.929 | 0.934 | 2.91% | 33.90% | 2,719 |
| 0.65 | 0.943 | 0.921 | 0.932 | 0.936 | 2.70% | 34.20% | 2,744 |
| 0.70 | 0.943 | 0.920 | 0.932 | 0.936 | 2.69% | 34.30% | 2,748 |
| 0.75 | 0.944 | 0.915 | 0.929 | 0.933 | 2.65% | 35.85% | 2,797 |
| 0.80 | 0.944 | 0.895 | 0.919 | 0.926 | 2.52% | 39.40% | 2,934 |
| 0.85 | 0.950 | 0.757 | 0.842 | 0.827 | 1.45% | 68.35% | 4,680 |
| 0.90 | 0.983 | 0.609 | 0.752 | 0.643 | 0.43% | 87.55% | 8,141 |
| 0.95 | 0.991 | 0.478 | 0.645 | 0.527 | 0.28% | 91.35% | 9,503 |

Best F1 on this grid: threshold **0.65** (F1 0.932). Run `scripts/tune.py` for finer grids, precision-constrained objectives and weight search.

![sweep](plots/sweep.png)

## Clusters

![cluster sizes](plots/cluster_sizes.png)

| | predicted | truth |
|---|---|---|
| mean | 6.73 | 10.00 |
| p50 | 3.00 | 6.00 |
| p90 | 16.00 | 21.00 |
| p99 | 45.58 | 55.02 |
| max | 353 | 368 |
| singletons | 947 | 113 |

## Over-merge detector

30 predicted clusters conflate ≥2 persons, covering 224 profiles and 58 persons. 2,163 accepted edges cross a person boundary.

Which agreeing feature carried the bad edges (an edge can count in several columns; `only` = that feature was the sole agreement):

| feature | bad edges agreeing | sole agreement |
|---|---|---|
| engine_scored | 2,052 | 2,052 |
| engine_deterministic | 89 | 89 |
| engine_trivial_duplicate | 22 | 22 |
| email | 0 | 0 |
| phone | 0 | 0 |
| dob | 0 | 0 |
| postal | 0 | 0 |
| name | 0 | 0 |
| addr | 0 | 0 |

Worst clusters (full list in `overmerge_clusters.json`, edges in `overmerge_edges.parquet`):

| cluster | persons | profiles | dominant feature | sample names by person |
|---|---|---|---|---|
| `w0-c147442332addb32` | 3 | 15 | engine_deterministic | ps_0001434: Bobby Smith, Robert Smith; ps_0000715: Robert Smith, robert smith; ps_0001974: Rob, rogert simth |
| `w0-660abc5d6b5852a0` | 2 | 28 | engine_scored | ps_0000504: Brian Cunningham, brian cunninfham; ps_0001171: B Cunningham |
| `w2-e99245b5bee51ff9` | 2 | 17 | engine_scored | ps_0000234: SNEHA BUTLER, Sneha Butler; ps_0001478: joshua butler |
| `w0-71d5ca1e5b80d050` | 2 | 15 | engine_scored | ps_0001551: Mark Martinez, mark martinez; ps_0000063: carol martinez |
| `w0-d8877791092e34e8` | 2 | 13 | engine_scored | ps_0001178: Michael, michael mith; ps_0000697: nicholas smith |
| `w0-28e13d75d332fe8d` | 2 | 11 | engine_scored | ps_0001659: James Brown; ps_0000639: J Brown |
| `w0-9fb62dc93015ce81` | 2 | 11 | engine_scored | ps_0000540: Aisha Brown, aisha brown; ps_0001791: Richard Brown, richard brown |
| `w0-c0e1a22452537e54` | 2 | 11 | engine_scored | ps_0000509: JOH ROGERS, John Rogers; ps_0000152: Jon Rogers, j rogers |
| `w0-6d7f66b09f610fa5` | 2 | 9 | engine_scored | ps_0001017: Janet Miller; ps_0001252: John Miller, john miller |
| `w0-4e96a5ede77b1f31` | 2 | 7 | engine_scored | ps_0000980: Aisha Carter, aisha catrer; ps_0001982: Maria Carter |
| `w0-d032304d26afb6e5` | 2 | 7 | engine_scored | ps_0001478: Joshua Butler; ps_0000234: SNEHA BUTLER, sneha butler |
| `w2-53105f8998c09eec` | 2 | 7 | engine_scored | ps_0001019: Donald Garcia, donald garciia; ps_0001889: Donald Garcia |

## ID churn per 30-day window

Churn = carried-over profiles whose stable cluster id changed vs the previous window. *merge* = the profile's whole previous cluster was absorbed; *split* = otherwise. *harmful* = the profile's new cluster is less pure for its true person than the old one.

![churn](plots/churn.png)

| window | profiles | clusters | new | carried | churned | churn rate | merge | split | harmful | justified |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 3,213 | 1,510 | – | – | – | – | – | – | – | – |
| 1 | 6,614 | 2,141 | 3,401 | 3,213 | 51 | 1.59% | 46 | 5 | 2 | 49 |
| 2 | 9,981 | 2,463 | 3,367 | 6,614 | 116 | 1.75% | 67 | 49 | 5 | 111 |
| 3 | 13,381 | 2,652 | 3,400 | 9,981 | 202 | 2.02% | 134 | 68 | 3 | 199 |
| 4 | 16,720 | 2,834 | 3,339 | 13,381 | 165 | 1.23% | 68 | 97 | 5 | 160 |
| 5 | 20,000 | 2,972 | 3,280 | 16,720 | 121 | 0.72% | 59 | 62 | 3 | 118 |

Quality per window snapshot:

| window | profiles | precision | recall | F1 | false-merge clusters |
|---|---|---|---|---|---|
| 0 | 3,213 | 0.998 | 0.865 | 0.927 | 0.26% |
| 1 | 6,614 | 0.998 | 0.887 | 0.940 | 0.42% |
| 2 | 9,981 | 0.998 | 0.878 | 0.934 | 0.65% |
| 3 | 13,381 | 0.999 | 0.879 | 0.935 | 0.72% |
| 4 | 16,720 | 0.999 | 0.880 | 0.936 | 0.85% |
| 5 | 20,000 | 0.999 | 0.882 | 0.937 | 1.01% |

## Resources

Wall 17.5s · peak RSS 743 MB · mean CPU 100% (peak 117%, 8 cores) · 18 samples @ 1.0s

![resources](plots/resources.png)

| stage | wall s | peak RSS MB | mean CPU % |
|---|---|---|---|
| resolve:w0 | 0.8 | 312 | 80 |
| resolve:w1 | 1.2 | 357 | 102 |
| resolve:w2 | 1.9 | 424 | 101 |
| resolve:w3 | 2.9 | 477 | 101 |
| resolve:w4 | 3.9 | 600 | 101 |
| resolve:w5 | 5.1 | 633 | 102 |
| persist | 0.4 | 726 | 117 |
| metrics | 0.9 | 743 | 86 |
| report | 0.0 | 743 | 98 |

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
python -m aurora_eval.cli run --adapter aurora_cdp --dataset small --seed 20261022 --run-name small-v4 --date 2026-10-22 --reports-root /Users/harshmaster/Desktop/Projects/aurora-cdp/reports
# resume after interruption: same command (checkpoints in /Users/harshmaster/Desktop/Projects/aurora-eval-harness/runs/small-v4/checkpoints)
```

## Files

- `metrics.json` — everything above, machine-readable (same shape as `aurora_eval.score()` output)
- `plots/` — PNGs embedded here
- `overmerge_clusters.json`, `overmerge_edges.parquet` — drill-down for the detector
- `provenance.json`, `resources.jsonl`, `events.jsonl`, `state.json` — provenance, resource samples, failure/retry log, stage state
