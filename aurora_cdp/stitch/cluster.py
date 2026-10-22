"""Clustering: connected components -> supersized partitioning -> conflict-aware single-link merge.

Amperity (internals §2.7-2.9): positive pairs are edges; connected components are *not* the answer because
transitive chains over-merge, so each component is re-clustered with hard-conflict rules; supersized
components are first broken apart with a bounded breadth-first search (US11704315).
Here: edges are processed in descending score (ties by ascending ids) and two clusters are unioned only when
no hard-conflict attribute disagrees between them. This is a deterministic, conflict-free single-link scheme.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx
from rapidfuzz.distance import Levenshtein

log = logging.getLogger(__name__)


@dataclass
class ClusterResult:
    assignment: dict[str, str] = field(default_factory=dict)  # rid -> cluster_id
    component: dict[str, str] = field(default_factory=dict)  # rid -> component_id
    supersized: dict[str, str] = field(default_factory=dict)  # rid -> supersized_id
    members: dict[str, list[str]] = field(default_factory=dict)  # cluster_id -> [rid]
    qa: dict = field(default_factory=dict)


def _short_id(seed: str) -> str:
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


class _UnionFind:
    def __init__(self, nodes):
        self.parent = {n: n for n in nodes}
        self.rank = dict.fromkeys(nodes, 0)

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return ra


def _values_compatible(attr: str, vals_a: set[str], vals_b: set[str], tol: int) -> bool:
    if not vals_a or not vals_b:
        return True
    for x in vals_a:
        for y in vals_b:
            if x != y and (attr != "birthdate" or Levenshtein.distance(x, y) > tol):
                return False
    return True


def _bfs_partition(graph: nx.Graph, nodes: list[str], max_size: int) -> list[list[str]]:
    """Bounded BFS partitioning of an oversized component (US11704315 analogue)."""
    remaining = set(nodes)
    parts: list[list[str]] = []
    while remaining:
        start = min(remaining)
        visited: list[str] = []
        queue = [start]
        seen = {start}
        while queue and len(visited) < max_size:
            n = queue.pop(0)
            visited.append(n)
            for nb in sorted(graph.neighbors(n)):
                if nb in remaining and nb not in seen:
                    seen.add(nb)
                    queue.append(nb)
        parts.append(visited)
        remaining -= set(visited)
    return parts


def cluster_records(
    rids: list[str],
    edges: list[tuple[str, str, float]],
    conflict_values: dict[str, dict[str, str | None]],
    cfg,
) -> ClusterResult:
    """rids: all record ids; edges: (a, b, score) positive edges; conflict_values: rid -> {attr: value}.
    cfg: the `cluster` config section (+ optional birthdate_typo_tolerance)."""
    max_size = int(cfg.get("supersized_min_size", 500))
    conflict_attrs = list(cfg.get("conflict_attributes", ["birthdate"]))
    tol = int(cfg.get("birthdate_typo_tolerance", 2))

    g = nx.Graph()
    g.add_nodes_from(rids)
    for a, b, s in edges:
        if g.has_edge(a, b):
            g[a][b]["score"] = max(g[a][b]["score"], s)
        else:
            g.add_edge(a, b, score=s)

    res = ClusterResult()
    component_sizes = []
    supersized_count = 0
    allowed_groups: list[list[str]] = []
    for comp in nx.connected_components(g):
        members = sorted(comp)
        cid = _short_id(members[0])
        for r in members:
            res.component[r] = cid
        component_sizes.append(len(members))
        if len(members) > max_size:
            supersized_count += 1
            for r in members:
                res.supersized[r] = cid
            allowed_groups.extend(_bfs_partition(g, members, max_size))
        else:
            allowed_groups.append(members)

    # Conflict-aware single-link union within each (possibly partitioned) group.
    group_of: dict[str, int] = {}
    for gi, grp in enumerate(allowed_groups):
        for r in grp:
            group_of[r] = gi
    uf = _UnionFind(rids)
    values: dict[str, dict[str, set[str]]] = {}
    for r in rids:
        values[r] = {
            attr: ({v} if (v := (conflict_values.get(r) or {}).get(attr)) else set()) for attr in conflict_attrs
        }
    rejected = 0
    sorted_edges = sorted(((a, b, s) for a, b, s in edges), key=lambda e: (-e[2], e[0], e[1]))
    for a, b, _s in sorted_edges:
        if group_of.get(a) != group_of.get(b):
            continue
        ra, rb = uf.find(a), uf.find(b)
        if ra == rb:
            continue
        if all(_values_compatible(attr, values[ra][attr], values[rb][attr], tol) for attr in conflict_attrs):
            root = uf.union(a, b)
            other = rb if root == ra else ra
            for attr in conflict_attrs:
                values[root][attr] |= values[other][attr]
        else:
            rejected += 1

    groups: dict[str, list[str]] = defaultdict(list)
    for r in rids:
        groups[uf.find(r)].append(r)
    split_components = 0
    comp_cluster_count: dict[str, int] = defaultdict(int)
    for _root, members in groups.items():
        members.sort()
        cid = _short_id("cluster:" + members[0])
        res.members[cid] = members
        for r in members:
            res.assignment[r] = cid
        comp_cluster_count[res.component[members[0]]] += 1
    split_components = sum(1 for c in comp_cluster_count.values() if c > 1)

    sizes = sorted((len(m) for m in res.members.values()), reverse=True)
    hist: dict[str, int] = defaultdict(int)
    for s in sizes:
        bucket = "1" if s == 1 else "2" if s == 2 else "3-5" if s <= 5 else "6-10" if s <= 10 else "11-50" if s <= 50 else "50+"
        hist[bucket] += 1
    res.qa = {
        "components": len(component_sizes),
        "clusters": len(res.members),
        "max_component_size": max(component_sizes) if component_sizes else 0,
        "max_cluster_size": sizes[0] if sizes else 0,
        "supersized_components": supersized_count,
        "split_components": split_components,  # components split by hard conflicts (over-merge guard)
        "edges_rejected_by_conflict": rejected,
        "cluster_size_distribution": dict(hist),
        "singleton_pct": round(100.0 * sum(1 for s in sizes if s == 1) / max(1, len(sizes)), 2),
    }
    return res
