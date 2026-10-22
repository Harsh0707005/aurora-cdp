# Blocking / threshold sweep (held-out seeds)

_Generated 2026-10-22T10:33:39.217129+00:00 · engine `92e02c67912946a69522c4320c8429240a97c134` (dirty) · 20 trials · wall 833.4 s · peak RSS 2289.9 MB_

## Protocol

Tuned on: `small-s7` (tier small, seed 7, 20,000 profiles), `small-s11` (tier small, seed 11, 20,000 profiles).  
Confirmed on: `medium-s7` (tier medium, seed 7, 200,000 profiles).  
Reported tiers (seed 42: small / medium / large) are never read by this sweep; they are evaluated afterwards by the harness with the chosen config.

## Search space

| parameter | values |
|---|---|
| `matcher.scorer` | ['rules'] |
| `matcher.match_threshold` | [3.0, 3.25, 3.5, 3.75, 4.0] |
| `cluster.given_name_conflict_min` | [None, 0.5, 0.6, 0.7] |
| `blocking.name_budget` | [50000] |
| `blocking.max_pairs_per_block` | [500000] |
| `blocking.sn_window` | [25] |

Gates (means over tuning corpora): precision ≥ 0.98, F1 ≥ 0.9, blocking recall ≥ 0.85, false-merge clusters ≤ 0.02.

## Ranking (gates first, then F1, then fewer scored pairs)

