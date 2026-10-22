# Learned DNF blocking (truth labels)

_Generated 2026-10-22T09:22:47.646675+00:00 · engine `55157c39107d424fc9125b2932fdae00e71fcd34` · trained on `small-s7` (tier small, seed 7), 20,000 sampled records, 5,000 positive pairs, self-label purity vs truth 1.000 · wall 18.2 s_

Result: `{"dnf_strategies": 6, "dnf_pc_train": 0.7952, "dnf_cost_train": 392345, "dnf_budget": 400000, "dnf_positives": 5000, "dnf_records": 20000, "dnf_fallback_reason": null}`

## Chosen conjunctions (greedy red-blue set cover)

| # | conjunction | PC | cost (sample pairs) | new positives | cumulative PC |
|---|---|---|---|---|---|
| 1 | email_norm.exact ∧ house_no.exact | 0.1018 | 22,090 | 509 | 0.1018 |
| 2 | given_name_canon.exact ∧ email_norm.exact | 0.4542 | 99,814 | 1909 | 0.4836 |
| 3 | surname_norm.exact ∧ phone_match.suffix4 | 0.182 | 44,549 | 480 | 0.5796 |
| 4 | birthdate_norm.exact | 0.0724 | 17,071 | 107 | 0.601 |
| 5 | given_name_canon.exact ∧ postal_norm.exact | 0.1202 | 27,164 | 143 | 0.6296 |
| 6 | given_name_canon.soundex ∧ surname_norm.exact | 0.6002 | 181,657 | 828 | 0.7952 |

## Unary predicates

| attribute | transform | blocks | cost | PC | pruned |
|---|---|---|---|---|---|
| given_name_canon | soundex | 417 | 4,942,132 | 0.8344 | cost |
| given_name_canon | prefix3 | 611 | 4,619,938 | 0.8302 | cost |
| surname_norm | soundex | 511 | 3,218,718 | 0.7918 | cost |
| surname_norm | suffix3 | 580 | 5,354,619 | 0.782 | cost |
| surname_norm | prefix3 | 627 | 3,258,957 | 0.7788 | cost |
| given_name_canon | exact | 1,223 | 3,844,871 | 0.7446 | cost |
| surname_norm | exact | 1,300 | 2,583,075 | 0.7196 | cost |
| email_norm | prefix5 | 832 | 1,618,437 | 0.675 | cost |
| email_local | prefix5 | 832 | 1,618,437 | 0.675 | cost |
| email_local | exact | 2,590 | 138,970 | 0.6252 |  |
| email_norm | exact | 2,819 | 133,915 | 0.61 |  |
| phone_match | suffix4 | 1,645 | 61,369 | 0.2286 |  |
| phone_match | exact | 1,945 | 55,073 | 0.2204 |  |
| postal_norm | exact | 1,619 | 43,114 | 0.164 |  |
| postal_norm | prefix3 | 345 | 170,301 | 0.164 |  |
| address_norm | first_token | 1,647 | 44,516 | 0.1592 |  |
| house_no | exact | 1,601 | 44,513 | 0.1592 |  |
| address_norm | exact | 2,010 | 38,222 | 0.1494 |  |
| birthdate_norm | year | 71 | 255,252 | 0.0742 |  |
| birthdate_norm | exact | 1,630 | 17,071 | 0.0724 |  |
| loy_id_norm | exact | 0 | 0 | 0.0 | pc |
| ck | exact | 0 | 0 | 0.0 | pc |

## Learned vs fixed strategies (pairwise completeness on truth pairs / candidate pairs on the sample)

| corpus | role | fixed PC | fixed cost | learned PC | learned cost |
|---|---|---|---|---|---|
| small-s7 | train | 0.9014 | 432,785 | 0.7936 | 392,345 |
| small-s11 (seed 11) | confirm | 0.8954 | 524,314 | 0.7902 | 475,215 |
| medium-s7 (seed 7) | confirm | 0.8864 | 105,340 | 0.7758 | 92,354 |

Generalisation gap (train PC − confirm PC): [0.0034, 0.0178]

Overlay written to `configs/learned/dnf-truth.yaml`; evaluate it on the reported tiers with the harness (`--cdp-config`).
