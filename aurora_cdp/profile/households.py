"""Households as an owned entity (Amperity: Merged Households; internals §3.3).

A household is **not** recomputed from "same surname + same address" on every run (that recipe churns on every
move). It is an owned entity with a persistent ``household_id`` and explicit **evidence edges** between
customers (``aurora_id`` pairs): shared standardised address (+ postal), shared surname at a postal code, shared
phone, explicit relationships (registry, gift, account owner — ``household_relationships``) and operator
labels. Evidence is persisted with first/last-seen stamps; an edge that is no longer observed stays active until
``household.evidence_ttl_days`` after it was last seen, so a customer who moves keeps the household until the
shared evidence has genuinely aged out. Values shared by too many customers (apartment towers, placeholder
phones) are not evidence (``skipped_values``). Household membership is the connected components of active
evidence whose summed weight per pair reaches ``min_evidence_weight``; household ids follow the same greedy
max-overlap stability rule as customer ids.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import duckdb

from aurora_cdp.config import Config
from aurora_cdp.stitch.cluster import UnionFind
from aurora_cdp.stitch.stable_id import assign_stable_ids
from aurora_cdp.storage.duck import latest_run_id

log = logging.getLogger(__name__)

DEFAULT_EVIDENCE = {
    "shared_address": {"weight": 1.0, "columns": ["address_norm", "postal_norm"]},
    "shared_surname_postal": {"weight": 0.4, "columns": ["surname_norm", "postal_norm"]},
    "shared_phone": {"weight": 0.6, "columns": ["phone_match"]},
    "relationship": {"weight": 1.0},
}


@dataclass
class HouseholdResult:
    run_id: str
    metrics: dict = field(default_factory=dict)


def _cfg(cfg: Config) -> dict:
    h = dict(cfg.get("household") or {})
    h.setdefault("evidence", DEFAULT_EVIDENCE)
    h.setdefault("min_evidence_weight", 1.0)
    h.setdefault("evidence_ttl_days", 365)
    h.setdefault("max_customers_per_value", 25)
    return h


def observe_evidence(con: duckdb.DuckDBPyConnection, stitch_run_id: str, hcfg: dict) -> tuple[list[tuple], dict]:
    """Current evidence edges from this run's clusters: (kind, left_id, right_id, value, weight)."""
    edges: list[tuple] = []
    skipped: dict[str, int] = {}
    cap = int(hcfg["max_customers_per_value"])
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _hh_rec AS
        SELECT c.aurora_id, s.address_norm, s.postal_norm, s.surname_norm, s.phone_match, s.datasource, s.pk
        FROM stitch_clusters c
        JOIN (
            SELECT * FROM silver_unified_preprocessed
            QUALIFY ROW_NUMBER() OVER (PARTITION BY datasource, pk ORDER BY preprocessed_at DESC) = 1
        ) s ON s.datasource = c.datasource AND s.pk = c.pk
        WHERE c.run_id = ?
        """,
        [stitch_run_id],
    )
    for kind, spec in hcfg["evidence"].items():
        cols = spec.get("columns")
        if not cols:
            continue
        key = " || ':' || ".join(cols)
        nonnull = " AND ".join(f"{c} IS NOT NULL" for c in cols)
        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE _hh_key AS
            SELECT DISTINCT aurora_id, {key} AS k FROM _hh_rec WHERE {nonnull}
            """
        )
        skipped[kind] = con.execute(f"SELECT COUNT(*) FROM (SELECT k FROM _hh_key GROUP BY k HAVING COUNT(*) > {cap})").fetchone()[0]
        rows = con.execute(
            f"""
            SELECT a.aurora_id, b.aurora_id, a.k FROM _hh_key a JOIN _hh_key b ON a.k = b.k AND a.aurora_id < b.aurora_id
            WHERE a.k IN (SELECT k FROM _hh_key GROUP BY k HAVING COUNT(*) BETWEEN 2 AND {cap})
            """
        ).fetchall()
        edges.extend((kind, a, b, k, float(spec["weight"])) for a, b, k in rows)
    # explicit relationships between records -> between their current customers
    rel = con.execute(
        """
        SELECT LEAST(ca.aurora_id, cb.aurora_id), GREATEST(ca.aurora_id, cb.aurora_id), r.kind
        FROM household_relationships r
        JOIN stitch_clusters ca ON ca.run_id = ? AND ca.datasource = r.left_datasource AND ca.pk = r.left_pk
        JOIN stitch_clusters cb ON cb.run_id = ? AND cb.datasource = r.right_datasource AND cb.pk = r.right_pk
        WHERE ca.aurora_id <> cb.aurora_id
        """,
        [stitch_run_id, stitch_run_id],
    ).fetchall()
    w_rel = float(hcfg["evidence"].get("relationship", {}).get("weight", 1.0))
    edges.extend(("relationship", a, b, kind, w_rel) for a, b, kind in rel)
    con.execute("DROP TABLE IF EXISTS _hh_key")
    return edges, skipped


