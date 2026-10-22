"""Orchestrate one Stitch run: load -> blocklist -> blocking -> scoring -> clustering -> stable IDs -> persist.

Modes:
- full:        every current record is blocked and scored.
- incremental: only candidate pairs touching a record changed since the last successful run are scored;
               previous cluster memberships are carried in as high-confidence edges (internals §2.12).

Memory model: records, blocking keys and candidate pairs live in DuckDB temp tables (``_rec``, ``_bk``,
``_pairs``, ``_scores``) under the configured ``storage.duckdb.memory_limit`` and spill to
``temp_directory``; scoring streams the pair table in ``matcher.score_chunk_size`` chunks through the
vectorised scorer; clustering works on integer arrays. The only per-record Python structures are the rid
list and the cluster / stable-id dictionaries.
"""

from __future__ import annotations

import json
import logging
import resource
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

import duckdb
import numpy as np
import pandas as pd

from aurora_cdp.config import Config
from aurora_cdp.storage.duck import apply_settings, latest_run_id, read_df, write_df

from .blocking import REC_COLUMNS, build_candidate_pairs
from .cluster import attach_rids, cluster_indices
from .features import SIDE_COLUMNS, features_frame
from .matcher import score_frame
from .stable_id import assign_stable_ids

log = logging.getLogger(__name__)
TEMP_TABLES = ("_rec", "_bk", "_blk", "_blk_full", "_budget", "_pairs", "_pairs_n", "_scores", "_gs", "_changed")


@dataclass
class StitchRunResult:
    run_id: str
    mode: str
    metrics: dict = field(default_factory=dict)

    def summary(self) -> str:
        m = self.metrics
        return (
            f"stitch run {self.run_id} ({self.mode}): records={m.get('records')} pairs={m.get('pairs_scored')} "
            f"edges={m.get('edges')} clusters={m.get('clusters')} jitter={m.get('jitter', {}).get('jitter_pct')}%"
        )


def _peak_rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(r / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)


