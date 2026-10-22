# Evaluation report — `small-v5`

_Generated 2026-10-22T16:41:54 · dataset `small` · resolver `aurora_cdp` · threshold 0.6 (engine scale 3.0) · block cap 100 · seed 20261022_

## Provenance

```json
{
  "adapter": "aurora_cdp",
  "aurora_cdp_commit": "f1237325fa2d36c9469b5557f8722806ece954d8",
  "aurora_cdp_commit_source": "git",
  "aurora_cdp_dirty_worktree": false,
  "aurora_cdp_path": "/Users/harshmaster/Desktop/Projects/aurora-cdp",
  "aurora_cdp_version": "0.1.0",
  "harness_commit": "1211f2017a2dcaf198a4002f7323561ee6e8edca",
  "harness_version": "0.1.0",
  "seed": 20261022,
  "dataset": "/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/small",
  "run_at": "2026-10-22T11:11:36+00:00",
  "host": {
    "platform": "macOS",
    "platform_release": "25.5.0",
    "machine": "arm64",
    "python": "3.11.11",
    "cpu_count": 8,
    "mem_total_gb": 8.59,
    "hostname": "Harshs-Macbook-Air"
  },
  "run_name": "small-v5",
  "input_hash": "6a87a56df6bc45b6ccfb",
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
    "trivial_dupe": {
      "fields": [
        "given_name_norm",
        "surname_norm",
        "email_norm",
        "phone_match",
        "address_norm",
        "postal_norm",
        "birthdate_norm"
      ],
      "identifier_fields": [
        "email_norm",
        "phone_match",
        "address_norm"
      ],
      "requires_identifier": true
    },
    "hard_conflicts": {
      "birthdate": true,
      "birthdate_typo_tolerance": 2
    }
  },
  "cluster": {
    "supersized_min_size": 500,
    "linkage": "fusion",
    "fusion": {
      "tiers": [
        4.75,
        4.0
      ],
      "strong_edge_score": 4.0,
      "min_cross_edges": 2,
      "min_cross_edge_ratio": 0.1
    },
    "carve": {
      "enabled": true,
      "max_cluster_size": 500
    },
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
      },
      "contact": {
        "measure": "any_overlap"
      }
    },
    "conflict_columns": {
      "birthdate": "birthdate_norm",
      "given_name": "given_name_canon",
      "surname": "surname_norm",
      "ck": "ck",
      "loy_id": "loy_id_norm",
      "contact": [
        "email_norm",
        "phone_match"
      ]
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
pairwise P=0.998 R=0.872 F1=0.931 | B3 F1=0.937 | false-merge clusters=1.04% (profiles 1.25%) | split persons=38.10% | ID churn/30d mean=1.53% max=2.19% | AUC-ROC=0.936 AP=0.977 blocking-recall=0.878
```

| Metric | Value |
|---|---|
| Pairwise precision / recall / F1 | 0.998 / 0.872 / 0.931 |
| Pairs: TP / FP / FN | 260,994 / 425 / 38,252 |
| B-cubed precision / recall / F1 | 0.996 / 0.885 / 0.937 |
| Clusters predicted / truth persons (ratio) | 2,994 / 2,000 (1.497) |
| Exact-match clusters | 1,220 (61.00% of persons) |
| **False-merge rate** (clusters / profiles / pairs) | 1.04% / 1.25% / 0.16% |
| Over-merged clusters (max persons in one) | 31 (3) |
| Split persons (profiles) | 762 = 38.10% (55.77% of profiles) |
| **ID churn per 30-day window** mean / max | 1.53% / 2.19% |
| Harmful share of churn (purity dropped) | 4.21% |
| AUC-ROC / average precision (candidate pairs) | 0.936 / 0.977 |
| Blocking recall (true pairs reaching scoring) | 0.878 |
| Operating point P / R-in-candidates / effective R | 0.990 / 0.812 / 0.713 |
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
| time: engine_blocking | 4.54s |
| time: engine_scoring | 3.17s |
| time: engine_clustering | 0.7s |
| time: engine_stable_id | 0.13s |
| time: engine_persist | 0.31s |
| time: resolve_windows | 15.78s |
| time: wall_total | 16.62s |
| candidate pairs | 329,263 |
| block `engine (final snapshot)` | 97,863 pairs, 6,896 groups, 0 over cap (n/a) |

Engine snapshots (one engine run per replayed window; `previous=` carries stable ids forward):

