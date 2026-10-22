"""Learned DNF blocking (Bilenko, Kamath & Mooney 2006, "Adaptive Blocking"; Amperity internals §2.4).

A *predicate* is (attribute, transform) — e.g. ``(surname_norm, prefix3)`` — and maps a record to a blocking key.
A *conjunction* of predicates over distinct attributes maps a record to the concatenated key. The learner picks a
small *disjunction* of conjunctions that covers as many known-matching pairs as possible (pairwise completeness,
PC) within a candidate-pair budget (reduction), using the red-blue set-cover greedy of the paper:

1. evaluate every unary predicate on a record sample: ``cost`` = Σ n(n−1)/2 over its blocks, ``PC`` = share of
   positive pairs that share its key; prune predicates with PC below ``min_predicate_pc`` or cost above the budget;
2. form conjunctions of up to ``max_terms`` surviving predicates over distinct attributes — exhaustively, or
   with a beam of width ``beam_width`` (the ``beam_width`` best (new positives / cost) conjunctions of each
   length are extended by one predicate; ``null`` keeps the exhaustive search, which is what ``max_terms: 2``
   needs);
3. greedily add the conjunction with the best (newly covered positives / cost) ratio until the target PC is
   reached, the budget is spent, or no conjunction adds ``min_gain_pairs`` new positives.

Positives come either from truth labels (evaluation corpora) or are *self-labelled* from the deterministic rules
(same e-mail or phone with agreeing names, same customer/loyalty key) — the label-free setting Amperity describes
(§2.6). If too few positives exist the learner returns ``fallback_reason`` and the fixed strategies stay in force.

The learned strategies are ordinary blocking strategies of type ``dnf`` and run through the same zero-discard
candidate generation as the hand-written ones (oversized blocks are sub-blocked, never skipped).
"""

from __future__ import annotations

import itertools
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rapidfuzz.distance import JaroWinkler

log = logging.getLogger(__name__)

LEARNED_FILE_VERSION = (
    1  # schema of the learned-strategies YAML (``{schema_version, strategies: [...], ...}``)
)

# ----------------------------------------------------------------------------------------- transforms
_SOUNDEX_CODES = {
    c: d
    for d, letters in {
        "1": "bfpv",
        "2": "cgjkqsxz",
        "3": "dt",
        "4": "l",
        "5": "mn",
        "6": "r",
    }.items()
    for c in letters
}


def soundex(value: str | None) -> str | None:
    """American Soundex (4 characters) of the first alphabetic token; None for empty/non-alphabetic input."""
    if not isinstance(value, str) or not value:
        return None
    s = "".join(ch for ch in str(value).lower() if ch.isalpha())
    if not s:
        return None
    out = s[0].upper()
    last = _SOUNDEX_CODES.get(s[0], "")
    for ch in s[1:]:
        code = _SOUNDEX_CODES.get(ch, "")
        if code and code != last:
            out += code
        if ch not in "hw":
            last = code
        if len(out) == 4:
            break
    return (out + "000")[:4]


def _str(v) -> str | None:
    """None for NaN / empty / non-string values (pandas hands NaN for missing strings)."""
    return v if isinstance(v, str) and v else None


def _py_prefix(n: int) -> Callable[[Any], str | None]:
    def f(v: Any) -> str | None:
        s = _str(v)
        return s[:n] if s else None

    return f


def _py_suffix(n: int) -> Callable[[Any], str | None]:
    def f(v: Any) -> str | None:
        s = _str(v)
        return s[-n:] if s else None

    return f


def _py_first_token(v: Any) -> str | None:
    s = _str(v)
    return s.split(" ", 1)[0] if s else None


def _py_last_token(v: Any) -> str | None:
    s = _str(v)
    return s.rsplit(" ", 1)[-1] if s else None


TRANSFORMS: dict[str, tuple[str, Callable[[Any], str | None]]] = {
    # name: (SQL template over column {c}, python equivalent)
    "exact": ("{c}", _str),
    "prefix3": ("substr({c}, 1, 3)", _py_prefix(3)),
    "prefix5": ("substr({c}, 1, 5)", _py_prefix(5)),
    "suffix3": ("right({c}, 3)", _py_suffix(3)),
    "suffix4": ("right({c}, 4)", _py_suffix(4)),
    "first_token": ("split_part({c}, ' ', 1)", _py_first_token),
    "last_token": ("regexp_extract({c}, '(\\S+)$', 1)", _py_last_token),
    "year": ("substr({c}, 1, 4)", _py_prefix(4)),
    "soundex": ("aurora_soundex({c})", soundex),
}

