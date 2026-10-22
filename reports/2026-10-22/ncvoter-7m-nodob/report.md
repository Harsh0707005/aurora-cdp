# Evaluation report — `ncvoter-7m-nodob`

_Generated 2026-10-22T15:39:58 · dataset `ncvoter-7m-nodob` · resolver `aurora_cdp` · threshold 0.6 (engine scale 3.0) · block cap 100 · seed 20261022_

## Provenance

```json
{
  "adapter": "aurora_cdp",
  "aurora_cdp_commit": "c3f4375b7d0ecd2abd4c4ef815f0836f1022881e",
  "aurora_cdp_commit_source": "git",
  "aurora_cdp_dirty_worktree": false,
  "aurora_cdp_path": "/home/ubuntu/Projects/aurora-cdp",
  "aurora_cdp_version": "0.1.0",
  "harness_commit": "1211f2017a2dcaf198a4002f7323561ee6e8edca",
  "harness_version": "0.1.0",
  "seed": 20261022,
  "dataset": "/home/ubuntu/data/aurora-testdata/ncvoter-7m-nodob",
  "run_at": "2026-10-22T14:39:04+00:00",
  "host": {
    "platform": "Linux",
    "platform_release": "7.0.0-1014-aws",
    "machine": "x86_64",
    "python": "3.11.17",
    "cpu_count": 32,
    "mem_total_gb": 264.74,
    "hostname": "ip-172-31-37-105"
  },
  "run_name": "ncvoter-7m-nodob",
  "input_hash": "bb7e15afe5ff310c310e",
  "dataset_manifest_fingerprint": 10493625382862189683,
  "dataset_seed": null,
  "sample": null
}
```

<details><summary><code>adapter config</code></summary>

```json
{
  "cdp_path": null,
  "config": {
    "matcher": {
      "max_expanded_pairs": 300000000
    }
  },
  "threshold": 0.6,
  "datasource_column": "source",
  "datasource": "input",
  "windows": "replay",
  "deterministic_ids": true,
  "seed": 20261022,
  "isolate_windows": true,
  "max_stored_pairs": 80000000,
  "epoch": "2026-01-01",
  "window_days": 30,
  "retries": 1,
  "timeout_s": 36000.0,
  "threshold_raw": 3.0,
  "score_scale": 5.0,
  "engine_path": "/home/ubuntu/Projects/aurora-cdp"
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
    "max_expanded_pairs": 300000000,
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
pairwise P=0.986 R=0.924 F1=0.954 | B3 F1=0.973 | false-merge clusters=0.48% (profiles 0.97%) | split persons=9.63% | ID churn/30d mean=0.05% max=0.07% | AUC-ROC=0.996 AP=0.971 blocking-recall=0.673
```

| Metric | Value |
|---|---|
| Pairwise precision / recall / F1 | 0.986 / 0.924 / 0.954 |
| Pairs: TP / FP / FN | 6,053,418 / 87,466 / 494,590 |
| B-cubed precision / recall / F1 | 0.995 / 0.952 / 0.973 |
| Clusters predicted / truth persons (ratio) | 2,833,701 / 2,585,325 (1.096) |
| Exact-match clusters | 2,311,404 (89.40% of persons) |
| **False-merge rate** (clusters / profiles / pairs) | 0.48% / 0.97% / 1.42% |
| Over-merged clusters (max persons in one) | 13,720 (4) |
| Split persons (profiles) | 248,994 = 9.63% (10.43% of profiles) |
| **ID churn per 30-day window** mean / max | 0.05% / 0.07% |
| Harmful share of churn (purity dropped) | 20.87% |
| AUC-ROC / average precision (candidate pairs) | 0.996 / 0.971 |
| Blocking recall (true pairs reaching scoring) | 0.673 |
| Operating point P / R-in-candidates / effective R | 0.989 / 0.941 / 0.634 |
| Scored candidate pairs (stored fraction) | 62,334,982 (100.00%) |

> **Notes**
> - Engine scores are normalised from the 0–5 band scale to [0, 1] (score/5); the operating threshold 0.60 is the engine's 3.0 on its own scale.
> - The threshold sweep re-clusters engine pair scores with plain connected components, so it approximates (does not reproduce) the engine's conflict-aware clustering at other thresholds.

## Dataset

| | |
|---|---|
| profiles | 7,000,002 |
| persons | 2,585,325 |
| true_pairs | 6,548,008 |
| profiles_per_person_max | 3 |
| singleton_persons | 303,979 |
| status | {'ACTIVE': 6149540, 'INACTIVE': 850462} |
| records_with_phone | 3,296,245 |
| records_with_dob | 0 |
| records_with_address | 7,000,002 |

## Resolver run

| | |
|---|---|
| time: engine_load | 67.35s |
| time: engine_blocking | 42.82s |
| time: engine_scoring | 1637.79s |
| time: engine_clustering | 103.19s |
| time: engine_stable_id | 22.15s |
| time: engine_persist | 25.53s |
| time: resolve_windows | 2908.68s |
| time: wall_total | 3196.98s |
| candidate pairs | 62,334,982 |
| block `engine (final snapshot)` | 58,336,458 pairs, 651,430 groups, 0 over cap (n/a) |

