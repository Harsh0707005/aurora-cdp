# Blocking / threshold sweep (held-out seeds)

_Generated 2026-10-22T11:06:49.008853+00:00 · engine `24018bfd14bc1c1533f9f6cdbb81efb07470a0ca` · 16 trials · wall 791.4 s · peak RSS 2252.8 MB_

## Protocol

Tuned on: `small-s7` (tier small, seed 7, 20,000 profiles), `small-s11` (tier small, seed 11, 20,000 profiles).  
Confirmed on: `medium-s7` (tier medium, seed 7, 200,000 profiles).  
Reported tiers (seed 42: small / medium / large) are never read by this sweep; they are evaluated afterwards by the harness with the chosen config.

## Search space

| parameter | values |
|---|---|
| `matcher.scorer` | ['rules'] |
| `matcher.match_threshold` | [3.25] |
| `cluster.linkage` | ['single', 'fusion'] |
| `cluster.contact_conflict` | [False, True] |
| `matcher.trivial_dupe.requires_identifier` | [False, True] |
| `cluster.fusion.min_cross_edges` | [1, 2] |
| `blocking.name_budget` | [50000] |
| `blocking.max_pairs_per_block` | [500000] |
| `blocking.sn_window` | [25] |

Gates (means over tuning corpora): precision ≥ 0.98, F1 ≥ 0.9, blocking recall ≥ 0.85, false-merge clusters ≤ 0.02.

## Ranking (gates first, then F1, then fewer scored pairs)

| # | scorer | threshold | name budget | max_pairs_per_block | sn_window | P | R | F1 | B³ F1 | blocking R | false-merge | pairs | wall s | gates (all tune corpora) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | rules linkage=single contact_conflict=False trivial_dupe.requires_identifier=False fusion.min_cross_edges=1 | 3.25 | 50,000 | 500,000 | 25 | 0.9959 | 0.8584 | 0.922 | 0.9334 | 0.8979 | 0.0124 | 292,682 | 5.05 | ✅ |
| 2 | rules linkage=single contact_conflict=False trivial_dupe.requires_identifier=False fusion.min_cross_edges=2 | 3.25 | 50,000 | 500,000 | 25 | 0.9959 | 0.8584 | 0.922 | 0.9334 | 0.8979 | 0.0124 | 292,682 | 5.05 | ✅ |
| 3 | rules linkage=single contact_conflict=False trivial_dupe.requires_identifier=True fusion.min_cross_edges=1 | 3.25 | 50,000 | 500,000 | 25 | 0.9959 | 0.8584 | 0.922 | 0.9334 | 0.8979 | 0.0124 | 292,682 | 4.95 | ✅ |
| 4 | rules linkage=single contact_conflict=False trivial_dupe.requires_identifier=True fusion.min_cross_edges=2 | 3.25 | 50,000 | 500,000 | 25 | 0.9959 | 0.8584 | 0.922 | 0.9334 | 0.8979 | 0.0124 | 292,682 | 4.95 | ✅ |
| 9 | rules linkage=fusion contact_conflict=False trivial_dupe.requires_identifier=False fusion.min_cross_edges=1 | 3.25 | 50,000 | 500,000 | 25 | 0.9959 | 0.8584 | 0.922 | 0.9334 | 0.8979 | 0.0124 | 292,682 | 5.05 | ✅ |
| 11 | rules linkage=fusion contact_conflict=False trivial_dupe.requires_identifier=True fusion.min_cross_edges=1 | 3.25 | 50,000 | 500,000 | 25 | 0.9959 | 0.8584 | 0.922 | 0.9334 | 0.8979 | 0.0124 | 292,682 | 5.05 | ✅ |
| 10 | rules linkage=fusion contact_conflict=False trivial_dupe.requires_identifier=False fusion.min_cross_edges=2 | 3.25 | 50,000 | 500,000 | 25 | 0.9959 | 0.8579 | 0.9216 | 0.9328 | 0.8979 | 0.0124 | 292,682 | 5.05 | ✅ |
| 12 | rules linkage=fusion contact_conflict=False trivial_dupe.requires_identifier=True fusion.min_cross_edges=2 | 3.25 | 50,000 | 500,000 | 25 | 0.9959 | 0.8579 | 0.9216 | 0.9328 | 0.8979 | 0.0124 | 292,682 | 5.05 | ✅ |
| 5 | rules linkage=single contact_conflict=True trivial_dupe.requires_identifier=False fusion.min_cross_edges=1 | 3.25 | 50,000 | 500,000 | 25 | 0.996 | 0.8406 | 0.9115 | 0.9237 | 0.8979 | 0.0114 | 292,682 | 5.05 | ❌ |
| 6 | rules linkage=single contact_conflict=True trivial_dupe.requires_identifier=False fusion.min_cross_edges=2 | 3.25 | 50,000 | 500,000 | 25 | 0.996 | 0.8406 | 0.9115 | 0.9237 | 0.8979 | 0.0114 | 292,682 | 5.05 | ❌ |
| 7 | rules linkage=single contact_conflict=True trivial_dupe.requires_identifier=True fusion.min_cross_edges=1 | 3.25 | 50,000 | 500,000 | 25 | 0.996 | 0.8406 | 0.9115 | 0.9237 | 0.8979 | 0.0114 | 292,682 | 5.0 | ❌ |
| 8 | rules linkage=single contact_conflict=True trivial_dupe.requires_identifier=True fusion.min_cross_edges=2 | 3.25 | 50,000 | 500,000 | 25 | 0.996 | 0.8406 | 0.9115 | 0.9237 | 0.8979 | 0.0114 | 292,682 | 5.05 | ❌ |
| 13 | rules linkage=fusion contact_conflict=True trivial_dupe.requires_identifier=False fusion.min_cross_edges=1 | 3.25 | 50,000 | 500,000 | 25 | 0.996 | 0.8406 | 0.9115 | 0.9237 | 0.8979 | 0.0114 | 292,682 | 5.1 | ❌ |
| 15 | rules linkage=fusion contact_conflict=True trivial_dupe.requires_identifier=True fusion.min_cross_edges=1 | 3.25 | 50,000 | 500,000 | 25 | 0.996 | 0.8406 | 0.9115 | 0.9237 | 0.8979 | 0.0114 | 292,682 | 5.15 | ❌ |
| 14 | rules linkage=fusion contact_conflict=True trivial_dupe.requires_identifier=False fusion.min_cross_edges=2 | 3.25 | 50,000 | 500,000 | 25 | 0.996 | 0.8403 | 0.9114 | 0.9237 | 0.8979 | 0.0114 | 292,682 | 5.15 | ❌ |
| 16 | rules linkage=fusion contact_conflict=True trivial_dupe.requires_identifier=True fusion.min_cross_edges=2 | 3.25 | 50,000 | 500,000 | 25 | 0.996 | 0.8403 | 0.9114 | 0.9237 | 0.8979 | 0.0114 | 292,682 | 5.05 | ❌ |

