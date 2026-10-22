# Evaluation report — `medium-v4-dupefix`

_Generated 2026-10-22T18:23:38 · dataset `medium` · resolver `aurora_cdp` · threshold 0.6 (engine scale 3.0) · block cap 100 · seed 20261022_

## Provenance

```json
{
  "adapter": "aurora_cdp",
  "aurora_cdp_commit": "9c1d7fb86e8a6592ecda06942405e66d61ad700f",
  "aurora_cdp_commit_source": "git",
  "aurora_cdp_dirty_worktree": true,
  "aurora_cdp_path": "/Users/harshmaster/Desktop/Projects/aurora-cdp",
  "aurora_cdp_version": "0.1.0",
  "harness_commit": "1211f2017a2dcaf198a4002f7323561ee6e8edca",
  "harness_version": "0.1.0",
  "seed": 20261022,
  "dataset": "/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/medium",
  "run_at": "2026-10-22T12:51:25+00:00",
  "host": {
    "platform": "macOS",
    "platform_release": "25.5.0",
    "machine": "arm64",
    "python": "3.11.11",
    "cpu_count": 8,
    "mem_total_gb": 8.59,
    "hostname": "Harshs-Macbook-Air"
  },
  "run_name": "medium-v4-dupefix",
  "input_hash": "4e92cd2e55f4c8f88b43",
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
    "dupe_group_requires_identifier": true,
    "dupe_group_identifier_fields": [
      "email_norm",
      "phone_match",
      "address_norm",
      "loy_id_norm",
      "ck"
    ],
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
  "identity": {
    "ampid_mode": true,
    "external_id_name": "amperity_id",
    "email_ampid_assignment": true
  },
  "household": {
    "build_with_profile": true,
    "min_evidence_weight": 1.0,
    "evidence_ttl_days": 365,
    "max_customers_per_value": 25,
    "evidence": {
      "shared_address": {
        "weight": 1.0,
        "columns": [
          "address_norm",
          "postal_norm"
        ]
      },
      "shared_surname_postal": {
        "weight": 0.4,
        "columns": [
          "surname_norm",
          "postal_norm"
        ]
      },
      "shared_phone": {
        "weight": 0.6,
        "columns": [
          "phone_match"
        ]
      },
      "relationship": {
        "weight": 1.0
      }
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
    "jitter_alert_pct": 2.0,
    "tie_break": "stable"
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
pairwise P=0.996 R=0.860 F1=0.923 | B3 F1=0.934 | false-merge clusters=0.83% (profiles 1.67%) | split persons=39.05% | ID churn/30d mean=1.51% max=2.47% | AUC-ROC=0.952 AP=0.913 blocking-recall=0.892
```

| Metric | Value |
|---|---|
| Pairwise precision / recall / F1 | 0.996 / 0.860 / 0.923 |
| Pairs: TP / FP / FN | 1,999,752 / 8,126 / 325,435 |
| B-cubed precision / recall / F1 | 0.995 / 0.880 / 0.934 |
| Clusters predicted / truth persons (ratio) | 31,313 / 20,000 (1.566) |
| Exact-match clusters | 12,012 (60.06% of persons) |
| **False-merge rate** (clusters / profiles / pairs) | 0.83% / 1.67% / 0.40% |
| Over-merged clusters (max persons in one) | 260 (3) |
| Split persons (profiles) | 7,811 = 39.05% (57.10% of profiles) |
| **ID churn per 30-day window** mean / max | 1.51% / 2.47% |
| Harmful share of churn (purity dropped) | 4.72% |
| AUC-ROC / average precision (candidate pairs) | 0.952 / 0.913 |
| Blocking recall (true pairs reaching scoring) | 0.892 |
| Operating point P / R-in-candidates / effective R | 0.983 / 0.829 / 0.740 |
| Scored candidate pairs (stored fraction) | 6,687,751 (100.00%) |

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
| time: engine_load | 2.44s |
| time: engine_blocking | 1.65s |
| time: engine_scoring | 51.24s |
| time: engine_clustering | 7.55s |
| time: engine_stable_id | 0.94s |
| time: engine_persist | 1.93s |
| time: resolve_windows | 107.8s |
| time: wall_total | 119.71s |
| candidate pairs | 6,687,751 |
| block `engine (final snapshot)` | 2,767,061 pairs, 64,057 groups, 0 over cap (n/a) |

Engine snapshots (one engine run per replayed window; `previous=` carries stable ids forward):

| window | run_date | records | pairs scored | edges | clusters | skipped blocks | jitter % | ids minted | ids retired | engine s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2026-01-31 | 33,331 | 251,284 | 34,555 | 15,775 | 0 | 0.0 | 15775 | 0 | 3.96 |
| 1 | 2026-03-02 | 66,557 | 912,887 | 112,738 | 21,502 | 0 | 2.4662 | 6316 | 589 | 8.8 |
| 2 | 2026-04-01 | 99,677 | 1,927,337 | 215,005 | 24,951 | 0 | 1.7083 | 4065 | 616 | 13.75 |
| 3 | 2026-05-01 | 132,926 | 3,280,616 | 335,154 | 27,416 | 0 | 1.3474 | 3084 | 619 | 20.65 |
| 4 | 2026-05-31 | 166,430 | 4,815,995 | 467,823 | 29,503 | 0 | 1.1187 | 2613 | 526 | 26.69 |
| 5 | 2026-06-30 | 200,000 | 6,687,751 | 611,276 | 31,313 | 0 | 0.9013 | 2289 | 479 | 33.95 |