def persist_evidence(con, edges: list[tuple], run_id: str, now: datetime, ttl_days: int) -> dict:
    """Upsert observed edges (first/last seen), expire edges not seen for ttl_days. Returns counters."""
    existing = {
        (k, a, b, v): (eid, last_seen)
        for eid, k, a, b, v, last_seen in con.execute(
            "SELECT evidence_id, kind, left_aurora_id, right_aurora_id, value, last_seen FROM household_evidence WHERE active"
        ).fetchall()
    }
    new, refreshed = [], []
    seen_ids = set()
    for kind, a, b, value, weight in edges:
        key = (kind, a, b, value)
        if key in existing:
            refreshed.append(existing[key][0])
            seen_ids.add(existing[key][0])
        else:
            new.append((str(uuid.uuid4()), kind, a, b, value, weight, run_id, run_id, now, now, True))
    if refreshed:
        con.executemany("UPDATE household_evidence SET last_seen = ?, last_seen_run = ? WHERE evidence_id = ?", [(now, run_id, eid) for eid in refreshed])
    if new:
        con.executemany("INSERT INTO household_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", new)
    cutoff = now - timedelta(days=int(ttl_days))
    expired = con.execute("SELECT COUNT(*) FROM household_evidence WHERE active AND last_seen < ?", [cutoff]).fetchone()[0]
    con.execute("UPDATE household_evidence SET active = FALSE WHERE active AND last_seen < ?", [cutoff])
    return {"evidence_new": len(new), "evidence_refreshed": len(refreshed), "evidence_expired": int(expired)}


def build_households(con: duckdb.DuckDBPyConnection, cfg: Config, stitch_run_id: str | None = None, run_id: str | None = None) -> HouseholdResult:
    hcfg = _cfg(cfg)
    stitch_run_id = stitch_run_id or latest_run_id(con)
    if stitch_run_id is None:
        raise RuntimeError("no successful stitch run; run `aurora stitch` first")
    run_id = run_id or f"hh-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    now = datetime.utcnow()
    customers = [r[0] for r in con.execute("SELECT DISTINCT aurora_id FROM stitch_clusters WHERE run_id = ? ORDER BY 1", [stitch_run_id]).fetchall()]
    edges, skipped = observe_evidence(con, stitch_run_id, hcfg)
    counters = persist_evidence(con, edges, run_id, now, hcfg["evidence_ttl_days"])
    # active evidence (incl. still-valid historical edges) between current customers, summed per pair
    cur = set(customers)
    weight: dict[tuple[str, str], float] = defaultdict(float)
    for a, b, w in con.execute("SELECT left_aurora_id, right_aurora_id, weight FROM household_evidence WHERE active").fetchall():
        if a in cur and b in cur:
            weight[(a, b)] += float(w)
    pos = {aid: i for i, aid in enumerate(customers)}
    uf = UnionFind(len(customers))
    min_w = float(hcfg["min_evidence_weight"])
    for (a, b), w in weight.items():
        if w >= min_w:
            uf.union(pos[a], pos[b])
    roots = uf.roots()
    current = {aid: f"g{int(roots[i])}" for aid, i in pos.items()}
    previous = dict(con.execute("SELECT aurora_id, household_id FROM household_members WHERE is_current").fetchall())
    stable = assign_stable_ids(current, previous, jitter_alert_pct=float(cfg.get("stable_id", {}).get("jitter_alert_pct", 2.0)))
    changed = [c for c in stable.pk_changes]
    if changed:
        con.executemany("UPDATE household_members SET valid_to = ?, is_current = FALSE WHERE is_current AND aurora_id = ?", [(now, c["rid"]) for c in changed])
        con.executemany(
            "INSERT INTO household_members VALUES (?, ?, ?, ?, NULL, TRUE)",
            [(c["aurora_id"], c["rid"], run_id, now) for c in changed if c["change_type"] != "deleted"],
        )
    if stable.minted:
        con.executemany("INSERT INTO households VALUES (?, ?, ?, 'active')", [(hid, run_id, now) for hid in sorted(stable.minted)])
    if stable.retired:
        con.executemany("UPDATE households SET status = 'retired' WHERE household_id = ?", [(hid,) for hid in sorted(stable.retired)])
    sizes = defaultdict(int)
    for hid in stable.record_to_id.values():
        sizes[hid] += 1
    metrics = {
        "stitch_run_id": stitch_run_id, "customers": len(customers), "households": len(sizes),
        "multi_member_households": sum(1 for s in sizes.values() if s > 1), "max_household_size": max(sizes.values()) if sizes else 0,
        "evidence_observed": len(edges), "evidence_skipped_values": skipped, **counters,
        "evidence_active": con.execute("SELECT COUNT(*) FROM household_evidence WHERE active").fetchone()[0],
        "jitter": stable.jitter.as_dict() if stable.jitter else {},
    }
    con.execute("INSERT INTO household_runs VALUES (?, ?, ?, ?)", [run_id, stitch_run_id, now, json.dumps(metrics, default=str)])
    con.execute("DROP TABLE IF EXISTS _hh_rec")
    return HouseholdResult(run_id, metrics)


def add_relationship(con, left: tuple[str, str], right: tuple[str, str], kind: str, source: str | None = None) -> None:
    con.execute("INSERT INTO household_relationships VALUES (?, ?, ?, ?, ?, ?, ?)", [left[0], left[1], right[0], right[1], kind, source, datetime.utcnow()])


def household_of(con, aurora_id: str) -> dict | None:
    row = con.execute("SELECT household_id FROM household_members WHERE is_current AND aurora_id = ?", [aurora_id]).fetchone()
    if not row:
        return None
    hid = row[0]
    members = [r[0] for r in con.execute("SELECT aurora_id FROM household_members WHERE is_current AND household_id = ? ORDER BY 1", [hid]).fetchall()]
    evidence = con.execute(
        "SELECT kind, left_aurora_id, right_aurora_id, value, weight, first_seen, last_seen FROM household_evidence "
        "WHERE active AND left_aurora_id IN (SELECT aurora_id FROM household_members WHERE is_current AND household_id = ?) "
        "AND right_aurora_id IN (SELECT aurora_id FROM household_members WHERE is_current AND household_id = ?)",
        [hid, hid],
    ).fetchall()
    return {"household_id": hid, "members": members,
            "evidence": [dict(zip(["kind", "left", "right", "value", "weight", "first_seen", "last_seen"], e, strict=True)) for e in evidence]}
