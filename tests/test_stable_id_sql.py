"""The DuckDB stable-ID core must reproduce the documented greedy max-overlap rule exactly (randomised check)."""

from __future__ import annotations

import random
from collections import Counter

from aurora_cdp.stitch.stable_id import assign_stable_ids


def _reference(current: dict[str, str], previous: dict[str, str]) -> dict[str, str]:
    """Brute-force greedy: weight desc, ties (prev id asc, cluster id asc), both endpoints free."""
    w: Counter = Counter()
    for rid, cid in current.items():
        if rid in previous:
            w[(previous[rid], cid)] += 1
    out, used_p, used_c = {}, set(), set()
    for (p, c), _ in sorted(w.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1])):
        if p in used_p or c in used_c:
            continue
        used_p.add(p)
        used_c.add(c)
        out[c] = p
    return out


def test_sql_core_matches_reference_on_random_histories():
    rng = random.Random(5)
    for trial in range(25):
        n = rng.randrange(20, 400)
        prev_ids = [f"P{i}" for i in range(rng.randrange(5, 60))]
        previous = {f"r{i}": rng.choice(prev_ids) for i in range(n) if rng.random() > 0.15}
        cur_ids = [f"C{i}" for i in range(rng.randrange(5, 80))]
        current = {f"r{i}": rng.choice(cur_ids) for i in range(n + rng.randrange(0, 30)) if rng.random() > 0.1}
        res = assign_stable_ids(current, previous)
        ref = _reference(current, previous)
        assert res.inherited == ref, trial
        inherited_ids = set(ref.values())
        for cid in set(current.values()):
            aid = res.cluster_to_id[cid]
            if cid in ref:
                assert aid == ref[cid]
            else:
                assert aid in res.minted and aid not in inherited_ids and aid not in set(previous.values())
        assert res.retired == set(previous.values()) - inherited_ids
        compared = sum(1 for r in current if r in previous)
        changed = sum(1 for r in current if r in previous and res.record_to_id[r] != previous[r])
        assert (res.jitter.records_compared, res.jitter.records_changed) == (compared, changed)
        kinds = Counter(c["change_type"] for c in res.pk_changes)
        assert kinds["added"] == sum(1 for r in current if r not in previous)
        assert kinds["deleted"] == sum(1 for r in previous if r not in current)
        assert kinds["updated"] == changed
