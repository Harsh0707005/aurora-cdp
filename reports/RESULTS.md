# Aurora CDP — test results (as of 2026-10-29)

All numbers come from runs recorded under `reports/<date>/<run>/` (each with `metrics.json`, `report.md`, provenance). Nothing here was tuned on the data it is reported on.

## 1. EDAP → Amperity → EDAP contract, simulated (Williams-Sonoma feed shapes)

Feeds: ORDER_HEADER (bill-to PII), ORDER_LINE (ship-to PII), RETAIL_STORE_ESTIMATE_HEADER (clienteling PII) → Aurora resolve + households → CUSTOMER rows (survivorship, FIRST/SECOND/LATEST order, LIFETIME/L12M/L6M/L3M/L30D aggregates, RFM, flags) scored against the truth. Seven concepts; web / call-centre / POS channels; POS receipts carry only an e-mail (45 %), a phone (15 %), a loyalty id, or nothing (15 %, excluded as unlinkable); 10 % of DTC orders are gifts shipped to someone else; no date of birth in the contract. Generator: `tools/wsi_edap_sim.py`; evaluator: `tools/wsi_edap_eval.py`.

| run | persons | identity records | pairwise P / R / F1 | B³ F1 | false-merge clusters | split persons | gift recipients merged into buyer | CUSTOMER rows fully exact | lifetime net exact | household pair P / R | resolve |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3k, e-mail rule off (engine before 2026-10-29) | 3,000 | 19,264 | 0.996 / 0.811 / 0.894 | 0.907 | 0.32% | 34.8% | 0 / 1,148 | 69.8% | 71.2% | 1.0 / 0.5648 | 2.9 s |
| 3k, default engine | 3,000 | 19,264 | 0.996 / 0.922 / 0.958 | 0.953 | 0.37% | 21.7% | 0 / 1,148 | 81.6% | 83.0% | 1.0 / 0.6271 | 2.8 s |
| 3k, + phone-only rule | 3,000 | 19,264 | 0.996 / 0.962 / 0.978 | 0.967 | 0.52% | 15.4% | 0 / 1,148 | 87.5% | 88.8% | 1.0 / 0.6402 | 3.1 s |
| **60k, default engine** | 60,000 | 397,512 | 0.993 / 0.928 / 0.960 | 0.955 | 0.35% | 21.7% | 0 / 23,592 | 81.7% | 83.0% | 0.9998 / 0.6182 | 111.7 s |
| **60k, + phone-only rule** | 60,000 | 397,512 | 0.993 / 0.966 / 0.979 | 0.969 | 0.47% | 14.9% | 0 / 23,592 | 88.0% | 89.2% | 0.9998 / 0.6368 | 151.1 s |

Recall by the roles of the two records (60k, default engine):

| pair | pairs | recall |
|---|---|---|
| bill_to <-> ship_to_self | 1,509,735 | 0.9389 |
| bill_to <-> bill_to | 951,922 | 0.8838 |
| ship_to_self <-> ship_to_self | 488,576 | 0.9939 |
| bill_to <-> ship_to_gift | 40,733 | 0.8168 |
| ship_to_gift <-> ship_to_self | 14,504 | 0.9087 |
| estimate <-> ship_to_self | 11,887 | 0.9695 |
| ship_to_gift <-> ship_to_gift | 4,835 | 0.8269 |
| estimate <-> estimate | 1,203 | 0.9909 |
| estimate <-> ship_to_gift | 944 | 0.8231 |

CUSTOMER attribute exact-match share (60k, default engine; lowest first):