Engine snapshots (one engine run per replayed window; `previous=` carries stable ids forward):

| window | run_date | records | pairs scored | edges | clusters | skipped blocks | jitter % | ids minted | ids retired | engine s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2024-01-01 | 2,295,862 | 39,389,370 | 32,487 | 2,284,999 | 0 | 0.0 | 2284999 | 0 | 571.88 |
| 1 | 2024-12-31 | 4,571,862 | 151,913,385 | 2,132,792 | 2,463,708 | 0 | 0.0681 | 178760 | 51 | 1028.14 |
| 2 | 2025-12-31 | 7,000,002 | 62,334,982 | 4,198,387 | 2,833,701 | 0 | 0.0386 | 370952 | 959 | 1308.66 |

## Score quality (candidate pairs)

![ROC](plots/roc.png) ![PR](plots/pr.png)

![score histogram](plots/score_hist.png)

## Threshold sweep (final window)

| threshold | precision | recall | F1 | B³ F1 | false-merge clusters | split persons | clusters |
|---|---|---|---|---|---|---|---|
| 0.30 | 0.000 | 0.991 | 0.000 | 0.702 | 16.10% | 1.21% | 1,426,049 |
| 0.35 | 0.022 | 0.946 | 0.043 | 0.909 | 5.84% | 6.96% | 2,385,136 |
| 0.40 | 0.193 | 0.943 | 0.320 | 0.943 | 4.46% | 7.37% | 2,570,474 |
| 0.45 | 0.909 | 0.939 | 0.924 | 0.967 | 2.48% | 7.87% | 2,718,945 |
| 0.50 | 0.948 | 0.927 | 0.937 | 0.969 | 1.47% | 9.41% | 2,793,697 |
| 0.55 | 0.951 | 0.927 | 0.939 | 0.969 | 1.40% | 9.42% | 2,796,482 |
| 0.60 | 0.953 | 0.925 | 0.938 | 0.969 | 1.33% | 9.62% | 2,807,996 |
| 0.65 | 0.953 | 0.925 | 0.938 | 0.969 | 1.33% | 9.62% | 2,808,226 |
| 0.70 | 0.954 | 0.925 | 0.939 | 0.969 | 1.30% | 9.62% | 2,809,203 |
| 0.75 | 0.955 | 0.924 | 0.939 | 0.969 | 1.27% | 9.64% | 2,810,471 |
| 0.80 | 0.959 | 0.923 | 0.941 | 0.969 | 1.14% | 9.77% | 2,818,063 |
| 0.85 | 0.974 | 0.881 | 0.925 | 0.957 | 0.70% | 15.13% | 2,977,927 |
| 0.90 | 0.993 | 0.880 | 0.933 | 0.960 | 0.19% | 15.25% | 2,996,633 |
| 0.95 | 0.993 | 0.880 | 0.933 | 0.960 | 0.19% | 15.25% | 2,996,655 |

Best F1 on this grid: threshold **0.80** (F1 0.941). Run `scripts/tune.py` for finer grids, precision-constrained objectives and weight search.

![sweep](plots/sweep.png)

## Clusters

![cluster sizes](plots/cluster_sizes.png)

| | predicted | truth |
|---|---|---|
| mean | 2.47 | 2.71 |
| p50 | 3.00 | 3.00 |
| p90 | 3.00 | 3.00 |
| p99 | 3.00 | 3.00 |
| max | 12 | 3 |
| singletons | 590,186 | 303,979 |

## Over-merge detector

13,720 predicted clusters conflate ≥2 persons, covering 67,903 profiles and 27,431 persons. 47,392 accepted edges cross a person boundary.

Which agreeing feature carried the bad edges (an edge can count in several columns; `only` = that feature was the sole agreement):

| feature | bad edges agreeing | sole agreement |
|---|---|---|
| engine_scored | 39,786 | 39,786 |
| engine_trivial_duplicate | 6,455 | 6,455 |
| engine_deterministic | 1,151 | 1,151 |
| email | 0 | 0 |
| phone | 0 | 0 |
| dob | 0 | 0 |
| postal | 0 | 0 |
| name | 0 | 0 |
| addr | 0 | 0 |

Worst clusters (full list in `overmerge_clusters.json`, edges in `overmerge_edges.parquet`):

