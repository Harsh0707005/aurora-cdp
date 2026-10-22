"""Learned ordinal-regression pairwise scorer with label-free (self-training) fitting.

Amperity (SIGMOD 2020; internals §2.5–2.6) classifies candidate pairs with *threshold-based ordinal regression*:
a linear score ``z = w·x`` and learned, ordered thresholds ``θ1 < θ2 < …`` that cut ``z`` into the ordered
labels (hard-conflict / non-match … strong match). The loss is the all-threshold logistic loss
(Rennie & Srebro 2005): every threshold the prediction *crosses* on the wrong side is penalised, so a near miss
costs less than a wild one. Training data is not labelled by hand: positives are pairs that satisfy the
deterministic rules (same e-mail / phone with agreeing names, same customer or loyalty key, trivial dupes),
negatives are hard-conflict pairs and random pairs that share no blocking key, and the model then labels the
remaining candidate pairs itself in a few self-training rounds (confident predictions join the training set,
the uncertain band becomes the middle "weak/moderate" label).

Levels (``levels = 3``): 0 = non-match, 1 = weak/moderate (suggested), 2 = match. The continuous 0–5 score the
rest of the engine expects is a monotone map of ``z`` anchored at the learned thresholds
(0–2 below θ1, 2–3 between θ1 and θ2, 3–5 above θ2), so ``match_threshold = 3.0`` means "level 2".

Feature families (``EXTENDED_FEATURE_NAMES``, on top of ``features.FEATURE_NAMES``): name ↔ e-mail closeness,
first-name popularity and postal-code population (corpus statistics), address token Jaccard, phone Hamming
distance, token agreement, null-pattern agreement, e-mail domain agreement.

Graceful degradation: if fewer than ``min_positive_pairs`` / ``min_negative_pairs`` training pairs exist or the
fit does not converge, :func:`train_from_candidates` returns ``None`` with a ``fallback_reason`` and the caller
keeps the rule scorer.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from rapidfuzz.distance import Hamming, JaroWinkler

from .features import FEATURE_NAMES, SIDE_COLUMNS, features_frame
from .matcher import CATEGORY_BANDS, score_frame

EXTENDED_FEATURE_NAMES = [
    "name_email_closeness",   # best Jaro-Winkler between either side's names and the other side's e-mail local part
    "given_popularity",       # log-frequency of the shared given name in the corpus (common names are weak evidence)
    "postal_population",      # log-frequency of the shared postal code in the corpus
    "address_token_jaccard",  # Jaccard over address tokens
    "phone_hamming",          # 1 - normalised Hamming distance over equal-length phone digits
    "token_agreement",        # share of comparable fields (both present) that agree exactly
    "null_pattern_agreement", # share of fields with the same presence pattern on both sides
    "email_domain_exact",     # same e-mail domain
    "surname_jaccard",        # Jaccard over surname tokens (compound surnames)
]
ALL_FEATURE_NAMES = FEATURE_NAMES + EXTENDED_FEATURE_NAMES
_FIELDS = ("given_name_canon", "surname_norm", "email_norm", "phone_match", "address_norm", "postal_norm", "birthdate_norm")


# ----------------------------------------------------------------------------------------- features
def corpus_context(con, rec_table: str = "_rec") -> dict:
    """Corpus statistics the extended features need (given-name and postal frequencies as fractions)."""
    n = max(1, con.execute(f"SELECT COUNT(*) FROM {rec_table}").fetchone()[0])
    given = dict(con.execute(f"SELECT given_name_canon, COUNT(*) FROM {rec_table} WHERE given_name_canon IS NOT NULL GROUP BY 1").fetchall())
    postal = dict(con.execute(f"SELECT postal_norm, COUNT(*) FROM {rec_table} WHERE postal_norm IS NOT NULL GROUP BY 1").fetchall())
    return {"n": n, "given_pop": {k: v / n for k, v in given.items()}, "postal_pop": {k: v / n for k, v in postal.items()}}


def context_from_frame(df: pd.DataFrame) -> dict:
    n = max(1, len(df))
    g = df["given_name_canon"].dropna().value_counts() if "given_name_canon" in df else pd.Series(dtype=float)
    p = df["postal_norm"].dropna().value_counts() if "postal_norm" in df else pd.Series(dtype=float)
    return {"n": n, "given_pop": (g / n).to_dict(), "postal_pop": (p / n).to_dict()}


def _s(v) -> str | None:
    return v if isinstance(v, str) and v.strip() else None


def _tokens(v) -> set[str]:
    return set(v.split()) if _s(v) else set()


def extended_features(left: pd.DataFrame, right: pd.DataFrame, context: dict | None) -> pd.DataFrame:
    """Vectorised-enough extended features for aligned frames (NaN = not comparable)."""
    n = len(left)
    ctx = context or {"given_pop": {}, "postal_pop": {}, "n": 1}
    L = {c: (left[c].to_numpy(dtype=object) if c in left else np.full(n, None, dtype=object)) for c in _FIELDS}
    R = {c: (right[c].to_numpy(dtype=object) if c in right else np.full(n, None, dtype=object)) for c in _FIELDS}
    out = {k: np.full(n, np.nan) for k in EXTENDED_FEATURE_NAMES}
    for i in range(n):
        ga, gb, sa, sb = _s(L["given_name_canon"][i]), _s(R["given_name_canon"][i]), _s(L["surname_norm"][i]), _s(R["surname_norm"][i])
        ea, eb = _s(L["email_norm"][i]), _s(R["email_norm"][i])
        # name <-> email closeness: either side's name tokens vs the other side's e-mail local part
        best = None
        for name_side, email in (((ga, sa), eb), ((gb, sb), ea)):
            if email and any(name_side):
                local = email.split("@", 1)[0]
                compact = "".join(x for x in name_side if x)
                cand = [JaroWinkler.normalized_similarity(x, local) for x in (name_side[0], name_side[1], compact) if x]
                best = max([best or 0.0] + cand)
        if best is not None:
            out["name_email_closeness"][i] = best
        if ga and gb and ga == gb:
            out["given_popularity"][i] = -math.log(max(ctx["given_pop"].get(ga, 1.0 / ctx["n"]), 1e-9)) / 10.0
        pa, pb = _s(L["postal_norm"][i]), _s(R["postal_norm"][i])
        if pa and pb and pa == pb:
            out["postal_population"][i] = -math.log(max(ctx["postal_pop"].get(pa, 1.0 / ctx["n"]), 1e-9)) / 10.0
        aa, ab = _tokens(L["address_norm"][i]), _tokens(R["address_norm"][i])
        if aa and ab:
            out["address_token_jaccard"][i] = len(aa & ab) / len(aa | ab)
        pha, phb = _s(L["phone_match"][i]), _s(R["phone_match"][i])
        if pha and phb and len(pha) == len(phb):
            out["phone_hamming"][i] = 1.0 - Hamming.distance(pha, phb) / len(pha)
        comparable = agree = same_pattern = 0
        for f in _FIELDS:
            a, b = _s(L[f][i]), _s(R[f][i])
            if (a is None) == (b is None):
                same_pattern += 1
            if a and b:
                comparable += 1
                agree += int(a == b)
        out["token_agreement"][i] = agree / comparable if comparable else np.nan
        out["null_pattern_agreement"][i] = same_pattern / len(_FIELDS)
        if ea and eb:
            out["email_domain_exact"][i] = float(ea.rsplit("@", 1)[-1] == eb.rsplit("@", 1)[-1])
        ta, tb = _tokens(sa), _tokens(sb)
        if ta and tb:
            out["surname_jaccard"][i] = len(ta & tb) / len(ta | tb)
    return pd.DataFrame(out, columns=EXTENDED_FEATURE_NAMES)


def all_features(left: pd.DataFrame, right: pd.DataFrame, matcher_cfg, context: dict | None) -> pd.DataFrame:
    base = features_frame(left, right, matcher_cfg)
    ext = extended_features(left, right, context)
    return pd.concat([base.reset_index(drop=True), ext.reset_index(drop=True)], axis=1)


# ----------------------------------------------------------------------------------------- model
@dataclass
class OrdinalModel:
    feature_names: list[str]
    w: np.ndarray              # weights over [standardised features, missing indicators]
    thresholds: np.ndarray     # increasing, length levels-1
    mean: np.ndarray
    std: np.ndarray
    levels: int = 3
    meta: dict = field(default_factory=dict)

    def design(self, F: pd.DataFrame) -> np.ndarray:
        X = F[self.feature_names].to_numpy(dtype=np.float64)
        miss = np.isnan(X)
        Xs = np.where(miss, 0.0, (X - self.mean) / self.std)
        return np.hstack([Xs, miss.astype(np.float64)])

    def z(self, F: pd.DataFrame) -> np.ndarray:
        return self.design(F) @ self.w

    def level(self, z: np.ndarray) -> np.ndarray:
        return (z[:, None] > self.thresholds[None, :]).sum(axis=1)

    def score(self, z: np.ndarray) -> np.ndarray:
        """Monotone map of z to the engine's 0–5 scale anchored at the learned thresholds."""
        t1, t2 = float(self.thresholds[0]), float(self.thresholds[-1])
        s = max(t2 - t1, 1e-3)
        low = 2.0 / (1.0 + np.exp(-(z - t1) / s))
        mid = 2.0 + (z - t1) / s
        high = 3.0 + 2.0 * (1.0 - np.exp(-(z - t2) / s))
        return np.round(np.where(z < t1, low, np.where(z < t2, mid, high)), 3)

    def to_json(self) -> dict:
        return {"feature_names": self.feature_names, "w": self.w.tolist(), "thresholds": self.thresholds.tolist(), "mean": self.mean.tolist(),
                "std": self.std.tolist(), "levels": self.levels, "meta": self.meta}

    @classmethod
    def from_json(cls, d: dict) -> OrdinalModel:
        return cls(list(d["feature_names"]), np.array(d["w"]), np.array(d["thresholds"]), np.array(d["mean"]), np.array(d["std"]), int(d.get("levels", 3)), dict(d.get("meta", {})))

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_json(), indent=1))

    @classmethod
    def load(cls, path: str | Path) -> OrdinalModel:
        return cls.from_json(json.loads(Path(path).read_text()))


