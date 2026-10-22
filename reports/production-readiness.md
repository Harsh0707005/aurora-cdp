# Production-readiness decision memo — aurora-cdp identity resolver

_Date 2026-10-22 · engine commit `95fc88d4b56d762d384dc952d63d9d1ecca37add` (clean worktree) · harness aurora-eval-harness @ `01795d8`+ · evaluation seed 20261022 · corpora seed 42 · host macOS arm64, 8 cores, 8.59 GB RAM, Python 3.11.11 · all runs local, no cloud spend._

Evidence: `reports/2026-10-22/{small,medium,large}/`, `reports/2026-10-22/public-*/`, `reports/2026-10-22/stress/`. Every report carries a provenance block (engine commit, fully expanded config, seed, dataset path, run time, host), a resource section and a *Metric validation* section. How to reproduce: `docs/evaluation.md`.

## Addendum 2026-10-22 (engine `6d2cf9b`) — blocking-recall defect closed; large tier moved to AWS

The block-size cap no longer discards anything: oversized blocks are compared in full within a pair budget or
sub-blocked on composite secondary keys plus a sorted-neighbourhood sweep, identical records are collapsed into
trivial-dupe groups, a name-prefix strategy covers records that carry only a name, and every run asserts
`records_dropped_by_blocking == 0`. Scoring is vectorised and streamed in chunks, clustering runs on integer
union-find, and stable IDs / change feeds / the ledger are computed inside DuckDB under an explicit memory limit.

| gate | before (`08be538`, small) | after (`6d2cf9b`, `reports/2026-10-22/small-v3`) |
|---|---|---|
| Pairwise P / R / F1 | 0.980 / 0.649 / 0.781 | **0.983 / 0.914 / 0.947** |
| B³ P / R / F1 | 0.987 / 0.881 / 0.931 | **0.983 / 0.908 / 0.944** |
| Blocking recall (≥ 0.85) | 0.537 | **0.878** |
| False-merge clusters / profiles / pairs | 1.75 % / 4.54 % / 1.96 % | 2.51 % / 5.41 % / 1.74 % (cluster-weighted now over the 2 % ceiling — recall was bought with the documented default weights; the threshold must be re-tuned on held-out seeds, see below) |
| ID churn mean / max per window | 1.65 % / 2.10 % | 1.33 % / 1.77 % |
| Records dropped by blocking | 5 skipped blocks | **0** (asserted) |
| Wall / peak RSS (20k, 6 windows) | 19 s / 0.87 GB | 18 s / 0.72 GB |

Update (engine `26bea50`, swept defaults threshold 3.25 + given-name conflict 0.6; `docs/tuning.md`): small seed 42
→ P/R/F1 0.999/0.882/0.937, B³ 0.940, blocking recall 0.878, false merges **1.01 %** (all gates); medium seed 42
(`reports/2026-10-22/medium-v2`) → 0.990/0.869/0.926, B³ 0.934, blocking recall 0.893, false merges **2.51 %**
(all gates except the 2.0 % false-merge ceiling). With HC_fusion and the trivial-dupe identifier rule (engine `300a425`+): small `small-v5` 0.998/0.872/0.931, B³ 0.937, 1.04 %; medium `medium-v3` 0.994/0.860/0.923, B³ 0.932, blocking recall 0.893, false merges **2.22 %** (ceiling still missed). The large tier is owned by the AWS task (an `r6a.4xlarge`
benchmark box was running at the time of writing). A 1M-row blocking-only probe with the new engine was interrupted before completing, so no 1M
number is claimed here. Tuning protocol: `tools/sweep_blocking.py` (held-out seeds 7/11, confirm medium seed 7)
was started and stopped for the same reason — the shipped defaults are the documented Amperity values plus
budgets chosen by reasoning, not by a sweep; that is recorded in `docs/feature-parity.md` (assumption 13) and is
the first thing to run on the AWS box.

