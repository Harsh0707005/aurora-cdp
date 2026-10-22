# Evaluation report — `small-ordinal-hn`

_Generated 2026-10-22T15:09:19 · dataset `small` · resolver `aurora_cdp` · threshold 0.6 (engine scale 3.0) · block cap 100 · seed 20261022_

## Provenance

```json
{
  "adapter": "aurora_cdp",
  "aurora_cdp_commit": "5adff2b7503948009c372faa64163fb2bafe054e",
  "aurora_cdp_commit_source": "git",
  "aurora_cdp_dirty_worktree": true,
  "aurora_cdp_path": "/Users/harshmaster/Desktop/Projects/aurora-cdp",
  "aurora_cdp_version": "0.1.0",
  "harness_commit": "1211f2017a2dcaf198a4002f7323561ee6e8edca",
  "harness_version": "0.1.0",
  "seed": 20261022,
  "dataset": "/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/small",
  "run_at": "2026-10-22T09:37:50+00:00",
  "host": {
    "platform": "macOS",
    "platform_release": "25.5.0",
    "machine": "arm64",
    "python": "3.11.11",
    "cpu_count": 8,
    "mem_total_gb": 8.59,
    "hostname": "Harshs-Macbook-Air"
  },
  "run_name": "small-ordinal-hn",
  "input_hash": "11fdbc3b5436556866db",
  "dataset_manifest_fingerprint": 1314847783426890627,
  "dataset_seed": 42,
  "sample": null
}
```

<details><summary><code>adapter config</code></summary>

```json
{
  "cdp_path": null,
  "config": "/Users/harshmaster/Desktop/Projects/aurora-cdp/.tmp/overlays/ordinal.yaml",
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
    "address_max_given_names": 40
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
    "match_threshold": 3.0,
    "scorer": "ordinal",
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
      "birthdate"
    ]
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
pairwise P=0.957 R=0.954 F1=0.956 | B3 F1=0.951 | false-merge clusters=6.75% (profiles 13.88%) | split persons=23.25% | ID churn/30d mean=2.66% max=4.42% | AUC-ROC=0.956 AP=0.989 blocking-recall=0.878
```

| Metric | Value |
|---|---|
| Pairwise precision / recall / F1 | 0.957 / 0.954 / 0.956 |
| Pairs: TP / FP / FN | 285,449 / 12,748 / 13,797 |
| B-cubed precision / recall / F1 | 0.956 / 0.946 / 0.951 |
| Clusters predicted / truth persons (ratio) | 2,311 / 2,000 (1.155) |
| Exact-match clusters | 1,328 (66.40% of persons) |
| **False-merge rate** (clusters / profiles / pairs) | 6.75% / 13.88% / 4.28% |
| Over-merged clusters (max persons in one) | 156 (7) |
| Split persons (profiles) | 465 = 23.25% (33.93% of profiles) |
| **ID churn per 30-day window** mean / max | 2.66% / 4.42% |
| Harmful share of churn (purity dropped) | 28.74% |
| AUC-ROC / average precision (candidate pairs) | 0.956 / 0.989 |
| Blocking recall (true pairs reaching scoring) | 0.878 |
| Operating point P / R-in-candidates / effective R | 0.967 / 0.884 / 0.776 |
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
| time: engine_load | 0.7s |
| time: engine_blocking | 9.15s |
| time: engine_scoring | 59.13s |
| time: engine_clustering | 1.05s |
| time: engine_stable_id | 0.25s |
| time: engine_persist | 0.6s |
| time: resolve_windows | 83.73s |
| time: wall_total | 85.28s |
| candidate pairs | 329,263 |
| block `engine (final snapshot)` | 97,863 pairs, 6,896 groups, 0 over cap (n/a) |

Engine snapshots (one engine run per replayed window; `previous=` carries stable ids forward):

| window | run_date | records | pairs scored | edges | clusters | skipped blocks | jitter % | ids minted | ids retired | engine s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2026-01-31 | 3,213 | 8,798 | 3,875 | 1,341 | 0 | 0.0 | 1341 | 0 | 1.87 |
| 1 | 2026-03-02 | 6,614 | 35,373 | 12,906 | 1,812 | 0 | 4.4195 | 525 | 54 | 4.69 |
| 2 | 2026-04-01 | 9,981 | 83,412 | 25,673 | 1,996 | 0 | 3.7194 | 264 | 80 | 11.54 |
| 3 | 2026-05-01 | 13,381 | 149,235 | 39,891 | 2,112 | 0 | 2.2242 | 184 | 68 | 15.51 |
| 4 | 2026-05-31 | 16,720 | 229,027 | 53,856 | 2,237 | 0 | 1.8011 | 171 | 46 | 25.36 |
| 5 | 2026-06-30 | 20,000 | 329,263 | 69,415 | 2,311 | 0 | 1.1543 | 110 | 36 | 24.76 |

