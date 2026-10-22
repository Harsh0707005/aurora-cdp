# Blocking / threshold sweep (held-out seeds)

_Generated 2026-10-22T10:16:13.446530+00:00 · engine `af26406833d146b927e5cab5f7073c719dfee846` · 6 trials · wall 889.4 s · peak RSS 2357.4 MB_

## Protocol

Tuned on: `small-s7` (tier small, seed 7, 20,000 profiles), `small-s11` (tier small, seed 11, 20,000 profiles).  
Confirmed on: `medium-s7` (tier medium, seed 7, 200,000 profiles).  
Reported tiers (seed 42: small / medium / large) are never read by this sweep; they are evaluated afterwards by the harness with the chosen config.

## Search space

| parameter | values |
|---|---|
| `matcher.scorer` | ['rules'] |
| `matcher.match_threshold` | [2.5, 3.0, 3.25, 3.5, 3.75, 4.0] |
| `blocking.name_budget` | [50000] |
| `blocking.max_pairs_per_block` | [500000] |
| `blocking.sn_window` | [25] |

Gates (means over tuning corpora): precision ≥ 0.98, F1 ≥ 0.9, blocking recall ≥ 0.85, false-merge clusters ≤ 0.02.

## Ranking (gates first, then F1, then fewer scored pairs)

| # | scorer | threshold | name budget | max_pairs_per_block | sn_window | P | R | F1 | B³ F1 | blocking R | false-merge | pairs | wall s | gates (all tune corpora) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | rules | 3.25 | 50,000 | 500,000 | 25 | 0.9848 | 0.9125 | 0.9473 | 0.9415 | 0.8979 | 0.0289 | 292,682 | 5.45 | ❌ |
| 4 | rules | 3.5 | 50,000 | 500,000 | 25 | 0.9849 | 0.9122 | 0.9471 | 0.9412 | 0.8979 | 0.0286 | 292,682 | 5.45 | ❌ |
| 5 | rules | 3.75 | 50,000 | 500,000 | 25 | 0.9851 | 0.9081 | 0.945 | 0.939 | 0.8979 | 0.0278 | 292,682 | 5.45 | ❌ |
| 2 | rules | 3.0 | 50,000 | 500,000 | 25 | 0.9784 | 0.9129 | 0.9445 | 0.9401 | 0.8979 | 0.0315 | 292,682 | 6.25 | ❌ |
| 1 | rules | 2.5 | 50,000 | 500,000 | 25 | 0.9771 | 0.913 | 0.944 | 0.9395 | 0.8979 | 0.033 | 292,682 | 5.4 | ❌ |
| 6 | rules | 4.0 | 50,000 | 500,000 | 25 | 0.9851 | 0.8869 | 0.9335 | 0.9309 | 0.8979 | 0.0265 | 292,682 | 5.35 | ❌ |

**Noise band:** top-3 F1 = [0.9473, 0.9471, 0.945], spread 0.0023 → the top configs are within noise of each other; the chosen one is the cheapest of them, not a clear winner.

## Confirmation on held-out corpora

| config | tune F1 / blocking R / false-merge | confirm F1 / blocking R / false-merge | gates on confirm |
|---|---|---|---|
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.25, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.9473 / 0.8979 / 0.0289 | 0.9442 / 0.8931 / 0.0365 | ❌ |
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.5, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.9471 / 0.8979 / 0.0286 | 0.9444 / 0.8931 / 0.0361 | ❌ |
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.75, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.945 / 0.8979 / 0.0278 | 0.9418 / 0.8931 / 0.0352 | ❌ |

**Chosen config:** `{'matcher.scorer': 'rules', 'matcher.match_threshold': 3.25, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25}` → written to `aurora_cdp/config/defaults.yaml` by hand (documented as swept), then evaluated on the reported seed-42 tiers by the harness.