def fit_ordinal(F: pd.DataFrame, y: np.ndarray, levels: int = 3, l2: float = 1e-3, lr: float = 0.05, epochs: int = 300,
                feature_names: list[str] | None = None, seed: int = 0) -> OrdinalModel:
    """All-threshold logistic ordinal regression by full-batch Adam; thresholds kept ordered via softplus gaps."""
    names = feature_names or ALL_FEATURE_NAMES
    X = F[names].to_numpy(dtype=np.float64)
    miss = np.isnan(X)
    mean = np.nanmean(np.where(miss, np.nan, X), axis=0)
    mean = np.where(np.isnan(mean), 0.0, mean)
    std = np.nanstd(np.where(miss, np.nan, X), axis=0)
    std = np.where(np.isnan(std) | (std < 1e-6), 1.0, std)
    D = np.hstack([np.where(miss, 0.0, (X - mean) / std), miss.astype(np.float64)])
    n, d = D.shape
    y = np.asarray(y, dtype=np.int64)
    K = levels - 1
    rng = np.random.default_rng(seed)
    w = rng.normal(0, 0.01, d)
    t0 = 0.0
    gaps = np.zeros(K - 1)  # softplus(gaps) = θ_{k+1} - θ_k
    m = np.zeros(d + K)
    v = np.zeros(d + K)
    b1, b2, eps = 0.9, 0.999, 1e-8
    cw = n / (levels * np.maximum(np.bincount(y, minlength=levels), 1))  # class balancing

    def thresholds(t0, gaps):
        return t0 + np.concatenate([[0.0], np.cumsum(np.log1p(np.exp(gaps)))])

    def loss_grad(w, t0, gaps):
        th = thresholds(t0, gaps)
        z = D @ w
        # s_k = +1 if y > k (z should exceed θ_k), -1 otherwise; loss = log(1 + exp(-s_k (z - θ_k)))
        s = np.where(y[:, None] > np.arange(K)[None, :], 1.0, -1.0)
        marg = s * (z[:, None] - th[None, :])
        sig = 1.0 / (1.0 + np.exp(marg))  # d loss / d marg = -sig
        wt = cw[y][:, None]
        L = float(np.mean(wt * np.logaddexp(0.0, -marg))) + l2 * float(w @ w)
        g_marg = -sig * wt / n
        gz = (g_marg * s).sum(axis=1)
        gw = D.T @ gz + 2 * l2 * w
        gth = -(g_marg * s).sum(axis=0)
        gt0 = float(gth.sum())
        sp = 1.0 / (1.0 + np.exp(-gaps))  # d softplus
        ggaps = np.array([gth[k + 1:].sum() * sp[k] for k in range(K - 1)])
        return L, gw, gt0, ggaps

    params = np.concatenate([w, [t0], gaps])
    hist = []
    for it in range(1, epochs + 1):
        w, t0, gaps = params[:d], params[d], params[d + 1:]
        L, gw, gt0, gg = loss_grad(w, t0, gaps)
        g = np.concatenate([gw, [gt0], gg])
        m = b1 * m + (1 - b1) * g
        v = b2 * v + (1 - b2) * g * g
        mh, vh = m / (1 - b1 ** it), v / (1 - b2 ** it)
        params = params - lr * mh / (np.sqrt(vh) + eps)
        hist.append(L)
    w, t0, gaps = params[:d], params[d], params[d + 1:]
    th = thresholds(t0, gaps)
    model = OrdinalModel(list(names), w, th, mean, std, levels, {"loss_first": round(hist[0], 5), "loss_last": round(hist[-1], 5), "epochs": epochs, "n_train": int(n),
                                                                    "class_counts": np.bincount(y, minlength=levels).tolist(), "l2": l2, "lr": lr})
    return model