## Score quality (candidate pairs)

![ROC](plots/roc.png) ![PR](plots/pr.png)

![score histogram](plots/score_hist.png)

## Threshold sweep (final window)

| threshold | precision | recall | F1 | B³ F1 | false-merge clusters | split persons | clusters |
|---|---|---|---|---|---|---|---|
| 0.30 | 0.377 | 0.970 | 0.543 | 0.844 | 12.66% | 13.60% | 1,691 |
| 0.35 | 0.377 | 0.970 | 0.543 | 0.844 | 12.66% | 13.60% | 1,691 |
| 0.40 | 0.377 | 0.970 | 0.543 | 0.844 | 12.66% | 13.60% | 1,691 |
| 0.45 | 0.447 | 0.970 | 0.612 | 0.850 | 12.32% | 14.35% | 1,729 |
| 0.50 | 0.498 | 0.969 | 0.658 | 0.862 | 11.07% | 15.65% | 1,816 |
| 0.55 | 0.572 | 0.965 | 0.718 | 0.881 | 8.94% | 17.75% | 1,947 |
| 0.60 | 0.581 | 0.964 | 0.725 | 0.883 | 8.31% | 18.90% | 1,997 |
| 0.65 | 0.778 | 0.957 | 0.859 | 0.911 | 6.97% | 22.55% | 2,211 |
| 0.70 | 0.847 | 0.952 | 0.897 | 0.922 | 5.63% | 26.15% | 2,380 |
| 0.75 | 0.916 | 0.921 | 0.919 | 0.929 | 3.37% | 33.15% | 2,702 |
| 0.80 | 0.945 | 0.869 | 0.905 | 0.915 | 2.28% | 43.60% | 3,159 |
| 0.85 | 0.964 | 0.757 | 0.848 | 0.827 | 1.01% | 67.35% | 4,635 |
| 0.90 | 0.999 | 0.373 | 0.544 | 0.516 | 0.17% | 90.15% | 9,625 |
| 0.95 | 0.999 | 0.134 | 0.236 | 0.363 | 0.09% | 92.30% | 11,318 |

Best F1 on this grid: threshold **0.75** (F1 0.919). Run `scripts/tune.py` for finer grids, precision-constrained objectives and weight search.

![sweep](plots/sweep.png)

## Clusters

![cluster sizes](plots/cluster_sizes.png)

| | predicted | truth |
|---|---|---|
| mean | 8.65 | 10.00 |
| p50 | 5.00 | 6.00 |
| p90 | 20.00 | 21.00 |
| p99 | 53.00 | 55.02 |
| max | 363 | 368 |
| singletons | 487 | 113 |

## Over-merge detector

156 predicted clusters conflate ≥2 persons, covering 2,775 profiles and 352 persons. 8,040 accepted edges cross a person boundary.

Which agreeing feature carried the bad edges (an edge can count in several columns; `only` = that feature was the sole agreement):

| feature | bad edges agreeing | sole agreement |
|---|---|---|
| engine_scored | 7,929 | 7,929 |
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
| `w0-d4bb5a56d4b8af4c` | 7 | 26 | engine_scored | ps_0001939: James Johnson; ps_0000423: James, james hohnson; ps_0001965: James Johnson; ps_0001235: J Johnsoh, james johnson |
| `w0-58f11bbee4bf5646` | 6 | 110 | engine_scored | ps_0000762: james rodriguez; ps_0001010: Patrick Rodriguez, patrick rodriguez; ps_0001991: Jack Rodriguez, jack rodriguez; ps_0001414: john rodriguez |
| `w0-5488df64ab91a5fe` | 6 | 30 | engine_scored | ps_0001095: matthew smith, matthew ssmith; ps_0001037: Matthew Smith, matthew sith; ps_0000791: Matt Smith, Matthew Smith; ps_0001041: raymod smith, raymond smith |
| `w0-c0f0f62ec742a5a3` | 4 | 58 | engine_scored | ps_0001239: John Hernandez; ps_0001574: John Heranndez; ps_0001545: Daniek Hernandez; ps_0000736: Robert Hernandez |
| `w0-790c1cb92038f476` | 4 | 55 | engine_scored | ps_0001935: JAMES MILLER, James Miller; ps_0001389: James Miller; ps_0000734: James Miller, james miller; ps_0000246: j miller |
| `w1-fe8a5adba1144379` | 4 | 27 | engine_scored | ps_0000731: James Rodriguez, j rodriguez; ps_0000594: James Rodriguez, james rodriguez; ps_0001314: james rodriguez; ps_0000762: james rodriguez |
| `w0-6964534e4edcf2da` | 4 | 24 | engine_scored | ps_0000416: John Taylor, jon taylor; ps_0001622: A Tayllor, Anna Taylor; ps_0000452: BARB TAYLOR, barbafa taylor; ps_0001914: John Taylor |
| `w2-d8877791092e34e8` | 4 | 20 | engine_scored | ps_0000697: nicholas smith, niholas smith; ps_0000426: Michael, Michael Smith; ps_0000349: J SMITH, James Smith; ps_0001178: Michael Smith |
| `w0-5f51af89cf34e2e4` | 4 | 18 | engine_scored | ps_0001290: Steven, steven dvis; ps_0001220: James Davis, james davis; ps_0000858: Christopher Davis; ps_0000080: Frank Davis, f davis |
| `w0-b8634dbf338d89a5` | 4 | 17 | engine_scored | ps_0000969: Robert Bfown, robert brown; ps_0000083: ROBERT, Robert Brown; ps_0000897: robert, robert brown; ps_0000130: Robert Brown, robert brown |
| `w0-b192a5e969176646` | 4 | 14 | engine_scored | ps_0000008: John Soctt, john scott; ps_0001502: Charles Scott; ps_0001339: charles scott, chuck scott; ps_0001336: Robert Csott, Robert Scoft |
| `w2-df17e5b950a2ddf5` | 4 | 14 | engine_scored | ps_0000617: Thomas Smith; ps_0000066: Jason Smith, jason smith; ps_0000128: James Smith; ps_0000227: jason smith |