Handed over to the Amperity-gap worker (not evaluated here): learned DNF blocking (`stitch/dnf.py`; on held-out
seed 7 the learned disjunction reaches PC 0.68 self-labelled / 0.79 truth-labelled vs 0.90 for the fixed list),
the ordinal scorer (`stitch/ordinal.py`, unit-tested, not wired), HC_fusion, stitch labels, households.

## Verdict (original, engine `95fc88d`)

**Not production-grade yet — conditional PASS on robustness, FAIL on recall at scale.**

The resolver is deterministic, crash-safe to operate, idempotent, and does not crash or drop records on malformed, duplicate-flooded or adversarial input; precision is excellent (≥ 0.98 pairwise, 1.00 on the public corpora) and false merges stay near the 2 % ceiling. It fails the accuracy and capacity gates for one structural reason: the blocking stage skips every block larger than `blocking.block_size_limit = 100`, so records of any person (or any shared key) with more than ~100 occurrences are never compared. That caps blocking recall at 0.54 (small) / 0.69 (medium) / 0.29 (UCI retail) and makes recall *collapse* under duplicate floods and supersized clusters (stress: recall 0.0006 / 0.004). Until hot-key blocks are handled (larger cap with supersized partitioning, or sub-blocking on a second key), the engine will systematically under-stitch the most valuable customers — exactly the ones with the most records.

| gate | threshold (production-grade) | small 20k/2k | medium 200k/20k | large 1M/100k | result |
|---|---|---|---|---|---|
| Pairwise F1 | ≥ 0.90 | 0.781 | **0.912** | pending | ❌ small / ✅ medium |
| Pairwise precision | ≥ 0.98 | 0.980 | 0.980 | pending | ✅ |
| B³ F1 | ≥ 0.93 | 0.931 | 0.936 | pending | ✅ |
| False-merge ceiling (cluster-weighted) | ≤ 2.0 % | 1.75 % | 2.12 % | pending | ⚠️ medium marginally over |
| False-merge ceiling (profile-weighted) | ≤ 5.0 % | 4.54 % | 5.62 % | pending | ⚠️ medium marginally over |
| False-merge (pair-level, 1 − P) | ≤ 2.0 % | 1.96 % | 1.97 % | pending | ✅ |
| Blocking recall floor | ≥ 0.85 | 0.537 | 0.690 | pending | ❌ |
| ID churn per 30-day window (harness) / engine jitter alert (2 %) | mean ≤ 2 %, no window ≥ 3 % | mean 1.65 %, max 2.10 % (2 engine alerts) | mean 1.57 %, max 2.63 % (1 engine alert) | pending | ⚠️ alerts fire |
| Determinism (same seed ⇒ identical partition, ids, metrics, report) | required | ✅ | ✅ | — | ✅ |
| Crash / abort recovery (SIGKILL mid-run → resume == clean run) | required | ✅ (test) | — | — | ✅ |
| Retry / timeout handling | required | ✅ (test + stress) | — | — | ✅ |
| Idempotent re-runs | required | ✅ (test) | — | — | ✅ |
| DQ edge cases: no crash, no dropped/duplicated keys | required | ✅ | — | — | ✅ |
| DQ edge cases: recall under hot-key floods | ≥ 0.5 | 0.0006 (dup flood), 0.004 (supersized) | — | — | ❌ |
| Resource envelope | small ≤ 1 GB / 1 min · medium ≤ 2.5 GB / 10 min · large ≤ 6.4 GB / 2 h | 0.87 GB, 19 s | 2.3 GB, 207 s | pending | ✅ small, ✅ medium |
| Metric validity | 100 % of gating metrics validated | 91/91 checks | 91/91 | — | ✅ |

## 1. Accuracy (seeded synthetic tiers, every 30-day window replayed with stable-id inheritance)

