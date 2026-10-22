"""Stable ID assignment across runs via maximum-overlap bipartite matching.

Given the previous run's ``(datasource, pk) -> aurora_id`` and the current
run's ``(datasource, pk) -> cluster_id``, build a bipartite graph whose edge
weights are the number of shared primary keys. Decompose it into connected
blocks; for each block solve the maximum-weight assignment with the Hungarian
algorithm (``scipy.optimize.linear_sum_assignment``) when the block is small
enough, otherwise with a greedy "largest remaining overlap first" pass.

Rules (the ones that produce *jitter*):

* **recognized** – one old cluster ↔ one new cluster, nothing else touched.
* **split** – an old cluster feeds several new clusters; only the
  largest-overlap fragment keeps the old ID, the others receive new IDs.
* **merged** – a new cluster absorbs several old clusters; the one with the
  largest overlap donates its ID, the others' IDs are retired.
* **split_merged** – both of the above at once.
* **added** – a new cluster with no overlap with any old cluster.
* **deleted** – an old ID with no surviving records (or that lost the matching).

Ties are broken by the lexicographically smaller old ID so results are stable
across runs with identical inputs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from aurora.utils.ids import aurora_id_from_seed, cluster_seed

EVENT_TYPES = ("added", "deleted", "merged", "recognized", "split", "split_merged")


@dataclass
class StableIdResult:
    cluster_to_id: dict[int, str]
    events: pd.DataFrame  # one row per new cluster or retired old id
    jitter: dict[str, float] = field(default_factory=dict)


def _block_components(overlaps: pd.DataFrame) -> list[tuple[list[str], list[int]]]:
    """Connected blocks of the bipartite old-id / new-cluster graph."""
    parent: dict[tuple[str, object], tuple[str, object]] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for old, new in zip(overlaps["aurora_id"], overlaps["cluster_id"], strict=True):
        a, b = find(("o", old)), find(("n", int(new)))
        if a != b:
            parent[a] = b
    groups: dict = defaultdict(lambda: ([], []))
    for node in list(parent):
        root = find(node)
        groups[root][0 if node[0] == "o" else 1].append(node[1])
    return [(sorted(o), sorted(n)) for o, n in groups.values()]


def _assign_block(
    olds: list[str], news: list[int], w: dict[tuple[str, int], int], hungarian_max_nodes: int
) -> list[tuple[str, int]]:
    """Return (old_id, new_cluster) matched pairs maximising total overlap."""
    if len(olds) == 1 and len(news) == 1:
        return [(olds[0], news[0])]
    if len(olds) + len(news) <= hungarian_max_nodes:
        from scipy.optimize import linear_sum_assignment

        m = np.zeros((len(olds), len(news)), dtype=float)
        for i, o in enumerate(olds):
            for j, n in enumerate(news):
                m[i, j] = w.get((o, n), 0)
        # tiny tie-break bonus favouring lower old id (olds is sorted) keeps results deterministic
        m += np.linspace(1e-6, 0, len(olds))[:, None]
        rows, cols = linear_sum_assignment(m, maximize=True)
        return [(olds[i], news[j]) for i, j in zip(rows, cols, strict=True) if w.get((olds[i], news[j]), 0) > 0]
    # greedy: sort by weight desc, then old id asc, new id asc
    cand = sorted(((o, n, cnt) for (o, n), cnt in w.items() if o in set(olds)), key=lambda t: (-t[2], t[0], t[1]))
    used_o: set[str] = set()
    used_n: set[int] = set()
    out = []
    for o, n, _ in cand:
        if o in used_o or n in used_n:
            continue
        out.append((o, n))
        used_o.add(o)
        used_n.add(n)
    return out


def assign_stable_ids(
    prev: pd.DataFrame | None,
    new: pd.DataFrame,
    namespace: str = "aurora-cdp",
    hungarian_max_nodes: int = 2000,
) -> StableIdResult:
    """Map new ``cluster_id`` values to stable ``aurora_id`` strings.

    ``prev`` columns: datasource, pk, aurora_id.  ``new`` columns: datasource, pk, cluster_id.
    """
    new = new[["datasource", "pk", "cluster_id"]].copy()
    new["cluster_id"] = new["cluster_id"].astype(int)
    members: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for ds, pk, cid in zip(new["datasource"], new["pk"], new["cluster_id"], strict=True):
        members[int(cid)].append((ds, pk))
    new_sizes = {cid: len(m) for cid, m in members.items()}

    cluster_to_id: dict[int, str] = {}
    rows: list[dict] = []
    if prev is None or prev.empty:
        for cid, m in members.items():
            cluster_to_id[cid] = aurora_id_from_seed(namespace, cluster_seed(m))
            rows.append({"cluster_id": cid, "current_id": cluster_to_id[cid], "previous_id": None,
                         "change_type": "added", "overlap": 0, "new_size": new_sizes[cid],
                         "previous_size": 0, "fragments": 0, "absorbed": 0})
        ev = pd.DataFrame(rows)
        return StableIdResult(cluster_to_id, ev, _jitter(ev, len(new)))

    prev = prev[["datasource", "pk", "aurora_id"]]
    prev_sizes = prev.groupby("aurora_id").size().to_dict()
    joined = new.merge(prev, on=["datasource", "pk"], how="left")
    overlaps = (
        joined.dropna(subset=["aurora_id"]).groupby(["aurora_id", "cluster_id"]).size().reset_index(name="n")
    )
    w = {(o, int(n)): int(c) for o, n, c in zip(overlaps["aurora_id"], overlaps["cluster_id"], overlaps["n"], strict=True)}
    old_to_news: dict[str, set[int]] = defaultdict(set)
    new_to_olds: dict[int, set[str]] = defaultdict(set)
    for o, n in w:
        old_to_news[o].add(n)
        new_to_olds[n].add(o)

    matched_new: dict[int, str] = {}
    for olds, news in _block_components(overlaps):
        for o, n in _assign_block(olds, news, w, hungarian_max_nodes):
            matched_new[n] = o
    matched_old = set(matched_new.values())

    for cid, m in members.items():
        olds = new_to_olds.get(cid, set())
        if cid in matched_new:
            old = matched_new[cid]
            fragments = len(old_to_news[old]) - 1
            absorbed = len(olds) - 1
            if fragments and absorbed:
                ct = "split_merged"
            elif fragments:
                ct = "split"
            elif absorbed:
                ct = "merged"
            else:
                ct = "recognized"
            cluster_to_id[cid] = old
            rows.append({"cluster_id": cid, "current_id": old, "previous_id": old, "change_type": ct,
                         "overlap": w[(old, cid)], "new_size": new_sizes[cid],
                         "previous_size": prev_sizes.get(old, 0), "fragments": fragments, "absorbed": absorbed})
        else:
            # unmatched: either brand-new records, or a split/merge loser -> fresh id
            new_id = aurora_id_from_seed(namespace, cluster_seed(m))
            cluster_to_id[cid] = new_id
            if olds:
                best = max(olds, key=lambda o: (w[(o, cid)], o))
                ct = "split_merged" if len(olds) > 1 else "split"
                rows.append({"cluster_id": cid, "current_id": new_id, "previous_id": best, "change_type": ct,
                             "overlap": w[(best, cid)], "new_size": new_sizes[cid],
                             "previous_size": prev_sizes.get(best, 0), "fragments": len(old_to_news[best]) - 1,
                             "absorbed": len(olds) - 1})
            else:
                rows.append({"cluster_id": cid, "current_id": new_id, "previous_id": None, "change_type": "added",
                             "overlap": 0, "new_size": new_sizes[cid], "previous_size": 0, "fragments": 0,
                             "absorbed": 0})
    for old in prev["aurora_id"].unique():
        if old not in matched_old:
            rows.append({"cluster_id": None, "current_id": None, "previous_id": old, "change_type": "deleted",
                         "overlap": 0, "new_size": 0, "previous_size": prev_sizes.get(old, 0),
                         "fragments": 0, "absorbed": 0})
    ev = pd.DataFrame(rows)
    return StableIdResult(cluster_to_id, ev, _jitter(ev, len(new)))


def _jitter(ev: pd.DataFrame, n_records: int) -> dict[str, float]:
    counts = {t: int((ev["change_type"] == t).sum()) for t in EVENT_TYPES}
    changed = ev[ev["change_type"] != "recognized"]
    affected = int(changed["new_size"].fillna(0).sum())
    counts["records"] = n_records
    counts["clusters"] = int(ev["current_id"].notna().sum())
    counts["percent"] = round(100.0 * affected / n_records, 3) if n_records else 0.0
    return counts
