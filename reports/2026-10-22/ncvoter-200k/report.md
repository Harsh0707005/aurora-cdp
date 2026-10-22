# Evaluation report — `ncvoter-200k`

_Generated 2026-10-22T13:47:41 · dataset `ncvoter-200k` · resolver `aurora_cdp` · threshold 0.6 (engine scale 3.0) · block cap 100 · seed 20261022_

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
  "dataset": "/home/ubuntu/data/aurora-testdata/ncvoter-200k",
  "run_at": "2026-10-22T13:46:45+00:00",
  "host": {
    "platform": "Linux",
    "platform_release": "7.0.0-1014-aws",
    "machine": "x86_64",
    "python": "3.11.17",
    "cpu_count": 32,
    "mem_total_gb": 264.74,
    "hostname": "ip-172-31-37-105"
  },
  "run_name": "ncvoter-200k",
  "input_hash": "3fc4039f9a895c4c51cd",
  "dataset_manifest_fingerprint": 2368289578311954877,
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
pairwise P=0.998 R=0.990 F1=0.994 | B3 F1=0.996 | false-merge clusters=0.10% (profiles 0.16%) | split persons=1.30% | ID churn/30d mean=0.14% max=0.24% | AUC-ROC=1.000 AP=0.999 blocking-recall=0.994
```

| Metric | Value |
|---|---|
| Pairwise precision / recall / F1 | 0.998 / 0.990 / 0.994 |
| Pairs: TP / FP / FN | 185,265 / 316 / 1,869 |
| B-cubed precision / recall / F1 | 0.999 / 0.994 / 0.996 |
| Clusters predicted / truth persons (ratio) | 74,734 / 73,849 (1.012) |
| Exact-match clusters | 72,747 (98.51% of persons) |
| **False-merge rate** (clusters / profiles / pairs) | 0.10% / 0.16% / 0.17% |
| Over-merged clusters (max persons in one) | 76 (2) |
| Split persons (profiles) | 960 = 1.30% (1.41% of profiles) |
| **ID churn per 30-day window** mean / max | 0.14% / 0.24% |
| Harmful share of churn (purity dropped) | 10.24% |
| AUC-ROC / average precision (candidate pairs) | 1.000 / 0.999 |
| Blocking recall (true pairs reaching scoring) | 0.994 |
| Operating point P / R-in-candidates / effective R | 0.947 / 1.000 / 0.994 |
| Scored candidate pairs (stored fraction) | 696,762 (100.00%) |

> **Notes**
> - Engine scores are normalised from the 0–5 band scale to [0, 1] (score/5); the operating threshold 0.60 is the engine's 3.0 on its own scale.
> - The threshold sweep re-clusters engine pair scores with plain connected components, so it approximates (does not reproduce) the engine's conflict-aware clustering at other thresholds.

## Dataset

| | |
|---|---|
| profiles | 200,003 |
| persons | 73,849 |
| true_pairs | 187,134 |
| profiles_per_person_max | 3 |
| singleton_persons | 8,675 |
| status | {'ACTIVE': 175453, 'INACTIVE': 24550} |
| records_with_phone | 94,275 |
| records_with_dob | 199,966 |
| records_with_address | 200,003 |

## Resolver run

| | |
|---|---|
| time: engine_load | 2.23s |
| time: engine_blocking | 0.71s |
| time: engine_scoring | 3.65s |
| time: engine_clustering | 2.59s |
| time: engine_stable_id | 0.91s |
| time: engine_persist | 2.36s |
| time: resolve_windows | 43.68s |
| time: wall_total | 48.39s |
| candidate pairs | 696,762 |
| block `engine (final snapshot)` | 101,345 pairs, 41,018 groups, 0 over cap (n/a) |

Engine snapshots (one engine run per replayed window; `previous=` carries stable ids forward):

| window | run_date | records | pairs scored | edges | clusters | skipped blocks | jitter % | ids minted | ids retired | engine s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2024-01-01 | 65,641 | 56,455 | 204 | 65,453 | 0 | 0.0 | 65453 | 0 | 7.68 |
| 1 | 2024-12-31 | 130,635 | 283,289 | 62,037 | 68,776 | 0 | 0.2361 | 3324 | 1 | 14.31 |
| 2 | 2025-12-31 | 200,003 | 696,762 | 125,880 | 74,734 | 0 | 0.0383 | 5985 | 27 | 21.69 |

## Score quality (candidate pairs)

![ROC](plots/roc.png) ![PR](plots/pr.png)

![score histogram](plots/score_hist.png)

## Threshold sweep (final window)

| threshold | precision | recall | F1 | B³ F1 | false-merge clusters | split persons | clusters |
|---|---|---|---|---|---|---|---|
| 0.30 | 0.079 | 0.994 | 0.146 | 0.816 | 16.69% | 0.72% | 51,427 |
| 0.35 | 0.080 | 0.994 | 0.148 | 0.819 | 16.21% | 0.73% | 51,843 |
| 0.40 | 0.093 | 0.994 | 0.170 | 0.842 | 14.01% | 0.73% | 54,357 |
| 0.45 | 0.223 | 0.994 | 0.364 | 0.893 | 10.90% | 0.73% | 60,263 |
| 0.50 | 0.725 | 0.994 | 0.838 | 0.953 | 7.23% | 0.73% | 67,861 |
| 0.55 | 0.794 | 0.994 | 0.883 | 0.965 | 5.60% | 0.73% | 69,519 |
| 0.60 | 0.942 | 0.994 | 0.967 | 0.989 | 1.74% | 0.75% | 73,026 |
| 0.65 | 0.990 | 0.990 | 0.990 | 0.995 | 0.33% | 1.31% | 74,562 |
| 0.70 | 0.998 | 0.941 | 0.969 | 0.981 | 0.06% | 7.58% | 79,535 |
| 0.75 | 0.999 | 0.941 | 0.969 | 0.981 | 0.03% | 7.63% | 79,596 |
| 0.80 | 0.999 | 0.927 | 0.962 | 0.976 | 0.03% | 9.44% | 81,019 |
| 0.85 | 0.999 | 0.903 | 0.949 | 0.968 | 0.02% | 12.48% | 83,380 |
| 0.90 | 0.999 | 0.903 | 0.949 | 0.968 | 0.02% | 12.51% | 83,405 |
| 0.95 | 1.000 | 0.901 | 0.948 | 0.968 | 0.00% | 12.75% | 83,617 |

Best F1 on this grid: threshold **0.65** (F1 0.990). Run `scripts/tune.py` for finer grids, precision-constrained objectives and weight search.

![sweep](plots/sweep.png)

## Clusters

![cluster sizes](plots/cluster_sizes.png)

| | predicted | truth |
|---|---|---|
| mean | 2.68 | 2.71 |
| p50 | 3.00 | 3.00 |
| p90 | 3.00 | 3.00 |
| p99 | 3.00 | 3.00 |
| max | 6 | 3 |
| singletons | 9,625 | 8,675 |

## Over-merge detector

76 predicted clusters conflate ≥2 persons, covering 320 profiles and 152 persons. 10,410 accepted edges cross a person boundary.

Which agreeing feature carried the bad edges (an edge can count in several columns; `only` = that feature was the sole agreement):

| feature | bad edges agreeing | sole agreement |
|---|---|---|
| engine_scored | 10,410 | 10,410 |
| email | 0 | 0 |
| phone | 0 | 0 |
| dob | 0 | 0 |
| postal | 0 | 0 |
| name | 0 | 0 |
| addr | 0 | 0 |
| engine_deterministic | 0 | 0 |
| engine_trivial_duplicate | 0 | 0 |

Worst clusters (full list in `overmerge_clusters.json`, edges in `overmerge_edges.parquet`):

| cluster | persons | profiles | dominant feature | sample names by person |
|---|---|---|---|---|
| `w0-05685f4d5fd89511` | 2 | 6 | engine_scored | BW10116: TONY MATTHEWS; DH12021: ANTHONY MATTHEWS |
| `w0-145b866ec2c801fa` | 2 | 6 | engine_scored | BC50462: MARY SHIPMAN; BC62972: MARGARET SIMMONS |
| `w0-2fc51aaad3ff6cc3` | 2 | 6 | engine_scored | BD93119: WILLIAM DAVIS; BF21821: BILLY DAVIS |
| `w0-32ef9ae40a7e11fa` | 2 | 6 | engine_scored | AX9214: JAMES POLLARD; CJ11085: JAMES POLLARD |
| `w0-375de31d4e111bf9` | 2 | 6 | engine_scored | AW154082: RANDALL PAINTER; AW173476: MALINDA PAINTER |
| `w0-486bba5c8e46829a` | 2 | 6 | engine_scored | BL555589: AUSTIN BROWN; EH1370567: AUSTIN BROWN |
| `w0-554333e99c4e693b` | 2 | 6 | engine_scored | BF2766: JAMES OVERTON; BF2767: JAMES OVERTON |
| `w0-5d1d42f3939b6c0e` | 2 | 6 | engine_scored | BG33068: DARRYL HILL; BG45048: DARRYL HILL |
| `w0-62e9a1304a641371` | 2 | 6 | engine_scored | EP72888: PATRICIA JOSEPH; EP77130: PATRICIA JONES |
| `w0-67702d3dd0e64665` | 2 | 6 | engine_scored | AX17760: MICHAEL BAKER; AX17767: PAMELA BAKER |
| `w0-792518d1b3596e2b` | 2 | 6 | engine_scored | AL269992: RYAN SMITH; CG120556: RYAN SMITH |
| `w0-8bce905242e0960e` | 2 | 6 | engine_scored | BN177488: MICHAEL BROWN; BN223493: MIKE BROWN |

## ID churn per 30-day window

Churn = carried-over profiles whose stable cluster id changed vs the previous window. *merge* = the profile's whole previous cluster was absorbed; *split* = otherwise. *harmful* = the profile's new cluster is less pure for its true person than the old one.

![churn](plots/churn.png)

| window | profiles | clusters | new | carried | churned | churn rate | merge | split | harmful | justified |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 65,641 | 65,453 | – | – | – | – | – | – | – | – |
| 1 | 130,635 | 68,776 | 64,994 | 65,641 | 155 | 0.24% | 1 | 154 | 1 | 154 |
| 2 | 200,003 | 74,734 | 69,368 | 130,635 | 50 | 0.04% | 36 | 14 | 20 | 30 |

Quality per window snapshot:

| window | profiles | precision | recall | F1 | false-merge clusters |
|---|---|---|---|---|---|
| 0 | 65,641 | 0.000 | 1.000 | 0.000 | 0.29% |
| 1 | 130,635 | 0.998 | 0.995 | 0.997 | 0.06% |
| 2 | 200,003 | 0.998 | 0.990 | 0.994 | 0.10% |

## Resources

Wall 54.9s · peak RSS 1,688 MB · mean CPU 110% (peak 145%, 32 cores) · 22 samples @ 2.0s

![resources](plots/resources.png)

| stage | wall s | peak RSS MB | mean CPU % |
|---|---|---|---|
| resolve:w0 | 8.6 | 963 | 106 |
| resolve:w1 | 15.4 | 1,346 | 106 |
| resolve:w2 | 23.2 | 1,688 | 111 |
| assemble | 1.2 | 1,522 | 142 |
| persist | 2.2 | 1,253 | 101 |
| metrics | 4.1 | 1,336 | 101 |
| report | 0.0 | 1,308 | 123 |

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
# dataset: /home/ubuntu/data/aurora-testdata/ncvoter-200k
python -m aurora_eval.cli run --adapter aurora_cdp --dataset /home/ubuntu/data/aurora-testdata/ncvoter-200k --seed 20261022 --run-name ncvoter-200k --date 2026-10-22 --resource-interval 2 --reports-root ../aurora-cdp/reports
# resume after interruption: same command (checkpoints in /home/ubuntu/Projects/aurora-eval-harness/runs/ncvoter-200k/checkpoints)
```

## Files

- `metrics.json` — everything above, machine-readable (same shape as `aurora_eval.score()` output)
- `plots/` — PNGs embedded here
- `overmerge_clusters.json`, `overmerge_edges.parquet` — drill-down for the detector
- `provenance.json`, `resources.jsonl`, `events.jsonl`, `state.json` — provenance, resource samples, failure/retry log, stage state
