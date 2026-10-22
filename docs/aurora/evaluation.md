# Evaluation

Latest job: `20261022-042509` (2026-10-22T04:25:36.050132+00:00)

- records: 4974
- clusters: 3067
- truth clusters: 3112

## B-cubed (cluster-level)

| precision | recall | f1 |
|---|---|---|
| 0.9771 | 0.9955 | 0.9862 |

## Pairwise over all true pairs (includes blocking misses)

| precision | recall | f1 | true pairs | predicted pairs |
|---|---|---|---|---|
| 0.8969 | 0.9899 | 0.9412 | 2286 | 2523 |

## Pairwise among candidate pairs by keep threshold

| threshold | precision | recall | f1 | tp | fp | fn |
|---|---|---|---|---|---|---|
| 2.0 | 0.9339 | 1.0 | 0.9658 | 2248 | 159 | 0 |
| 2.5 | 0.9339 | 1.0 | 0.9658 | 2248 | 159 | 0 |
| 3.0 | 0.9461 | 1.0 | 0.9723 | 2248 | 128 | 0 |
| 3.5 | 0.9613 | 0.9942 | 0.9775 | 2235 | 90 | 13 |
| 4.0 | 0.9839 | 0.9764 | 0.9801 | 2195 | 36 | 53 |
| 4.5 | 0.9982 | 0.9671 | 0.9824 | 2174 | 4 | 74 |
| 5.0 | 0.9986 | 0.9444 | 0.9707 | 2123 | 3 | 125 |

## Stable-ID churn vs previous run

- common records: 4827
- moved to a different aurora_id: 2
- churn: 0.041%

## Jitter events (this job)

- added: 144
- deleted: 36
- recognized: 2919
- split: 4

## Method

- **Pair P/R/F1** compares scored candidate pairs against `truth_id` equality; the *global* variant counts every true pair, so recall there also reflects blocking misses.
- **B-cubed** averages per-record precision/recall of its predicted cluster vs its truth cluster.
- **Churn** = share of records present in both runs whose `aurora_id` changed (jitter).

Regenerate with `make eval` (optionally `PREV=data/eval/prev_assignments.parquet`).
