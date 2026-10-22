"""Orchestrate one Stitch run: load -> blocklist -> blocking -> scoring -> clustering -> stable IDs -> persist.

Modes:
- full:        every current record is blocked and scored.
- incremental: only candidate pairs touching a record changed since the last successful run are scored;
               previous cluster memberships are carried in as high-confidence edges (internals §2.12).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

import duckdb
import pandas as pd

from aurora_cdp.config import Config
from aurora_cdp.storage.duck import latest_run_id, read_df, write_df

from .blocking import build_blocks
from .cluster import cluster_records
from .matcher import score_pairs
from .stable_id import assign_stable_ids

log = logging.getLogger(__name__)


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


def load_current_records(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return read_df(
        con,
        """
        SELECT * FROM silver_unified_preprocessed
        QUALIFY ROW_NUMBER() OVER (PARTITION BY datasource, pk ORDER BY preprocessed_at DESC) = 1
        ORDER BY datasource, pk
        """,
    )


def apply_blocklist(df: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, list[dict]]:
    """Automatic bad-value detection: null out values linked to too many distinct names (dossier §3.8)."""
    bl = cfg.blocklist
    rules = [
        ("email_norm", "given_name_canon", int(bl.get("email_max_given_names", 20)), "email"),
        ("email_norm", "surname_norm", int(bl.get("email_max_surnames", 20)), "email"),
        ("phone_match", "given_name_canon", int(bl.get("phone_max_given_names", 20)), "phone"),
        ("address_norm", "given_name_canon", int(bl.get("address_max_given_names", 40)), "address"),
    ]
    flagged: list[dict] = []
    df = df.copy()
    for value_col, name_col, limit, semantic in rules:
        sub = df[[value_col, name_col]].dropna()
        if sub.empty:
            continue
        counts = sub.groupby(value_col)[name_col].nunique()
        bad = counts[counts > limit]
        for value, n in bad.items():
            flagged.append(
                {"semantic": semantic, "value": value, "reason": f"{name_col} distinct > {limit}", "distinct_count": int(n)}
            )
            df.loc[df[value_col] == value, value_col] = None
    return df, flagged


def records_from_frame(df: pd.DataFrame) -> dict[str, dict]:
    """silver_unified_preprocessed rows -> {rid: record} with NaN/NaT normalised to None."""
    recs = {}
    cols = list(df.columns)
    for row in df.itertuples(index=False):
        d = dict(zip(cols, row, strict=False))
        d = {k: (None if (isinstance(v, float) and pd.isna(v)) or v is pd.NaT else v) for k, v in d.items()}
        recs[f"{d['datasource']}|{d['pk']}"] = d
    return recs


def _changed_rids(con: duckdb.DuckDBPyConnection, records: dict[str, dict], prev_run_id: str | None) -> set[str]:
    if prev_run_id is None:
        return set(records)
    started = con.execute("SELECT started_at FROM stitch_runs WHERE run_id = ?", [prev_run_id]).fetchone()[0]
    batches = {
        r[0] for r in con.execute("SELECT batch_id FROM bronze_batches WHERE loaded_at >= ?", [started]).fetchall()
    }
    in_ledger = {
        f"{r[0]}|{r[1]}" for r in con.execute("SELECT datasource, pk FROM id_ledger WHERE is_current").fetchall()
    }
    return {rid for rid, r in records.items() if r.get("batch_id") in batches or rid not in in_ledger}


def run_stitch(con: duckdb.DuckDBPyConnection, cfg: Config, mode: str = "full", run_id: str | None = None) -> StitchRunResult:
    if mode not in {"full", "incremental"}:
        raise ValueError("mode must be 'full' or 'incremental'")
    run_id = run_id or f"run-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    started = datetime.utcnow()
    timings: dict[str, float] = {}
    con.execute(
        "INSERT INTO stitch_runs (run_id, mode, started_at, status, config_json) VALUES (?, ?, ?, 'running', ?)",
        [run_id, mode, started, json.dumps({"matcher": cfg["matcher"], "blocking": cfg["blocking"], "cluster": cfg["cluster"]})],
    )
    prev_run_id = latest_run_id(con)

    t = time.perf_counter()
    df = load_current_records(con)
    df, flagged = apply_blocklist(df, cfg)
    records = records_from_frame(df)
    rids = sorted(records)
    timings["load"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    blocks = build_blocks(records, cfg.blocking)
    pairs = blocks.pairs
    previous = {
        f"{r[0]}|{r[1]}": r[2]
        for r in con.execute("SELECT datasource, pk, aurora_id FROM id_ledger WHERE is_current").fetchall()
    }
    carried: list[tuple[str, str, float]] = []
    if mode == "incremental" and previous:
        changed = _changed_rids(con, records, prev_run_id)
        pairs = {p for p in pairs if p[0] in changed or p[1] in changed}
        by_id: dict[str, list[str]] = {}
        for rid, aid in previous.items():
            if rid in records:
                by_id.setdefault(aid, []).append(rid)
        for members in by_id.values():
            members.sort()
            for other in members[1:]:
                carried.append((members[0], other, 5.0))
    timings["blocking"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    scores = score_pairs(records, pairs, cfg.matcher)
    edges = [
        (r.left_rid, r.right_rid, float(r.score))
        for r in scores[scores["is_edge"]].itertuples(index=False)
    ]
    edges.extend(carried)
    timings["scoring"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    conflict_values = {rid: {"birthdate": rec.get("birthdate_norm")} for rid, rec in records.items()}
    ccfg = dict(cfg.cluster)
    ccfg["birthdate_typo_tolerance"] = cfg.matcher.get("hard_conflicts", {}).get("birthdate_typo_tolerance", 2)
    clusters = cluster_records(rids, edges, conflict_values, ccfg)
    timings["clustering"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    stable = assign_stable_ids(clusters.assignment, previous, float(cfg.stable_id.get("jitter_alert_pct", 2.0)))
    timings["stable_id"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    now = datetime.utcnow()
    _persist(con, run_id, now, records, blocks, flagged, scores, carried, clusters, stable, previous)
    timings["persist"] = round(time.perf_counter() - t, 3)

    metrics = {
        "records": len(rids),
        "mode": mode,
        "prev_run_id": prev_run_id,
        "blocks": blocks.block_count,
        "skipped_blocks": len(blocks.skipped),
        "blocklisted_values": len(flagged),
        "pairs_blocked": blocks.pair_count,
        "pairs_scored": int(len(scores)),
        "edges": int(scores["is_edge"].sum()) if len(scores) else 0,
        "carried_edges": len(carried),
        "match_rate": round(float(scores["is_edge"].mean()), 4) if len(scores) else 0.0,
        "match_category_counts": scores["match_category"].value_counts().to_dict() if len(scores) else {},
        "clusters": clusters.qa["clusters"],
        "multi_record_clusters": sum(1 for m in clusters.members.values() if len(m) > 1),
        "records_in_multi_record_clusters_pct": round(
            100.0 * sum(len(m) for m in clusters.members.values() if len(m) > 1) / max(1, len(rids)), 2
        ),
        **{k: v for k, v in clusters.qa.items() if k != "clusters"},
        "jitter": stable.jitter.as_dict() if stable.jitter else {},
        "timings_sec": timings,
        "threshold": cfg.matcher.get("match_threshold"),
    }
    con.execute(
        "UPDATE stitch_runs SET finished_at = ?, status = 'succeeded', metrics_json = ? WHERE run_id = ?",
        [datetime.utcnow(), json.dumps(metrics, default=str), run_id],
    )
    return StitchRunResult(run_id, mode, metrics)


def _persist(con, run_id, now, records, blocks, flagged, scores, carried, clusters, stable, previous):
    if blocks.keys:
        bk = pd.DataFrame(blocks.keys, columns=["bk", "datasource", "pk", "strategy"])
        bk["run_id"] = run_id
        write_df(con, "stitch_blocking_keys", bk, ["run_id", "bk", "datasource", "pk", "strategy"])
    if blocks.skipped:
        sk = pd.DataFrame(blocks.skipped, columns=["strategy", "bk", "block_size", "size_limit"])
        sk["run_id"] = run_id
        write_df(con, "stitch_skipped_blocks", sk, ["run_id", "strategy", "bk", "block_size", "size_limit"])
    if flagged:
        fl = pd.DataFrame(flagged)
        fl["run_id"] = run_id
        write_df(con, "stitch_blocklist_values", fl, ["run_id", "semantic", "value", "reason", "distinct_count"])
    if len(scores):
        sc = scores.copy()
        sc["run_id"] = run_id
        write_df(
            con,
            "stitch_scores",
            sc,
            ["run_id", "left_datasource", "left_pk", "right_datasource", "right_pk", "score", "match_category", "match_type", "is_edge", "features_json"],
        )
    if carried:
        cr = pd.DataFrame(
            [
                {
                    "run_id": run_id,
                    "left_datasource": records[a]["datasource"], "left_pk": records[a]["pk"],
                    "right_datasource": records[b]["datasource"], "right_pk": records[b]["pk"],
                    "score": s, "match_category": "exact", "match_type": "carried", "is_edge": True, "features_json": None,
                }
                for a, b, s in carried
            ]
        )
        write_df(con, "stitch_scores", cr)

    rows = []
    for rid, cid in clusters.assignment.items():
        rec = records[rid]
        rows.append(
            {
                "run_id": run_id, "datasource": rec["datasource"], "pk": rec["pk"], "cluster_id": cid,
                "aurora_id": stable.cluster_to_id[cid], "component_id": clusters.component.get(rid),
                "supersized_id": clusters.supersized.get(rid), "is_supersized": rid in clusters.supersized,
            }
        )
    write_df(con, "stitch_clusters", pd.DataFrame(rows))

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
