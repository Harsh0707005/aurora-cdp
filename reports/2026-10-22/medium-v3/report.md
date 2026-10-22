# Evaluation report — `medium-v3`

_Generated 2026-10-22T16:53:44 · dataset `medium` · resolver `aurora_cdp` · threshold 0.6 (engine scale 3.0) · block cap 100 · seed 20261022_

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
  "dataset": "/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/medium",
  "run_at": "2026-10-22T11:11:56+00:00",
  "host": {
    "platform": "macOS",
    "platform_release": "25.5.0",
    "machine": "arm64",
    "python": "3.11.11",
    "cpu_count": 8,
    "mem_total_gb": 8.59,
    "hostname": "Harshs-Macbook-Air"
  },
  "run_name": "medium-v3",
  "input_hash": "c01ed07319ef9b6229f2",
  "dataset_manifest_fingerprint": 7100844426990289322,
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
pairwise P=0.994 R=0.860 F1=0.923 | B3 F1=0.932 | false-merge clusters=2.22% (profiles 2.40%) | split persons=39.04% | ID churn/30d mean=1.51% max=2.46% | AUC-ROC=0.951 AP=0.908 blocking-recall=0.893
```

| Metric | Value |
|---|---|
| Pairwise precision / recall / F1 | 0.994 / 0.860 / 0.923 |
| Pairs: TP / FP / FN | 2,000,814 / 11,576 / 324,373 |
| B-cubed precision / recall / F1 | 0.991 / 0.880 / 0.932 |
| Clusters predicted / truth persons (ratio) | 29,603 / 20,000 (1.480) |
| Exact-match clusters | 12,000 (60.00% of persons) |
| **False-merge rate** (clusters / profiles / pairs) | 2.22% / 2.40% / 0.58% |
| Over-merged clusters (max persons in one) | 658 (32) |
| Split persons (profiles) | 7,808 = 39.04% (57.10% of profiles) |
| **ID churn per 30-day window** mean / max | 1.51% / 2.46% |
| Harmful share of churn (purity dropped) | 4.75% |
| AUC-ROC / average precision (candidate pairs) | 0.951 / 0.908 |
| Blocking recall (true pairs reaching scoring) | 0.893 |
| Operating point P / R-in-candidates / effective R | 0.981 / 0.830 / 0.740 |
| Scored candidate pairs (stored fraction) | 6,737,512 (100.00%) |

> **Notes**
> - Engine scores are normalised from the 0–5 band scale to [0, 1] (score/5); the operating threshold 0.60 is the engine's 3.0 on its own scale.
> - The threshold sweep re-clusters engine pair scores with plain connected components, so it approximates (does not reproduce) the engine's conflict-aware clustering at other thresholds.

## Dataset

| | |
|---|---|
| persons | 20,000 |
| persons_with_profiles | 20,000 |
| profiles | 200,000 |
| months | 6 |
| true_pairs | 2,325,187 |
| households | 1,315 |
| movers | 2,038 |
| exact_duplicates | 17,965 |
| profiles_per_person_max | 275 |

Regenerate: `python scripts/generate.py --persons 20000 --profiles 200000 --months 6 --seed 42 --tier medium`

## Resolver run

| | |
|---|---|
| time: engine_load | 2.46s |
| time: engine_blocking | 518.5s |
| time: engine_scoring | 82.79s |
| time: engine_clustering | 7.76s |
| time: engine_stable_id | 1.05s |
| time: engine_persist | 2.07s |
| time: resolve_windows | 681.48s |
| time: wall_total | 693.73s |
| candidate pairs | 6,737,512 |
| block `engine (final snapshot)` | 2,676,111 pairs, 64,008 groups, 0 over cap (n/a) |

Engine snapshots (one engine run per replayed window; `previous=` carries stable ids forward):

| window | run_date | records | pairs scored | edges | clusters | skipped blocks | jitter % | ids minted | ids retired | engine s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2026-01-31 | 33,331 | 251,312 | 34,643 | 15,685 | 0 | 0.0 | 15685 | 0 | 10.5 |
| 1 | 2026-03-02 | 66,557 | 913,027 | 113,007 | 21,223 | 0 | 2.4602 | 6125 | 587 | 30.47 |
| 2 | 2026-04-01 | 99,677 | 1,927,934 | 215,523 | 24,403 | 0 | 1.7053 | 3793 | 613 | 69.53 |
| 3 | 2026-05-01 | 132,926 | 3,281,654 | 335,931 | 26,563 | 0 | 1.3484 | 2779 | 619 | 140.58 |
| 4 | 2026-05-31 | 166,430 | 4,817,983 | 468,948 | 28,232 | 0 | 1.1217 | 2196 | 527 | 178.2 |
| 5 | 2026-06-30 | 200,000 | 6,737,512 | 612,772 | 29,603 | 0 | 0.9079 | 1853 | 482 | 252.2 |

## Score quality (candidate pairs)

![ROC](plots/roc.png) ![PR](plots/pr.png)

![score histogram](plots/score_hist.png)

## Threshold sweep (final window)

| threshold | precision | recall | F1 | B³ F1 | false-merge clusters | split persons | clusters |
|---|---|---|---|---|---|---|---|
| 0.30 | 0.003 | 0.982 | 0.007 | 0.478 | 24.35% | 9.86% | 7,770 |
| 0.35 | 0.006 | 0.982 | 0.011 | 0.495 | 23.72% | 10.06% | 8,146 |
| 0.40 | 0.007 | 0.981 | 0.014 | 0.552 | 22.22% | 10.40% | 9,220 |
| 0.45 | 0.720 | 0.928 | 0.811 | 0.906 | 6.73% | 32.34% | 24,723 |
| 0.50 | 0.793 | 0.919 | 0.852 | 0.910 | 5.95% | 34.66% | 25,902 |
| 0.55 | 0.814 | 0.919 | 0.863 | 0.913 | 5.63% | 34.80% | 26,143 |
| 0.60 | 0.836 | 0.919 | 0.876 | 0.917 | 5.25% | 34.83% | 26,339 |
| 0.65 | 0.905 | 0.918 | 0.912 | 0.929 | 4.16% | 34.92% | 26,889 |
| 0.70 | 0.906 | 0.918 | 0.912 | 0.928 | 4.11% | 35.25% | 27,004 |
| 0.75 | 0.907 | 0.913 | 0.910 | 0.926 | 4.00% | 36.86% | 27,577 |
| 0.80 | 0.907 | 0.900 | 0.903 | 0.919 | 3.78% | 40.41% | 29,023 |
| 0.85 | 0.913 | 0.736 | 0.815 | 0.818 | 2.15% | 69.34% | 47,076 |
| 0.90 | 0.966 | 0.527 | 0.682 | 0.621 | 0.81% | 87.57% | 86,800 |
| 0.95 | 0.981 | 0.277 | 0.432 | 0.452 | 0.59% | 91.12% | 104,245 |

Best F1 on this grid: threshold **0.70** (F1 0.912). Run `scripts/tune.py` for finer grids, precision-constrained objectives and weight search.

![sweep](plots/sweep.png)

## Clusters

![cluster sizes](plots/cluster_sizes.png)

| | predicted | truth |
|---|---|---|
| mean | 6.76 | 10.00 |
| p50 | 3.00 | 6.00 |
| p90 | 16.00 | 21.00 |
| p99 | 46.00 | 60.00 |
| max | 261 | 275 |
| singletons | 9,112 | 1,238 |

## Over-merge detector

658 predicted clusters conflate ≥2 persons, covering 4,793 profiles and 1,586 persons. 32,889 accepted edges cross a person boundary.

Which agreeing feature carried the bad edges (an edge can count in several columns; `only` = that feature was the sole agreement):

| feature | bad edges agreeing | sole agreement |
|---|---|---|
| engine_scored | 28,590 | 28,590 |
| engine_trivial_duplicate | 3,331 | 3,331 |
| engine_deterministic | 968 | 968 |
| email | 0 | 0 |
| phone | 0 | 0 |
| dob | 0 | 0 |
| postal | 0 | 0 |
| name | 0 | 0 |
| addr | 0 | 0 |

Worst clusters (full list in `overmerge_clusters.json`, edges in `overmerge_edges.parquet`):

| cluster | persons | profiles | dominant feature | sample names by person |
|---|---|---|---|---|
| `w0-97a10dbe96a1d761` | 32 | 36 | engine_trivial_duplicate | ps_0008394: James; ps_0011641: JAMES; ps_0019624: James; ps_0011128: James |
| `w0-904f344bab0c1153` | 23 | 25 | engine_trivial_duplicate | ps_0008688: James Smith; ps_0002773: james smith; ps_0012322: James Smith; ps_0013030: JAMES SMITH |
| `w0-e08048f04bbac63b` | 14 | 14 | engine_trivial_duplicate | ps_0009815: Robert; ps_0014943: robert; ps_0017285: robert; ps_0001224: Robert |
| `w0-9b689a463bc4f3cb` | 13 | 19 | engine_trivial_duplicate | ps_0002350: james williams; ps_0006157: James Williams; ps_0019898: James Williams; ps_0004199: james williams |
| `w0-03f6a4b119807675` | 13 | 17 | engine_trivial_duplicate | ps_0015918: John Smith, john smith; ps_0006835: John Smith; ps_0007136: john smith; ps_0008941: John Smith |
| `w0-b1bc9ceb1d974c14` | 13 | 16 | engine_trivial_duplicate | ps_0005925: Robert Smith; ps_0018244: robert smith; ps_0005506: Robert Smith, robert smith; ps_0003517: robert smith |
| `w0-747a30cc17388b95` | 13 | 14 | engine_trivial_duplicate | ps_0000937: John; ps_0000524: JOHN; ps_0000702: John; ps_0002779: John |
| `w0-fdce2e789bc288ba` | 11 | 14 | engine_trivial_duplicate | ps_0003318: james johnson; ps_0008692: James Johnson, james johnson; ps_0003320: James Johnson; ps_0004402: james johnson |
| `w0-b308bfc929c10b19` | 11 | 12 | engine_trivial_duplicate | ps_0003867: William Smith; ps_0005495: william smith; ps_0015391: william smith; ps_0017134: William Smith |
| `w0-7ed2250fb134be6b` | 10 | 14 | engine_trivial_duplicate | ps_0015281: JOHN JOHNSON, John Johnson; ps_0001914: John Johnson, john johnson; ps_0018731: John Johnson, john johnson; ps_0010309: john johnson |
| `w0-dcfab4cec522ea32` | 10 | 12 | engine_trivial_duplicate | ps_0008162: michael; ps_0001456: michael; ps_0002997: Michael; ps_0017785: MICHAEL |
| `w2-24c4c784e6e77f6a` | 8 | 11 | engine_trivial_duplicate | ps_0010760: ROBERT JONES, robert jones; ps_0005715: ROBERT JONES, Robert Jones; ps_0012742: Robert Jones; ps_0017214: Robert Jones |

## ID churn per 30-day window

Churn = carried-over profiles whose stable cluster id changed vs the previous window. *merge* = the profile's whole previous cluster was absorbed; *split* = otherwise. *harmful* = the profile's new cluster is less pure for its true person than the old one.

![churn](plots/churn.png)

| window | profiles | clusters | new | carried | churned | churn rate | merge | split | harmful | justified |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 33,331 | 15,685 | – | – | – | – | – | – | – | – |
| 1 | 66,557 | 21,223 | 33,226 | 33,331 | 820 | 2.46% | 669 | 151 | 46 | 774 |
| 2 | 99,677 | 24,403 | 33,120 | 66,557 | 1,135 | 1.71% | 776 | 359 | 43 | 1,092 |
| 3 | 132,926 | 26,563 | 33,249 | 99,677 | 1,344 | 1.35% | 836 | 508 | 81 | 1,263 |
| 4 | 166,430 | 28,232 | 33,504 | 132,926 | 1,491 | 1.12% | 809 | 682 | 51 | 1,440 |
| 5 | 200,000 | 29,603 | 33,570 | 166,430 | 1,511 | 0.91% | 754 | 757 | 78 | 1,433 |

Quality per window snapshot:

| window | profiles | precision | recall | F1 | false-merge clusters |
|---|---|---|---|---|---|
| 0 | 33,331 | 0.991 | 0.851 | 0.916 | 0.66% |
| 1 | 66,557 | 0.994 | 0.871 | 0.929 | 1.14% |
| 2 | 99,677 | 0.994 | 0.866 | 0.925 | 1.45% |
| 3 | 132,926 | 0.994 | 0.871 | 0.929 | 1.77% |
| 4 | 166,430 | 0.994 | 0.865 | 0.925 | 1.95% |
| 5 | 200,000 | 0.994 | 0.860 | 0.923 | 2.22% |

## Resources

Wall 708.0s · peak RSS 2,308 MB · mean CPU 306% (peak 402%, 8 cores) · 698 samples @ 1.0s

![resources](plots/resources.png)

| stage | wall s | peak RSS MB | mean CPU % |
|---|---|---|---|
| resolve:w0 | 11.1 | 654 | 132 |
| resolve:w1 | 31.3 | 781 | 222 |
| resolve:w2 | 70.6 | 1,167 | 268 |
| resolve:w3 | 141.8 | 1,587 | 321 |
| resolve:w4 | 179.5 | 1,886 | 330 |
| resolve:w5 | 254.4 | 2,057 | 325 |
| assemble | 5.1 | 2,308 | 103 |
| persist | 6.9 | 1,941 | 96 |
| metrics | 7.1 | 1,909 | 95 |
| report | 0.0 | 1,890 | 99 |

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
# dataset: /Users/harshmaster/Documents/aanya/datasets/aurora-testdata/medium  (regenerate: python scripts/generate.py --persons 20000 --profiles 200000 --months 6 --seed 42 --tier medium)
python -m aurora_eval.cli run --adapter aurora_cdp --dataset medium --seed 20261022 --run-name medium-v3 --date 2026-10-22 --reports-root /Users/harshmaster/Desktop/Projects/aurora-cdp/reports
# resume after interruption: same command (checkpoints in /Users/harshmaster/Desktop/Projects/aurora-eval-harness/runs/medium-v3/checkpoints)
```

## Files

- `metrics.json` — everything above, machine-readable (same shape as `aurora_eval.score()` output)
- `plots/` — PNGs embedded here
- `overmerge_clusters.json`, `overmerge_edges.parquet` — drill-down for the detector
- `provenance.json`, `resources.jsonl`, `events.jsonl`, `state.json` — provenance, resource samples, failure/retry log, stage state