## Score quality (candidate pairs)

![ROC](plots/roc.png) ![PR](plots/pr.png)

![score histogram](plots/score_hist.png)

## Threshold sweep (final window)

| threshold | precision | recall | F1 | B³ F1 | false-merge clusters | split persons | clusters |
|---|---|---|---|---|---|---|---|
| 0.30 | 0.003 | 0.982 | 0.007 | 0.479 | 22.96% | 9.86% | 7,989 |
| 0.35 | 0.006 | 0.982 | 0.011 | 0.496 | 22.40% | 10.06% | 8,365 |
| 0.40 | 0.007 | 0.981 | 0.014 | 0.553 | 21.09% | 10.40% | 9,439 |
| 0.45 | 0.767 | 0.927 | 0.840 | 0.909 | 4.81% | 32.38% | 26,461 |
| 0.50 | 0.813 | 0.919 | 0.863 | 0.912 | 4.15% | 34.70% | 27,641 |
| 0.55 | 0.832 | 0.918 | 0.873 | 0.916 | 3.86% | 34.83% | 27,882 |
| 0.60 | 0.856 | 0.918 | 0.886 | 0.920 | 3.52% | 34.86% | 28,079 |
| 0.65 | 0.907 | 0.918 | 0.912 | 0.931 | 2.52% | 34.95% | 28,606 |
| 0.70 | 0.907 | 0.918 | 0.912 | 0.930 | 2.48% | 35.28% | 28,720 |
| 0.75 | 0.908 | 0.912 | 0.910 | 0.928 | 2.41% | 36.90% | 29,293 |
| 0.80 | 0.908 | 0.899 | 0.904 | 0.921 | 2.27% | 40.44% | 30,814 |
| 0.85 | 0.914 | 0.736 | 0.815 | 0.819 | 1.25% | 69.38% | 48,867 |
| 0.90 | 0.968 | 0.527 | 0.682 | 0.621 | 0.34% | 87.61% | 88,591 |
| 0.95 | 0.986 | 0.276 | 0.431 | 0.452 | 0.20% | 91.16% | 106,036 |

Best F1 on this grid: threshold **0.70** (F1 0.912). Run `scripts/tune.py` for finer grids, precision-constrained objectives and weight search.

![sweep](plots/sweep.png)

## Clusters

![cluster sizes](plots/cluster_sizes.png)

| | predicted | truth |
|---|---|---|
| mean | 6.39 | 10.00 |
| p50 | 3.00 | 6.00 |
| p90 | 16.00 | 21.00 |
| p99 | 45.00 | 60.00 |
| max | 261 | 275 |
| singletons | 11,773 | 1,238 |

## Over-merge detector

260 predicted clusters conflate ≥2 persons, covering 3,336 profiles and 488 persons. 29,489 accepted edges cross a person boundary.

Which agreeing feature carried the bad edges (an edge can count in several columns; `only` = that feature was the sole agreement):

| feature | bad edges agreeing | sole agreement |
|---|---|---|
| engine_scored | 28,510 | 28,510 |
| engine_deterministic | 968 | 968 |
| engine_trivial_duplicate | 11 | 11 |
| email | 0 | 0 |
| phone | 0 | 0 |
| dob | 0 | 0 |
| postal | 0 | 0 |
| name | 0 | 0 |
| addr | 0 | 0 |

Worst clusters (full list in `overmerge_clusters.json`, edges in `overmerge_edges.parquet`):

