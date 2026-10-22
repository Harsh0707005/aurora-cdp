# Learned DNF blocking (self labels)

_Generated 2026-10-22T09:22:28.510847+00:00 · engine `55157c39107d424fc9125b2932fdae00e71fcd34` · trained on `small-s7` (tier small, seed 7), 20,000 sampled records, 5,000 positive pairs, self-label purity vs truth 1.000 · wall 38.4 s_

Result: `{"dnf_strategies": 5, "dnf_pc_train": 0.9828, "dnf_cost_train": 278003, "dnf_budget": 400000, "dnf_positives": 5000, "dnf_records": 20000, "dnf_fallback_reason": null}`

## Chosen conjunctions (greedy red-blue set cover)

| # | conjunction | PC | cost (sample pairs) | new positives | cumulative PC |
|---|---|---|---|---|---|
| 1 | given_name_canon.exact ∧ phone_match.exact | 0.3108 | 38,726 | 1554 | 0.3108 |
| 2 | surname_norm.suffix3 ∧ email_norm.exact | 0.785 | 102,749 | 3110 | 0.9328 |
| 3 | phone_match.exact ∧ house_no.exact | 0.0968 | 14,510 | 36 | 0.94 |
| 4 | email_local.exact ∧ birthdate_norm.exact | 0.082 | 11,216 | 22 | 0.9444 |
| 5 | given_name_canon.prefix3 ∧ email_norm.exact | 0.777 | 110,802 | 192 | 0.9828 |

## Unary predicates

| attribute | transform | blocks | cost | PC | pruned |
|---|---|---|---|---|---|
| surname_norm | soundex | 511 | 3,218,718 | 0.945 | cost |
| surname_norm | prefix3 | 627 | 3,258,957 | 0.9374 | cost |
| given_name_canon | soundex | 417 | 4,942,132 | 0.9272 | cost |
| surname_norm | suffix3 | 580 | 5,354,619 | 0.9256 | cost |
| given_name_canon | prefix3 | 611 | 4,619,938 | 0.9214 | cost |
| email_norm | prefix5 | 832 | 1,618,437 | 0.8658 | cost |
| email_local | prefix5 | 832 | 1,618,437 | 0.8658 | cost |
| surname_norm | exact | 1,300 | 2,583,075 | 0.8564 | cost |
| email_local | exact | 2,590 | 138,970 | 0.8494 |  |
| email_norm | exact | 2,819 | 133,915 | 0.846 |  |
| given_name_canon | exact | 1,223 | 3,844,871 | 0.8282 | cost |
| phone_match | suffix4 | 1,645 | 61,369 | 0.373 |  |
| phone_match | exact | 1,945 | 55,073 | 0.3664 |  |
| postal_norm | exact | 1,619 | 43,114 | 0.186 |  |
| postal_norm | prefix3 | 345 | 170,301 | 0.186 |  |
| address_norm | first_token | 1,647 | 44,516 | 0.1798 |  |
| house_no | exact | 1,601 | 44,513 | 0.1798 |  |
| address_norm | exact | 2,010 | 38,222 | 0.1692 |  |
| birthdate_norm | year | 71 | 255,252 | 0.1002 |  |
| birthdate_norm | exact | 1,630 | 17,071 | 0.0982 |  |
| loy_id_norm | exact | 0 | 0 | 0.0 | pc |
| ck | exact | 0 | 0 | 0.0 | pc |

## Learned vs fixed strategies (pairwise completeness on truth pairs / candidate pairs on the sample)

| corpus | role | fixed PC | fixed cost | learned PC | learned cost |
|---|---|---|---|---|---|
| small-s7 | train | 0.9014 | 432,785 | 0.676 | 278,003 |
| small-s11 (seed 11) | confirm | 0.8954 | 524,314 | 0.6766 | 343,730 |
| medium-s7 (seed 7) | confirm | 0.8864 | 105,340 | 0.659 | 28,607 |

Generalisation gap (train PC − confirm PC): [-0.0006, 0.017]

Overlay written to `configs/learned/dnf-self.yaml`; evaluate it on the reported tiers with the harness (`--cdp-config`).
