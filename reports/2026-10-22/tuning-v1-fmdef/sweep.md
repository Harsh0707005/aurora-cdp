# Blocking / threshold sweep (held-out seeds)

_Generated 2026-10-22T10:01:17.273504+00:00 · engine `a142c2fc25977aa1b9693384153873b8a615221f` (dirty) · 24 trials · wall 1516.3 s · peak RSS 2085.8 MB_

## Protocol

Tuned on: `small-s7` (tier small, seed 7, 20,000 profiles), `small-s11` (tier small, seed 11, 20,000 profiles).  
Confirmed on: `medium-s7` (tier medium, seed 7, 200,000 profiles).  
Reported tiers (seed 42: small / medium / large) are never read by this sweep; they are evaluated afterwards by the harness with the chosen config.

## Search space

| parameter | values |
|---|---|
| `matcher.scorer` | ['rules', 'ordinal'] |
| `matcher.match_threshold` | [2.5, 3.0, 3.5, 4.0] |
| `blocking.name_budget` | [20000, 50000, 200000] |
| `blocking.max_pairs_per_block` | [500000] |
| `blocking.sn_window` | [25] |

Gates (means over tuning corpora): precision ≥ 0.98, F1 ≥ 0.9, blocking recall ≥ 0.85, false-merge clusters ≤ 0.02.

## Ranking (gates first, then F1, then fewer scored pairs)