# attribute -> transforms worth trying (the search space of the learner; documented in defaults.yaml)
DEFAULT_PREDICATE_SPACE: dict[str, list[str]] = {
    "given_name_canon": ["exact", "prefix3", "soundex"],
    "surname_norm": ["exact", "prefix3", "suffix3", "soundex"],
    "email_norm": ["exact", "prefix5"],
    "email_local": ["exact", "prefix5"],
    "phone_match": ["exact", "suffix4"],
    "postal_norm": ["exact", "prefix3"],
    "birthdate_norm": ["exact", "year"],
    "address_norm": ["exact", "first_token"],
    "house_no": ["exact"],
    "loy_id_norm": ["exact"],
    "ck": ["exact"],
}


def term_sql(attr: str, transform: str) -> str:
    return TRANSFORMS[transform][0].format(c=attr)


def conjunction_sql(terms: list[dict]) -> str:
    """SQL key expression for a conjunction: NULL unless every term is non-empty."""
    exprs = [f"NULLIF({term_sql(t['attr'], t['transform'])}, '')" for t in terms]
    cond = " AND ".join(f"{e} IS NOT NULL" for e in exprs)
    return f"CASE WHEN {cond} THEN concat_ws(':', {', '.join(exprs)}) END"


def conjunction_key(record: dict, terms: list[dict]) -> str | None:
    parts = []
    for t in terms:
        v = TRANSFORMS[t["transform"]][1](_str(record.get(t["attr"])))
        if not v:
            return None
        parts.append(str(v))
    return ":".join(parts)


def register_udfs(con) -> None:
    """Register the Python-side transforms DuckDB lacks (idempotent)."""
    try:
        con.create_function(
            "aurora_soundex", soundex, ["VARCHAR"], "VARCHAR", null_handling="special"
        )
    except Exception as exc:  # already registered on this connection
        if "already" not in str(exc).lower() and "exists" not in str(exc).lower():
            raise


# ----------------------------------------------------------------------------------------- learner
@dataclass
class PredicateStats:
    attr: str
    transform: str
    cost: int  # candidate pairs on the sample
    pc: float  # pairwise completeness on the positive sample
    blocks: int
    pruned: str | None = None


@dataclass
class DnfResult:
    strategies: list[dict] = field(default_factory=list)
    predicates: list[PredicateStats] = field(default_factory=list)
    chosen: list[dict] = field(default_factory=list)  # per conjunction: terms, pc, cost, new_pairs
    pc: float = 0.0
    cost: int = 0
    budget: int = 0
    positives: int = 0
    records: int = 0
    fallback_reason: str | None = None

    def as_metrics(self) -> dict:
        return {
            "dnf_strategies": len(self.strategies),
            "dnf_pc_train": round(self.pc, 4),
            "dnf_cost_train": self.cost,
            "dnf_budget": self.budget,
            "dnf_positives": self.positives,
            "dnf_records": self.records,
            "dnf_fallback_reason": self.fallback_reason,
        }


