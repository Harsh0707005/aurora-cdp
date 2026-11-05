# Incremental vs full Stitch — equivalence measurement

_corpus `/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/small/profiles.parquet`, 30-day windows, overrides `{}`_

| window | incr mode | pairs scored full / incr | carried edges | wall full / incr | pair P / R vs full | records with identical membership | clusters full / incr |
|---|---|---|---|---|---|---|---|
| 0 | full | 8,798 / 8,798 | 0 | 0.4 s / 0.32 s | 1.0 / 1.0 | 100.00% | 1,517 / 1,517 |
| 1 | incremental | 35,373 / 34,352 | 173 | 0.68 s / 0.7 s | 1.0 / 1.0 | 100.00% | 2,167 / 2,167 |
| 2 | incremental | 83,412 / 78,938 | 597 | 1.08 s / 1.04 s | 1.0 / 1.0 | 100.00% | 2,507 / 2,507 |
| 3 | incremental | 149,234 / 140,860 | 934 | 1.52 s / 1.51 s | 1.0 / 1.0 | 100.00% | 2,713 / 2,713 |
| 4 | incremental | 229,024 / 212,676 | 1,486 | 1.96 s / 2.11 s | 1.0 / 1.0 | 100.00% | 2,916 / 2,916 |
| 5 | incremental | 329,258 / 303,535 | 2,234 | 2.24 s / 1.99 s | 1.0 / 1.0 | 100.00% | 3,086 / 3,086 |
