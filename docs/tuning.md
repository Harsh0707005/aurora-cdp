# Tuning

The pairwise match threshold (default **3.0** on the 0–5 scale, the documented Amperity default) is the main
lever between over-merging (false merges, ID churn through splits later) and under-merging (missed links).
`aurora tune --quick` sweeps a threshold grid on the synthetic demo dataset (two Stitch runs: a full run and
an incremental late batch), reports pairwise precision / recall / F1, the false-merge rate (share of
multi-record clusters mixing more than one true person) and ID churn (jitter on run 2), then writes the best
threshold to `.aurora/last_best.yaml`, which the config loader overlays. Selection rule: among thresholds whose
pairwise precision is at least `tuning.min_precision` (default 0.98; all thresholds if none qualify), take the
highest F1; ties go to the lowest ID churn, then to the value closest to Amperity's documented default 3.0.
Rationale: in a CDP a false merge (two people sharing one profile, later a split and ID churn) costs more than
a missed link, so recall is bought only when precision stays high. The synthetic set includes look-alikes
(same name and postal code) and household members (same surname and address) as hard negatives.

The table below is rewritten by the tuner between the AUTOGEN markers.

<!-- AUTOGEN:tuning-start -->
_Last sweep: 2026-10-22 04:35 UTC, synthetic demo (400 people, two runs: full + incremental). Best threshold (precision ≥ 0.98 if attainable, then F1, lowest churn, closest to 3.0): **4.0**._

| threshold | precision | recall | f1 | false_merge_rate | id_churn_pct | ids_minted_run2 | clusters_run1 | edges_run1 | seconds |
|---|---|---|---|---|---|---|---|---|---|
| 2.0 | 0.9447 | 0.9608 | 0.9527 | 0.0359 | 0.0 | 62.0 | 350.0 | 1123.0 | 0.42 |
| 2.5 | 0.9461 | 0.9608 | 0.9534 | 0.0331 | 0.0 | 62.0 | 351.0 | 1078.0 | 0.41 |
| 3.0 | 0.9951 | 0.8957 | 0.9428 | 0.0028 | 0.0 | 68.0 | 398.0 | 835.0 | 0.42 |
| 3.5 | 0.9951 | 0.8957 | 0.9428 | 0.0028 | 0.0 | 68.0 | 398.0 | 834.0 | 0.4 |
| **4.0** | 1.0 | 0.8957 | 0.945 | 0.0 | 0.0 | 68.0 | 399.0 | 833.0 | 0.42 |
<!-- AUTOGEN:tuning-end -->

## Other knobs (see `aurora_cdp/config/defaults.yaml`)

- `matcher.weights.*` — logistic weights per feature (hand-set; TODO learn from labelled signatures).
- `matcher.deterministic.*` — scores for exact-key rules.
- `blocking.block_size_limit` / `fk_block_size_limit` — size above which a block counts as *oversized* (nothing is skipped).
- `blocking.max_pairs_per_block` (global) and `strategies[].max_pairs_per_block` (per strategy) — an oversized block whose
  n·(n−1)/2 fits the budget is compared in full; beyond it the block is refined on `refine_keys` (composite secondary
  keys, until sub-blocks are ≤ `refine_target`) and swept with a sorted-neighbourhood window `sn_window`.
- `blocking.collapse_trivial_dupes` — identical records are blocked/scored once through a representative.
- `matcher.score_chunk_size`, `matcher.persist_features`, `matcher.export_expanded_dupe_pairs`, `matcher.max_expanded_pairs`.
- `storage.duckdb.{memory_limit, threads, temp_directory}` — the memory envelope of a run.
- `blocklist.*` — automatic bad-value thresholds.
- `cluster.supersized_min_size` — BFS partition threshold.
- `stable_id.jitter_alert_pct` — alert threshold (Amperity: 2%).

## Held-out sweep protocol (anti-overfitting)

`tools/sweep_blocking.py` sweeps the blocking budgets, the sorted-neighbourhood window and the match threshold on
corpora generated with seeds that the reported evaluations never use (tune: small seed 7 + small seed 11; confirm:
medium seed 7), ranks trials by gates → F1 → fewer scored pairs, reports the noise band of the top configs, and
confirms the top configs on the held-out medium corpus. The chosen values are then written to `defaults.yaml` and
evaluated by the harness on the reported seed-42 tiers (small, medium, large) **without re-tuning**; the report
states the generalisation gap (tuned-on vs held-out metrics). Output: `reports/<date>/tuning/sweep.md`.

## TODO
- Full sweep (`aurora tune --full`) on larger synthetic data and on a labelled real sample.
- Grid over weights, not just the threshold; per-attribute conflict tolerances.
