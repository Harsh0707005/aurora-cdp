# Stress test — aurora-cdp resolver via aurora-eval-harness

_Generated 2026-10-22T11:09:49 · corpus `/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/large` (1,000,000 profiles) · RSS budget 6,442 MB · wall 223.7s_

## Provenance

```json
{
  "adapter": "aurora_cdp",
  "aurora_cdp_commit": "b6697b08995f8d167722221efd9d5a1d2c131714",
  "aurora_cdp_commit_source": "git",
  "aurora_cdp_dirty_worktree": false,
  "aurora_cdp_path": "/Users/harshmaster/Desktop/Projects/aurora-cdp",
  "aurora_cdp_version": "0.1.0",
  "harness_commit": "cbe663baea9ec428dd46fc0c7cdd91788d26e608",
  "harness_version": "0.1.0",
  "seed": 20261022,
  "dataset": "/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/large",
  "run_at": "2026-10-22T05:30:31+00:00",
  "host": {
    "platform": "macOS",
    "platform_release": "25.5.0",
    "machine": "arm64",
    "python": "3.11.11",
    "cpu_count": 8,
    "mem_total_gb": 8.59,
    "hostname": "Harshs-Macbook-Air"
  },
  "kind": "stress",
  "scenarios": [
    "windows",
    "flood",
    "timeout",
    "concurrency",
    "ramp"
  ]
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
  "windows": "final",
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

## Size ramp (single pass, isolated child process)

Limit per size: 1800s wall, 6,442 MB RSS. Each size is a seeded *uniform subsample* of the corpus, so it is sparser (fewer same-person pairs per record) than a real tier of that size — compare pairs/record with the per-window table below before reading these as tier throughput.

| records | status | wall s | engine s | pairs scored | pairs/s | records/s | peak RSS MB | mean CPU % | skipped blocks | max cluster |
|---|---|---|---|---|---|---|---|---|---|---|
| 20,000 | ok | 4.3 | 2.4 | 3,834 | 901 | 4,699 | 852 | 14 | 0 | 11 |
| 50,000 | ok | 8.4 | 6.3 | 24,108 | 2,862 | 5,936 | 942 | 17 | 0 | 32 |
| 100,000 | ok | 18.2 | 15.4 | 95,815 | 5,251 | 5,480 | 755 | 10 | 0 | 56 |
| 200,000 | ok | 36.3 | 32.2 | 377,968 | 10,407 | 5,507 | 1,216 | 10 | 1 | 79 |
| 400,000 | ok | 107.5 | 103.0 | 1,490,414 | 13,863 | 3,720 | 1,985 | 5 | 6 | 138 |

**Ceiling actually hit:** last size that passed = 400,000 records; no failure up to 400,000 records (larger sizes were not attempted).
Scaling exponents between the first and last passing size (log-log): wall ∝ N^1.08, peak RSS ∝ N^0.28, candidate pairs ∝ N^1.99.

## Concurrency and backpressure

20,000 records per job; worker pool of 4 — jobs beyond the pool size queue (backpressure) and the queue wait is measured.

| parallel jobs | effective | wall s | aggregate rec/s | speed-up vs serial | per-job wall s | max queue wait s | peak RSS MB (tree) | mean CPU % (tree) | identical partitions | all records returned |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 4.6 | 4,348.9 | 1.0 | 4.02 | 0.0 | 834 | 22 | ✅ | ✅ |
| 2 | 2 | 5.68 | 7,040.5 | 1.62 | 4.64, 4.64 | 0.0 | 986 | 26 | ✅ | ✅ |
| 4 | 4 | 7.17 | 11,151.0 | 2.57 | 5.15, 5.28, 5.28, 5.25 | 0.0 | 1,596 | 30 | ✅ | ✅ |

## Malformed / partial records and duplicate floods

Scale parameter 20,000.

| case | records | persons | status | wall s | peak RSS MB | pairs scored | skipped blocks | max cluster | pairwise P / R / F1 | false-merge clusters |
|---|---|---|---|---|---|---|---|---|---|---|
| null_heavy | 20,000 | 4000 | ok | 4.0 | 850 | 1,416 | 0 | 9 | 0.9771 / 0.0109 / 0.0215 | 0.0008 |
| literal_null_spellings | 10,000 | 2000 | ok | 3.0 | 676 | 10,126 | 0 | 40 | 0.9263 / 0.2304 / 0.369 | 0.0058 |
| duplicate_flood | 20,000 | 20 | ok | 4.2 | 522 | 4,919 | 53 | 26 | 0.9996 / 0.0006 / 0.0011 | 0.0001 |
| supersized_cluster | 4,000 | 401 | ok | 2.1 | 491 | 7,275 | 4 | 57 | 0.9515 / 0.0041 / 0.0081 | 0.0052 |
| adversarial_strings | 5,000 | 1000 | ok | 2.5 | 569 | 13,015 | 0 | 53 | 0.9529 / 0.6626 / 0.7817 | 0.0136 |

## Timeout handling

20,000 records resolved under a 0.5s limit with 1 retry: **killed_and_surfaced** in 1.28s; 2 failed attempt(s) and 1 retry logged; orphaned child processes afterwards: 0.

Surfaced error: `stage 'timeout_probe' failed after 2 attempts: window 0 exceeded 0.5s and was killed (pid 38766)`

## Throughput per 30-day window (tier runs on disk)

**small** (run state: complete)

| window | records | pairs scored | engine s | records/s | pairs/s | peak RSS MB | skipped blocks |
|---|---|---|---|---|---|---|---|
| 0 | 3,213 | 5,684 | 0.9 | 3,570 | 6,316 | 307 | 0 |
| 1 | 6,614 | 22,937 | 1.21 | 5,466 | 18,956 | 357 | 0 |
| 2 | 9,981 | 51,598 | 2.05 | 4,869 | 25,170 | 475 | 1 |
| 3 | 13,381 | 84,033 | 3.1 | 4,316 | 27,107 | 656 | 3 |
| 4 | 16,720 | 119,960 | 4.6 | 3,635 | 26,078 | 743 | 4 |
| 5 | 20,000 | 166,297 | 5.11 | 3,914 | 32,543 | 865 | 5 |

**medium** (run state: complete)

| window | records | pairs scored | engine s | records/s | pairs/s | peak RSS MB | skipped blocks |
|---|---|---|---|---|---|---|---|
| 0 | 33,331 | 48,322 | 4.75 | 7,017 | 10,173 | 652 | 0 |
| 1 | 66,557 | 197,787 | 10.57 | 6,297 | 18,712 | 1,070 | 0 |
| 2 | 99,677 | 444,622 | 20.95 | 4,758 | 21,223 | 1,123 | 0 |
| 3 | 132,926 | 778,901 | 33.32 | 3,989 | 23,376 | 1,403 | 3 |
| 4 | 166,430 | 1,193,049 | 49.78 | 3,343 | 23,966 | 2,257 | 9 |
| 5 | 200,000 | 1,673,355 | 70.06 | 2,855 | 23,885 | 2,324 | 21 |

## Files

- `stress.json` — all numbers above (machine-readable, with provenance)
- `*_resources.jsonl` — psutil samples per scenario step