# ----------------------------------------------------------------------------------------- scoring
def score_frame_ordinal(F: pd.DataFrame, model: OrdinalModel, cfg) -> pd.DataFrame:
    """Score with the ordinal model; deterministic rules / hard conflicts / trivial dupes still take precedence
    when ``matcher.ordinal.apply_rules_first`` (default) so the two scorers stay comparable."""
    threshold = float(cfg.get("match_threshold", 3.0))
    ocfg = cfg.get("ordinal", {}) or {}
    z = model.z(F)
    score = model.score(z)
    match_type = np.full(len(F), "scored", dtype=object)
    if bool(ocfg.get("apply_rules_first", True)):
        rules = score_frame(F, cfg)
        take = (rules["match_type"] != "scored").to_numpy() | (rules["match_category"] == "hard_conflict").to_numpy()
        score = np.where(take, rules["score"].to_numpy(), score)
        match_type = np.where(take, rules["match_type"].to_numpy(), "scored")
        conflict = (rules["match_category"] == "hard_conflict").to_numpy()
    else:
        conflict = np.zeros(len(F), dtype=bool)
    cat = np.full(len(F), "non_conflict", dtype=object)
    for floor, name in reversed(CATEGORY_BANDS):
        cat[score >= floor] = name
    cat[conflict] = "hard_conflict"
    return pd.DataFrame({"score": score, "match_category": cat, "match_type": match_type, "hard_conflict": conflict,
                         "is_edge": (~conflict) & (score >= threshold)})


