"""Blocking strategies (Amperity: internals §2.4) with zero-discard handling of oversized blocks.

A strategy maps a record to zero or more blocking keys; records sharing a key form a block and pairs inside a
block become candidate pairs. Amperity documents a block-size limit (100; 1000 for foreign keys) above which a
block is *skipped*. We keep the limit as the definition of "oversized" but **never discard a block**:

* an oversized block whose pair count fits ``max_pairs_per_block`` is compared in full (hot keys are usually
  the most valuable customers: repeat buyers, shared household keys, wholesale accounts);
* a larger block is **sub-blocked**: it is refined on a cascade of secondary keys (``refine_keys`` per strategy
  type, composite DNF-style keys such as e-mail ∧ surname/given prefix, ∧ postal, ∧ birthdate, …) until every
  sub-block is small enough, and a **sorted-neighbourhood** sweep over the whole block (window ``sn_window`` on
  surname/given/postal/e-mail/update time) keeps cross-sub-block pairs reachable;
* identical records (trivial dupe groups, §2.9) are blocked and scored once through a representative and
  expanded back at export time, so duplicate floods cost O(distinct) rather than O(copies²).

Everything runs inside DuckDB (``_rec`` → ``_bk`` keys → ``_pairs``), so memory is bounded by DuckDB's buffer
pool; only the members of blocks that need Python-side refinement are materialised, one block at a time.

Proof of zero discard: :func:`coverage_stats` counts, for the records that carry at least one blocking key and
share a block with another record, how many ended up in **no** candidate pair; :func:`build_candidate_pairs`
asserts that number is 0 and reports it as ``records_dropped_by_blocking`` (always 0) next to
``records_without_any_blocking_key`` (records with no comparable attribute at all; reported, not asserted).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import combinations

import duckdb
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

REC_COLUMNS = [
    "idx", "rid", "datasource", "pk", "ck", "given_name_norm", "given_name_canon", "surname_norm", "email_norm",
    "phone_match", "address_norm", "postal_norm", "birthdate_norm", "loy_id_norm", "fk_json", "update_dt",
]
# attributes that make two records "the same record" (trivial dupes); any difference here is a real difference
DUPE_KEY_FIELDS = [
    "given_name_norm", "surname_norm", "email_norm", "phone_match", "address_norm", "postal_norm", "birthdate_norm",
    "loy_id_norm", "ck",
]

_GIVEN = "coalesce(given_name_canon, given_name_norm)"

# secondary keys used to refine oversized blocks (NULL -> the record goes to the '∅' sub-block and is refined further)
REFINE_SQL: dict[str, str] = {
    "name3": f"CASE WHEN {_GIVEN} IS NOT NULL AND surname_norm IS NOT NULL THEN substr({_GIVEN},1,3)||':'||substr(surname_norm,1,3) END",
    "given3": f"substr({_GIVEN},1,3)",
    "surname3": "substr(surname_norm,1,3)",
    "postal": "postal_norm",
    "birthdate": "birthdate_norm",
    "email": "email_norm",
    "phone": "phone_match",
    "house_number": "CASE WHEN regexp_matches(address_norm, '^[0-9]+ ') THEN regexp_extract(address_norm, '^([0-9]+) ', 1) END",
    "update_month": "strftime(update_dt, '%Y-%m')",
}
SN_SORT_COLUMNS = ["surname_norm", "given_name_canon", "postal_norm", "email_norm", "update_dt", "idx"]


def strategy_key_sql(strategy: dict) -> tuple[str, str | None]:
    """(strategy name, SQL expression for its blocking key); the expression is None for the fk type."""
    kind = strategy["type"]
    name = strategy.get("name", kind)
    if kind == "email":
        return name, "email_norm"
    if kind == "phone":
        return name, "phone_match"
    if kind == "name_postal":
        return name, ("CASE WHEN given_name_canon IS NOT NULL AND surname_norm IS NOT NULL AND postal_norm IS NOT NULL "
                      "THEN substr(given_name_canon,1,3)||':'||surname_norm||':'||postal_norm END")
    if kind == "name_birthdate":
        return name, ("CASE WHEN given_name_canon IS NOT NULL AND surname_norm IS NOT NULL AND birthdate_norm IS NOT NULL "
                      "THEN substr(given_name_canon,1,3)||':'||substr(surname_norm,1,1)||':'||birthdate_norm END")
    if kind == "name":
        return name, (f"CASE WHEN {_GIVEN} IS NOT NULL AND surname_norm IS NOT NULL "
                      f"THEN substr({_GIVEN},1,3)||':'||substr(surname_norm,1,3) END")
    if kind == "loy_id":
        return name, "loy_id_norm"
    if kind == "ck":
        return name, "CAST(ck AS VARCHAR)"
    if kind == "fk":
        return name, None
    raise ValueError(f"unknown blocking strategy type: {kind}")


def blocking_keys_for(record: dict, strategy: dict) -> list[tuple[str, str]]:
    """Pure-Python equivalent of :func:`strategy_key_sql` for one record (kept for callers and tests)."""
    import json

    kind = strategy["type"]
    name = strategy.get("name", kind)
    if kind == "email":
        v = record.get("email_norm")
        return [(name, v)] if v else []
    if kind == "phone":
        v = record.get("phone_match")
        return [(name, v)] if v else []
    if kind == "name_postal":
        g, s, p = record.get("given_name_canon"), record.get("surname_norm"), record.get("postal_norm")
        return [(name, f"{g[:3]}:{s}:{p}")] if g and s and p else []
    if kind == "name_birthdate":
        g, s, b = record.get("given_name_canon"), record.get("surname_norm"), record.get("birthdate_norm")
        return [(name, f"{g[:3]}:{s[:1]}:{b}")] if g and s and b else []
    if kind == "name":
        g, s = record.get("given_name_canon") or record.get("given_name_norm"), record.get("surname_norm")
        return [(name, f"{g[:3]}:{s[:3]}")] if g and s else []
    if kind == "loy_id":
        v = record.get("loy_id_norm")
        return [(name, v)] if v else []
    if kind == "ck":
        v = record.get("ck")
        return [(name, str(v))] if v else []
    if kind == "fk":
        raw = record.get("fk_json")
        if not raw:
            return []
        try:
            fks = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except json.JSONDecodeError:
            return []
        return [(f"fk-{ns.removeprefix('fk-')}", f"{ns}:{v}") for ns, v in fks.items()]
    raise ValueError(f"unknown blocking strategy type: {kind}")


@dataclass
class OversizedBlock:
    strategy: str
    bk: str
    size: int
    limit: int
    handling: str  # full | refined
    sub_blocks: int = 0
    pairs: int = 0


@dataclass
class BlockingStats:
    pairs: int = 0
    blocks: int = 0  # blocks with >= 2 members that produced pairs
    oversized: list[OversizedBlock] = field(default_factory=list)
    records: int = 0
    representatives: int = 0
    dupe_groups: int = 0  # groups with > 1 member
    records_with_keys: int = 0
    records_without_any_blocking_key: int = 0
    records_in_multi_record_blocks: int = 0
    records_in_candidate_pairs: int = 0
    records_dropped_by_blocking: int = 0  # asserted == 0
    keys: int = 0

    def as_metrics(self) -> dict:
        handling: dict[str, int] = {}
        for o in self.oversized:
            handling[o.handling] = handling.get(o.handling, 0) + 1
        return {
            "blocks": self.blocks,
            "pairs_blocked": self.pairs,
            "blocking_keys": self.keys,
            "skipped_blocks": 0,  # kept for the interface contract: no block is ever skipped any more
            "oversized_blocks": len(self.oversized),
            "oversized_handling": handling,
            "oversized_pairs": sum(o.pairs for o in self.oversized),
            "dupe_groups": self.dupe_groups,
            "representatives": self.representatives,
            "records_with_keys": self.records_with_keys,
            "records_without_any_blocking_key": self.records_without_any_blocking_key,
            "records_in_multi_record_blocks": self.records_in_multi_record_blocks,
            "records_in_candidate_pairs": self.records_in_candidate_pairs,
            "records_dropped_by_blocking": self.records_dropped_by_blocking,
        }


# ----------------------------------------------------------------------------------------- dupe groups
def assign_dupe_groups(con: duckdb.DuckDBPyConnection, collapse: bool, rec_table: str = "_rec") -> None:
    """Add ``dupe_group`` (idx of the group's representative) and ``is_rep`` to the record table."""
    key = ", ".join(DUPE_KEY_FIELDS)
    nonnull = " OR ".join(f"{c} IS NOT NULL" for c in DUPE_KEY_FIELDS)
    con.execute(f"ALTER TABLE {rec_table} ADD COLUMN IF NOT EXISTS dupe_group INTEGER")
    con.execute(f"ALTER TABLE {rec_table} ADD COLUMN IF NOT EXISTS is_rep BOOLEAN")
    if not collapse:
        con.execute(f"UPDATE {rec_table} SET dupe_group = idx, is_rep = TRUE")
        return
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _dg AS
        SELECT idx, CASE WHEN ({nonnull}) THEN MIN(idx) OVER (PARTITION BY {key}) ELSE idx END AS dupe_group
        FROM {rec_table}
        """
    )
    con.execute(f"UPDATE {rec_table} SET dupe_group = _dg.dupe_group FROM _dg WHERE {rec_table}.idx = _dg.idx")
    con.execute(f"UPDATE {rec_table} SET is_rep = (idx = dupe_group)")
    con.execute("DROP TABLE _dg")


# ----------------------------------------------------------------------------------------- keys
def build_keys(con: duckdb.DuckDBPyConnection, strategies: list[dict], rec_table: str = "_rec") -> None:
    """``_bk(idx, strategy, bk)`` for representatives only (members inherit their representative's keys)."""
    parts = []
    for strategy in strategies:
        name, expr = strategy_key_sql(strategy)
        if expr is None:
            parts.append(
                f"SELECT idx, 'fk-' || replace(k, 'fk-', '') AS strategy, k || ':' || json_extract_string(fk_json, '$.' || k) AS bk "
                f"FROM {rec_table}, UNNEST(json_keys(fk_json)) AS t(k) WHERE is_rep AND fk_json IS NOT NULL AND json_valid(fk_json)"
            )
        else:
            parts.append(f"SELECT idx, '{name}' AS strategy, {expr} AS bk FROM {rec_table} WHERE is_rep")
    sql = " UNION ALL ".join(parts) if parts else "SELECT NULL::INTEGER AS idx, NULL::VARCHAR AS strategy, NULL::VARCHAR AS bk WHERE FALSE"
    con.execute(f"CREATE OR REPLACE TEMP TABLE _bk AS SELECT DISTINCT idx, strategy, bk FROM ({sql}) WHERE bk IS NOT NULL AND bk <> ''")
    con.execute("CREATE OR REPLACE TEMP TABLE _blk AS SELECT strategy, bk, COUNT(*) AS n FROM _bk GROUP BY strategy, bk")


# ----------------------------------------------------------------------------------------- refinement
def _pairs_of(idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    idx = np.sort(idx.astype(np.int64))
    i, j = np.triu_indices(len(idx), k=1)
    return idx[i], idx[j]


def _sn_pairs(members: pd.DataFrame, window: int) -> tuple[np.ndarray, np.ndarray]:
    """Sorted-neighbourhood pairs: each record with the next ``window`` records in sort order."""
    cols = [c for c in SN_SORT_COLUMNS if c in members.columns]
    ordered = members.sort_values(cols, kind="mergesort", na_position="last")["idx"].to_numpy(dtype=np.int64)
    n = len(ordered)
    ls, rs = [], []
    for off in range(1, min(window, n - 1) + 1):
        ls.append(ordered[:-off])
        rs.append(ordered[off:])
    if not ls:
        return np.empty(0, np.int64), np.empty(0, np.int64)
    left, right = np.concatenate(ls), np.concatenate(rs)
    return np.minimum(left, right), np.maximum(left, right)


def _refine(members: pd.DataFrame, keys: list[str], target: int, budget: int, window: int, out: list, counter: dict) -> None:
    """Recursive composite-key refinement of one oversized block; every record ends in >= 1 comparison set."""
    n = len(members)
    if n < 2:
        return
    if n <= target or n * (n - 1) // 2 <= budget:
        counter["sub_blocks"] += 1
        out.append(_pairs_of(members["idx"].to_numpy()))
        return
    if not keys:
        counter["sub_blocks"] += 1
        counter["sn_only"] += 1
        out.append(_sn_pairs(members, window))  # keys exhausted: bounded sweep, nothing dropped
        return
    key, rest = keys[0], keys[1:]
    col = f"_rk_{key}"
    if col not in members.columns or members[col].isna().all():
        _refine(members, rest, target, budget, window, out, counter)
        return
    for _value, grp in members.groupby(col, dropna=False, sort=True):
        _refine(grp, rest, target, budget, window, out, counter)


def refine_oversized_block(
    con: duckdb.DuckDBPyConnection, strategy: str, bk: str, refine_keys: list[str], target: int, budget: int, window: int,
    rec_table: str = "_rec",
) -> tuple[pd.DataFrame, int]:
    """Candidate pairs for one oversized block that does not fit the pair budget: refinement + SN sweep."""
    sel = ", ".join([f"r.{c}" for c in SN_SORT_COLUMNS] + [f"({REFINE_SQL[k]}) AS _rk_{k}" for k in refine_keys if k in REFINE_SQL])
    members = con.execute(
        f"SELECT {sel} FROM _bk b JOIN {rec_table} r USING (idx) WHERE b.strategy = ? AND b.bk = ? ORDER BY r.idx",
        [strategy, bk],
    ).df()
    out: list[tuple[np.ndarray, np.ndarray]] = []
    counter = {"sub_blocks": 0, "sn_only": 0}
    _refine(members, [k for k in refine_keys if k in REFINE_SQL], target, budget, window, out, counter)
    out.append(_sn_pairs(members, window))  # cross-sub-block coverage over the whole block
    left = np.concatenate([o[0] for o in out]) if out else np.empty(0, np.int64)
    right = np.concatenate([o[1] for o in out]) if out else np.empty(0, np.int64)
    pairs = pd.DataFrame({"l": left, "r": right}).drop_duplicates()
    return pairs, counter["sub_blocks"]


# ----------------------------------------------------------------------------------------- pairs
def build_candidate_pairs(con: duckdb.DuckDBPyConnection, cfg, rec_table: str = "_rec") -> BlockingStats:
    """Populate ``_pairs(l, r)`` (representative idx, l < r) from ``rec_table`` and return coverage statistics.

    ``cfg`` is the ``blocking`` config section. Raises ``AssertionError`` if any keyed record that shares a block
    with another record did not end up in a candidate pair (the zero-discard invariant)."""
    limit = int(cfg.get("block_size_limit", 100))
    fk_limit = int(cfg.get("fk_block_size_limit", 1000))
    budget = int(cfg.get("max_pairs_per_block", 500_000))
    target = int(cfg.get("refine_target", limit))
    window = int(cfg.get("sn_window", 25))
    collapse = bool(cfg.get("collapse_trivial_dupes", True))
    refine_keys = cfg.get("refine_keys", {}) or {}
    strategies = list(cfg.get("strategies", []))
    kinds = {s.get("name", s["type"]): s["type"] for s in strategies}
    budgets = {s.get("name", s["type"]): int(s.get("max_pairs_per_block", budget)) for s in strategies}

    stats = BlockingStats()
    assign_dupe_groups(con, collapse, rec_table)
    build_keys(con, strategies, rec_table)
    con.register("_budget_src", pd.DataFrame({"strategy": list(budgets), "budget": list(budgets.values())}))
    con.execute("CREATE OR REPLACE TEMP TABLE _budget AS SELECT * FROM _budget_src")
    con.unregister("_budget_src")
    stats.records = con.execute(f"SELECT COUNT(*) FROM {rec_table}").fetchone()[0]
    stats.representatives = con.execute(f"SELECT COUNT(*) FROM {rec_table} WHERE is_rep").fetchone()[0]
    stats.dupe_groups = con.execute(f"SELECT COUNT(*) FROM (SELECT dupe_group FROM {rec_table} GROUP BY 1 HAVING COUNT(*) > 1)").fetchone()[0]
    stats.keys = con.execute("SELECT COUNT(*) FROM _bk").fetchone()[0]

    # 1. blocks compared in full: within the documented limit, or oversized but inside the pair budget
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _blk_full AS
        SELECT k.strategy, k.bk, k.n,
               CASE WHEN k.strategy LIKE 'fk-%' THEN ? ELSE ? END AS size_limit,
               k.n > CASE WHEN k.strategy LIKE 'fk-%' THEN ? ELSE ? END AS oversized
        FROM _blk k LEFT JOIN _budget b ON b.strategy = k.strategy
        WHERE k.n >= 2 AND k.n * (k.n - 1) / 2 <= COALESCE(b.budget, ?)
        """,
        [fk_limit, limit, fk_limit, limit, budget],
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _pairs AS
        SELECT a.idx AS l, b.idx AS r
        FROM _bk a JOIN _bk b ON a.strategy = b.strategy AND a.bk = b.bk AND a.idx < b.idx
        JOIN _blk_full f ON f.strategy = a.strategy AND f.bk = a.bk
        """
    )
    stats.blocks = con.execute("SELECT COUNT(*) FROM _blk_full").fetchone()[0]
    for strategy, bk, n, size_limit in con.execute(
        "SELECT strategy, bk, n, size_limit FROM _blk_full WHERE oversized ORDER BY n DESC, strategy, bk"
    ).fetchall():
        stats.oversized.append(OversizedBlock(strategy, bk, int(n), int(size_limit), "full", 1, int(n) * (int(n) - 1) // 2))

    # 2. blocks beyond the pair budget: composite-key refinement + sorted-neighbourhood sweep (never dropped)
    big = con.execute(
        """
        SELECT k.strategy, k.bk, k.n, CASE WHEN k.strategy LIKE 'fk-%' THEN ? ELSE ? END AS size_limit, COALESCE(b.budget, ?) AS budget
        FROM _blk k LEFT JOIN _budget b ON b.strategy = k.strategy
        WHERE k.n * (k.n - 1) / 2 > COALESCE(b.budget, ?) ORDER BY k.n DESC, k.strategy, k.bk
        """,
        [fk_limit, limit, budget, budget],
    ).fetchall()
    for strategy, bk, n, size_limit, blk_budget in big:
        kind = "fk" if strategy.startswith("fk-") else kinds.get(strategy, strategy)
        keys = list(refine_keys.get(strategy) or refine_keys.get(kind) or ["name3", "postal", "birthdate", "update_month"])
        pairs, sub_blocks = refine_oversized_block(con, strategy, bk, keys, target, int(blk_budget), window, rec_table)
        con.register("_refined_pairs", pairs)
        con.execute("INSERT INTO _pairs SELECT l, r FROM _refined_pairs")
        con.unregister("_refined_pairs")
        stats.oversized.append(OversizedBlock(strategy, bk, int(n), int(size_limit), "refined", sub_blocks, int(len(pairs))))
        stats.blocks += 1
        log.info("refined oversized block strategy=%s key=%s size=%d -> %d sub-blocks, %d pairs", strategy, bk, n, sub_blocks, len(pairs))

    con.execute("CREATE OR REPLACE TEMP TABLE _pairs_d AS SELECT DISTINCT l, r FROM _pairs")
    con.execute("DROP TABLE _pairs")
    con.execute("ALTER TABLE _pairs_d RENAME TO _pairs")
    stats.pairs = con.execute("SELECT COUNT(*) FROM _pairs").fetchone()[0]
    coverage_stats(con, stats, rec_table)
    assert stats.records_dropped_by_blocking == 0, (
        f"{stats.records_dropped_by_blocking} keyed records in multi-record blocks have no candidate pair"
    )
    return stats


def coverage_stats(con: duckdb.DuckDBPyConnection, stats: BlockingStats, rec_table: str = "_rec") -> BlockingStats:
    """Zero-discard accounting over representatives (members share their representative's fate)."""
    stats.records_with_keys = con.execute("SELECT COUNT(DISTINCT idx) FROM _bk").fetchone()[0]
    stats.records_without_any_blocking_key = con.execute(
        f"SELECT COUNT(*) FROM {rec_table} r WHERE is_rep AND NOT EXISTS (SELECT 1 FROM _bk b WHERE b.idx = r.idx)"
    ).fetchone()[0]
    stats.records_in_multi_record_blocks = con.execute(
        "SELECT COUNT(DISTINCT b.idx) FROM _bk b JOIN _blk k ON k.strategy = b.strategy AND k.bk = b.bk WHERE k.n >= 2"
    ).fetchone()[0]
    stats.records_in_candidate_pairs = con.execute(
        "SELECT COUNT(*) FROM (SELECT l AS idx FROM _pairs UNION SELECT r FROM _pairs)"
    ).fetchone()[0]
    stats.records_dropped_by_blocking = con.execute(
        """
        SELECT COUNT(DISTINCT b.idx) FROM _bk b JOIN _blk k ON k.strategy = b.strategy AND k.bk = b.bk
        WHERE k.n >= 2 AND NOT EXISTS (SELECT 1 FROM _pairs p WHERE p.l = b.idx OR p.r = b.idx)
        """
    ).fetchone()[0]
    return stats


# ----------------------------------------------------------------------------------------- in-memory API
@dataclass
class BlockingResult:
    """Python-level view used by tests and small callers (built through the same DuckDB code path)."""

    pairs: set[tuple[str, str]] = field(default_factory=set)
    keys: list[tuple[str, str, str, str]] = field(default_factory=list)  # (bk, datasource, pk, strategy)
    skipped: list[tuple[str, str, int, int]] = field(default_factory=list)  # always empty: nothing is skipped
    oversized: list[OversizedBlock] = field(default_factory=list)
    block_count: int = 0
    stats: BlockingStats | None = None

    @property
    def pair_count(self) -> int:
        return len(self.pairs)


def load_records_table(con: duckdb.DuckDBPyConnection, records: dict[str, dict] | pd.DataFrame, rec_table: str = "_rec") -> None:
    """Create ``rec_table`` (REC_COLUMNS, idx ordered by rid) from {rid: record} or a preprocessed frame."""
    if isinstance(records, dict):
        rows = []
        for rid in sorted(records):
            r = records[rid]
            rows.append({c: r.get(c) for c in REC_COLUMNS if c not in ("idx", "rid")} | {"rid": rid})
        df = pd.DataFrame(rows, columns=[c for c in REC_COLUMNS if c != "idx"])
    else:
        df = records.copy()
        if "rid" not in df.columns:
            df["rid"] = df["datasource"].astype(str) + "|" + df["pk"].astype(str)
        for c in REC_COLUMNS:
            if c not in df.columns and c != "idx":
                df[c] = None
        df = df.sort_values("rid", kind="mergesort")[[c for c in REC_COLUMNS if c != "idx"]]
    df = df.astype(object).where(pd.notna(df), None)
    if "update_dt" in df.columns:
        df["update_dt"] = pd.to_datetime(df["update_dt"], errors="coerce")
    con.register("_rec_src", df)
    cols = ", ".join(c for c in REC_COLUMNS if c != "idx")
    con.execute(
        f"CREATE OR REPLACE TABLE {rec_table} AS SELECT (ROW_NUMBER() OVER (ORDER BY rid) - 1)::INTEGER AS idx, {cols} "
        f"FROM (SELECT * FROM _rec_src)"
    )
    con.unregister("_rec_src")


def build_blocks(records: dict[str, dict], cfg) -> BlockingResult:
    """records: rid -> preprocessed record. cfg: the `blocking` config section. In-memory DuckDB, same code path."""
    con = duckdb.connect(":memory:")
    try:
        load_records_table(con, records)
        stats = build_candidate_pairs(con, cfg)
        res = BlockingResult(oversized=stats.oversized, block_count=stats.blocks, stats=stats)
        rid_of = dict(con.execute("SELECT idx, rid FROM _rec").fetchall())
        members = {}
        for idx, grp in con.execute("SELECT idx, dupe_group FROM _rec").fetchall():
            members.setdefault(grp, []).append(idx)
        for l, r in con.execute("SELECT l, r FROM _pairs").fetchall():
            for a in members[l]:
                for b in members[r]:
                    res.pairs.add((min(rid_of[a], rid_of[b]), max(rid_of[a], rid_of[b])))
        for grp, mem in members.items():  # trivial dupes are candidate pairs too
            for a, b in combinations(sorted(mem), 2):
                res.pairs.add((min(rid_of[a], rid_of[b]), max(rid_of[a], rid_of[b])))
        res.keys = [
            (bk, ds, pk, st) for bk, ds, pk, st in con.execute(
                "SELECT b.bk, r.datasource, r.pk, b.strategy FROM _bk b JOIN _rec rep ON rep.idx = b.idx "
                "JOIN _rec r ON r.dupe_group = rep.idx ORDER BY r.idx, b.strategy, b.bk"
            ).fetchall()
        ]
        return res
    finally:
        con.close()