| window | run_date | records | pairs scored | edges | clusters | skipped blocks | jitter % | ids minted | ids retired | engine s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2026-01-31 | 3,213 | 8,798 | 3,408 | 1,513 | 0 | 0.0 | 1513 | 0 | 0.79 |
| 1 | 2026-03-02 | 6,614 | 35,373 | 11,481 | 2,153 | 0 | 1.6184 | 678 | 38 | 1.14 |
| 2 | 2026-04-01 | 9,981 | 83,412 | 22,639 | 2,480 | 0 | 1.8143 | 384 | 57 | 1.9 |
| 3 | 2026-05-01 | 13,381 | 149,235 | 35,244 | 2,668 | 0 | 2.1942 | 284 | 96 | 2.89 |
| 4 | 2026-05-31 | 16,720 | 229,027 | 48,307 | 2,851 | 0 | 1.3004 | 233 | 50 | 3.89 |
| 5 | 2026-06-30 | 20,000 | 329,263 | 62,108 | 2,994 | 0 | 0.7416 | 187 | 44 | 5.17 |

## Score quality (candidate pairs)

![ROC](plots/roc.png) ![PR](plots/pr.png)

![score histogram](plots/score_hist.png)

## Threshold sweep (final window)

| threshold | precision | recall | F1 | B³ F1 | false-merge clusters | split persons | clusters |
|---|---|---|---|---|---|---|---|
| 0.30 | 0.254 | 0.971 | 0.402 | 0.817 | 13.94% | 12.75% | 1,600 |
| 0.35 | 0.268 | 0.971 | 0.420 | 0.828 | 12.97% | 12.80% | 1,634 |
| 0.40 | 0.352 | 0.970 | 0.517 | 0.850 | 12.04% | 12.90% | 1,702 |
| 0.45 | 0.931 | 0.924 | 0.927 | 0.934 | 3.56% | 31.45% | 2,611 |
| 0.50 | 0.931 | 0.915 | 0.923 | 0.930 | 3.25% | 33.95% | 2,705 |
| 0.55 | 0.934 | 0.914 | 0.924 | 0.932 | 2.93% | 34.15% | 2,726 |
| 0.60 | 0.937 | 0.914 | 0.925 | 0.933 | 2.85% | 34.15% | 2,733 |
| 0.65 | 0.943 | 0.914 | 0.928 | 0.935 | 2.65% | 34.45% | 2,758 |
| 0.70 | 0.943 | 0.914 | 0.928 | 0.935 | 2.64% | 34.55% | 2,762 |
| 0.75 | 0.943 | 0.908 | 0.926 | 0.932 | 2.60% | 36.10% | 2,811 |
| 0.80 | 0.944 | 0.895 | 0.919 | 0.926 | 2.44% | 39.40% | 2,949 |
| 0.85 | 0.949 | 0.740 | 0.832 | 0.822 | 1.38% | 68.70% | 4,776 |
| 0.90 | 0.983 | 0.572 | 0.723 | 0.619 | 0.37% | 88.15% | 8,818 |
| 0.95 | 0.991 | 0.311 | 0.473 | 0.458 | 0.24% | 91.95% | 10,414 |

Best F1 on this grid: threshold **0.65** (F1 0.928). Run `scripts/tune.py` for finer grids, precision-constrained objectives and weight search.

![sweep](plots/sweep.png)

## Clusters

![cluster sizes](plots/cluster_sizes.png)

| | predicted | truth |
|---|---|---|
| mean | 6.68 | 10.00 |
| p50 | 3.00 | 6.00 |
| p90 | 16.00 | 21.00 |
| p99 | 43.14 | 55.02 |
| max | 353 | 368 |
| singletons | 966 | 113 |

## Over-merge detector

31 predicted clusters conflate ≥2 persons, covering 250 profiles and 61 persons. 2,160 accepted edges cross a person boundary.

Which agreeing feature carried the bad edges (an edge can count in several columns; `only` = that feature was the sole agreement):

| feature | bad edges agreeing | sole agreement |
|---|---|---|
| engine_scored | 2,052 | 2,052 |
| engine_deterministic | 89 | 89 |
| engine_trivial_duplicate | 19 | 19 |
| email | 0 | 0 |
| phone | 0 | 0 |
| dob | 0 | 0 |
| postal | 0 | 0 |
| name | 0 | 0 |
| addr | 0 | 0 |

Worst clusters (full list in `overmerge_clusters.json`, edges in `overmerge_edges.parquet`):

