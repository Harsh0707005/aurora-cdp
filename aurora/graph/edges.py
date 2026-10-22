"""Edge selection: scored pairs -> graph edges above the keep threshold."""

from __future__ import annotations

import pandas as pd

from aurora.config.schema import ScoringConfig


def keep_edges(scored: pd.DataFrame, cfg: ScoringConfig) -> pd.DataFrame:
    """Return rows whose ``score`` >= ``edge_keep_threshold`` and are mergeable.

    Hard-conflict pairs are never kept regardless of score.
    """
    mask = (scored["score"] >= cfg.edge_keep_threshold) & (scored["match_type"] != "hard_conflict")
    return scored.loc[mask, ["rid_l", "rid_r", "score", "category", "match_type"]].reset_index(drop=True)
