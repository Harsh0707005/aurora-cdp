"""`stable_id.tie_break`: equal-overlap ties are resolved by age / size instead of the previous-id string."""

from __future__ import annotations

from datetime import datetime

import pytest

from aurora_cdp.stitch.stable_id import assign_stable_ids

OLD, NEW = datetime(2025, 1, 1), datetime(2026, 1, 1)


def test_documented_rule_is_lexical():
    # merge of two equal halves: the documented rule keeps the lexically smaller previous id
    current = {"r1": "C", "r2": "C", "r3": "C", "r4": "C"}
    previous = {"r1": "zz-old", "r2": "zz-old", "r3": "aa-new", "r4": "aa-new"}
    res = assign_stable_ids(current, previous, tie_break="documented")
    assert res.cluster_to_id["C"] == "aa-new"


def test_stable_rule_keeps_the_older_id_on_an_equal_merge():
    current = {"r1": "C", "r2": "C", "r3": "C", "r4": "C"}
    previous = {"r1": "zz-old", "r2": "zz-old", "r3": "aa-new", "r4": "aa-new"}
    res = assign_stable_ids(current, previous, tie_break="stable", first_seen={"zz-old": OLD, "aa-new": NEW})
    assert res.cluster_to_id["C"] == "zz-old"
    assert res.retired == {"aa-new"}


def test_stable_rule_keeps_the_id_on_the_larger_half_of_an_equal_split():
    # P splits into C-big (2 shared + 3 new records) and C-small (2 shared): the id follows more records
    current = {"r1": "zc-big", "r2": "zc-big", "n1": "zc-big", "n2": "zc-big", "n3": "zc-big", "r3": "aa-small", "r4": "aa-small"}
    previous = {"r1": "P", "r2": "P", "r3": "P", "r4": "P"}
    assert assign_stable_ids(current, previous, tie_break="documented").cluster_to_id["aa-small"] == "P"
    res = assign_stable_ids(current, previous, tie_break="stable", first_seen={"P": OLD})
    assert res.cluster_to_id["zc-big"] == "P"
    assert res.jitter.records_changed == 2


def test_stable_rule_without_metadata_falls_back_to_the_documented_order():
    current = {"r1": "C", "r2": "C", "r3": "C", "r4": "C"}
    previous = {"r1": "zz-old", "r2": "zz-old", "r3": "aa-new", "r4": "aa-new"}
    res = assign_stable_ids(current, previous, tie_break="stable")
    assert res.cluster_to_id["C"] == "aa-new"


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        assign_stable_ids({"r1": "C"}, {"r1": "P"}, tie_break="random")