| cluster | persons | profiles | dominant feature | sample names by person |
|---|---|---|---|---|
| `w0-0d755ddb9966b5a2` | 3 | 28 | engine_scored | ps_0007081: Rachel Johnsin, rachel johnson; ps_0014101: MICHAEL JOHNSON, michael johnson; ps_0013102: matthew johnson |
| `w0-0cc0bc7e4612dec5` | 3 | 22 | engine_scored | ps_0009039: j patel; ps_0007958: James Patel, james patel; ps_0019628: J Patel |
| `w0-944b35e75daaa45e` | 3 | 20 | engine_scored | ps_0014894: matt murphy, matthew murphy; ps_0009724: jonathan murphy; ps_0000081: matthew murphy |
| `w1-d30aec1fe497f5b1` | 3 | 14 | engine_scored | ps_0017315: Andrea Smith, andrea smith; ps_0004693: Diane Smith; ps_0004797: Andrew Smith |
| `w0-21cf6317a143e2f1` | 3 | 10 | engine_scored | ps_0006809: SHARON DAGIS, sharon davis; ps_0016989: Sarah Davis; ps_0011419: karan davis |
| `w0-dc0329c92778d024` | 3 | 10 | engine_scored | ps_0019163: john fernandez; ps_0015939: John Fernandez; ps_0016894: J Fernandez |
| `w0-412699f6779074d9` | 3 | 9 | engine_scored | ps_0001181: John Lewis, John Lwis; ps_0019026: j lewis; ps_0008683: joyce lewis |
| `w0-e64d1727419f8108` | 3 | 8 | engine_scored | ps_0012662: Jason Aguilar, jason aguilar; ps_0008642: Jame, james aguilar; ps_0004558: James Aguilar |
| `w1-a84d92c331f16b42` | 3 | 7 | engine_scored | ps_0006452: Joshua Salazar, o salazar; ps_0014961: JOHN SALAZAR; ps_0011148: John Salazar |
| `w2-fe5cd551a92ca369` | 3 | 7 | engine_scored | ps_0011491: JAMES COLE, james cole; ps_0002492: James Cole; ps_0017719: Charles Cole |
| `w0-715ab732484d278c` | 3 | 6 | engine_scored | ps_0007143: James Rodriguez, james rodriguez; ps_0008487: james rodriguez; ps_0009998: Charles Rodriguez |
| `w0-1e326b032d6e23c0` | 2 | 69 | engine_scored | ps_0017551: John Davis; ps_0012265: J Davis |

## ID churn per 30-day window

Churn = carried-over profiles whose stable cluster id changed vs the previous window. *merge* = the profile's whole previous cluster was absorbed; *split* = otherwise. *harmful* = the profile's new cluster is less pure for its true person than the old one.

![churn](plots/churn.png)

| window | profiles | clusters | new | carried | churned | churn rate | merge | split | harmful | justified |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 33,331 | 15,775 | – | – | – | – | – | – | – | – |
| 1 | 66,557 | 21,502 | 33,226 | 33,331 | 822 | 2.47% | 672 | 150 | 46 | 776 |
| 2 | 99,677 | 24,951 | 33,120 | 66,557 | 1,137 | 1.71% | 782 | 355 | 43 | 1,094 |
| 3 | 132,926 | 27,416 | 33,249 | 99,677 | 1,343 | 1.35% | 836 | 507 | 81 | 1,262 |
| 4 | 166,430 | 29,503 | 33,504 | 132,926 | 1,487 | 1.12% | 807 | 680 | 51 | 1,436 |
| 5 | 200,000 | 31,313 | 33,570 | 166,430 | 1,500 | 0.90% | 744 | 756 | 76 | 1,424 |

Quality per window snapshot:

| window | profiles | precision | recall | F1 | false-merge clusters |
|---|---|---|---|---|---|
| 0 | 33,331 | 0.993 | 0.851 | 0.917 | 0.41% |
| 1 | 66,557 | 0.995 | 0.871 | 0.929 | 0.66% |
| 2 | 99,677 | 0.995 | 0.865 | 0.926 | 0.74% |
| 3 | 132,926 | 0.996 | 0.871 | 0.929 | 0.82% |
| 4 | 166,430 | 0.996 | 0.865 | 0.926 | 0.80% |
| 5 | 200,000 | 0.996 | 0.860 | 0.923 | 0.83% |

## Resources

Wall 132.9s · peak RSS 2,297 MB · mean CPU 118% (peak 367%, 8 cores) · 130 samples @ 1.0s

![resources](plots/resources.png)

| stage | wall s | peak RSS MB | mean CPU % |
|---|---|---|---|
| resolve:w0 | 4.5 | 577 | 96 |
| resolve:w1 | 9.5 | 865 | 112 |
| resolve:w2 | 14.7 | 1,146 | 118 |
| resolve:w3 | 21.8 | 1,226 | 121 |
| resolve:w4 | 28.1 | 1,365 | 126 |
| resolve:w5 | 36.4 | 1,478 | 124 |
| assemble | 4.8 | 2,241 | 106 |
| persist | 6.5 | 2,083 | 98 |
| metrics | 6.3 | 2,297 | 98 |
| report | 0.0 | 2,245 | 99 |

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
python -m aurora_eval.cli run --adapter aurora_cdp --dataset medium --seed 20261022 --run-name medium-v4-dupefix --date 2026-10-22 --reports-root /Users/harshmaster/Desktop/Projects/aurora-cdp/reports
# resume after interruption: same command (checkpoints in /Users/harshmaster/Desktop/Projects/aurora-eval-harness/runs/medium-v4-dupefix/checkpoints)
```

## Files

- `metrics.json` — everything above, machine-readable (same shape as `aurora_eval.score()` output)
- `plots/` — PNGs embedded here
- `overmerge_clusters.json`, `overmerge_edges.parquet` — drill-down for the detector
- `provenance.json`, `resources.jsonl`, `events.jsonl`, `state.json` — provenance, resource samples, failure/retry log, stage state
