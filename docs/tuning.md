# Tuning

The pairwise match threshold (default **3.0** on the 0–5 scale, the documented Amperity default) is the main
lever between over-merging (false merges, ID churn through splits later) and under-merging (missed links).
`aurora tune --quick` sweeps a threshold grid on the synthetic demo dataset (two Stitch runs: a full run and
an incremental late batch), reports pairwise precision / recall / F1, the false-merge rate (share of
multi-record clusters mixing more than one true person) and ID churn (jitter on run 2), then writes the best
threshold (highest F1, ties → lowest churn) to `.aurora/last_best.yaml`, which the config loader overlays.

The table below is rewritten by the tuner between the AUTOGEN markers.

<!-- AUTOGEN:tuning-start -->
_No sweep recorded yet. Run `aurora tune --quick`._

| threshold | precision | recall | f1 | false_merge_rate | id_churn_pct | ids_minted_run2 | clusters_run1 | edges_run1 | seconds |
|---|---|---|---|---|---|---|---|---|---|
<!-- AUTOGEN:tuning-end -->

## Other knobs (see `aurora_cdp/config/defaults.yaml`)

- `matcher.weights.*` — logistic weights per feature (hand-set; TODO learn from labelled signatures).
- `matcher.deterministic.*` — scores for exact-key rules.
- `blocking.block_size_limit` / `fk_block_size_limit` — bigger = more recall, slower, riskier blackholes.
- `blocklist.*` — automatic bad-value thresholds.
- `cluster.supersized_min_size` — BFS partition threshold.
- `stable_id.jitter_alert_pct` — alert threshold (Amperity: 2%).

## TODO
- Full sweep (`aurora tune --full`) on larger synthetic data and on a labelled real sample.
- Grid over weights, not just the threshold; per-attribute conflict tolerances.