| attribute | exact |
|---|---|
| LIFETIME_ORDER_NET_AMT | 0.8300 |
| LIFETIME_ORDER_TOTAL_AMT | 0.8300 |
| LIFETIME_AVERAGE_ORDER_VALUE_AMT | 0.8300 |
| LIFETIME_AVERAGE_ITEM_PRICE | 0.8300 |
| LIFETIME_TOTAL_ITEMS | 0.8301 |
| LIFETIME_ORDER_FREQUENCY | 0.8306 |
| LIFETIME_STORES | 0.8542 |
| L12M_ORDER_NET_AMT | 0.9023 |
| L12M_ORDER_TOTAL_AMT | 0.9023 |
| L12M_AVERAGE_ORDER_VALUE_AMT | 0.9023 |
| L12M_TOTAL_ITEMS | 0.9024 |
| L12M_AVERAGE_ITEM_PRICE | 0.9024 |
| L12M_ORDER_FREQUENCY | 0.9026 |
| SECOND_ORDER_ID | 0.9061 |
| SECOND_ORDER_NET_AMT | 0.9061 |
| SECOND_ORDER_TOTAL_AMT | 0.9061 |
| FIRST_TO_SECOND_ORDER_DAYS | 0.9062 |
| SECOND_ORDER_DATE | 0.9063 |
| FIRST_TO_LATEST_ORDER_DAYS | 0.9066 |
| LIFETIME_PREFERRED_STORE_ID | 0.9139 |
| SECOND_ORDER_TOTAL_ITEMS | 0.9155 |
| L12M_STORES | 0.9165 |
| L12M_RFM_SCORE | 0.9254 |
| SECOND_ORDER_CHANNEL | 0.9256 |
| LIFETIME_AVERAGE_NUM_ITEMS | 0.9275 |
| L12M_FREQUENCY | 0.9305 |
| LIFETIME_CHANNELS | 0.9345 |
| SECOND_ORDER_STORE_ID | 0.9393 |
| SECOND_ORDER_BRAND | 0.9399 |
| L12M_PREFERRED_STORE_ID | 0.9409 |
| L12M_AVERAGE_NUM_ITEMS | 0.9451 |
| L6M_ORDER_NET_AMT | 0.9456 |
| L6M_ORDER_TOTAL_AMT | 0.9456 |
| L6M_TOTAL_ITEMS | 0.9456 |
| L6M_AVERAGE_ORDER_VALUE_AMT | 0.9456 |
| L6M_AVERAGE_ITEM_PRICE | 0.9456 |
| L6M_ORDER_FREQUENCY | 0.9458 |
| L12M_CHANNELS | 0.9483 |
| SINGLE_CHANNEL | 0.9484 |
| MULTI_CHANNEL | 0.9484 |
| LATEST_ORDER_ID | 0.9500 |
| LATEST_ORDER_NET_AMT | 0.9500 |
| LATEST_ORDER_TOTAL_AMT | 0.9500 |
| LATEST_ORDER_DATE | 0.9502 |
| DAYS_SINCE_LATEST_ORDER | 0.9502 |
| LIFETIME_LARGEST_ORDER_VALUE_AMT | 0.9506 |
| L12M_MONETARY | 0.9510 |
| FIRST_ORDER_ID | 0.9511 |
| FIRST_ORDER_NET_AMT | 0.9511 |
| FIRST_ORDER_TOTAL_AMT | 0.9511 |
| FIRST_ORDER_DATE | 0.9512 |
| PRIMARY_PHONE | 0.9514 |
| L12M_RFM_CUSTOMER_SEGMENT | 0.9519 |
| RETAIL_FLAG | 0.9538 |
| L6M_STORES | 0.9539 |
| LATEST_ORDER_STORE_ID | 0.9546 |
| FIRST_ORDER_STORE_ID | 0.9558 |
| RECENT_PHONE | 0.9559 |
| LIFETIME_BRANDS | 0.9579 |
| LATEST_ORDER_TOTAL_ITEMS | 0.9581 |
| FIRST_ORDER_TOTAL_ITEMS | 0.9590 |
| ONE_AND_DONE | 0.9610 |
| L12M_BRANDS | 0.9615 |
| L6M_AVERAGE_NUM_ITEMS | 0.9619 |
| L6M_PREFERRED_STORE_ID | 0.9631 |
| LIFETIME_PREFERRED_CHANNEL | 0.9639 |
| L12M_PREFERRED_CHANNEL | 0.9639 |
| L6M_CHANNELS | 0.9642 |
| L12M_RECENCY | 0.9644 |
| LATEST_ORDER_CHANNEL | 0.9647 |
| FIRST_ORDER_CHANNEL | 0.9655 |
| ADDRESS | 0.9659 |
| RECENT_EMAIL_ID | 0.9673 |
| EARLY_REPEAT_PURCHASER | 0.9674 |
| PRIMARY_EMAIL_ID | 0.9707 |
| L6M_BRANDS | 0.9710 |
| L3M_ORDER_NET_AMT | 0.9711 |
| L3M_ORDER_TOTAL_AMT | 0.9711 |
| L3M_TOTAL_ITEMS | 0.9711 |
| L3M_AVERAGE_ORDER_VALUE_AMT | 0.9711 |
| L3M_AVERAGE_ITEM_PRICE | 0.9711 |
| L3M_ORDER_FREQUENCY | 0.9712 |
| SINGLE_BRAND | 0.9716 |
| MULTI_BRAND | 0.9716 |
| L6M_PREFERRED_CHANNEL | 0.9722 |
| L12M_PREFERRED_BRAND | 0.9724 |
| ADDRESS2 | 0.9729 |
| FIRST_NAME | 0.9733 |
| CITY | 0.9752 |
| POSTAL_CD | 0.9752 |
| STATE_CD | 0.9753 |
| L3M_STORES | 0.9759 |
| L6M_PREFERRED_BRAND | 0.9760 |
| L3M_AVERAGE_NUM_ITEMS | 0.9766 |
| COUNTRY_CD | 0.9773 |
| L3M_CHANNELS | 0.9773 |
| LIFETIME_PREFERRED_BRAND | 0.9784 |
| L3M_PREFERRED_STORE_ID | 0.9787 |
| FIRST_ORDER_BRAND | 0.9790 |
| LATEST_ORDER_BRAND | 0.9791 |
| LAST_NAME | 0.9806 |
| L3M_BRANDS | 0.9808 |
| L3M_PREFERRED_CHANNEL | 0.9810 |
| L3M_PREFERRED_BRAND | 0.9827 |
| L30D_ORDER_NET_AMT | 0.9895 |
| L30D_ORDER_TOTAL_AMT | 0.9895 |
| L30D_ORDER_FREQUENCY | 0.9895 |
| L30D_TOTAL_ITEMS | 0.9895 |
| L30D_AVERAGE_ORDER_VALUE_AMT | 0.9895 |
| L30D_AVERAGE_ITEM_PRICE | 0.9895 |
| L30D_AVERAGE_NUM_ITEMS | 0.9904 |
| L30D_CHANNELS | 0.9905 |
| L30D_BRANDS | 0.9910 |
| L30D_PREFERRED_CHANNEL | 0.9912 |
| L30D_STORES | 0.9915 |
| L30D_PREFERRED_BRAND | 0.9916 |
| L30D_PREFERRED_STORE_ID | 0.9920 |
| LOYALTY_ACCT_CNT | 0.9933 |
| LOYALTY_MEMBER_FLAG | 0.9939 |
| CURRENT_EMPLOYEE_FLAG | 0.9996 |

