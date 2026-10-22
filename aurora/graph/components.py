"""Connected components (union-find) and cluster hygiene.

Hygiene = over-merge guard. Components larger than ``supersized_threshold``
are carved by removing weak edges (score below ``weak_bridge_score``) and, if
still over ``hard_limit``, by cutting the weakest *bridge* edges. Rows that
end up in a component that is still too large are flagged ``is_supersized``
and keep the original ``supersized_id`` for QA.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx
import pandas as pd

from aurora.config.schema import HygieneConfig


class UnionFind:
    """Array-free union-find keyed by arbitrary hashables (path compression + rank)."""

    def __init__(self) -> None:
        self.parent: dict[int, int] = {}
        self.rank: dict[int, int] = {}

    def add(self, x: int) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0

    def find(self, x: int) -> int:
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def components(self, nodes: list[int]) -> dict[int, int]:
        """node -> component id (smallest member id in the component)."""
        groups: dict[int, list[int]] = defaultdict(list)
        for n in nodes:
            groups[self.find(n)].append(n)
        out: dict[int, int] = {}
        for members in groups.values():
            cid = min(members)
            for m in members:
                out[m] = cid
        return out


def connected_components(edges: pd.DataFrame, nodes: list[int]) -> dict[int, int]:
    uf = UnionFind()
    for a, b in zip(edges["rid_l"].to_numpy(), edges["rid_r"].to_numpy(), strict=True):
        uf.union(int(a), int(b))
    return uf.components(nodes)


@dataclass
class HygieneResult:
    assignment: dict[int, int]  # rid -> final cluster id
    supersized: dict[int, int] = field(default_factory=dict)  # rid -> original component id
    dropped_edges: list[tuple[int, int, float]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


def apply_hygiene(edges: pd.DataFrame, nodes: list[int], cfg: HygieneConfig) -> HygieneResult:
    """Union-find over all edges, then carve supersized components."""
    comp = connected_components(edges, nodes)
    sizes: dict[int, int] = defaultdict(int)
    for c in comp.values():
        sizes[c] += 1
    big = {c for c, n in sizes.items() if n > cfg.supersized_threshold}
    stats = {"components": len(sizes), "supersized_initial": len(big), "edges_dropped": 0}
    if not big:
        return HygieneResult(assignment=comp, stats=stats)

    big_edges = edges[edges["rid_l"].map(comp).isin(big)]
    dropped: list[tuple[int, int, float]] = []
    final = dict(comp)
    supersized: dict[int, int] = {}
    for cid in big:
        sub = big_edges[big_edges["rid_l"].map(comp) == cid]
        g = nx.Graph()
        g.add_nodes_from(r for r, c in comp.items() if c == cid)
        for a, b, s in zip(sub["rid_l"], sub["rid_r"], sub["score"], strict=True):
            g.add_edge(int(a), int(b), score=float(s))
        # pass 1: remove all weak edges
        weak = [(a, b) for a, b, d in g.edges(data=True) if d["score"] < cfg.weak_bridge_score]
        for a, b in weak:
            dropped.append((a, b, g.edges[a, b]["score"]))
        g.remove_edges_from(weak)
        # pass 2: cut weakest bridges until every piece is under the hard limit
        for _ in range(cfg.max_carve_iterations):
            too_big = [c for c in nx.connected_components(g) if len(c) > cfg.hard_limit]
            if not too_big:
                break
            for c in too_big:
                h = g.subgraph(c)
                bridges = sorted(nx.bridges(h), key=lambda e: h.edges[e]["score"])
                if not bridges:
                    continue
                a, b = bridges[0]
                dropped.append((a, b, g.edges[a, b]["score"]))
                g.remove_edge(a, b)
        for piece in nx.connected_components(g):
            new_id = min(piece)
            for r in piece:
                final[r] = new_id
                if len(piece) > cfg.supersized_threshold:
                    supersized[r] = cid
    stats["edges_dropped"] = len(dropped)
    stats["supersized_final"] = len({v for v in supersized.values()})
    stats["components_final"] = len(set(final.values()))
    return HygieneResult(assignment=final, supersized=supersized, dropped_edges=dropped, stats=stats)
