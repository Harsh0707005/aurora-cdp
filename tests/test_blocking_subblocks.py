"""Zero-discard blocking: oversized blocks are compared in full or sub-blocked, never dropped."""

from __future__ import annotations

import duckdb
import pandas as pd

from aurora_cdp.config import load_config
from aurora_cdp.stitch.blocking import build_blocks, build_candidate_pairs, load_records_table

BASE = dict(load_config(use_last_best=False).blocking)
EMAIL_ONLY = [{"name": "email_exact", "type": "email"}]


def _hot(n: int, **extra) -> dict[str, dict]:
    return {
        f"s|{i:05d}": {"datasource": "s", "pk": f"{i:05d}", "email_norm": "hot@example.org",
                       "given_name_canon": f"g{i % 7}", "given_name_norm": f"g{i % 7}", "surname_norm": f"s{i % 5}",
                       "postal_norm": f"{i % 11:05d}", "birthdate_norm": f"19{i % 60:02d}-01-01", **extra}
        for i in range(n)
    }


def test_full_comparison_within_pair_budget():
    cfg = {**BASE, "block_size_limit": 100, "max_pairs_per_block": 500_000, "strategies": EMAIL_ONLY}
    res = build_blocks(_hot(400), cfg)
    assert res.pair_count == 400 * 399 // 2
    assert res.oversized[0].handling == "full" and res.stats.records_dropped_by_blocking == 0


def test_refinement_beyond_budget_keeps_every_record():
    cfg = {**BASE, "block_size_limit": 10, "max_pairs_per_block": 200, "refine_target": 10, "sn_window": 5, "strategies": EMAIL_ONLY}
    recs = _hot(300)
    res = build_blocks(recs, cfg)
    o = res.oversized[0]
    assert o.handling == "refined" and o.sub_blocks > 1
    assert 0 < res.pair_count < 300 * 299 // 2
    touched = {a for a, _ in res.pairs} | {b for _, b in res.pairs}
    assert touched == set(recs)  # every record is a candidate in at least one pair
    assert res.stats.records_dropped_by_blocking == 0
    # records that share the composite key (same given/surname/postal/birthdate) are always compared
    same = [r for r in recs if recs[r]["given_name_canon"] == "g0" and recs[r]["surname_norm"] == "s0" and recs[r]["postal_norm"] == "00000"]
    for i, a in enumerate(same):
        for b in same[i + 1:]:
            assert (min(a, b), max(a, b)) in res.pairs


def test_duplicate_flood_collapses_to_representatives():
    """1,000 identical copies of 3 people: scored once per distinct record, expanded to all pairs."""
    recs = {}
    for p in range(3):
        for i in range(1000):
            recs[f"s|{p}-{i:04d}"] = {"datasource": "s", "pk": f"{p}-{i:04d}", "email_norm": f"p{p}@x.org", "given_name_norm": f"p{p}",
                                      "surname_norm": "flood", "postal_norm": "11111"}
    cfg = {**BASE, "strategies": EMAIL_ONLY}
    con = duckdb.connect(":memory:")
    load_records_table(con, recs)
    st = build_candidate_pairs(con, cfg)
    assert st.representatives == 3 and st.dupe_groups == 3 and st.pairs == 0  # three distinct people, no cross pairs
    assert st.records_dropped_by_blocking == 0
    con.close()
    res = build_blocks(recs, cfg)
    assert res.pair_count == 3 * (1000 * 999 // 2)  # expanded trivial-dupe pairs


def test_keyless_records_are_reported_not_asserted():
    recs = _hot(5) | {"s|zz": {"datasource": "s", "pk": "zz"}}
    res = build_blocks(recs, {**BASE, "strategies": EMAIL_ONLY})
    assert res.stats.records_without_any_blocking_key == 1
    assert res.stats.records_dropped_by_blocking == 0


def test_frame_input_and_fk_keys():
    df = pd.DataFrame([
        {"datasource": "a", "pk": "1", "fk_json": '{"pos": "7"}', "given_name_norm": "x"},
        {"datasource": "b", "pk": "2", "fk_json": '{"pos": "7"}', "given_name_norm": "y"},
        {"datasource": "b", "pk": "3", "fk_json": '{"pos": "8"}', "given_name_norm": "z"},
    ])
    con = duckdb.connect(":memory:")
    load_records_table(con, df)
    st = build_candidate_pairs(con, {**BASE, "strategies": [{"name": "fk", "type": "fk"}]})
    assert st.pairs == 1 and st.keys == 3


def test_name_strategy_and_per_strategy_budget():
    recs = {f"s|{i:03d}": {"datasource": "s", "pk": f"{i:03d}", "given_name_canon": "dorothy", "surname_norm": "hunter" if i % 2 else "hunterr",
                           "postal_norm": f"{i % 3}", "email_norm": f"e{i}@x.org"} for i in range(60)}  # distinct e-mails: no dupe collapse
    cfg = {**BASE, "strategies": [{"name": "name", "type": "name", "max_pairs_per_block": 300}], "sn_window": 2, "refine_target": 5}
    res = build_blocks(recs, cfg)
    assert res.oversized and res.oversized[0].handling == "refined"  # 60*59/2 > 300 -> refined on postal
    touched = {a for a, _ in res.pairs} | {b for _, b in res.pairs}
    assert touched == set(recs) and res.stats.records_dropped_by_blocking == 0
    assert ("s|000", "s|003") in res.pairs  # same postal sub-block (0 and 3 -> postal 0); trailing surname typo bridged by the 3-char prefix