def derive_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Python version of the derived columns the SQL loader adds to ``_rec``."""
    df = df.copy()
    em = df.get("email_norm")
    df["email_local"] = [
        v.split("@", 1)[0] if isinstance(v, str) and v else None
        for v in (em if em is not None else [None] * len(df))
    ]
    ad = df.get("address_norm")
    df["house_no"] = [
        (v.split(" ", 1)[0] if isinstance(v, str) and v and v.split(" ", 1)[0].isdigit() else None)
        for v in (ad if ad is not None else [None] * len(df))
    ]
    df["given_sdx"] = [soundex(v) for v in df.get("given_name_canon", pd.Series([None] * len(df)))]
    df["surname_sdx"] = [soundex(v) for v in df.get("surname_norm", pd.Series([None] * len(df)))]
    return df


def _keys(df: pd.DataFrame, terms: list[dict]) -> np.ndarray:
    cols: list[np.ndarray] = []
    for t in terms:
        fn = TRANSFORMS[t["transform"]][1]
        col: list[object] = [fn(v) for v in df[t["attr"]].to_numpy(dtype=object)]
        cols.append(np.array(col, dtype=object))
    out = np.empty(len(df), dtype=object)
    for i in range(len(df)):
        parts = [c[i] for c in cols]
        out[i] = ":".join(str(p) for p in parts) if all(parts) else None
    return out


def _cost_and_cover(keys: np.ndarray, pos: np.ndarray) -> tuple[int, np.ndarray]:
    """cost = Σ n(n−1)/2 over blocks; cover = boolean per positive pair (both sides share the key)."""
    s = pd.Series(keys).dropna()
    counts = s.value_counts()
    cost = int((counts * (counts - 1) // 2).sum())
    if len(pos) == 0:
        return cost, np.zeros(0, dtype=bool)
    ka, kb = keys[pos[:, 0]], keys[pos[:, 1]]
    cover = np.array([a is not None and a == b for a, b in zip(ka, kb, strict=True)], dtype=bool)
    return cost, cover


def self_label_positives(
    df: pd.DataFrame, matcher_cfg: dict, max_pairs: int, rng: np.random.Generator
) -> np.ndarray:
    """Label-free positives: pairs that satisfy a deterministic rule (ck / loyalty exact; e-mail or phone exact with
    agreeing names). Returns an array of (i, j) index pairs, at most ``max_pairs`` (uniformly sampled).
    """
    det = matcher_cfg.get("deterministic", {})
    name_min = float(det.get("name_agreement_min", 0.85))
    given = df["given_name_canon"].to_numpy(dtype=object)
    sur = df["surname_norm"].to_numpy(dtype=object)
    pairs: list[tuple[int, int]] = []

    def names_agree(i, j) -> bool:
        if not (given[i] and given[j] and sur[i] and sur[j]):
            return False
        return (
            JaroWinkler.normalized_similarity(given[i], given[j]) >= name_min
            and JaroWinkler.normalized_similarity(sur[i], sur[j]) >= name_min
        )

    for col, need_names in (
        ("ck", False),
        ("loy_id_norm", False),
        ("email_norm", True),
        ("phone_match", True),
    ):
        if col not in df.columns:
            continue
        groups = df.groupby(col, sort=False).indices
        for key, idx in groups.items():
            if key is None or key == "" or len(idx) < 2:
                continue
            idx = np.sort(idx)
            if len(idx) > 60:  # hot keys: a bounded random subset keeps the sample balanced
                idx = np.sort(rng.choice(idx, 60, replace=False))
            for a, b in itertools.combinations(idx.tolist(), 2):
                if not need_names or names_agree(a, b):
                    pairs.append((a, b))
    if not pairs:
        return np.zeros((0, 2), dtype=np.int64)
    arr = np.unique(np.array(pairs, dtype=np.int64), axis=0)
    if len(arr) > max_pairs:
        arr = arr[np.sort(rng.choice(len(arr), max_pairs, replace=False))]
    return arr


def truth_positives(
    truth: np.ndarray, max_pairs: int, rng: np.random.Generator, max_per_entity: int = 40
) -> np.ndarray:
    """Positive pairs from an entity label per record (evaluation corpora only)."""
    pairs: list[tuple[int, int]] = []
    s = pd.Series(truth)
    for _, idx in s.groupby(s, sort=False).indices.items():
        idx = np.sort(idx)
        if len(idx) < 2:
            continue
        if len(idx) > max_per_entity:
            idx = np.sort(rng.choice(idx, max_per_entity, replace=False))
        pairs.extend(itertools.combinations(idx.tolist(), 2))
    arr = np.array(pairs, dtype=np.int64) if pairs else np.zeros((0, 2), dtype=np.int64)
    if len(arr) > max_pairs:
        arr = arr[np.sort(rng.choice(len(arr), max_pairs, replace=False))]
    return arr


def learn_dnf(
    df: pd.DataFrame, positives: np.ndarray, cfg: dict, full_records: int | None = None
) -> DnfResult:
    """Learn a disjunction of conjunctive blocking predicates on a record sample.

    ``df``: sample records with the attribute columns (``derive_columns`` applied). ``positives``: (i, j) index
    pairs known to match. ``cfg``: the ``blocking.dnf`` config section."""
    space = cfg.get("predicate_space") or DEFAULT_PREDICATE_SPACE
    max_terms = int(cfg.get("max_terms", 2))
    min_pos = int(cfg.get("min_positive_pairs", 200))
    min_pc = float(cfg.get("min_predicate_pc", 0.01))
    target = float(cfg.get("target_pc", 0.95))
    min_gain = int(cfg.get("min_gain_pairs", 5))
    per_record = float(cfg.get("pairs_per_record_budget", 20.0))
    n = len(df)
    res = DnfResult(positives=int(len(positives)), records=n, budget=int(per_record * n))
    if len(positives) < min_pos:
        res.fallback_reason = (
            f"insufficient positives ({len(positives)} < {min_positive_pairs(cfg)})"
        )
        return res
    if n < 2:
        res.fallback_reason = "insufficient records"
        return res
    # 1. unary predicates
    unary: list[tuple[dict, int, np.ndarray]] = []
    for attr, transforms in space.items():
        if attr not in df.columns:
            continue
        for tr in transforms:
            terms = [{"attr": attr, "transform": tr}]
            keys = _keys(df, terms)
            cost, cover = _cost_and_cover(keys, positives)
            pc = float(cover.mean()) if len(cover) else 0.0
            blocks = int(pd.Series(keys).dropna().nunique())
            st = PredicateStats(attr, tr, cost, round(pc, 4), blocks)
            if pc < min_pc:
                st.pruned = "pc"
            elif cost > res.budget:
                st.pruned = "cost"
            res.predicates.append(st)
            if st.pruned is None or (
                st.pruned == "cost" and max_terms > 1
            ):  # costly unaries may survive inside conjunctions
                unary.append((terms[0], cost, cover))
    if not unary:
        res.fallback_reason = "no usable predicate"
        return res
    # 2. conjunctions over distinct attributes (unaries that fit the budget stand alone)
    cands: list[tuple[list[dict], int, np.ndarray]] = []
    for term, cost, cover in unary:
        if cost <= res.budget:
            cands.append(([term], cost, cover))
    beam = cfg.get("beam_width")
    if beam:
        cands += _beam_conjunctions(
            df, positives, unary, max_terms, int(beam), min_gain, res.budget
        )
    else:
        for k in range(2, max_terms + 1):
            for combo in itertools.combinations(unary, k):
                attrs = {t[0]["attr"] for t in combo}
                if len(attrs) < k:
                    continue
                terms = [t[0] for t in combo]
                cover_ub = np.all(np.stack([t[2] for t in combo]), axis=0)
                if cover_ub.sum() < min_gain:  # cannot add enough
                    continue
                keys = _keys(df, terms)
                cost, cover = _cost_and_cover(keys, positives)
                if cost <= res.budget:
                    cands.append((terms, cost, cover))
    # 3. greedy red-blue set cover
    covered = np.zeros(len(positives), dtype=bool)
    spent = 0
    while cands and covered.mean() < target:
        best = None
        for terms, cost, cover in cands:
            if spent + cost > res.budget:
                continue
            new = int((cover & ~covered).sum())
            if new < min_gain:
                continue
            ratio = new / max(cost, 1)
            if best is None or ratio > best[0] or (ratio == best[0] and new > best[1]):
                best = (ratio, new, terms, cost, cover)
        if best is None:
            break
        _, new, terms, cost, cover = best
        covered |= cover
        spent += cost
        res.chosen.append(
            {
                "terms": terms,
                "pc": round(float(cover.mean()), 4),
                "cost": cost,
                "new_pairs": new,
                "cum_pc": round(float(covered.mean()), 4),
            }
        )
        cands = [c for c in cands if c[0] != terms]
    res.pc = float(covered.mean())
    res.cost = spent
    res.strategies = [
        {
            "name": "dnf_" + "_".join(f"{t['attr']}.{t['transform']}" for t in c["terms"]),
            "type": "dnf",
            "terms": c["terms"],
            "learned": {"pc": c["pc"], "cost_sample": c["cost"]},
        }
        for c in res.chosen
    ]
    if not res.strategies:
        res.fallback_reason = "greedy cover selected nothing within budget"
    return res


def _beam_conjunctions(df, positives, unary, max_terms: int, beam: int, min_gain: int, budget: int):
    """Beam search over conjunction length: keep the ``beam`` best (covered positives / cost) conjunctions of each
    length and extend each by one unary predicate over a new attribute. Deterministic: ties break on cost, then
    on the predicate names. Conjunctions that exceed the budget are still extended (a longer conjunction is
    cheaper) but only budget-fitting ones become candidates."""

    def rank(c):
        terms, cost, cover = c
        return (
            -(float(cover.sum()) / max(cost, 1)),
            cost,
            [(t["attr"], t["transform"]) for t in terms],
        )

    level = sorted([([t], c, cov) for t, c, cov in unary], key=rank)[:beam]
    out: list[tuple[list[dict], int, np.ndarray]] = []
    seen: set[tuple] = set()
    for _k in range(2, max_terms + 1):
        nxt: list[tuple[list[dict], int, np.ndarray]] = []
        for terms, _cost, cover_prev in level:
            used = {t["attr"] for t in terms}
            for term, _cu, cover_u in unary:
                if term["attr"] in used:
                    continue
                key = tuple(sorted((t["attr"], t["transform"]) for t in [*terms, term]))
                if key in seen:
                    continue
                seen.add(key)
                if int((cover_prev & cover_u).sum()) < min_gain:
                    continue
                new_terms = [*terms, term]
                cost, cover = _cost_and_cover(_keys(df, new_terms), positives)
                nxt.append((new_terms, cost, cover))
                if cost <= budget:
                    out.append((new_terms, cost, cover))
        level = sorted(nxt, key=rank)[:beam]
        if not level:
            break
    return out


def min_positive_pairs(cfg: dict) -> int:
    return int(cfg.get("min_positive_pairs", 200))


# ----------------------------------------------------------------------------------------- learned file
def validate_strategy(s: dict) -> None:
    """Raise ValueError unless ``s`` is a well-formed ``dnf`` strategy (terms over known attrs/transforms)."""
    if not isinstance(s, dict) or s.get("type") != "dnf":
        raise ValueError(f"learned strategy must have type 'dnf': {s!r}")
    terms = s.get("terms")
    if not isinstance(terms, list) or not terms:
        raise ValueError(f"learned strategy {s.get('name')!r} has no terms")
    for t in terms:
        if not isinstance(t, dict) or not t.get("attr") or t.get("transform") not in TRANSFORMS:
            raise ValueError(
                f"learned strategy {s.get('name')!r}: bad term {t!r} (transforms: {sorted(TRANSFORMS)})"
            )


def strategies_document(strategies: list[dict], **meta) -> dict:
    """The YAML document ``tools/learn_dnf.py`` writes and :func:`load_learned_strategies` reads."""
    return {
        "schema_version": LEARNED_FILE_VERSION,
        **meta,
        "strategies": [dict(s) for s in strategies],
    }


def load_learned_strategies(path: str | Path | None) -> tuple[list[dict], str | None]:
    """Read the learned-strategies YAML. Returns ``(strategies, reason)``: ``reason`` explains an empty result
    (missing path, missing file, empty or malformed document) so the caller can fall back to the fixed list.
    """
    import yaml

    if not path:
        return [], "blocking.learned_strategies_file is not set"
    p = Path(path)
    if not p.exists():
        return [], f"learned strategies file {str(p)!r} does not exist"
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [], f"learned strategies file {str(p)!r} is not valid YAML: {exc}"
    if isinstance(doc, list):
        strategies = doc
    elif isinstance(doc, dict):
        strategies = doc.get("strategies") or []
    else:
        strategies = []
    if not strategies:
        return [], f"learned strategies file {str(p)!r} contains no strategies"
    try:
        for s in strategies:
            validate_strategy(s)
    except ValueError as exc:
        return [], f"learned strategies file {str(p)!r} is malformed: {exc}"
    return [dict(s) for s in strategies], None


def evaluate_strategies(df: pd.DataFrame, positives: np.ndarray, strategies: list[dict]) -> dict:
    """PC and cost of an arbitrary strategy list (fixed or learned) on a sample — the learned-vs-fixed comparison."""
    from .blocking import blocking_keys_for

    covered = np.zeros(len(positives), dtype=bool)
    cost = 0
    recs = [
        {
            k: (
                _str(v)
                if not isinstance(v, (int, float)) or isinstance(v, bool)
                else (None if v != v else v)
            )
            for k, v in r.items()
        }
        for r in df.to_dict("records")
    ]
    per: list[dict] = []
    for s in strategies:
        vals: list[object] = []
        for r in recs:
            kl = blocking_keys_for(r, s)
            vals.append(kl[0][1] if kl else None)
        keys = np.array(vals, dtype=object)
        c, cover = _cost_and_cover(keys, positives)
        cost += c
        covered |= cover if len(cover) else covered
        per.append(
            {
                "name": s.get("name", s["type"]),
                "pc": round(float(cover.mean()), 4) if len(cover) else 0.0,
                "cost": c,
            }
        )
    return {
        "pc": round(float(covered.mean()), 4) if len(covered) else 0.0,
        "cost": cost,
        "per_strategy": per,
    }