| | small (20k profiles / 2k persons) | medium (200k / 20k) |
|---|---|---|
| pairwise P / R / F1 | 0.980 / 0.649 / 0.781 | 0.980 / 0.853 / 0.912 |
| TP / FP / FN pairs | 160,149 / 2,082 / … | 1,983,507 / 39,766 / 341,680 |
| B³ P / R / F1 | 0.987 / 0.881 / 0.931 | 0.983 / 0.894 / 0.936 |
| false-merge: clusters / profiles / pairs | 1.75 % / 4.54 % / 1.96 % (max 4 persons in one cluster) | 2.12 % / 5.62 % / 1.97 % (max 4) |
| split persons | 36.2 % | 37.3 % |
| exact-match clusters | 60.9 % of persons | 60.0 % |
| AUC-ROC / AP over scored candidate pairs | 0.919 / 0.997 | 0.899 / 0.994 |
| blocking recall (true pairs that reached scoring) | **0.537** | **0.690** |
| operating point @ engine threshold 3.0 (0.60): P / R-in-candidates / effective R | 0.987 / 0.997 / 0.535 | 0.983 / 0.996 / 0.688 |
| engine: skipped (oversized) blocks in the final window | 5 | 21 |
| engine: edges rejected by birthdate hard-conflict | 2,605 | 31,809 |
| threshold sweep (harness connected components over engine scores) | — | best F1 0.882 @ 0.70; 0.60 is already on the precision plateau |

Reading: within the candidate set the scorer is close to perfect (recall-in-candidates 0.996–0.997, precision 0.98); essentially *all* missed pairs are pairs that were never scored. The corpora are deliberately skewed (max 368 / 275 / 547 profiles per person); every such person's e-mail / phone / name+postal block exceeds 100 and is skipped. The harness' own baseline stitcher with a block cap of 200 reaches blocking recall 0.866 and F1 0.910 on the same medium corpus (`aurora-eval-harness/reports/baseline-medium-s42`), so the data is stitchable.

Birthdate hard conflicts (31,809 rejected edges at medium) are doing real work: they keep false merges near 2 % on a corpus with 20 % households and 5 % twins.

## 2. Stability over time (ID churn / jitter per 30-day window)

Harness churn (share of carried-over records whose unified id changed) and the engine's own `jitter_pct` were cross-checked per window and agree exactly in every run. Medium: 2.63 %, 1.74 %, 1.45 %, 1.12 %, 0.94 % for windows 1–5 (harmful share of churn 15 %); small: 1.68 %, 2.10 %, 2.06 %, 1.32 %, 1.09 % (harmful 10 %). The engine's own ≥ 2 % alert fires in the early windows of both tiers and in UCI retail (4.26 %). Churn decays as the corpus matures, which is the expected merge-driven pattern; ids are never regenerated wholesale.

Engine finding: stable-id inheritance breaks equal-overlap ties by the *lexical order of the previous id strings*. With production uuid4 ids, which of two equal-size clusters keeps its id after a merge is therefore random (jitter counts are unaffected, the surviving id is). The harness neutralises this by feeding deterministic labels back as `previous=`; production should break the tie on a stable attribute (e.g. the older cluster) — recommendation R3.

## 3. Public, PII-free corpora (50k-profile samples, 4 snapshots, pseudonymous `loy_id` as the only key)

| corpus | profiles / persons / true pairs | P / R / F1 | B³ F1 | false-merge | blocking recall | skipped blocks | churn mean / max | wall · peak RSS |
|---|---|---|---|---|---|---|---|---|
| Olist | 50,001 / 48,306 / 2,039 | 1.000 / 0.617 / 0.763 | 0.994 | 0 % | 0.617 | 0 | 0 / 0 | 14 s · 0.32 GB |
| Instacart 2017 | 50,017 / 3,106 / 775,145 | 1.000 / 0.639 / 0.780 | 0.796 | 0 % | 0.639 | 0 | 0 / 0 | 36 s · 0.41 GB |
| UCI Online Retail II | 44,876 / 5,942 / 904,835 | 1.000 / **0.291** / 0.451 | 0.773 | 0 % | 0.291 | 19 | 2.3 % / 4.3 % | 28 s · 0.55 GB |