Reading: every CUSTOMER attribute error traces to an identity split or merge; for correctly resolved clusters the survivorship and aggregate logic reproduces the expected row exactly. The remaining splits are mostly phone-only POS receipts; the phone-only rule (`matcher.deterministic.phone_exact_no_name_score`, off by default because phones are shared inside households) buys ~4 pts of recall and ~6 pts of fully-exact CUSTOMER rows for +0.12 pt of false-merge clusters. Household recall sits near the data ceiling (79 % of co-household pairs expose an address on both sides). Caveat: this is our simulation of the contract built from the DDL, not EDAP data.

## 2. Real PII: North Carolina voter-registration snapshots (2026-10-22)

Three statewide snapshots a year apart as three sources; NCID = truth. Real names, street addresses, households, moves; no e-mail; birth *year* only (the state publishes age).

| run | records | persons | P / R / F1 | B³ F1 | false-merge clusters | churn mean / max | engine, final window |
|---|---|---|---|---|---|---|---|
| ncvoter-200k | 200,003 | 73,849 | 0.998 / 0.990 / 0.994 | 0.996 | 0.10 % | 0.14 % / 0.24 % | 22 s |
| ncvoter-7m (birth year as DOB) | 7,000,002 | 2,585,325 | 0.911 / 0.987 / 0.947 | 0.983 | 3.00 % | 3.93 % / 6.92 % | 24 min |
| ncvoter-7m-nodob (ablation) | 7,000,002 | 2,585,325 | 0.986 / 0.924 / 0.954 | 0.973 | 0.48 % | 0.05 % / 0.07 % | 15 min |

