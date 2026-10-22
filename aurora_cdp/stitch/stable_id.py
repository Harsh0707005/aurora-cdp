"""Stable ID assignment across runs (Amperity: internals §1.3, stable-ID patent + SIGMOD 2020 Algorithm 2).

Edges between CURRENT clusters and PREVIOUS ids are weighted by the number of shared primary keys.
Edges are sorted by weight descending, ties broken by ascending (previous id, current cluster id); they are
taken greedily while neither endpoint has already been consumed. Surviving edges define the mapping; every
other current cluster mints a fresh UUID (with a collision check). Previous ids with no survivor are retired.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class JitterReport:
    records_total: int
    records_compared: int
    records_changed: int
    jitter_pct: float
    ids_minted: int
    ids_retired: int
    alert: bool

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class StableIdResult:
    cluster_to_id: dict[str, str] = field(default_factory=dict)
    record_to_id: dict[str, str] = field(default_factory=dict)
    minted: set[str] = field(default_factory=set)
    retired: set[str] = field(default_factory=set)
    inherited: dict[str, str] = field(default_factory=dict)  # cluster_id -> prev id (surviving edges)
    pk_changes: list[dict] = field(default_factory=list)  # Unified_Changes_PK analogue
    cluster_changes: list[dict] = field(default_factory=list)  # Unified_Changes_Clusters analogue
    jitter: JitterReport | None = None


def _mint(existing: set[str]) -> str:
    while True:
        candidate = str(uuid.uuid4())
        if candidate not in existing:
            existing.add(candidate)
            return candidate


def assign_stable_ids(
    current: dict[str, str],
    previous: dict[str, str],
    jitter_alert_pct: float = 2.0,
) -> StableIdResult:
    """current: rid -> cluster_id (this run). previous: rid -> aurora_id (last run's current ledger)."""
    res = StableIdResult()
    members: dict[str, list[str]] = defaultdict(list)
    for rid, cid in current.items():
        members[cid].append(rid)

    # Confusion matrix M[prev_id][cluster_id] = shared PK count.
    weights: Counter = Counter()
    for rid, cid in current.items():
        prev = previous.get(rid)
        if prev is not None:
            weights[(prev, cid)] += 1

    ranked = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))
    used_prev: set[str] = set()
    used_cur: set[str] = set()
    for (prev_id, cid), _w in ranked:
        if prev_id in used_prev or cid in used_cur:
            continue  # a higher-ranked edge already consumed one endpoint
        used_prev.add(prev_id)
        used_cur.add(cid)
        res.inherited[cid] = prev_id
        res.cluster_to_id[cid] = prev_id

    all_ids: set[str] = set(previous.values())
    for cid in sorted(members):
        if cid not in res.cluster_to_id:
            new_id = _mint(all_ids)
            res.cluster_to_id[cid] = new_id
            res.minted.add(new_id)
    res.retired = set(previous.values()) - set(res.cluster_to_id.values())
    for rid, cid in current.items():
        res.record_to_id[rid] = res.cluster_to_id[cid]

    # Record-level change feed.
    compared = changed = 0
    for rid in sorted(set(current) | set(previous)):
        new_id = res.record_to_id.get(rid)
        old_id = previous.get(rid)
        if old_id is None:
            res.pk_changes.append({"rid": rid, "aurora_id": new_id, "aurora_id_prev": None, "change_type": "added"})
        elif new_id is None:
            res.pk_changes.append({"rid": rid, "aurora_id": None, "aurora_id_prev": old_id, "change_type": "deleted"})
        else:
            compared += 1
            if new_id != old_id:
                changed += 1
                res.pk_changes.append(
                    {"rid": rid, "aurora_id": new_id, "aurora_id_prev": old_id, "change_type": "updated"}
                )

    # Cluster-level change feed: added / deleted / updated (composition changed).
    prev_members: dict[str, set[str]] = defaultdict(set)
    for rid, pid in previous.items():
        prev_members[pid].add(rid)
    for cid, rids in members.items():
        aid = res.cluster_to_id[cid]
        prev_id = res.inherited.get(cid)
        if prev_id is None:
            res.cluster_changes.append(
                {"aurora_id": aid, "aurora_id_prev": None, "change_type": "added", "pk_count": len(rids), "pk_count_prev": None}
            )
        elif set(rids) != prev_members[prev_id]:
            res.cluster_changes.append(
                {"aurora_id": aid, "aurora_id_prev": prev_id, "change_type": "updated", "pk_count": len(rids), "pk_count_prev": len(prev_members[prev_id])}
            )
    for pid in sorted(res.retired):
        res.cluster_changes.append(
            {"aurora_id": pid, "aurora_id_prev": pid, "change_type": "deleted", "pk_count": 0, "pk_count_prev": len(prev_members[pid])}
        )

    jitter_pct = round(100.0 * changed / compared, 4) if compared else 0.0
    res.jitter = JitterReport(
        records_total=len(current),
        records_compared=compared,
        records_changed=changed,
        jitter_pct=jitter_pct,
        ids_minted=len(res.minted),
        ids_retired=len(res.retired),
        alert=bool(previous) and jitter_pct >= jitter_alert_pct,
    )
    return res