# ----------------------------------------------------------------------------------------- training data
@dataclass
class TrainingReport:
    positives: int = 0
    negatives: int = 0
    unlabeled: int = 0
    rounds: list[dict] = field(default_factory=list)
    fallback_reason: str | None = None
    model_meta: dict = field(default_factory=dict)

    def as_metrics(self) -> dict:
        return {"ordinal_positives": self.positives, "ordinal_negatives": self.negatives, "ordinal_unlabeled": self.unlabeled,
                "ordinal_rounds": self.rounds, "ordinal_fallback_reason": self.fallback_reason, "ordinal_model": self.model_meta}


def weak_labels(F: pd.DataFrame, cfg) -> np.ndarray:
    """2 for deterministic / trivial-dupe pairs, 0 for hard conflicts, -1 (unlabeled) otherwise."""
    rules = score_frame(F, cfg)
    y = np.full(len(F), -1, dtype=np.int64)
    y[(rules["match_type"].isin(["deterministic", "trivial_duplicate"])).to_numpy()] = 2
    y[(rules["match_category"] == "hard_conflict").to_numpy()] = 0
    return y


def self_train(F_cand: pd.DataFrame, F_neg: pd.DataFrame, matcher_cfg, ocfg: dict) -> tuple[OrdinalModel | None, TrainingReport]:
    """Label-free training: rule positives + (random + conflict) negatives, then self-training rounds."""
    rep = TrainingReport()
    levels = int(ocfg.get("levels", 3))
    y_c = weak_labels(F_cand, matcher_cfg)
    F = pd.concat([F_cand, F_neg], ignore_index=True)
    y = np.concatenate([y_c, np.zeros(len(F_neg), dtype=np.int64)])
    rep.positives, rep.negatives, rep.unlabeled = int((y == 2).sum()), int((y == 0).sum()), int((y == -1).sum())
    if rep.positives < int(ocfg.get("min_positive_pairs", 300)):
        rep.fallback_reason = f"insufficient positives ({rep.positives})"
        return None, rep
    if rep.negatives < int(ocfg.get("min_negative_pairs", 300)):
        rep.fallback_reason = f"insufficient negatives ({rep.negatives})"
        return None, rep
    fit_kw = dict(levels=levels, l2=float(ocfg.get("l2", 1e-3)), lr=float(ocfg.get("lr", 0.05)), epochs=int(ocfg.get("epochs", 300)), seed=int(ocfg.get("sample_seed", 0)))
    margin = float(ocfg.get("confidence_margin", 1.0))
    labelled = y >= 0
    model = None
    for r in range(int(ocfg.get("self_train_rounds", 3)) + 1):
        model = fit_ordinal(F[labelled], y[labelled], **fit_kw)
        if not np.isfinite(model.meta["loss_last"]) or model.meta["loss_last"] > model.meta["loss_first"] * 1.5:
            rep.fallback_reason = "training diverged"
            return None, rep
        un = ~labelled
        if not un.any():
            rep.rounds.append({"round": r, "train": int(labelled.sum()), "added_pos": 0, "added_neg": 0})
            break
        z = model.z(F[un])
        t1, t2 = model.thresholds[0], model.thresholds[-1]
        conf_pos = z > t2 + margin
        conf_neg = z < t1 - margin
        idx = np.flatnonzero(un)
        y[idx[conf_pos]] = 2
        y[idx[conf_neg]] = 0
        labelled = y >= 0
        rep.rounds.append({"round": r, "train": int(labelled.sum()), "added_pos": int(conf_pos.sum()), "added_neg": int(conf_neg.sum()),
                           "loss": model.meta["loss_last"], "thresholds": [round(float(t), 3) for t in model.thresholds]})
        if not conf_pos.any() and not conf_neg.any():
            break
    # final: remaining unlabeled candidates become the middle band (weak/moderate), then one more fit
    if levels >= 3 and (~labelled).any():
        y[~labelled] = 1
        model = fit_ordinal(F, y, **fit_kw)
    rep.model_meta = model.meta
    return model, rep


