"""Ordinal-regression style match scoring.

Two modes, selected by ``scoring.mode`` in the tenant config:

* ``config`` — raw score ``z = b + w·x`` with hand-set weights; ordered
  thresholds ``θ1<…<θ5`` map ``z`` into categories 0..5. This is the default
  and is fully transparent/tunable from YAML.
* ``learned`` — a logistic model fitted on labelled pairs produces a decision
  value which is then quantised into 0..5 with calibrated bins
  (``fit_learned`` / ``LearnedScorer``).

Both modes honour *deterministic keys* (features that short-circuit to the
``exact`` category) and *hard conflicts* (features that cap the category so a
strong-looking pair is refused when, e.g., birthdates disagree).

The continuous ``score`` in [0, 5] is category + the fractional position of
``z`` inside the category's threshold interval, so scores are comparable
across the whole range (4.58 is stronger than 4.55).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from aurora.config.schema import ScoringConfig
from aurora.data.schemas import MATCH_CATEGORIES, PAIR_FEATURE_COLUMNS

HARD_CONFLICT_CAP = 2  # a hard conflict can never yield a mergeable category


def _quantise(z: np.ndarray, thresholds: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """Map raw scores to (category, continuous score) using ordered thresholds."""
    th = np.asarray(thresholds, dtype=float)
    cat = np.searchsorted(th, z, side="right")  # number of thresholds <= z  -> 0..5
    lower = np.concatenate([[th[0] - (th[1] - th[0])], th])  # synthetic lower bound for cat 0
    upper = np.concatenate([th, [th[-1] + (th[-1] - th[-2])]])
    lo, hi = lower[cat], upper[cat]
    frac = np.clip((z - lo) / np.where(hi - lo == 0, 1, hi - lo), 0.0, 0.999)
    score = np.where(cat >= 5, 5.0, cat + frac)
    return cat.astype(int), score.astype(float)


@dataclass
class ConfigScorer:
    cfg: ScoringConfig
    columns: list[str] = field(default_factory=lambda: list(PAIR_FEATURE_COLUMNS))

    def raw(self, X: pd.DataFrame) -> np.ndarray:
        w = np.array([self.cfg.weights.get(c, 0.0) for c in self.columns], dtype=float)
        return self.cfg.bias + X[self.columns].to_numpy(dtype=float) @ w

    def score(self, X: pd.DataFrame) -> pd.DataFrame:
        z = self.raw(X)
        cat, score = _quantise(z, self.cfg.thresholds)
        return apply_rules(X, z, cat, score, self.cfg)


@dataclass
class LearnedScorer:
    """Logistic model + calibrated bins. Falls back to config thresholds for bins."""

    cfg: ScoringConfig
    model: object
    bins: list[float]
    columns: list[str] = field(default_factory=lambda: list(PAIR_FEATURE_COLUMNS))

    def raw(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.model.decision_function(X[self.columns].to_numpy(dtype=float)))

    def score(self, X: pd.DataFrame) -> pd.DataFrame:
        z = self.raw(X)
        cat, score = _quantise(z, self.bins)
        return apply_rules(X, z, cat, score, self.cfg)

    def save(self, path: str | Path) -> None:
        import joblib

        joblib.dump({"model": self.model, "bins": self.bins, "columns": self.columns}, path)

    @classmethod
    def load(cls, cfg: ScoringConfig, path: str | Path) -> LearnedScorer:
        import joblib

        d = joblib.load(path)
        return cls(cfg=cfg, model=d["model"], bins=d["bins"], columns=d["columns"])


def apply_rules(
    X: pd.DataFrame, z: np.ndarray, cat: np.ndarray, score: np.ndarray, cfg: ScoringConfig
) -> pd.DataFrame:
    """Deterministic short-circuits and hard-conflict caps on top of the scorer."""
    cat = cat.copy()
    score = score.copy()
    conflict = np.zeros(len(X), dtype=bool)
    for col, on in cfg.hard_conflicts.items():
        if on and col in X:
            conflict |= X[col].to_numpy(dtype=float) >= 1.0
    deterministic = np.zeros(len(X), dtype=bool)
    for col in cfg.deterministic_keys:
        if col in X:
            deterministic |= X[col].to_numpy(dtype=float) >= 1.0
    deterministic &= ~conflict
    cat[deterministic] = 5
    score[deterministic] = 5.0
    capped = conflict & (cat > HARD_CONFLICT_CAP)
    cat[capped] = HARD_CONFLICT_CAP
    score[capped] = np.minimum(score[capped], HARD_CONFLICT_CAP + 0.999)
    match_type = np.where(deterministic, "deterministic", np.where(conflict, "hard_conflict", "scored"))
    return pd.DataFrame(
        {
            "raw_score": z,
            "category": cat,
            "score": np.round(score, 3),
            "match_category": [MATCH_CATEGORIES[int(c)] for c in cat],
            "match_type": match_type,
        }
    )


def build_scorer(cfg: ScoringConfig) -> ConfigScorer | LearnedScorer:
    if cfg.mode == "learned" and cfg.model_path and Path(cfg.model_path).exists():
        return LearnedScorer.load(cfg, cfg.model_path)
    return ConfigScorer(cfg)


# --------------------------------------------------------------------------- tuning


def pair_metrics(pred_match: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    tp = float(np.sum(pred_match & truth))
    fp = float(np.sum(pred_match & ~truth))
    fn = float(np.sum(~pred_match & truth))
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def tune_thresholds(
    X: pd.DataFrame,
    y: np.ndarray,
    cfg: ScoringConfig,
    grid: np.ndarray | None = None,
    weight_scales: tuple[float, ...] = (0.8, 1.0, 1.2),
    scale_features: tuple[str, ...] = ("email_sim", "given_jw", "surname_jw", "dob_eq"),
) -> dict:
    """Grid-search the edge-keep threshold (and a few weight scalings) on labelled pairs.

    Returns the best config fragment and its pair metrics. The other four
    thresholds are repositioned proportionally around the chosen keep threshold.
    """
    y = np.asarray(y, dtype=bool)
    base = ConfigScorer(cfg)
    grid = np.arange(1.0, 6.01, 0.25) if grid is None else grid
    best: dict = {"f1": -1.0}
    for scales in itertools.product(weight_scales, repeat=len(scale_features)):
        w = dict(cfg.weights)
        for feat, s in zip(scale_features, scales, strict=True):
            if feat in w:
                w[feat] = w[feat] * s
        scorer = ConfigScorer(cfg.model_copy(update={"weights": w}), base.columns)
        z = scorer.raw(X)
        for t in grid:
            m = pair_metrics(z >= t, y)
            if m["f1"] > best["f1"]:
                best = {**m, "keep_threshold": float(t), "weights": w}
    t = best["keep_threshold"]
    best["thresholds"] = [round(t - 2.0, 3), round(t - 1.0, 3), round(t, 3), round(t + 1.0, 3), round(t + 2.0, 3)]
    return best


def fit_learned(X: pd.DataFrame, y: np.ndarray, cfg: ScoringConfig) -> LearnedScorer:
    """Fit a logistic model; derive 0..5 bins from decision values of positives/negatives."""
    from sklearn.linear_model import LogisticRegression

    cols = list(PAIR_FEATURE_COLUMNS)
    model = LogisticRegression(max_iter=1000, C=1.0)
    model.fit(X[cols].to_numpy(dtype=float), np.asarray(y, dtype=int))
    z = model.decision_function(X[cols].to_numpy(dtype=float))
    y = np.asarray(y, dtype=bool)
    # keep threshold: best F1 cut; other bins at quantiles of each class.
    cands = np.quantile(z, np.linspace(0.05, 0.95, 37))
    keep = max(cands, key=lambda t: pair_metrics(z >= t, y)["f1"])
    neg, pos = z[~y], z[y]
    b1 = float(np.quantile(neg, 0.5)) if len(neg) else keep - 2
    b2 = float(np.quantile(neg, 0.9)) if len(neg) else keep - 1
    b4 = float(np.quantile(pos, 0.5)) if len(pos) else keep + 1
    b5 = float(np.quantile(pos, 0.9)) if len(pos) else keep + 2
    bins = sorted({b1, b2, float(keep), b4, b5})
    while len(bins) < 5:  # degenerate data: pad monotonically
        bins.append(bins[-1] + 0.5)
    return LearnedScorer(cfg=cfg, model=model, bins=bins[:5], columns=cols)