| cluster | persons | profiles | dominant feature | sample names by person |
|---|---|---|---|---|
| `w0-c147442332addb32` | 3 | 16 | engine_deterministic | ps_0001434: Bobby Smith, Robert Smith; ps_0000715: Robert Smith; ps_0001974: Rob, rogert simth |
| `w0-660abc5d6b5852a0` | 2 | 28 | engine_scored | ps_0000504: Brian Cunningham, brian cunninfham; ps_0001171: B Cunningham |
| `w0-8c439c8aa7643cec` | 2 | 20 | engine_scored | ps_0001342: DREW MUNOZ, andrew munoz; ps_0001372: Matthew Munoz, matthew munoz |
| `w2-e99245b5bee51ff9` | 2 | 17 | engine_scored | ps_0000234: SNEHA BUTLER, Sneha Butler; ps_0001478: joshua butler |
| `w0-71d5ca1e5b80d050` | 2 | 15 | engine_scored | ps_0001551: Mark Martinez, mark martinez; ps_0000063: carol martinez |
| `w0-d8877791092e34e8` | 2 | 13 | engine_scored | ps_0001178: Michael, michael mith; ps_0000697: nicholas smith |
| `w0-28e13d75d332fe8d` | 2 | 11 | engine_scored | ps_0001659: James Brown; ps_0000639: J Brown |
| `w0-9fb62dc93015ce81` | 2 | 11 | engine_scored | ps_0000540: Aisha Brown, aisha brown; ps_0001791: Richard Brown, richard brown |
| `w0-c0e1a22452537e54` | 2 | 11 | engine_scored | ps_0000509: JOH ROGERS, John Rogers; ps_0000152: Jon Rogers, j rogers |
| `w0-5051463a9171bd05` | 2 | 10 | engine_scored | ps_0000703: kelly jones; ps_0000277: Kevin, Kevin Jones |
| `w0-6d7f66b09f610fa5` | 2 | 9 | engine_scored | ps_0001017: Janet Miller; ps_0001252: John Miller, john miller |
| `w0-4e96a5ede77b1f31` | 2 | 7 | engine_scored | ps_0000980: Aisha Carter, aisha catrer; ps_0001982: Maria Carter |

## ID churn per 30-day window

Churn = carried-over profiles whose stable cluster id changed vs the previous window. *merge* = the profile's whole previous cluster was absorbed; *split* = otherwise. *harmful* = the profile's new cluster is less pure for its true person than the old one.

![churn](plots/churn.png)

| window | profiles | clusters | new | carried | churned | churn rate | merge | split | harmful | justified |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 3,213 | 1,513 | – | – | – | – | – | – | – | – |
| 1 | 6,614 | 2,153 | 3,401 | 3,213 | 52 | 1.62% | 43 | 9 | 5 | 47 |
| 2 | 9,981 | 2,480 | 3,367 | 6,614 | 120 | 1.81% | 70 | 50 | 5 | 115 |
| 3 | 13,381 | 2,668 | 3,400 | 9,981 | 219 | 2.19% | 150 | 69 | 3 | 216 |
| 4 | 16,720 | 2,851 | 3,339 | 13,381 | 174 | 1.30% | 74 | 100 | 14 | 160 |
| 5 | 20,000 | 2,994 | 3,280 | 16,720 | 124 | 0.74% | 62 | 62 | 2 | 122 |

Quality per window snapshot:

| window | profiles | precision | recall | F1 | false-merge clusters |
|---|---|---|---|---|---|
| 0 | 3,213 | 0.998 | 0.861 | 0.925 | 0.26% |
| 1 | 6,614 | 0.998 | 0.881 | 0.936 | 0.42% |
| 2 | 9,981 | 0.998 | 0.873 | 0.931 | 0.69% |
| 3 | 13,381 | 0.999 | 0.872 | 0.931 | 0.75% |
| 4 | 16,720 | 0.998 | 0.874 | 0.932 | 0.91% |
| 5 | 20,000 | 0.998 | 0.872 | 0.931 | 1.04% |

## Resources

Wall 18.1s · peak RSS 752 MB · mean CPU 100% (peak 115%, 8 cores) · 18 samples @ 1.0s

![resources](plots/resources.png)

| stage | wall s | peak RSS MB | mean CPU % |
|---|---|---|---|
| resolve:w0 | 0.9 | 312 | 81 |
| resolve:w1 | 1.2 | 357 | 101 |
| resolve:w2 | 2.0 | 420 | 100 |
| resolve:w3 | 3.0 | 488 | 101 |
| resolve:w4 | 4.0 | 592 | 102 |
| resolve:w5 | 5.4 | 637 | 100 |
| persist | 0.4 | 734 | 115 |
| report | 0.0 | 752 | 90 |

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
python -m aurora_eval.cli run --adapter aurora_cdp --dataset small --seed 20261022 --run-name small-v5 --date 2026-10-22 --reports-root /Users/harshmaster/Desktop/Projects/aurora-cdp/reports
# resume after interruption: same command (checkpoints in /Users/harshmaster/Desktop/Projects/aurora-eval-harness/runs/small-v5/checkpoints)
```

## Files

- `metrics.json` — everything above, machine-readable (same shape as `aurora_eval.score()` output)
- `plots/` — PNGs embedded here
- `overmerge_clusters.json`, `overmerge_edges.parquet` — drill-down for the detector
- `provenance.json`, `resources.jsonl`, `events.jsonl`, `state.json` — provenance, resource samples, failure/retry log, stage state