# ----------------------------------------------------------------------------------------- load
def load_current_records(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return read_df(
        con,
        """
        SELECT * FROM silver_unified_preprocessed
        QUALIFY ROW_NUMBER() OVER (PARTITION BY datasource, pk ORDER BY preprocessed_at DESC) = 1
        ORDER BY datasource, pk
        """,
    )


def load_records_table(con: duckdb.DuckDBPyConnection) -> int:
    """``_rec``: the current version of every record, integer-indexed in rid order."""
    cols = ", ".join(c for c in REC_COLUMNS if c not in ("idx", "rid"))
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _rec AS
        SELECT (ROW_NUMBER() OVER (ORDER BY rid) - 1)::INTEGER AS idx, rid, {cols}
        FROM (
            SELECT datasource || '|' || pk AS rid, *
            FROM silver_unified_preprocessed
            QUALIFY ROW_NUMBER() OVER (PARTITION BY datasource, pk ORDER BY preprocessed_at DESC) = 1
        )
        """
    )
    return con.execute("SELECT COUNT(*) FROM _rec").fetchone()[0]


def apply_blocklist(df: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, list[dict]]:
    """Automatic bad-value detection on a frame (kept for callers/tests; the run uses the SQL variant)."""
    flagged: list[dict] = []
    df = df.copy()
    for value_col, name_col, limit, semantic in _blocklist_rules(cfg):
        sub = df[[value_col, name_col]].dropna()
        if sub.empty:
            continue
        counts = sub.groupby(value_col)[name_col].nunique()
        bad = counts[counts > limit]
        for value, n in bad.items():
            flagged.append({"semantic": semantic, "value": value, "reason": f"{name_col} distinct > {limit}", "distinct_count": int(n)})
            df.loc[df[value_col] == value, value_col] = None
    return df, flagged


def _blocklist_rules(cfg: Config):
    bl = cfg.blocklist
    return [
        ("email_norm", "given_name_canon", int(bl.get("email_max_given_names", 20)), "email"),
        ("email_norm", "surname_norm", int(bl.get("email_max_surnames", 20)), "email"),
        ("phone_match", "given_name_canon", int(bl.get("phone_max_given_names", 20)), "phone"),
        ("address_norm", "given_name_canon", int(bl.get("address_max_given_names", 40)), "address"),
    ]


def apply_blocklist_sql(con: duckdb.DuckDBPyConnection, cfg: Config) -> list[dict]:
    """Null out values linked to too many distinct names, in place on ``_rec`` (dossier §3.8)."""
    flagged: list[dict] = []
    for value_col, name_col, limit, semantic in _blocklist_rules(cfg):
        bad = con.execute(
            f"SELECT {value_col}, COUNT(DISTINCT {name_col}) AS n FROM _rec WHERE {value_col} IS NOT NULL AND {name_col} IS NOT NULL "
            f"GROUP BY {value_col} HAVING COUNT(DISTINCT {name_col}) > ?",
            [limit],
        ).fetchall()
        for value, n in bad:
            flagged.append({"semantic": semantic, "value": value, "reason": f"{name_col} distinct > {limit}", "distinct_count": int(n)})
        if bad:
            con.register("_bad", pd.DataFrame({"v": [b[0] for b in bad]}))
            con.execute(f"UPDATE _rec SET {value_col} = NULL WHERE {value_col} IN (SELECT v FROM _bad)")
            con.unregister("_bad")
    return flagged


def records_from_frame(df: pd.DataFrame) -> dict[str, dict]:
    """silver_unified_preprocessed rows -> {rid: record} with NaN/NaT normalised to None (tests / small callers)."""
    recs = {}
    cols = list(df.columns)
    for row in df.itertuples(index=False):
        d = dict(zip(cols, row, strict=False))
        d = {k: (None if (isinstance(v, float) and pd.isna(v)) or v is pd.NaT else v) for k, v in d.items()}
        recs[f"{d['datasource']}|{d['pk']}"] = d
    return recs


def _changed_rids(con: duckdb.DuckDBPyConnection, prev_run_id: str | None) -> set[str] | None:
    """rids ingested after the previous run or not yet in the ledger; None = everything."""
    if prev_run_id is None:
        return None
    started = con.execute("SELECT started_at FROM stitch_runs WHERE run_id = ?", [prev_run_id]).fetchone()[0]
    rows = con.execute(
        """
        SELECT r.rid FROM _rec r
        LEFT JOIN silver_unified_preprocessed s ON s.datasource = r.datasource AND s.pk = r.pk
        LEFT JOIN bronze_batches b ON b.batch_id = s.batch_id
        LEFT JOIN id_ledger l ON l.is_current AND l.datasource = r.datasource AND l.pk = r.pk
        WHERE b.loaded_at >= ? OR l.aurora_id IS NULL
        """,
        [started],
    ).fetchall()
    return {r[0] for r in rows}


# ----------------------------------------------------------------------------------------- scoring
def score_candidates(con: duckdb.DuckDBPyConnection, cfg: Config) -> dict:
    """Stream ``_pairs`` through the vectorised scorer in chunks into ``_scores``. Returns counters."""
    mcfg = cfg.matcher
    chunk = int(mcfg.get("score_chunk_size", 250_000))
    keep_features = bool(mcfg.get("persist_features", False))
    con.execute("CREATE OR REPLACE TEMP TABLE _pairs_n AS SELECT (ROW_NUMBER() OVER (ORDER BY l, r) - 1) AS n, l, r FROM _pairs")
    con.execute(
        "CREATE OR REPLACE TEMP TABLE _scores (l INTEGER, r INTEGER, score DOUBLE, match_category VARCHAR, "
        "match_type VARCHAR, is_edge BOOLEAN, features_json VARCHAR)"
    )
    total = con.execute("SELECT COUNT(*) FROM _pairs_n").fetchone()[0]
    lcols = ", ".join(f"a.{c} AS l_{c}" for c in SIDE_COLUMNS)
    rcols = ", ".join(f"b.{c} AS r_{c}" for c in SIDE_COLUMNS)
    counts: dict[str, int] = {}
    edges = 0
    for start in range(0, total, chunk):
        df = con.execute(
            f"SELECT p.l, p.r, {lcols}, {rcols} FROM _pairs_n p JOIN _rec a ON a.idx = p.l JOIN _rec b ON b.idx = p.r "
            f"WHERE p.n >= ? AND p.n < ? ORDER BY p.n",
            [start, start + chunk],
        ).df()
        left = df[[f"l_{c}" for c in SIDE_COLUMNS]].rename(columns=lambda c: c[2:])
        right = df[[f"r_{c}" for c in SIDE_COLUMNS]].rename(columns=lambda c: c[2:])
        F = features_frame(left, right, mcfg)
        S = score_frame(F, mcfg)
        out = pd.DataFrame({"l": df["l"].to_numpy(), "r": df["r"].to_numpy(), "score": S["score"].to_numpy(),
                            "match_category": S["match_category"].to_numpy(), "match_type": S["match_type"].to_numpy(),
                            "is_edge": S["is_edge"].to_numpy()})
        out["features_json"] = (
            [json.dumps({k: (None if pd.isna(v) else float(v)) for k, v in row.items()}) for row in F.to_dict("records")]
            if keep_features else None
        )
        con.register("_chunk", out)
        con.execute("INSERT INTO _scores SELECT * FROM _chunk")
        con.unregister("_chunk")
        for cat, n in S["match_category"].value_counts().items():
            counts[cat] = counts.get(cat, 0) + int(n)
        edges += int(S["is_edge"].sum())
        del df, left, right, F, S, out
    return {"pairs_scored_representative": int(total), "edges_representative": edges, "match_category_counts": counts}


def expand_scores(con: duckdb.DuckDBPyConnection, run_id: str, cfg: Config) -> dict:
    """Write stitch_scores for the run, expanding collapsed trivial-dupe groups back to member pairs."""
    mcfg = cfg.matcher
    expand = bool(mcfg.get("export_expanded_dupe_pairs", True))
    cap = int(mcfg.get("max_expanded_pairs", 50_000_000))
    con.execute("CREATE OR REPLACE TEMP TABLE _gs AS SELECT dupe_group AS g, COUNT(*) AS k FROM _rec GROUP BY dupe_group")
    within = con.execute("SELECT COALESCE(SUM(k * (k - 1) / 2), 0) FROM _gs").fetchone()[0]
    cross = con.execute("SELECT COALESCE(SUM(ga.k * gb.k), 0) FROM _scores s JOIN _gs ga ON ga.g = s.l JOIN _gs gb ON gb.g = s.r").fetchone()[0]
    total_expanded = int(within) + int(cross)
    truncated = not expand or total_expanded > cap
    cols = "run_id, left_datasource, left_pk, right_datasource, right_pk, score, match_category, match_type, is_edge, features_json"
    if not truncated:
        con.execute(
            f"""
            INSERT INTO stitch_scores ({cols})
            SELECT ?, ma.datasource, ma.pk, mb.datasource, mb.pk, s.score, s.match_category, s.match_type, s.is_edge, s.features_json
            FROM _scores s JOIN _rec ma ON ma.dupe_group = s.l JOIN _rec mb ON mb.dupe_group = s.r
            """,
            [run_id],
        )
        con.execute(
            f"""
            INSERT INTO stitch_scores ({cols})
            SELECT ?, a.datasource, a.pk, b.datasource, b.pk, 5.0, 'exact', 'trivial_duplicate', TRUE, NULL
            FROM _rec a JOIN _rec b ON a.dupe_group = b.dupe_group AND a.idx < b.idx
            """,
            [run_id],
        )
    else:
        con.execute(
            f"""
            INSERT INTO stitch_scores ({cols})
            SELECT ?, a.datasource, a.pk, b.datasource, b.pk, s.score, s.match_category, s.match_type, s.is_edge, s.features_json
            FROM _scores s JOIN _rec a ON a.idx = s.l JOIN _rec b ON b.idx = s.r
            """,
            [run_id],
        )
        con.execute(
            f"""
            INSERT INTO stitch_scores ({cols})
            SELECT ?, a.datasource, a.pk, b.datasource, b.pk, 5.0, 'exact', 'trivial_duplicate', TRUE, NULL
            FROM _rec a JOIN _rec b ON b.dupe_group = a.idx AND b.idx <> a.idx
            """,
            [run_id],
        )
    written = con.execute("SELECT COUNT(*) FROM stitch_scores WHERE run_id = ?", [run_id]).fetchone()[0]
    return {"pairs_scored": int(written), "pairs_expanded_total": total_expanded, "pairs_expansion_truncated": bool(truncated),
            "pairs_within_dupe_groups": int(within)}


def edge_arrays(con: duckdb.DuckDBPyConnection) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Positive edges over record indices: representative pairs that are edges + member->representative links."""
    e = con.execute("SELECT l, r, score FROM _scores WHERE is_edge").fetchnumpy()
    d = con.execute("SELECT dupe_group AS l, idx AS r, 5.0 AS score FROM _rec WHERE idx <> dupe_group").fetchnumpy()
    left = np.concatenate([np.asarray(e["l"], dtype=np.int64), np.asarray(d["l"], dtype=np.int64)])
    right = np.concatenate([np.asarray(e["r"], dtype=np.int64), np.asarray(d["r"], dtype=np.int64)])
    score = np.concatenate([np.asarray(e["score"], dtype=np.float64), np.asarray(d["score"], dtype=np.float64)])
    return left, right, score


# ----------------------------------------------------------------------------------------- run
def run_stitch(con: duckdb.DuckDBPyConnection, cfg: Config, mode: str = "full", run_id: str | None = None) -> StitchRunResult:
    if mode not in {"full", "incremental"}:
        raise ValueError("mode must be 'full' or 'incremental'")
    run_id = run_id or f"run-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    started = datetime.utcnow()
    timings: dict[str, float] = {}
    duck_settings = apply_settings(con, (cfg.get("storage") or {}).get("duckdb"), getattr(cfg, "workspace_path", None))
    con.execute(
        "INSERT INTO stitch_runs (run_id, mode, started_at, status, config_json) VALUES (?, ?, ?, 'running', ?)",
        [run_id, mode, started, json.dumps({"matcher": cfg["matcher"], "blocking": cfg["blocking"], "cluster": cfg["cluster"]})],
    )
    prev_run_id = latest_run_id(con)

    t = time.perf_counter()
    n = load_records_table(con)
    flagged = apply_blocklist_sql(con, cfg)
    timings["load"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    bstats = build_candidate_pairs(con, cfg.blocking)
    previous = {
        f"{r[0]}|{r[1]}": r[2]
        for r in con.execute("SELECT datasource, pk, aurora_id FROM id_ledger WHERE is_current").fetchall()
    }
    carried: list[tuple[str, str, float]] = []
    if mode == "incremental" and previous:
        changed = _changed_rids(con, prev_run_id)
        if changed is not None:
            con.register("_changed_src", pd.DataFrame({"rid": sorted(changed)}))
            con.execute("CREATE OR REPLACE TEMP TABLE _changed AS SELECT DISTINCT r.dupe_group AS g FROM _rec r JOIN _changed_src c USING (rid)")
            con.unregister("_changed_src")
            con.execute("DELETE FROM _pairs WHERE l NOT IN (SELECT g FROM _changed) AND r NOT IN (SELECT g FROM _changed)")
        rids_present = set(r[0] for r in con.execute("SELECT rid FROM _rec").fetchall())
        by_id: dict[str, list[str]] = {}
        for rid, aid in previous.items():
            if rid in rids_present:
                by_id.setdefault(aid, []).append(rid)
        for members in by_id.values():
            members.sort()
            for other in members[1:]:
                carried.append((members[0], other, 5.0))
        del rids_present
    timings["blocking"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    scoring = score_candidates(con, cfg)
    expansion = expand_scores(con, run_id, cfg)
    left, right, score = edge_arrays(con)
    rids: list[str] = [r[0] for r in con.execute("SELECT rid FROM _rec ORDER BY idx").fetchall()]
    if carried:
        pos = {rid: i for i, rid in enumerate(rids)}
        cl = np.array([pos[a] for a, _, _ in carried], dtype=np.int64)
        cr = np.array([pos[b] for _, b, _ in carried], dtype=np.int64)
        left = np.concatenate([left, np.minimum(cl, cr)])
        right = np.concatenate([right, np.maximum(cl, cr)])
        score = np.concatenate([score, np.full(len(carried), 5.0)])
        del pos
    timings["scoring"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    birthdates = [r[0] for r in con.execute("SELECT birthdate_norm FROM _rec ORDER BY idx").fetchall()]
    ccfg = dict(cfg.cluster)
    ccfg["birthdate_typo_tolerance"] = cfg.matcher.get("hard_conflicts", {}).get("birthdate_typo_tolerance", 2)
    clusters = attach_rids(cluster_indices(n, left, right, score, {"birthdate": birthdates}, ccfg), rids)
    del birthdates, left, right, score
    timings["clustering"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    stable = assign_stable_ids(clusters.assignment, previous, float(cfg.stable_id.get("jitter_alert_pct", 2.0)))
    timings["stable_id"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    now = datetime.utcnow()
    _persist(con, run_id, now, cfg, bstats, flagged, carried, clusters, stable)
    timings["persist"] = round(time.perf_counter() - t, 3)

    edges_total = int(clusters.qa.get("edges", 0))
    metrics = {
        "records": n,
        "mode": mode,
        "prev_run_id": prev_run_id,
        **bstats.as_metrics(),
        "blocklisted_values": len(flagged),
        "pairs_scored": expansion["pairs_scored"],
        "pairs_scored_representative": scoring["pairs_scored_representative"],
        "pairs_expanded_total": expansion["pairs_expanded_total"],
        "pairs_expansion_truncated": expansion["pairs_expansion_truncated"],
        "edges": edges_total,
        "carried_edges": len(carried),
        "match_rate": round(scoring["edges_representative"] / scoring["pairs_scored_representative"], 4) if scoring["pairs_scored_representative"] else 0.0,
        "match_category_counts": scoring["match_category_counts"],
        "clusters": clusters.qa["clusters"],
        "multi_record_clusters": sum(1 for m in clusters.members.values() if len(m) > 1),
        "records_in_multi_record_clusters_pct": round(
            100.0 * sum(len(m) for m in clusters.members.values() if len(m) > 1) / max(1, n), 2
        ),
        **{k: v for k, v in clusters.qa.items() if k not in ("clusters", "edges")},
        "jitter": stable.jitter.as_dict() if stable.jitter else {},
        "timings_sec": timings,
        "threshold": cfg.matcher.get("match_threshold"),
        "peak_rss_mb": _peak_rss_mb(),
        "duckdb_settings": duck_settings,
    }
    for tbl in TEMP_TABLES:
        con.execute(f"DROP TABLE IF EXISTS {tbl}")
    con.execute(
        "UPDATE stitch_runs SET finished_at = ?, status = 'succeeded', metrics_json = ? WHERE run_id = ?",
        [datetime.utcnow(), json.dumps(metrics, default=str), run_id],
    )
    return StitchRunResult(run_id, mode, metrics)


def _persist(con, run_id, now, cfg, bstats, flagged, carried, clusters, stable):
    if cfg.blocking.get("persist_blocking_keys", True):
        con.execute(
            "INSERT INTO stitch_blocking_keys (run_id, bk, datasource, pk, strategy) "
            "SELECT ?, b.bk, r.datasource, r.pk, b.strategy FROM _bk b JOIN _rec r ON r.dupe_group = b.idx",
            [run_id],
        )
    if bstats.oversized:
        ov = pd.DataFrame([{"run_id": run_id, "strategy": o.strategy, "bk": o.bk, "block_size": o.size, "size_limit": o.limit,
                            "handling": o.handling, "sub_blocks": o.sub_blocks, "pairs": o.pairs} for o in bstats.oversized])
        write_df(con, "stitch_oversized_blocks", ov)
    if flagged:
        fl = pd.DataFrame(flagged)
        fl["run_id"] = run_id
        write_df(con, "stitch_blocklist_values", fl, ["run_id", "semantic", "value", "reason", "distinct_count"])
    if carried:
        cr = pd.DataFrame(
            [
                {
                    "run_id": run_id,
                    "left_datasource": a.split("|", 1)[0], "left_pk": a.split("|", 1)[1],
                    "right_datasource": b.split("|", 1)[0], "right_pk": b.split("|", 1)[1],
                    "score": s, "match_category": "exact", "match_type": "carried", "is_edge": True, "features_json": None,
                }
                for a, b, s in carried
            ]
        )
        write_df(con, "stitch_scores", cr)

    rids = clusters.rids
    ds = [r.split("|", 1)[0] for r in rids]
    pk = [r.split("|", 1)[1] for r in rids]
    cluster_id = [clusters.assignment[r] for r in rids]
    rows = pd.DataFrame({
        "run_id": run_id, "datasource": ds, "pk": pk, "cluster_id": cluster_id,
        "aurora_id": [stable.cluster_to_id[c] for c in cluster_id],
        "component_id": [clusters.component.get(r) for r in rids],
        "supersized_id": [clusters.supersized.get(r) for r in rids],
        "is_supersized": [r in clusters.supersized for r in rids],
    })
    write_df(con, "stitch_clusters", rows)
    del rows, ds, pk, cluster_id

    # SCD2 ledger: close rows whose id changed or whose record disappeared, open rows for new/changed.
    changed_rids = [c["rid"] for c in stable.pk_changes]
    if changed_rids:
        ch = pd.DataFrame(
            [{"datasource": rid.split("|", 1)[0], "pk": rid.split("|", 1)[1]} for rid in changed_rids]
        )
        con.register("_aurora_changed", ch)
        con.execute(
            """
            UPDATE id_ledger SET valid_to = ?, is_current = FALSE
            WHERE is_current AND (datasource, pk) IN (SELECT datasource, pk FROM _aurora_changed)
            """,
            [now],
        )
        con.unregister("_aurora_changed")
        opens = [
            {"aurora_id": c["aurora_id"], "datasource": c["rid"].split("|", 1)[0], "pk": c["rid"].split("|", 1)[1],
             "run_id": run_id, "valid_from": now, "valid_to": None, "is_current": True}
            for c in stable.pk_changes if c["change_type"] != "deleted"
        ]
        write_df(con, "id_ledger", pd.DataFrame(opens))
        pkc = pd.DataFrame(
            [
                {"run_id": run_id, "datasource": c["rid"].split("|", 1)[0], "pk": c["rid"].split("|", 1)[1],
                 "aurora_id": c["aurora_id"], "aurora_id_prev": c["aurora_id_prev"], "change_type": c["change_type"], "changed_at": now}
                for c in stable.pk_changes
            ]
        )
        write_df(con, "unified_changes_pk", pkc)
    if stable.cluster_changes:
        cc = pd.DataFrame(stable.cluster_changes)
        cc["run_id"] = run_id
        cc["changed_at"] = now
        write_df(con, "unified_changes_clusters", cc, ["run_id", "aurora_id", "aurora_id_prev", "change_type", "pk_count", "pk_count_prev", "changed_at"])
    j = stable.jitter
    prev_run = latest_run_id(con)
    con.execute(
        "INSERT INTO jitter_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [run_id, prev_run, j.records_total, j.records_compared, j.records_changed, j.jitter_pct, j.ids_minted, j.ids_retired, j.alert, now],
    )
