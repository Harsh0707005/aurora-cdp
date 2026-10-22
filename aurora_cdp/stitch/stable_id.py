"""Stable ID assignment across runs (Amperity: internals §1.3, stable-ID patent + SIGMOD 2020 Algorithm 2).

Edges between CURRENT clusters and PREVIOUS ids are weighted by the number of shared primary keys. Edges are
sorted by weight descending, ties broken by ascending (previous id, current cluster id); they are taken greedily
while neither endpoint has already been consumed. Surviving edges define the mapping; every other current
cluster mints a fresh UUID (with a collision check). Previous ids with no survivor are retired.

Implementation: the work happens in DuckDB so nothing per-record lives in Python. Edges whose two endpoints are
each other's only candidate are assigned in SQL (they can never lose a greedy contest); only the ambiguous
subset (a previous id with several candidate clusters, or vice versa — a split or merge) is ranked and resolved
by the greedy loop in Python. Record- and cluster-level change feeds and the jitter report are SQL joins.
:func:`assign_stable_ids` keeps the dict-based API for small callers and tests over the same core.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import duckdb
import pandas as pd


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


def assign_stable_ids_duck(con: duckdb.DuckDBPyConnection, jitter_alert_pct: float = 2.0,
                           cur_table: str = "_cur", prev_table: str = "_prev") -> JitterReport:
    """Core. ``cur_table(rid, cid)``: this run's record -> cluster id; ``prev_table(rid, aurora_id)``: last ledger.

    Writes temp tables ``_cmap(cid, aurora_id, inherited_prev)``, ``_rid_map(rid, aurora_id)``,
    ``_pkchg(rid, aurora_id, aurora_id_prev, change_type)`` and
    ``_cluchg(aurora_id, aurora_id_prev, change_type, pk_count, pk_count_prev)`` and returns the jitter report."""
    con.execute(f"CREATE OR REPLACE TEMP TABLE _w AS SELECT p.aurora_id AS prev_id, c.cid, COUNT(*) AS w FROM {cur_table} c JOIN {prev_table} p USING (rid) GROUP BY 1, 2")
    con.execute("CREATE OR REPLACE TEMP TABLE _deg AS SELECT prev_id, cid, w, COUNT(*) OVER (PARTITION BY prev_id) AS dp, COUNT(*) OVER (PARTITION BY cid) AS dc FROM _w")
    con.execute("CREATE OR REPLACE TEMP TABLE _cmap (cid VARCHAR, aurora_id VARCHAR, inherited_prev VARCHAR)")
    con.execute("INSERT INTO _cmap SELECT cid, prev_id, prev_id FROM _deg WHERE dp = 1 AND dc = 1")
    # ambiguous subset: splits / merges, resolved greedily in weight order (ties: prev id, cluster id ascending)
    rows = con.execute("SELECT prev_id, cid, w FROM _deg WHERE dp > 1 OR dc > 1 ORDER BY w DESC, prev_id, cid").fetchall()
    used_prev: set[str] = set()
    used_cur: set[str] = set()
    picked = []
    for prev_id, cid, _w in rows:
        if prev_id in used_prev or cid in used_cur:
            continue
        used_prev.add(prev_id)
        used_cur.add(cid)
        picked.append((cid, prev_id, prev_id))
    if picked:
        con.register("_picked", pd.DataFrame(picked, columns=["cid", "aurora_id", "inherited_prev"]))
        con.execute("INSERT INTO _cmap SELECT * FROM _picked")
        con.unregister("_picked")
    # mint for the rest (collision-checked against every id ever seen in the previous ledger)
    new = [r[0] for r in con.execute(f"SELECT DISTINCT cid FROM {cur_table} WHERE cid NOT IN (SELECT cid FROM _cmap) ORDER BY cid").fetchall()]
    if new:
        ids = [str(uuid.uuid4()) for _ in new]
        while True:
            con.register("_mint", pd.DataFrame({"cid": new, "aurora_id": ids}))
            dup = [r[0] for r in con.execute(f"SELECT m.cid FROM _mint m WHERE m.aurora_id IN (SELECT aurora_id FROM {prev_table}) OR m.aurora_id IN (SELECT aurora_id FROM _cmap)").fetchall()]
            if not dup:
                break
            con.unregister("_mint")
            bad = set(dup)
            ids = [str(uuid.uuid4()) if c in bad else i for c, i in zip(new, ids, strict=True)]
        con.execute("INSERT INTO _cmap SELECT cid, aurora_id, NULL FROM _mint")
        con.unregister("_mint")
    con.execute(f"CREATE OR REPLACE TEMP TABLE _rid_map AS SELECT c.rid, c.cid, m.aurora_id FROM {cur_table} c JOIN _cmap m USING (cid)")
    # record-level change feed
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _pkchg AS
        SELECT COALESCE(c.rid, p.rid) AS rid, c.aurora_id, p.aurora_id AS aurora_id_prev,
               CASE WHEN p.rid IS NULL THEN 'added' WHEN c.rid IS NULL THEN 'deleted' WHEN c.aurora_id <> p.aurora_id THEN 'updated' END AS change_type
        FROM _rid_map c FULL OUTER JOIN {prev_table} p ON p.rid = c.rid
        WHERE p.rid IS NULL OR c.rid IS NULL OR c.aurora_id <> p.aurora_id
        """
    )
    # cluster-level change feed: added / updated (membership changed) / deleted (retired previous ids)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _cluchg AS
        WITH cur AS (
            SELECT m.cid, m.aurora_id, m.inherited_prev, COUNT(*) AS pk_count,
                   SUM(CASE WHEN p.aurora_id = m.inherited_prev THEN 1 ELSE 0 END) AS shared
            FROM _rid_map r JOIN _cmap m USING (cid) LEFT JOIN {prev_table} p ON p.rid = r.rid
            GROUP BY 1, 2, 3
        ), prevn AS (SELECT aurora_id, COUNT(*) AS n FROM {prev_table} GROUP BY 1)
        SELECT c.aurora_id, c.inherited_prev AS aurora_id_prev,
               CASE WHEN c.inherited_prev IS NULL THEN 'added' ELSE 'updated' END AS change_type,
               c.pk_count, pn.n AS pk_count_prev
        FROM cur c LEFT JOIN prevn pn ON pn.aurora_id = c.inherited_prev
        WHERE c.inherited_prev IS NULL OR c.pk_count <> pn.n OR c.shared <> c.pk_count
        UNION ALL
        SELECT pn.aurora_id, pn.aurora_id, 'deleted', 0, pn.n
        FROM prevn pn WHERE pn.aurora_id NOT IN (SELECT aurora_id FROM _cmap WHERE inherited_prev IS NOT NULL)
        """
    )
    total = con.execute(f"SELECT COUNT(*) FROM {cur_table}").fetchone()[0]
    compared, changed = con.execute(
        f"SELECT COUNT(*), SUM(CASE WHEN c.aurora_id <> p.aurora_id THEN 1 ELSE 0 END) FROM _rid_map c JOIN {prev_table} p USING (rid)"
    ).fetchone()
    compared, changed = int(compared or 0), int(changed or 0)
    minted = con.execute("SELECT COUNT(*) FROM _cmap WHERE inherited_prev IS NULL").fetchone()[0]
    retired = con.execute("SELECT COUNT(*) FROM _cluchg WHERE change_type = 'deleted'").fetchone()[0]
    has_prev = con.execute(f"SELECT COUNT(*) FROM {prev_table}").fetchone()[0] > 0
    jitter_pct = round(100.0 * changed / compared, 4) if compared else 0.0
    for t in ("_w", "_deg"):
        con.execute(f"DROP TABLE IF EXISTS {t}")
    return JitterReport(records_total=int(total), records_compared=compared, records_changed=changed, jitter_pct=jitter_pct,
                        ids_minted=int(minted), ids_retired=int(retired), alert=bool(has_prev) and jitter_pct >= jitter_alert_pct)


def assign_stable_ids(current: dict[str, str], previous: dict[str, str], jitter_alert_pct: float = 2.0) -> StableIdResult:
    """Dict API over the SQL core. current: rid -> cluster_id (this run). previous: rid -> aurora_id (last ledger)."""
    con = duckdb.connect(":memory:")
    try:
        con.register("_cur_src", pd.DataFrame({"rid": list(current), "cid": list(current.values())}, dtype=object))
        con.register("_prev_src", pd.DataFrame({"rid": list(previous), "aurora_id": list(previous.values())}, dtype=object))
        con.execute("CREATE TEMP TABLE _cur AS SELECT rid::VARCHAR AS rid, cid::VARCHAR AS cid FROM _cur_src")
        con.execute("CREATE TEMP TABLE _prev AS SELECT rid::VARCHAR AS rid, aurora_id::VARCHAR AS aurora_id FROM _prev_src")
        res = StableIdResult()
        res.jitter = assign_stable_ids_duck(con, jitter_alert_pct)
        for cid, aid, inh in con.execute("SELECT cid, aurora_id, inherited_prev FROM _cmap").fetchall():
            res.cluster_to_id[cid] = aid
            if inh is None:
                res.minted.add(aid)
            else:
                res.inherited[cid] = inh
        res.record_to_id = dict(con.execute("SELECT rid, aurora_id FROM _rid_map").fetchall())
        res.retired = {r[0] for r in con.execute("SELECT aurora_id FROM _cluchg WHERE change_type = 'deleted'").fetchall()}
        res.pk_changes = [dict(zip(["rid", "aurora_id", "aurora_id_prev", "change_type"], r, strict=True))
                          for r in con.execute("SELECT rid, aurora_id, aurora_id_prev, change_type FROM _pkchg ORDER BY rid").fetchall()]
        res.cluster_changes = [dict(zip(["aurora_id", "aurora_id_prev", "change_type", "pk_count", "pk_count_prev"], r, strict=True))
                               for r in con.execute("SELECT aurora_id, aurora_id_prev, change_type, pk_count, pk_count_prev FROM _cluchg ORDER BY change_type, aurora_id").fetchall()]
        return res
    finally:
        con.close()
