"""Clustering: connected components -> supersized partitioning -> conflict-aware single-link merge.

Amperity (internals §2.7-2.9): positive pairs are edges; connected components are *not* the answer because
transitive chains over-merge, so each component is re-clustered with hard-conflict rules; supersized
components are first broken apart with a bounded breadth-first search (US11704315).
Here: edges are processed in descending score (ties by ascending ids) and two clusters are unioned only when
no hard-conflict attribute disagrees between them. This is a deterministic, conflict-free single-link scheme.

Implementation note: everything runs on integer indices with array-based union-find; adjacency lists are
built only for the (rare) supersized components, so memory is O(records + edges) with small constants
(1M records / 10M edges fit comfortably in a few hundred MB).
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field

import numpy as np
from rapidfuzz.distance import JaroWinkler, Levenshtein

log = logging.getLogger(__name__)


@dataclass
class ClusterResult:
    assignment: dict[str, str] = field(default_factory=dict)  # rid -> cluster_id
    component: dict[str, str] = field(default_factory=dict)  # rid -> component_id
    supersized: dict[str, str] = field(default_factory=dict)  # rid -> supersized_id
    members: dict[str, list[str]] = field(default_factory=dict)  # cluster_id -> [rid]
    qa: dict = field(default_factory=dict)
    # integer views (same information, no per-record Python objects beyond the rid list)
    rids: list[str] = field(default_factory=list)
    cluster_idx: np.ndarray | None = None  # position -> cluster root index
    component_idx: np.ndarray | None = None
    supersized_idx: np.ndarray | None = None  # -1 when not supersized


def _short_id(seed: str) -> str:
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


class UnionFind:
    """Array union-find with path halving; roots are always the smallest index of their set."""

    def __init__(self, n: int):
        self.parent = np.arange(n, dtype=np.int64)

    def find(self, x: int) -> int:
        p = self.parent
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return int(x)

    def union(self, a: int, b: int) -> int:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if rb < ra:  # keep the smallest index as root -> deterministic, order-independent ids
            ra, rb = rb, ra
        self.parent[rb] = ra
        return ra

    def roots(self) -> np.ndarray:
        p = self.parent
        # iterate to full compression (depth is tiny after halving, so a few passes suffice)
        while True:
            q = p[p]
            if np.array_equal(q, p):
                return p
            p[:] = q


# per-attribute conflict tolerance (Amperity internals §2.8: a cluster is conflict-free when the weakest pairwise
# similarity inside each attribute's value set stays above that attribute's tolerance t_j)
DEFAULT_TOLERANCES = {"birthdate": {"measure": "levenshtein_max", "value": 2}}


def tolerances_from_cfg(cfg) -> dict[str, dict]:
    tol = {k: dict(v) for k, v in (cfg.get("conflict_tolerances") or {}).items()}
    if "birthdate" not in tol:  # legacy knob
        tol["birthdate"] = {"measure": "levenshtein_max", "value": int(cfg.get("birthdate_typo_tolerance", 2))}
    return tol


def _pair_ok(x: str, y: str, spec: dict | None) -> bool:
    if x == y:
        return True
    if not spec:
        return False  # exact agreement required
    measure, value = spec.get("measure", "exact"), spec.get("value")
    if measure == "levenshtein_max":
        return Levenshtein.distance(x, y) <= int(value)
    if measure == "jaro_winkler_min":
        return JaroWinkler.normalized_similarity(x, y) >= float(value)
    if measure == "exact":
        return False
    raise ValueError(f"unknown conflict measure {measure!r}")


def _values_compatible(attr: str, vals_a: set[str], vals_b: set[str], tol) -> bool:
    """``tol`` is either the legacy birthdate Levenshtein tolerance (int) or the tolerance dict per attribute."""
    if not vals_a or not vals_b:
        return True
    spec = tol.get(attr) if isinstance(tol, dict) else ({"measure": "levenshtein_max", "value": tol} if attr == "birthdate" else None)
    for x in vals_a:
        for y in vals_b:
            if not _pair_ok(x, y, spec):
                return False
    return True


def _bfs_partition(adj: dict[int, list[int]], nodes: list[int], max_size: int) -> list[list[int]]:
    """Bounded BFS partitioning of an oversized component (US11704315 analogue)."""
    remaining = set(nodes)
    parts: list[list[int]] = []
    while remaining:
        start = min(remaining)
        visited: list[int] = []
        queue = deque([start])
        seen = {start}
        while queue and len(visited) < max_size:
            n = queue.popleft()
            visited.append(n)
            for nb in sorted(adj.get(n, ())):
                if nb in remaining and nb not in seen:
                    seen.add(nb)
                    queue.append(nb)
        parts.append(visited)
        remaining -= set(visited)
    return parts


def cluster_indices(
    n: int,
    left: np.ndarray,
    right: np.ndarray,
    score: np.ndarray,
    conflict_values: list[dict[str, list[str | None]]] | dict[str, list],
    cfg,
    forbidden: list[tuple[int, int]] | None = None,
) -> ClusterResult:
    """Integer core. ``left/right/score`` are parallel edge arrays over indices 0..n-1;
    ``conflict_values`` maps attr -> list (length n) of that record's value (or None).
    ``forbidden`` lists index pairs that must never share a cluster (Stitch *split* labels): a union that would
    bring such a pair together is rejected like a hard attribute conflict (counted in
    ``edges_rejected_by_label``). Returns a ClusterResult with only the integer views filled (``rids`` empty).
    """
    max_size = int(cfg.get("supersized_min_size", 500))
    conflict_attrs = list(cfg.get("conflict_attributes", ["birthdate"]))
    tol = tolerances_from_cfg(cfg)
    left = np.asarray(left, dtype=np.int64)
    right = np.asarray(right, dtype=np.int64)
    score = np.asarray(score, dtype=np.float64)
    m = len(left)

    # 1. connected components
    uf = UnionFind(n)
    for a, b in zip(left.tolist(), right.tolist(), strict=True):
        uf.union(a, b)
    comp = uf.roots().copy()
    comp_sizes = np.bincount(comp, minlength=n)
    big_roots = np.flatnonzero(comp_sizes > max_size)
    supersized = np.full(n, -1, dtype=np.int64)

    # 2. supersized components: bounded BFS partition; group id per record restricts later unions
    group = comp.copy()
    if len(big_roots):
        big_set = set(big_roots.tolist())
        adj: dict[int, list[int]] = defaultdict(list)
        mask = np.isin(comp[left], big_roots)
        for a, b in zip(left[mask].tolist(), right[mask].tolist(), strict=True):
            adj[a].append(b)
            adj[b].append(a)
        for root in big_roots.tolist():
            nodes = np.flatnonzero(comp == root).tolist()
            supersized[nodes] = root
            for part in _bfs_partition(adj, nodes, max_size):
                gid = min(part)
                group[part] = gid
        del adj
        log.info("partitioned %d supersized components (> %d records)", len(big_set), max_size)

    # 3. conflict-aware single link, strongest edges first (ties: ascending ids)
    order = np.lexsort((right, left, -score))
    uf2 = UnionFind(n)
    values: dict[str, list] = {attr: list(conflict_values[attr]) for attr in conflict_attrs}
    # per-root value sets, created lazily on first merge; singletons use their own scalar value
    root_vals: dict[int, dict[str, set[str]]] = {}

    def vals_of(root: int, attr: str) -> set[str]:
        rv = root_vals.get(root)
        if rv is not None and attr in rv:
            return rv[attr]
        v = values[attr][root]
        return {v} if v else set()

    # pair-level vetoes (split labels): per root, the record indices its members must not be clustered with
    forbid: dict[int, set[int]] = defaultdict(set)
    for a, b in forbidden or ():
        if a != b:
            forbid[int(a)].add(int(b))
            forbid[int(b)].add(int(a))

    def label_blocks(ra: int, rb: int) -> bool:
        fa, fb = forbid.get(ra), forbid.get(rb)
        if fa and any(uf2.find(x) == rb for x in fa):
            return True
        return fb is not None and any(uf2.find(x) == ra for x in fb)

    rejected = 0
    rejected_label = 0
    for e in order.tolist():
        a, b = int(left[e]), int(right[e])
        if group[a] != group[b]:
            continue
        ra, rb = uf2.find(a), uf2.find(b)
        if ra == rb:
            continue
        if forbid and label_blocks(ra, rb):
            rejected_label += 1
            continue
        ok = True
        for attr in conflict_attrs:
            if not _values_compatible(attr, vals_of(ra, attr), vals_of(rb, attr), tol):
                ok = False
                break
        if not ok:
            rejected += 1
            continue
        merged = {attr: vals_of(ra, attr) | vals_of(rb, attr) for attr in conflict_attrs}
        root = uf2.union(a, b)
        root_vals.pop(ra, None)
        root_vals.pop(rb, None)
        root_vals[root] = merged
        if forbid:
            fa, fb = forbid.pop(ra, set()), forbid.pop(rb, set())
            if fa or fb:
                forbid[root] = fa | fb
    cluster = uf2.roots().copy()

    sizes = np.bincount(cluster, minlength=n)
    cluster_sizes = sizes[sizes > 0]
    comp_count = int(len(np.unique(comp)))
    # components split by hard conflicts: components whose records map to > 1 cluster
    pairs = np.unique(np.stack([comp, cluster], axis=1), axis=0)
    per_comp = np.bincount(pairs[:, 0], minlength=n)
    split_components = int(np.sum(per_comp > 1))
    hist: dict[str, int] = defaultdict(int)
    for s in cluster_sizes.tolist():
        bucket = (
            "1"
            if s == 1
            else (
                "2"
                if s == 2
                else "3-5" if s <= 5 else "6-10" if s <= 10 else "11-50" if s <= 50 else "50+"
            )
        )
        hist[bucket] += 1
    res = ClusterResult(cluster_idx=cluster, component_idx=comp, supersized_idx=supersized)
    res.qa = {
        "components": comp_count,
        "clusters": int(len(cluster_sizes)),
        "max_component_size": int(np.max(comp_sizes)) if n else 0,
        "max_cluster_size": int(np.max(cluster_sizes)) if n else 0,
        "supersized_components": int(len(big_roots)),
        "split_components": split_components,  # components split by hard conflicts (over-merge guard)
        "edges_rejected_by_conflict": rejected,
        "edges_rejected_by_label": rejected_label,
        "edges": int(m),
        "cluster_size_distribution": dict(hist),
        "singleton_pct": round(
            100.0 * int(np.sum(cluster_sizes == 1)) / max(1, len(cluster_sizes)), 2
        ),
    }
    return res


def attach_rids(res: ClusterResult, rids: list[str]) -> ClusterResult:
    """Fill the string views (assignment / component / supersized / members) from the integer views."""
    res.rids = rids
    cl, comp, sup = res.cluster_idx, res.component_idx, res.supersized_idx
    assert cl is not None and comp is not None and sup is not None
    cluster_ids: dict[int, str] = {}
    comp_ids: dict[int, str] = {}
    for i, rid in enumerate(rids):
        r = int(cl[i])
        cid = cluster_ids.get(r)
        if cid is None:
            cid = cluster_ids[r] = _short_id("cluster:" + rids[r])
        res.assignment[rid] = cid
        res.members.setdefault(cid, []).append(rid)
        c = int(comp[i])
        k = comp_ids.get(c)
        if k is None:
            k = comp_ids[c] = _short_id(rids[c])
        res.component[rid] = k
        if sup[i] >= 0:
            res.supersized[rid] = comp_ids.get(int(sup[i])) or _short_id(rids[int(sup[i])])
    for mem in res.members.values():
        mem.sort()
    return res


def cluster_records(
    rids: list[str],
    edges: list[tuple[str, str, float]],
    conflict_values: dict[str, dict[str, str | None]],
    cfg,
    forbidden: list[tuple[str, str]] | None = None,
) -> ClusterResult:
    """rids: all record ids; edges: (a, b, score) positive edges; conflict_values: rid -> {attr: value}.
    cfg: the `cluster` config section (+ optional birthdate_typo_tolerance); ``forbidden``: rid pairs that must
    never share a cluster (split labels)."""
    rids = sorted(rids)
    pos = {rid: i for i, rid in enumerate(rids)}
    forbid_idx = [(pos[a], pos[b]) for a, b in (forbidden or ()) if a in pos and b in pos]
    conflict_attrs = list(cfg.get("conflict_attributes", ["birthdate"]))
    cv = {
        attr: [(conflict_values.get(rid) or {}).get(attr) for rid in rids]
        for attr in conflict_attrs
    }
    if edges:
        left = np.array([pos[a] for a, _, _ in edges], dtype=np.int64)
        right = np.array([pos[b] for _, b, _ in edges], dtype=np.int64)
        score = np.array([s for _, _, s in edges], dtype=np.float64)
        lo, hi = np.minimum(left, right), np.maximum(left, right)
        # duplicate edges keep the max score (as before)
        import pandas as pd

        e = (
            pd.DataFrame({"l": lo, "r": hi, "s": score})
            .groupby(["l", "r"], as_index=False)["s"]
            .max()
        )
        left, right, score = e["l"].to_numpy(), e["r"].to_numpy(), e["s"].to_numpy()
    else:
        left = right = np.empty(0, dtype=np.int64)
        score = np.empty(0, dtype=np.float64)
    res = cluster_indices(len(rids), left, right, score, cv, cfg, forbidden=forbid_idx or None)
    return attach_rids(res, rids)
