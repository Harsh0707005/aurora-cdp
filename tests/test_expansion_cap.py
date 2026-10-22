"""Trivial-dupe expansion: full expansion below the cap, truncated (member->representative only) above it,
always reported in metrics and never silent."""

from __future__ import annotations

import pandas as pd

from aurora_cdp.adapters import resolve_records


def _flood(copies: int) -> pd.DataFrame:
    rows = []
    for p in range(3):
        for i in range(copies):
            rows.append({"source_record_id": f"{p}-{i}", "given_name": f"Person{p}", "surname": "Flood", "email": f"p{p}@example.org", "postal": "11111"})
    return pd.DataFrame(rows)


def test_expansion_full_and_truncated():
    df = _flood(30)
    full = resolve_records(df, config={"matcher": {"max_expanded_pairs": 10_000}}, datasource="s")
    assert full.metrics["pairs_expansion_truncated"] is False
    assert full.metrics["pairs_scored"] >= 3 * (30 * 29 // 2)  # every within-group pair is exported
    assert full.metrics["clusters"] == 3 and full.metrics["records_dropped_by_blocking"] == 0
    cut = resolve_records(df, config={"matcher": {"max_expanded_pairs": 100}}, datasource="s")
    assert cut.metrics["pairs_expansion_truncated"] is True
    assert cut.metrics["pairs_scored"] < full.metrics["pairs_scored"]
    assert cut.metrics["clusters"] == 3  # clustering is unaffected: member->representative links carry the groups
    assert cut.assignments["unified_id"].nunique() == 3
    assert cut.metrics["pairs_expanded_total"] == full.metrics["pairs_expanded_total"]
