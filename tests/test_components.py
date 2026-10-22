"""Union-find components and over-merge hygiene."""

import pandas as pd

from aurora.config.schema import HygieneConfig
from aurora.graph.components import UnionFind, apply_hygiene, connected_components


def test_union_find_components():
    edges = pd.DataFrame({"rid_l": [1, 2, 5], "rid_r": [2, 3, 6], "score": [4.0, 4.0, 4.0]})
    comp = connected_components(edges, [1, 2, 3, 4, 5, 6])
    assert comp[1] == comp[2] == comp[3] == 1
    assert comp[4] == 4
    assert comp[5] == comp[6] == 5
    uf = UnionFind()
    uf.union(10, 11)
    assert uf.find(10) == uf.find(11)


def test_hygiene_cuts_weak_bridge_in_supersized_component():
    # two dense groups of 6 joined by one weak edge; threshold 8 makes the union supersized
    edges = []
    for base in (0, 100):
        for i in range(6):
            for j in range(i + 1, 6):
                edges.append((base + i, base + j, 4.5))
    edges.append((5, 100, 3.1))  # weak bridge
    df = pd.DataFrame(edges, columns=["rid_l", "rid_r", "score"])
    nodes = list(range(6)) + list(range(100, 106))
    res = apply_hygiene(df, nodes, HygieneConfig(supersized_threshold=8, hard_limit=500, weak_bridge_score=3.5))
    assert res.stats["supersized_initial"] == 1
    assert len(set(res.assignment.values())) == 2
    assert res.assignment[0] != res.assignment[100]
    assert (5, 100, 3.1) in res.dropped_edges
    assert not res.supersized  # both pieces now under threshold


def test_hygiene_flags_unbreakable_component():
    edges = [(i, j, 4.9) for i in range(10) for j in range(i + 1, 10)]  # clique of 10, all strong
    df = pd.DataFrame(edges, columns=["rid_l", "rid_r", "score"])
    res = apply_hygiene(df, list(range(10)), HygieneConfig(supersized_threshold=4, hard_limit=500))
    assert len(set(res.assignment.values())) == 1
    assert set(res.supersized) == set(range(10))