| # | scorer | threshold | name budget | max_pairs_per_block | sn_window | P | R | F1 | B³ F1 | blocking R | false-merge | pairs | wall s | gates (all tune corpora) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | rules gn-conflict=0.5 | 3.25 | 50,000 | 500,000 | 25 | 0.9945 | 0.868 | 0.9268 | 0.936 | 0.8979 | 0.0175 | 292,682 | 5.05 | ✅ |
| 10 | rules gn-conflict=0.5 | 3.5 | 50,000 | 500,000 | 25 | 0.9945 | 0.8677 | 0.9266 | 0.9356 | 0.8979 | 0.0172 | 292,682 | 4.95 | ✅ |
| 7 | rules gn-conflict=0.6 | 3.25 | 50,000 | 500,000 | 25 | 0.997 | 0.863 | 0.9251 | 0.9344 | 0.8979 | 0.0132 | 292,682 | 5.0 | ✅ |
| 11 | rules gn-conflict=0.6 | 3.5 | 50,000 | 500,000 | 25 | 0.997 | 0.8629 | 0.925 | 0.9342 | 0.8979 | 0.0131 | 292,682 | 4.95 | ✅ |
| 14 | rules gn-conflict=0.5 | 3.75 | 50,000 | 500,000 | 25 | 0.9946 | 0.8639 | 0.9245 | 0.9335 | 0.8979 | 0.017 | 292,682 | 4.95 | ✅ |
| 3 | rules gn-conflict=0.6 | 3.0 | 50,000 | 500,000 | 25 | 0.9924 | 0.8632 | 0.9233 | 0.9332 | 0.8979 | 0.0154 | 292,682 | 5.45 | ✅ |
| 15 | rules gn-conflict=0.6 | 3.75 | 50,000 | 500,000 | 25 | 0.9971 | 0.8592 | 0.9229 | 0.9321 | 0.8979 | 0.0129 | 292,682 | 4.95 | ✅ |
| 5 | rules gn-conflict=None | 3.25 | 50,000 | 500,000 | 25 | 0.9848 | 0.9125 | 0.9473 | 0.9415 | 0.8979 | 0.0289 | 292,682 | 4.95 | ❌ |
| 9 | rules gn-conflict=None | 3.5 | 50,000 | 500,000 | 25 | 0.9849 | 0.9122 | 0.9471 | 0.9412 | 0.8979 | 0.0286 | 292,682 | 4.95 | ❌ |
| 13 | rules gn-conflict=None | 3.75 | 50,000 | 500,000 | 25 | 0.9851 | 0.9081 | 0.945 | 0.939 | 0.8979 | 0.0278 | 292,682 | 4.95 | ❌ |
| 1 | rules gn-conflict=None | 3.0 | 50,000 | 500,000 | 25 | 0.9784 | 0.9129 | 0.9445 | 0.9401 | 0.8979 | 0.0315 | 292,682 | 5.15 | ❌ |
| 17 | rules gn-conflict=None | 4.0 | 50,000 | 500,000 | 25 | 0.9851 | 0.8869 | 0.9335 | 0.9309 | 0.8979 | 0.0265 | 292,682 | 4.95 | ❌ |
| 2 | rules gn-conflict=0.5 | 3.0 | 50,000 | 500,000 | 25 | 0.9895 | 0.8682 | 0.9249 | 0.9348 | 0.8979 | 0.0197 | 292,682 | 5.3 | ❌ |
| 18 | rules gn-conflict=0.5 | 4.0 | 50,000 | 500,000 | 25 | 0.9948 | 0.8449 | 0.9137 | 0.9257 | 0.8979 | 0.0161 | 292,682 | 4.95 | ❌ |
| 8 | rules gn-conflict=0.7 | 3.25 | 50,000 | 500,000 | 25 | 0.9987 | 0.8397 | 0.9123 | 0.9282 | 0.8979 | 0.0097 | 292,682 | 4.95 | ❌ |
| 12 | rules gn-conflict=0.7 | 3.5 | 50,000 | 500,000 | 25 | 0.9987 | 0.8396 | 0.9122 | 0.9281 | 0.8979 | 0.0097 | 292,682 | 4.95 | ❌ |
| 19 | rules gn-conflict=0.6 | 4.0 | 50,000 | 500,000 | 25 | 0.9972 | 0.8403 | 0.9121 | 0.9243 | 0.8979 | 0.0121 | 292,682 | 4.95 | ❌ |
| 4 | rules gn-conflict=0.7 | 3.0 | 50,000 | 500,000 | 25 | 0.9945 | 0.84 | 0.9107 | 0.9271 | 0.8979 | 0.0119 | 292,682 | 5.15 | ❌ |
| 16 | rules gn-conflict=0.7 | 3.75 | 50,000 | 500,000 | 25 | 0.9987 | 0.8363 | 0.9103 | 0.926 | 0.8979 | 0.0096 | 292,682 | 4.95 | ❌ |
| 20 | rules gn-conflict=0.7 | 4.0 | 50,000 | 500,000 | 25 | 0.9989 | 0.8196 | 0.9004 | 0.9184 | 0.8979 | 0.009 | 292,682 | 4.95 | ❌ |

**Noise band:** top-3 F1 = [0.9268, 0.9266, 0.9251], spread 0.0017 → the top configs are within noise of each other; the chosen one is the cheapest of them, not a clear winner.

## Confirmation on held-out corpora

| config | tune F1 / blocking R / false-merge | confirm F1 / blocking R / false-merge | gates on confirm |
|---|---|---|---|
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.25, 'cluster.given_name_conflict_min': 0.5, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.9268 / 0.8979 / 0.0175 | 0.9306 / 0.8931 / 0.0276 | ❌ |
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.5, 'cluster.given_name_conflict_min': 0.5, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.9266 / 0.8979 / 0.0172 | 0.9307 / 0.8931 / 0.0274 | ❌ |
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.25, 'cluster.given_name_conflict_min': 0.6, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.9251 / 0.8979 / 0.0132 | 0.9268 / 0.8931 / 0.0233 | ❌ |

**Chosen config:** `{'matcher.scorer': 'rules', 'matcher.match_threshold': 3.25, 'cluster.given_name_conflict_min': 0.5, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25}` → written to `aurora_cdp/config/defaults.yaml` by hand (documented as swept), then evaluated on the reported seed-42 tiers by the harness.
