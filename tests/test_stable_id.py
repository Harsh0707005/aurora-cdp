"""Stable-ID max-overlap mapping: recognized / split / merge / added / deleted, Hungarian vs greedy."""

import pandas as pd

from aurora.graph.stable_id import assign_stable_ids


def _prev(assign: dict[str, str]):
    return pd.DataFrame({"datasource": "s", "pk": list(assign), "aurora_id": list(assign.values())})


def _new(assign: dict[str, int]):
    return pd.DataFrame({"datasource": "s", "pk": list(assign), "cluster_id": list(assign.values())})


def test_first_run_mints_deterministic_ids():
    new = _new({"a": 1, "b": 1, "c": 2})
    r1 = assign_stable_ids(None, new, "t")
    r2 = assign_stable_ids(None, new, "t")
    assert r1.cluster_to_id == r2.cluster_to_id
    assert r1.jitter["added"] == 2 and r1.jitter["recognized"] == 0


def test_recognized_split_merge_added_deleted():
    prev = _prev({"a": "A", "b": "A", "c": "A", "d": "B", "e": "B", "f": "C", "g": "D"})
    # A splits into {a,b} and {c}; {c} merges with B's {d,e}; C recognized with new row h; D vanishes; i is new
    new = _new({"a": 1, "b": 1, "c": 2, "d": 2, "e": 2, "f": 3, "h": 3, "i": 4})
    r = assign_stable_ids(prev, new, "t")
    assert r.cluster_to_id[1] == "A"            # largest fragment keeps A
    assert r.cluster_to_id[2] == "B"            # largest-overlap predecessor donates
    assert r.cluster_to_id[3] == "C"
    assert r.cluster_to_id[4] not in {"A", "B", "C", "D"}
    ev = r.events.set_index("cluster_id", drop=False)
    assert ev.loc[1, "change_type"] == "split"
    assert ev.loc[2, "change_type"] == "merged"
    assert ev.loc[3, "change_type"] == "recognized"
    assert ev.loc[4, "change_type"] == "added"
    assert (r.events["change_type"] == "deleted").sum() == 1
    assert r.events[r.events["change_type"] == "deleted"]["previous_id"].iloc[0] == "D"


def test_split_loser_gets_new_id_and_is_labelled_split():
    prev = _prev({"a": "A", "b": "A", "c": "A", "d": "A"})
    new = _new({"a": 1, "b": 1, "c": 2, "d": 2})  # exact tie 2 vs 2
    r = assign_stable_ids(prev, new, "t")
    ids = set(r.cluster_to_id.values())
    assert "A" in ids and len(ids) == 2
    assert sorted(r.events["change_type"]) == ["split", "split"]


def test_hungarian_and_greedy_agree_on_simple_block_and_hungarian_wins_when_greedy_is_myopic():
    # old X overlaps new 1 by 3 and new 2 by 2; old Y overlaps new 1 by 2 only.
    # Greedy: X->1 (3), Y unmatched.  Hungarian: X->2 (2) + Y->1 (2) = 4 > 3.
    prev = _prev({"a": "X", "b": "X", "c": "X", "d": "X", "e": "X", "f": "Y", "g": "Y"})
    new = _new({"a": 1, "b": 1, "c": 1, "d": 2, "e": 2, "f": 1, "g": 1})
    h = assign_stable_ids(prev, new, "t", hungarian_max_nodes=10)
    g = assign_stable_ids(prev, new, "t", hungarian_max_nodes=1)
    assert h.cluster_to_id == {1: "Y", 2: "X"}
    assert g.cluster_to_id[1] == "X" and g.cluster_to_id[2] not in {"X", "Y"}
    assert h.jitter["deleted"] == 0 and g.jitter["deleted"] == 1


def test_no_change_means_zero_jitter():
    prev = _prev({"a": "A", "b": "A", "c": "B"})
    new = _new({"a": 1, "b": 1, "c": 2})
    r = assign_stable_ids(prev, new, "t")
    assert r.jitter["recognized"] == 2 and r.jitter["percent"] == 0.0