| pair kind (7M) | share of true pairs | recall with year | without |
|---|---|---|---|
| identical name + address | 89.8 % | 1.000 | 0.998 |
| moved, same name | 9.0 % | 0.919 | 0.267 |
| surname changed, same address | 0.5 % | 0.550 | 0.446 |
| first name changed | 0.3 % | 0.684 | 0.563 |
| surname changed and moved | 0.4 % | 0.295 | 0.077 |

Reading: the 3 % false-merge rate at 7 M is the year-only birthdate (same name + same birth year collisions grow with N²); removing it cuts false merges to 0.5 % but drops mover recall because the year was the only evidence tying a mover's two addresses. A real date of birth or an e-mail gives both numbers at once. Engine lesson: hand-set weights do not know how discriminating a field is for the population; a classifier trained on labelled real pairs does.

## 3. Synthetic tiers (harness generator, seed 42, never used for tuning; 2026-10-22)

| gate | threshold | small 20k | medium 200k | large 1M |
|---|---|---|---|---|
| pairwise P / R / F1 | P ≥ 0.98, F1 ≥ 0.90 | 0.998 / 0.872 / 0.931 | 0.996 / 0.860 / 0.923 | 0.995 / 0.850 / 0.917 |
| B³ F1 | ≥ 0.93 | 0.937 | 0.934 | 0.934 |
| blocking recall | ≥ 0.85 | 0.878 | 0.892 | 0.872 |
| false-merge clusters | ≤ 2.0 % | 0.75 % | 0.83 % | 0.83 % |
| ID churn mean / max | report | 1.53 % / 2.19 % | 1.51 % / 2.47 % | 1.51 % / 2.39 % |
| wall (6 windows replayed) | | 10 s | 2 min | 26 min (r6a.4xlarge) |

All five gates pass on all three tiers. (After the 2026-10-29 e-mail rule the small tier reads 0.998 / 0.869 / 0.929, false merges 0.78 %: `reports/2026-10-29/small-idrule`.)

## 4. Performance work that made the large runs possible (2026-10-22)

| stage at 200k records (laptop) | before | after |
|---|---|---|
| blocking | 156.6 s | 0.6 s |
| scoring | 69.8 s | 21.3 s |
| whole run | 280.8 s | 51.8 s |

Cause: one accounting query in the zero-discard check (`NOT EXISTS … OR …`) scanned the pair table once per key row; plus per-element Python loops in the scorer and row-by-row date parsing. Output byte-identical.

## 5. What is left

1. A shadow run on a real EDAP extract next to Amperity's own CUSTOMER output — the decisive test.
2. A scorer trained on labelled real pairs (the ordinal scorer exists; it needs labels).
3. A tighter household rule (near-names at one address) and the phone-only policy, decided on real data.
4. Partitioned execution for tens of millions of records (single node is proven to 7–10 M).
5. Platform pieces outside identity: connectors, streaming, predictive models, warehouse bridge.

## Index of report directories

- `reports/2026-10-29/wsi-edap-p60k`, `wsi-edap-p60k-phonerule`, `wsi-edap-p3k-*` — EDAP-shaped simulation
- `reports/2026-10-22/ncvoter-200k`, `ncvoter-7m`, `ncvoter-7m-nodob` — NC voter data
- `reports/2026-10-22/small-v8-dupefix`, `medium-v4-dupefix`, `large-v2` — synthetic tiers (final engine); `large`, `large-fullpairs`, `large-head` — provenance runs
- `reports/production-readiness.md` — the decision memo with every section above in full
- 10 M-record EDAP corpus prepared (not yet run): `~/Documents/aanya/datasets/wsi-edap-sim/p1.5m`