**Noise band:** top-3 F1 = [0.922, 0.922, 0.922], spread 0.0 → the top configs are within noise of each other; the chosen one is the cheapest of them, not a clear winner.

## Confirmation on held-out corpora

| config | tune F1 / blocking R / false-merge | confirm F1 / blocking R / false-merge | gates on confirm |
|---|---|---|---|
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.25, 'cluster.linkage': 'single', 'cluster.contact_conflict': False, 'matcher.trivial_dupe.requires_identifier': False, 'cluster.fusion.min_cross_edges': 1, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.922 / 0.8979 / 0.0124 | 0.925 / 0.8931 / 0.0202 | ❌ |
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.25, 'cluster.linkage': 'single', 'cluster.contact_conflict': False, 'matcher.trivial_dupe.requires_identifier': False, 'cluster.fusion.min_cross_edges': 2, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.922 / 0.8979 / 0.0124 | 0.925 / 0.8931 / 0.0202 | ❌ |
| {'matcher.scorer': 'rules', 'matcher.match_threshold': 3.25, 'cluster.linkage': 'single', 'cluster.contact_conflict': False, 'matcher.trivial_dupe.requires_identifier': True, 'cluster.fusion.min_cross_edges': 1, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25} | 0.922 / 0.8979 / 0.0124 | 0.925 / 0.8931 / 0.0202 | ❌ |

**Chosen config:** `{'matcher.scorer': 'rules', 'matcher.match_threshold': 3.25, 'cluster.linkage': 'single', 'cluster.contact_conflict': False, 'matcher.trivial_dupe.requires_identifier': False, 'cluster.fusion.min_cross_edges': 1, 'blocking.name_budget': 50000, 'blocking.max_pairs_per_block': 500000, 'blocking.sn_window': 25}` → written to `aurora_cdp/config/defaults.yaml` by hand (documented as swept), then evaluated on the reported seed-42 tiers by the harness.
