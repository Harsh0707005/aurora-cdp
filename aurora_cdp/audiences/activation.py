"""Activation IDs (Amperity: §4.4): a per-destination identifier namespace that insulates downstream systems from
customer-id churn. The first time an id is sent to a destination it gets an activation id; on later sends the same
activation id is reused. When a customer id disappears because its cluster merged into another (recorded in
``unified_changes_clusters`` with ``aurora_id_prev``), the surviving id inherits the retired id's activation id
(the oldest one when several merged), so the destination keeps seeing the identifier it already knows.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import duckdb
import pandas as pd


def assign_activation_ids(con: duckdb.DuckDBPyConnection, destination_id: str, aurora_ids: list[str] | pd.Series) -> pd.DataFrame:
    """Return ``aurora_id, activation_id`` for the given ids, creating or inheriting as needed (persisted)."""
    ids = sorted({str(x) for x in aurora_ids if x})
    now = datetime.utcnow()
    if not ids:
        return pd.DataFrame(columns=["aurora_id", "activation_id"])
    con.execute("SELECT 1").fetchall()  # clear any unfetched result left by a caller's INSERT; register() refuses otherwise
    con.register("_want", pd.DataFrame({"aurora_id": ids}))
    have = dict(con.execute("SELECT aurora_id, activation_id FROM activation_ids WHERE destination_id = ? AND aurora_id IN (SELECT aurora_id FROM _want)", [destination_id]).fetchall())
    missing = [i for i in ids if i not in have]
    inherited: dict[str, tuple[str, str]] = {}
    if missing:
        con.register("_missing", pd.DataFrame({"aurora_id": missing}))
        # ids whose previous ids (merged / renamed in the change feed) already carry an activation id here
        rows = con.execute("""
            SELECT c.aurora_id, a.activation_id, a.aurora_id AS prev
            FROM unified_changes_clusters c JOIN _missing m USING (aurora_id)
            JOIN activation_ids a ON a.destination_id = ? AND a.aurora_id = c.aurora_id_prev
            WHERE c.aurora_id_prev IS NOT NULL AND c.aurora_id_prev <> c.aurora_id
            ORDER BY a.first_seen, c.changed_at
            """, [destination_id]).fetchall()
        for aid, act, prev in rows:
            inherited.setdefault(aid, (act, prev))
        con.unregister("_missing")
    new_rows = []
    for aid in missing:
        act, prev = inherited.get(aid, (str(uuid.uuid4()), None))
        new_rows.append((destination_id, aid, act, now, now, prev))
        have[aid] = act
    if new_rows:
        con.register("_new_act", pd.DataFrame(new_rows, columns=["destination_id", "aurora_id", "activation_id", "first_seen", "last_seen", "inherited_from"]))
        con.execute("INSERT INTO activation_ids SELECT * FROM _new_act")
        con.unregister("_new_act")
    con.execute("UPDATE activation_ids SET last_seen = ? WHERE destination_id = ? AND aurora_id IN (SELECT aurora_id FROM _want)", [now, destination_id]).fetchall()
    con.unregister("_want")
    return pd.DataFrame({"aurora_id": ids, "activation_id": [have[i] for i in ids]})


def attach_activation_ids(con: duckdb.DuckDBPyConnection, destination_id: str, members: pd.DataFrame) -> pd.DataFrame:
    if "aurora_id" not in members.columns or members.empty:
        return members.assign(activation_id=None)
    m = assign_activation_ids(con, destination_id, members["aurora_id"])
    return members.merge(m, on="aurora_id", how="left")