| cluster | persons | profiles | dominant feature | sample names by person |
|---|---|---|---|---|
| `w0-2db2becfcc963e92` | 4 | 12 | engine_scored | BE372026: QUINTERIOUS FELDER; BE393234: QUINTELLA FELDER; BE467902: QUINTEZIOUS FELDER; BE79429: QUINTELLA FELDER |
| `w0-0e7939d3a56b3ade` | 4 | 11 | engine_scored | AL333880: DONNA AMACHER; AL383967: JOHN CLARK; BN236383: SONYA BOONE; AL208582: JONATHAN MERRILL |
| `w0-c338c1a57d17a5a7` | 4 | 9 | engine_scored | CS36336: KELASIA MOORE; CS37929: KELTORIOUS MOORE; CS35946: KELESHIA MOORE; CS38868: KELBRIAH MOORE |
| `w0-00303f926d41134d` | 3 | 9 | engine_scored | BD153387: REGINA MCCRAY; BD166379: REGINALD MCCRAY; BD28944: REGINALD MCCRAY |
| `w0-1930fd62b1c219b3` | 3 | 9 | engine_scored | DA123418: DONNIE TILLERY; DA80026: JANIE TILLERY; DA84972: DONNIE TILLERY |
| `w0-1c42f410aee573b4` | 3 | 9 | engine_scored | DB314421: MARY HARDISON; DB334654: ALBERT HARDISON; DB78073: MARY HARDISON |
| `w0-2159b564bb0be255` | 3 | 9 | engine_scored | DL145981: JOANIE MERCER; DL40369: JANICE MERCER; DL40399: JESSIE MERCER |
| `w0-22f6db30838c505c` | 3 | 9 | engine_scored | CE15873: ERIC BRATCHER; CE48068: ERIC BRATCHER; CE51388: ERICQUESHA BRATCHER |
| `w0-2e7406ca0e672ac6` | 3 | 9 | engine_scored | CM72384: MIECHA POLLARD; CM77025: MAKIYA POLLARD; CM80966: MAKIYA POLLARD |
| `w0-33344da77303b7dd` | 3 | 9 | engine_trivial_duplicate | DW40144: LARRY SLAWSON; DW56041: LARRY SLAWSON; DW71439: PATRICK SLAWSON |
| `w0-3561922bbf8c5d1e` | 3 | 9 | engine_scored | DR55606: JAMES HUNT; DR99486: CAMERON HUNT; DR99489: JAMES HUNT |
| `w0-3893fb69a6c28298` | 3 | 9 | engine_scored | BM58158: MADELINE WILLIAMS; DA23797: KATHLEEN SULLIVAN; EP78673: MATTIE PITTMAN |

## ID churn per 30-day window

Churn = carried-over profiles whose stable cluster id changed vs the previous window. *merge* = the profile's whole previous cluster was absorbed; *split* = otherwise. *harmful* = the profile's new cluster is less pure for its true person than the old one.

![churn](plots/churn.png)

| window | profiles | clusters | new | carried | churned | churn rate | merge | split | harmful | justified |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2,295,862 | 2,284,999 | – | – | – | – | – | – | – | – |
| 1 | 4,571,862 | 2,463,708 | 2,276,000 | 2,295,862 | 1,563 | 0.07% | 51 | 1,512 | 51 | 1,512 |
| 2 | 7,000,002 | 2,833,701 | 2,428,140 | 4,571,862 | 1,763 | 0.04% | 1,244 | 519 | 643 | 1,120 |

Quality per window snapshot:

| window | profiles | precision | recall | F1 | false-merge clusters |
|---|---|---|---|---|---|
| 0 | 2,295,862 | 0.000 | 1.000 | 0.000 | 0.47% |
| 1 | 4,571,862 | 0.983 | 0.964 | 0.973 | 0.43% |
| 2 | 7,000,002 | 0.986 | 0.924 | 0.954 | 0.48% |

## Resources

Wall 3652.8s · peak RSS 48,219 MB · mean CPU 157% (peak 543%, 32 cores) · 697 samples @ 5.0s

![resources](plots/resources.png)

| stage | wall s | peak RSS MB | mean CPU % |
|---|---|---|---|
| resolve:w0 | 608.0 | 17,320 | 142 |
| resolve:w1 | 1070.2 | 48,219 | 176 |
| resolve:w2 | 1380.4 | 29,112 | 167 |
| assemble | 140.5 | 32,376 | 100 |
| persist | 157.1 | 17,581 | 101 |
| metrics | 292.9 | 15,656 | 100 |
| report | 0.0 | 9,832 | 100 |

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
# dataset: /home/ubuntu/data/aurora-testdata/ncvoter-7m-nodob
python -m aurora_eval.cli run --adapter aurora_cdp --dataset /home/ubuntu/data/aurora-testdata/ncvoter-7m-nodob --seed 20261022 --run-name ncvoter-7m-nodob --date 2026-10-22 --isolate-windows --resource-interval 5 --timeout-s 36000 --max-stored-pairs 80000000 --cdp-config {"matcher": {"max_expanded_pairs": 300000000}} --reports-root ../aurora-cdp/reports
# resume after interruption: same command (checkpoints in /home/ubuntu/Projects/aurora-eval-harness/runs/ncvoter-7m-nodob/checkpoints)
```

## Files

- `metrics.json` — everything above, machine-readable (same shape as `aurora_eval.score()` output)
- `plots/` — PNGs embedded here
- `overmerge_clusters.json`, `overmerge_edges.parquet` — drill-down for the detector
- `provenance.json`, `resources.jsonl`, `events.jsonl`, `state.json` — provenance, resource samples, failure/retry log, stage state