def sample_training_pairs(con, cfg, context: dict, rec_table: str = "_rec") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Candidate-pair sample (with features) and random non-candidate pairs (negatives) from the run's tables."""
    ocfg = cfg.matcher.get("ordinal", {}) or {}
    n_cand = int(ocfg.get("max_train_pairs", 40000))
    seed = int(ocfg.get("sample_seed", 0))
    neg_ratio = float(ocfg.get("negatives_per_positive", 2.0))
    lcols = ", ".join(f"a.{c} AS l_{c}" for c in SIDE_COLUMNS)
    rcols = ", ".join(f"b.{c} AS r_{c}" for c in SIDE_COLUMNS)
    cand = con.execute(
        f"SELECT {lcols}, {rcols} FROM (SELECT l, r FROM _pairs USING SAMPLE reservoir({n_cand} ROWS) REPEATABLE ({seed})) p "
        f"JOIN {rec_table} a ON a.idx = p.l JOIN {rec_table} b ON b.idx = p.r"
    ).df()
    n_neg = int(max(1000, neg_ratio * len(cand) / 4))
    neg = con.execute(
        f"""
        WITH a AS (SELECT * FROM {rec_table} USING SAMPLE reservoir({n_neg} ROWS) REPEATABLE ({seed + 1})),
             b AS (SELECT * FROM {rec_table} USING SAMPLE reservoir({n_neg} ROWS) REPEATABLE ({seed + 2}))
        SELECT {lcols}, {rcols} FROM (SELECT a.*, ROW_NUMBER() OVER () AS rn FROM a) a
        JOIN (SELECT b.*, ROW_NUMBER() OVER () AS rn FROM b) b USING (rn)
        WHERE a.idx <> b.idx AND NOT EXISTS (SELECT 1 FROM _pairs p WHERE (p.l = LEAST(a.idx, b.idx) AND p.r = GREATEST(a.idx, b.idx)))
        """
    ).df()

    def split(df):
        left = df[[f"l_{c}" for c in SIDE_COLUMNS]].rename(columns=lambda c: c[2:])
        right = df[[f"r_{c}" for c in SIDE_COLUMNS]].rename(columns=lambda c: c[2:])
        return all_features(left, right, cfg.matcher, context)

    return split(cand), split(neg)


