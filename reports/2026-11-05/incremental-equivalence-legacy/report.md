# Incremental vs full Stitch — equivalence measurement

_corpus `/Users/harshmaster/Documents/aanya/datasets/aurora-testdata/small/profiles.parquet`, 30-day windows, overrides `{"matcher": {"incremental_recluster_neighbourhood": false}}`_

| window | incr mode | pairs scored full / incr | carried edges | wall full / incr | pair P / R vs full | records with identical membership | clusters full / incr |
|---|---|---|---|---|---|---|---|
| 0 | full | 8,798 / 8,798 | 0 | 0.3 s / 0.29 s | 1.0 / 1.0 | 100.00% | 1,517 / 1,517 |
| 1 | incremental | 35,373 / 31,415 | 1,696 | 0.61 s / 0.61 s | 0.99633 / 0.99774 | 99.03% | 2,167 / 2,167 |
| 2 | incremental | 83,412 / 66,892 | 4,447 | 0.95 s / 0.91 s | 0.97492 / 0.99434 | 94.87% | 2,507 / 2,505 |
| 3 | incremental | 149,234 / 110,240 | 7,476 | 1.39 s / 1.27 s | 0.96863 / 0.99008 | 93.38% | 2,713 / 2,713 |
| 4 | incremental | 229,024 / 157,580 | 10,668 | 1.93 s / 1.73 s | 0.96346 / 0.98367 | 91.36% | 2,916 / 2,907 |
| 5 | incremental | 329,258 / 219,885 | 13,813 | 2.12 s / 1.78 s | 0.9612 / 0.98205 | 90.00% | 3,086 / 3,075 |