These are pipeline sanity checks, not accuracy benchmarks: the corpora have no names, e-mails or phones, so the only deterministic signal is a salted pseudonymous key present on 80 % of records (recall ceiling ≈ 0.64). Olist and Instacart sit exactly at that ceiling with zero false merges — the deterministic rule path, ingestion of real-world shapes, 25-month timelines and stable ids all work. UCI is the instructive one: wholesale customers with up to 510 invoices blow the 100-record block cap (19 blocks skipped), recall halves to 0.29, and ids churn 4.3 % in one window — the same block-cap failure mode as the synthetic tiers, now on real data.

## 4. Stress tests (`reports/2026-10-22/stress/`)

**Size ramp** (single pass, isolated child, uniform subsamples of the 1M corpus; limit 1800 s and 6.4 GB): 20k → 400k all passed; 400k = 107 s, 1.49 M candidate pairs, 1.99 GB peak RSS. Scaling between 20k and 400k: wall ∝ N^1.08, RSS ∝ N^0.28, candidate pairs ∝ N^1.99 (subsamples get denser as they grow). **No ceiling was hit up to 400k sampled records; the real capacity test is the full-density 1M run (section 6).**

**Throughput per 30-day window** (real tiers, uncontended re-run): 2.9k–7.0k records/s and 6k–30k scored pairs/s single-threaded; medium windows take 4.8 / 10.6 / 21.0 / 33.3 / 49.8 / 70.1 s, the final one (200k records, 1.67 M pairs) at 2.3 GB peak RSS. Time is dominated by candidate-pair count (Python-level scoring at ~15–30k pairs/s), not record count; RSS grows with the pair table (`features_json` per pair).

**Concurrency / backpressure** (20k records per job, pool of 4): 1 / 2 / 4 parallel jobs → aggregate 4.3k / 7.0k / 11.2k records/s (speed-up 1.6× at 2, 2.6× at 4), peak RSS of the whole tree 0.83 / 0.99 / 1.60 GB, every worker produced the identical partition, every record returned. The bounded pool queues excess jobs (queue wait measured; 0 s when jobs ≤ pool). Each worker is single-threaded, so parallelism is linear in memory (~0.4 GB per extra 20k job) — size a 1M job's workers by RSS, not CPU.

**Malformed / partial records and duplicate floods** (no crash, every record returned exactly once in all five cases):

| case | records | result |
|---|---|---|
| null-heavy (85 % blank cells, 10 % empty profiles, literal `NULL`/`nan`/`N/A`) | 20,000 | P 0.977, R 0.011 — blanks create no evidence (correct); literal null spellings are parsed as missing |
| duplicate flood (20 persons × ~1,000 copies) | 20,000 | 53 blocks skipped → **R 0.0006**; the engine refuses to stitch hot keys instead of exploding |
| supersized cluster (one person, 2,000 records sharing e-mail/phone) | 4,000 | 4 blocks skipped → **R 0.004**; `supersized_min_size = 500` partitioning never engages because the block is dropped first |
| adversarial Unicode (zero-width, RTL overrides, emoji, combining marks, 3k-char tokens, CSV/SQL-hostile text, control chars) | 5,000 | P 0.953, R 0.663, F1 0.782, deterministic across runs |

**Timeout handling:** a 20k-record window under a 0.5 s limit was killed in 1.3 s, logged as 2 failed attempts + 1 retry, surfaced as `StageFailed`, left no checkpoint and no orphan process.

## 5. Determinism, recovery, idempotency, metric validity (harness test suite, all against the real engine)

- **Determinism:** two seeded runs give byte-identical assignments, scores and metrics (order-insensitive partition signature + frame equality); cluster ids are invariant under any permutation of the input (unit + Hypothesis property tests); full re-runs of the small *and* medium tiers reproduced `metrics.json` (metrics, sweep, over-merge summary, per-window engine counters) exactly. `--no-deterministic-ids` is the documented legitimate-non-determinism toggle (raw uuid4 ids).
- **Crash / abort recovery:** the CLI is SIGKILLed after two window checkpoints; the resumed run reuses them, logs a `resume` event, and its assignments and metrics are bit-identical to an uninterrupted run.
- **Idempotency:** re-running a complete run with identical inputs recomputes nothing and leaves run and report directories byte-for-byte untouched; a new report date gets a pointer file; different inputs under the same name are refused without `--force`.
- **Metric validity:** 17 golden/sanity cases, 91 hand-computed checks (pairwise, B³, false-merge, split, blocking recall, AUC/AP, operating point, churn incl. merge/split and harmful/justified, perfect / all-singleton / all-merged / disjoint inputs) pass through the reports' own code path in every report; engine jitter is cross-checked against harness churn. Explicitly **untrusted** (no independent check, not used for gating): the threshold sweep (approximation), over-merge feature attribution, the score histogram, and engine counters reported verbatim.