## ID churn per 30-day window

Churn = carried-over profiles whose stable cluster id changed vs the previous window. *merge* = the profile's whole previous cluster was absorbed; *split* = otherwise. *harmful* = the profile's new cluster is less pure for its true person than the old one.

![churn](plots/churn.png)

| window | profiles | clusters | new | carried | churned | churn rate | merge | split | harmful | justified |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 3,213 | 1,341 | – | – | – | – | – | – | – | – |
| 1 | 6,614 | 1,812 | 3,401 | 3,213 | 142 | 4.42% | 62 | 80 | 40 | 102 |
| 2 | 9,981 | 1,996 | 3,367 | 6,614 | 246 | 3.72% | 106 | 140 | 95 | 151 |
| 3 | 13,381 | 2,112 | 3,400 | 9,981 | 222 | 2.22% | 106 | 116 | 64 | 158 |
| 4 | 16,720 | 2,237 | 3,339 | 13,381 | 241 | 1.80% | 74 | 167 | 58 | 183 |
| 5 | 20,000 | 2,311 | 3,280 | 16,720 | 193 | 1.15% | 55 | 138 | 43 | 150 |

Quality per window snapshot:

| window | profiles | precision | recall | F1 | false-merge clusters |
|---|---|---|---|---|---|
| 0 | 3,213 | 0.883 | 0.933 | 0.907 | 3.80% |
| 1 | 6,614 | 0.937 | 0.950 | 0.943 | 5.08% |
| 2 | 9,981 | 0.944 | 0.960 | 0.952 | 5.71% |
| 3 | 13,381 | 0.951 | 0.960 | 0.955 | 7.01% |
| 4 | 16,720 | 0.955 | 0.951 | 0.953 | 6.71% |
| 5 | 20,000 | 0.957 | 0.954 | 0.956 | 6.75% |

## Resources

Wall 87.9s · peak RSS 818 MB · mean CPU 99% (peak 124%, 8 cores) · 87 samples @ 1.0s

![resources](plots/resources.png)

| stage | wall s | peak RSS MB | mean CPU % |
|---|---|---|---|
| resolve:w0 | 1.9 | 299 | 91 |
| resolve:w1 | 4.8 | 411 | 100 |
| resolve:w2 | 11.7 | 465 | 99 |
| resolve:w3 | 15.7 | 492 | 100 |
| resolve:w4 | 25.7 | 484 | 98 |
| resolve:w5 | 25.2 | 702 | 101 |
| persist | 0.7 | 760 | 105 |
| metrics | 1.7 | 818 | 94 |
| report | 0.0 | 804 | 98 |

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
python -m aurora_eval.cli run --adapter aurora_cdp --dataset small --seed 20261022 --run-name small-ordinal-hn --date 2026-10-22 --reports-root /Users/harshmaster/Desktop/Projects/aurora-cdp/reports --cdp-config /Users/harshmaster/Desktop/Projects/aurora-cdp/.tmp/overlays/ordinal.yaml
# resume after interruption: same command (checkpoints in /Users/harshmaster/Desktop/Projects/aurora-eval-harness/runs/small-ordinal-hn/checkpoints)
```

## Files

- `metrics.json` — everything above, machine-readable (same shape as `aurora_eval.score()` output)
- `plots/` — PNGs embedded here
- `overmerge_clusters.json`, `overmerge_edges.parquet` — drill-down for the detector
- `provenance.json`, `resources.jsonl`, `events.jsonl`, `state.json` — provenance, resource samples, failure/retry log, stage state