def train_from_candidates(con, cfg, context: dict) -> tuple[OrdinalModel | None, TrainingReport]:
    F_cand, F_neg = sample_training_pairs(con, cfg, context)
    return self_train(F_cand, F_neg, cfg.matcher, cfg.matcher.get("ordinal", {}) or {})


# ----------------------------------------------------------------------------------------- scorer objects
class RulesScorer:
    """Baseline: hand-set logistic weights + deterministic rules (matcher.score_frame)."""

    name = "rules"

    def __init__(self, matcher_cfg):
        self.cfg = matcher_cfg

    def score_pairs(self, left: pd.DataFrame, right: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        F = features_frame(left, right, self.cfg)
        return F, score_frame(F, self.cfg)


class OrdinalScorer:
    name = "ordinal"

    def __init__(self, matcher_cfg, model: OrdinalModel, context: dict):
        self.cfg = matcher_cfg
        self.model = model
        self.context = context

    def score_pairs(self, left: pd.DataFrame, right: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        F = all_features(left, right, self.cfg, self.context)
        return F, score_frame_ordinal(F, self.model, self.cfg)


def prepare_scorer(con, cfg, run_id: str, workspace: Path | None = None) -> tuple[object, dict]:
    """Build the scorer selected by ``matcher.scorer``; never raises on insufficient training data.

    Returns ``(scorer, info)`` where ``info`` carries ``scorer_requested``, ``scorer_used``,
    ``scorer_fallback_reason`` (and, for ordinal, the training report / model file). Requires ``_rec`` and
    ``_pairs`` to exist (called after blocking)."""
    mcfg = cfg.matcher
    requested = str(mcfg.get("scorer", "rules"))
    info = {"scorer_requested": requested, "scorer_used": "rules", "scorer_fallback_reason": None}
    if requested == "rules":
        return RulesScorer(mcfg), info
    if requested != "ordinal":
        info["scorer_fallback_reason"] = f"unknown matcher.scorer {requested!r}"
        return RulesScorer(mcfg), info
    ocfg = dict(mcfg.get("ordinal") or {})
    retrain = str(ocfg.get("retrain", "auto"))
    model_file = ocfg.get("model_file")
    context = corpus_context(con)
    model = None
    if model_file and Path(model_file).exists() and retrain != "always":
        try:
            model = OrdinalModel.load(model_file)
            info["ordinal_model_file"] = str(model_file)
            info["ordinal_model_source"] = "file"
        except Exception as exc:  # noqa: BLE001 - a corrupt file must not kill the run
            info["scorer_fallback_reason"] = f"could not load model_file {model_file!r}: {exc}"
            return RulesScorer(mcfg), info
    if model is None:
        if retrain == "never":
            info["scorer_fallback_reason"] = f"retrain=never and no usable model_file ({model_file!r})"
            return RulesScorer(mcfg), info
        model, rep = train_from_candidates(con, cfg, context)
        info["ordinal_training"] = rep.as_metrics()
        if model is None:
            info["scorer_fallback_reason"] = rep.fallback_reason
            return RulesScorer(mcfg), info
        info["ordinal_model_source"] = "trained"
        if bool(ocfg.get("save_model", True)):
            target = Path(model_file) if model_file else Path(workspace or ".") / "models" / f"ordinal-{run_id}.json"
            try:
                model.save(target)
                info["ordinal_model_file"] = str(target)
            except OSError as exc:
                info["ordinal_model_save_error"] = str(exc)
    info["scorer_used"] = "ordinal"
    info["ordinal_thresholds"] = [round(float(t), 4) for t in model.thresholds]
    return OrdinalScorer(mcfg, model, context), info