| # | scorer | threshold | name budget | max_pairs_per_block | sn_window | P | R | F1 | B³ F1 | blocking R | false-merge | pairs | wall s | gates (all tune corpora) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | rules | 3.5 | 20,000 | 500,000 | 25 | 0.9849 | 0.9122 | 0.9471 | 0.9412 | 0.8979 | 0.0425 | 292,682 | 5.05 | ❌ |
| 8 | rules | 3.5 | 50,000 | 500,000 | 25 | 0.9849 | 0.9122 | 0.9471 | 0.9412 | 0.8979 | 0.0425 | 292,682 | 5.15 | ❌ |
| 9 | rules | 3.5 | 200,000 | 500,000 | 25 | 0.9849 | 0.9122 | 0.9471 | 0.9412 | 0.8979 | 0.0425 | 292,682 | 5.0 | ❌ |
| 20 | ordinal | 3.5 | 50,000 | 500,000 | 25 | 0.9442 | 0.9486 | 0.9464 | 0.9446 | 0.8979 | 0.1156 | 292,682 | 13.85 | ❌ |
| 21 | ordinal | 3.5 | 200,000 | 500,000 | 25 | 0.9399 | 0.9502 | 0.945 | 0.9436 | 0.8979 | 0.1205 | 292,682 | 14.15 | ❌ |
| 4 | rules | 3.0 | 20,000 | 500,000 | 25 | 0.9784 | 0.9129 | 0.9445 | 0.9401 | 0.8979 | 0.0466 | 292,682 | 5.05 | ❌ |
| 5 | rules | 3.0 | 50,000 | 500,000 | 25 | 0.9784 | 0.9129 | 0.9445 | 0.9401 | 0.8979 | 0.0466 | 292,682 | 5.1 | ❌ |
| 6 | rules | 3.0 | 200,000 | 500,000 | 25 | 0.9784 | 0.9129 | 0.9445 | 0.9401 | 0.8979 | 0.0466 | 292,682 | 5.15 | ❌ |
| 1 | rules | 2.5 | 20,000 | 500,000 | 25 | 0.9771 | 0.913 | 0.944 | 0.9395 | 0.8979 | 0.0489 | 292,682 | 4.95 | ❌ |
| 2 | rules | 2.5 | 50,000 | 500,000 | 25 | 0.9771 | 0.913 | 0.944 | 0.9395 | 0.8979 | 0.0489 | 292,682 | 4.85 | ❌ |
| 3 | rules | 2.5 | 200,000 | 500,000 | 25 | 0.9771 | 0.913 | 0.944 | 0.9395 | 0.8979 | 0.0489 | 292,682 | 4.85 | ❌ |
| 19 | ordinal | 3.5 | 20,000 | 500,000 | 25 | 0.9388 | 0.9486 | 0.9436 | 0.9425 | 0.8979 | 0.1199 | 292,682 | 13.6 | ❌ |
| 18 | ordinal | 3.0 | 200,000 | 500,000 | 25 | 0.9356 | 0.9515 | 0.9435 | 0.9441 | 0.8979 | 0.1286 | 292,682 | 13.7 | ❌ |
| 16 | ordinal | 3.0 | 20,000 | 500,000 | 25 | 0.9355 | 0.9501 | 0.9427 | 0.9433 | 0.8979 | 0.1298 | 292,682 | 14.45 | ❌ |
| 17 | ordinal | 3.0 | 50,000 | 500,000 | 25 | 0.9346 | 0.9506 | 0.9426 | 0.9434 | 0.8979 | 0.1293 | 292,682 | 13.85 | ❌ |
| 22 | ordinal | 4.0 | 20,000 | 500,000 | 25 | 0.9437 | 0.9365 | 0.9401 | 0.9374 | 0.8979 | 0.1096 | 292,682 | 15.4 | ❌ |
| 14 | ordinal | 2.5 | 50,000 | 500,000 | 25 | 0.9297 | 0.949 | 0.9393 | 0.9412 | 0.8979 | 0.1386 | 292,682 | 19.55 | ❌ |
| 23 | ordinal | 4.0 | 50,000 | 500,000 | 25 | 0.9426 | 0.9358 | 0.9391 | 0.9365 | 0.8979 | 0.1119 | 292,682 | 16.6 | ❌ |
| 24 | ordinal | 4.0 | 200,000 | 500,000 | 25 | 0.9431 | 0.9345 | 0.9388 | 0.9361 | 0.8979 | 0.1118 | 292,682 | 14.95 | ❌ |
| 15 | ordinal | 2.5 | 200,000 | 500,000 | 25 | 0.9286 | 0.9485 | 0.9385 | 0.9402 | 0.8979 | 0.1419 | 292,682 | 18.8 | ❌ |
| 13 | ordinal | 2.5 | 20,000 | 500,000 | 25 | 0.9283 | 0.9486 | 0.9384 | 0.9407 | 0.8979 | 0.1412 | 292,682 | 26.95 | ❌ |
| 10 | rules | 4.0 | 20,000 | 500,000 | 25 | 0.9851 | 0.8869 | 0.9335 | 0.9309 | 0.8979 | 0.0415 | 292,682 | 4.95 | ❌ |
| 11 | rules | 4.0 | 50,000 | 500,000 | 25 | 0.9851 | 0.8869 | 0.9335 | 0.9309 | 0.8979 | 0.0415 | 292,682 | 5.35 | ❌ |
| 12 | rules | 4.0 | 200,000 | 500,000 | 25 | 0.9851 | 0.8869 | 0.9335 | 0.9309 | 0.8979 | 0.0415 | 292,682 | 7.65 | ❌ |

**Noise band:** top-3 F1 = [0.9471, 0.9471, 0.9471], spread 0.0 → the top configs are within noise of each other; the chosen one is the cheapest of them, not a clear winner.

## Confirmation on held-out corpora

| config | tune F1 / blocking R / false-merge | confirm F1 / blocking R / false-merge | gates on confirm |
|---|---|---|---|
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.5, 'blocking.name_budget': 20000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.9471 / 0.8979 / 0.0425 | 0.9444 / 0.889 / 0.0514 | ❌ |
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.5, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.9471 / 0.8979 / 0.0425 | 0.9444 / 0.8931 / 0.0514 | ❌ |
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.5, 'blocking.name_budget': 200000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.9471 / 0.8979 / 0.0425 | 0.9444 / 0.8946 / 0.0514 | ❌ |

**Chosen config:** `{'matcher.scorer': 'rules', 'matcher.match_threshold': 3.5, 'blocking.name_budget': 20000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25}` → written to `aurora_cdp/config/defaults.yaml` by hand (documented as swept), then evaluated on the reported seed-42 tiers by the harness.
