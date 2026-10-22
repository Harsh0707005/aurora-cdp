"""Pairwise precision / recall / false-merge metrics against labelled truth (used by `aurora tune`).

This is deliberately small: the organisation's scoring harness lives in a separate repo and consumes the
assignment export described in docs/adapter-contract.md. These helpers exist only so the tuner can pick
a default threshold.
"""

from __future__ import annotations

from math import comb

import pandas as pd


def _pairs(counts: pd.Series) -> int:
    return int(sum(comb(int(n), 2) for n in counts))


def pairwise_metrics(assignment: pd.DataFrame, labels: pd.DataFrame) -> dict:
    """assignment: (datasource, pk, aurora_id); labels: (datasource, pk, truth_id)."""
    df = assignment.merge(labels, on=["datasource", "pk"], how="inner")
    if df.empty:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "false_merge_rate": 0.0, "labelled_records": 0}
    pred_pairs = _pairs(df.groupby("aurora_id").size())
    true_pairs = _pairs(df.groupby("truth_id").size())
    tp = _pairs(df.groupby(["aurora_id", "truth_id"]).size())
    precision = tp / pred_pairs if pred_pairs else 1.0
    recall = tp / true_pairs if true_pairs else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    sizes = df.groupby("aurora_id").agg(n=("pk", "size"), truths=("truth_id", "nunique"))
    multi = sizes[sizes["n"] > 1]
    false_merge = float((multi["truths"] > 1).mean()) if len(multi) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_merge_rate": round(false_merge, 4),  # share of multi-record clusters mixing >1 true person
        "labelled_records": int(len(df)),
        "clusters": int(df["aurora_id"].nunique()),
        "true_entities": int(df["truth_id"].nunique()),
    }
