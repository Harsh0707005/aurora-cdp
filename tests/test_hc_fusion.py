"""HC_fusion: hard conflicts enforced during clustering, evidence-gated fusion of formed entities, set-valued
identifier conflicts, and the supersized carve — all on the integer core, plus one run-level check."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aurora_cdp.config import load_config
from aurora_cdp.stitch.cluster import cluster_indices

BASE = dict(load_config(use_last_best=False).cluster)
BASE["birthdate_typo_tolerance"] = 2


def _run(n, edges, cfg=None, dob=None, contact=None, given=None):
    cfg = {**BASE, **(cfg or {})}
    left = np.array([a for a, _, _ in edges]); right = np.array([b for _, b, _ in edges]); score = np.array([s for _, _, s in edges], dtype=float)
    attrs = list(cfg["conflict_attributes"])
    cv = {}
    if "birthdate" in attrs:
        cv["birthdate"] = dob or [None] * n
    if "given_name" in attrs:
        cv["given_name"] = given or [None] * n
    if "contact" in attrs:
        cv["contact"] = contact or [frozenset()] * n
    return cluster_indices(n, left, right, score, cv, cfg)


def test_transitive_bridge_cannot_fuse_contradictory_birthdates():
    # A(1982) -5.0- X(no dob) -5.0- B(1990): the weaker/later edge is cut, the cluster is not dropped
    res = _run(3, [(0, 1, 5.0), (1, 2, 5.0)], dob=["1982-12-11", None, "1990-07-08"])
    cl = res.cluster_idx
    assert len(set(cl.tolist())) == 2 and cl[0] != cl[2]
    assert res.qa["edges_rejected_by_conflict"] == 1 and res.qa["split_components"] == 1


def _two_dense(bridge_score, extra_bridges=0):
    edges = []
    for base in (0, 10):
        for i in range(5):
            for j in range(i + 1, 5):
                edges.append((base + i, base + j, 4.3))
    edges.append((4, 10, bridge_score))
    for k in range(extra_bridges):
        edges.append((k, 11 + k, bridge_score))
    return edges


def test_single_weak_edge_does_not_fuse_two_formed_entities_under_fusion():
    fusion = _run(15, _two_dense(3.4), cfg={"linkage": "fusion"})
    single = _run(15, _two_dense(3.4), cfg={"linkage": "single"})
    assert fusion.cluster_idx[0] != fusion.cluster_idx[10] and fusion.qa["fusion_deferred_edges"] >= 1
    assert single.cluster_idx[0] == single.cluster_idx[10]
    strong = _run(15, _two_dense(4.6), cfg={"linkage": "fusion"})  # a strong edge fuses on its own
    assert strong.cluster_idx[0] == strong.cluster_idx[10]
    corroborated = _run(15, _two_dense(3.4, extra_bridges=2), cfg={"linkage": "fusion", "fusion": {**BASE["fusion"], "min_cross_edges": 2}})
    assert corroborated.cluster_idx[0] == corroborated.cluster_idx[10] and corroborated.qa["fusion_multi_merges"] >= 1


def test_contact_disjointness_is_a_set_level_conflict():
    cfg = {"conflict_attributes": ["birthdate", "contact"]}
    contact = [frozenset({"a@x.org"})] * 5 + [frozenset()] * 5 + [frozenset({"b@x.org", "111"})] * 5
    edges = _two_dense(4.6)  # strong bridge: only a hard conflict can stop it
    res = _run(15, edges, cfg=cfg, contact=contact)
    assert res.cluster_idx[0] != res.cluster_idx[10]  # both formed, disjoint identifier sets
    contact2 = [frozenset({"a@x.org", "111"})] * 5 + [frozenset()] * 5 + [frozenset({"b@x.org", "111"})] * 5
    res2 = _run(15, edges, cfg=cfg, contact=contact2)
    assert res2.cluster_idx[0] == res2.cluster_idx[10]  # a shared phone makes the sets compatible


def test_carve_trims_weak_tiers_and_surfaces_members():
    # hub 0 linked weakly (3.4) to 30 records that form 3 strong (4.8) triangles each with 9 others -> one blob of 31
    edges = [(0, i, 3.4) for i in range(1, 31)]
    for g in range(3):
        nodes = list(range(1 + g * 10, 11 + g * 10))
        for i in nodes:
            for j in nodes:
                if i < j:
                    edges.append((i, j, 4.8))
    res = _run(31, edges, cfg={"linkage": "single", "carve": {"enabled": True, "max_cluster_size": 12}})
    sizes = np.bincount(res.cluster_idx)
    assert sizes.max() <= 12 and res.qa["carved_clusters"] == 1 and res.qa["carved_records"] >= 20
    assert (res.carved_idx >= 0).sum() == res.qa["carved_records"] and (res.supersized_idx >= 0).all()
    off = _run(31, edges, cfg={"linkage": "single", "carve": {"enabled": False}})
    assert np.bincount(off.cluster_idx).max() == 31


def test_run_level_fusion_and_metrics():
    from aurora_cdp.adapters import resolve_records

    rows = []
    for p in range(40):
        for c in range(3):
            rows.append({"source_record_id": f"{p}-{c}", "given_name": f"Name{p}", "surname": "Lee", "email": f"p{p}@x.org" if c < 2 else None,
                         "phone": f"20655500{p:02d}", "postal": "98101"})
    res = resolve_records(pd.DataFrame(rows), config={"cluster": {"linkage": "fusion", "conflict_attributes": ["birthdate", "given_name", "contact"]}}, datasource="s")
    m = res.metrics
    assert m["linkage"] == "fusion" and m["clusters"] == 40 and "carved_records" in m and m["records_dropped_by_blocking"] == 0