## 6. Large tier (1M profiles / 100k persons)

Status: **PENDING — moved to the AWS evaluation box (2026-10-22).** The laptop (8.6 GB) did not complete the
1M run with the old engine and heavy local runs were stopped by instruction. The new engine's memory profile at
200k is 0.7 GB (small) and the per-record Python state is gone; the 1M/10M resource curve must come from the
AWS run. AWS prerequisites verified read-only on this machine: `aws` CLI 2.27, default profile (account
014490262341, region ap-south-1 — a **root** principal; use an IAM role on the box), SSH keys present; Docker
daemon not running locally; no terraform/cdk.

Resume if interrupted: `cd aurora-eval-harness && .venv/bin/aurora-eval run --adapter aurora_cdp --dataset large --seed 20261022 --run-name large --date 2026-10-22 --isolate-windows --resource-interval 2 --timeout-s 7200` (per-window checkpoints under `runs/large/checkpoints/`).

## 7. Recommendations (ordered)

1. **R1 — hot-key blocking.** Raise `blocking.block_size_limit` (the harness baseline uses 200) *and* make oversized blocks degrade gracefully (sub-block on a second key, or cap pairs per record) instead of being dropped; re-run the three tiers. Expected: blocking recall ≥ 0.85, pairwise F1 ≥ 0.90 on small, duplicate-flood recall > 0.5.
2. **R2 — memory and throughput at 1M.** `score_pairs` materialises every candidate pair as a Python dict with a `features_json` string; at ~8–9 M pairs this is several GB. Stream pairs in chunks and make feature persistence optional.
3. **R3 — deterministic stable-id tie-break.** Break equal-overlap ties on a stable cluster attribute, not the previous id string.
4. **R4 — jitter alerting.** The 2 % alert fires on healthy early windows; alert on *harmful* churn (purity dropped) or on the trend, and re-check once R1 lands (more merges early ⇒ less churn later).
5. **R5 — false-merge margin.** Medium sits at 2.12 % cluster-weighted; after R1 widens recall, re-verify the ceiling and consider adding `postal` to `cluster.conflict_attributes` for household twins.

## 8. Limitations (not executed or not executable here)

- **Large tier**: see section 6 — on this 8.6 GB laptop the 1M full-density run is memory-bound; whatever did not finish is documented there with resume instructions rather than extrapolated.
- **Stress ceiling**: the ramp stopped at 400k *sampled* records without failing; the ceiling beyond that was not probed except through the large run.
- **Public corpora**: 50k-profile samples only; the full Instacart (3.4 M orders) and UCI (1.07 M lines) corpora were not evaluated; the pseudonymous `loy_id` is an assumption that caps recall at ≈ 0.64 and the corpora carry no PII, so they say nothing about name/address matching quality.
- **Threshold sweep** approximates the engine's conflict-aware clustering with plain connected components (flagged in every report).
- **Over-merge attribution** can only use the engine's `match_type` because pair features are not exported by the stable interface.
- **No distributed / multi-node, no cloud, no GPU** runs; concurrency was tested as 1–4 single-threaded processes on one machine.
- **Engine config**: packaged defaults only (threshold 3.0, block cap 100); no tuning runs were executed against the engine.
- **Python**: the harness venv is 3.11.11 (uv-managed); the aurora-cdp repo's own `.venv` is 3.12 and was left untouched. Its Spark-engine tests need pyspark and were not run.
