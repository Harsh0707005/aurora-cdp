"""The vectorised feature/score path must agree with the per-pair reference implementation."""

from __future__ import annotations

import random

import numpy as np
import pandas as pd

from aurora_cdp.config import load_config
from aurora_cdp.stitch.features import FEATURE_NAMES, compute_features, features_frame
from aurora_cdp.stitch.matcher import score_features, score_frame

CFG = load_config(use_last_best=False).matcher


def _records(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    names = ["michael", "mike", "michelle", "robert", "bob", "sara", "tomas", None]
    sur = ["chen", "chan", "patel", "novak", "rossi", None]
    emails = ["a@x.org", "a@x.orh", "b@x.org", None]
    phones = ["2065550101", "2065550102", None]
    addrs = ["12 main street", "12 main st", "13 main street", None]
    posts = ["98101", "98102", None]
    dobs = ["1980-05-01", "1980-05-10", "1992-09-09", None]
    cks = ["c1", "c2", None]
    loys = ["L1", "L2", None]
    fks = ['{"pos":"1"}', '{"pos":"2"}', '{"web":"1"}', None]
    return [
        {"given_name_canon": rng.choice(names), "given_name_norm": rng.choice(names), "surname_norm": rng.choice(sur),
         "email_norm": rng.choice(emails), "phone_match": rng.choice(phones), "address_norm": rng.choice(addrs),
         "postal_norm": rng.choice(posts), "birthdate_norm": rng.choice(dobs), "ck": rng.choice(cks),
         "loy_id_norm": rng.choice(loys), "fk_json": rng.choice(fks)}
        for _ in range(n)
    ]


def test_vectorised_matches_reference():
    L, R = _records(1500, 1), _records(1500, 2)
    for i in range(0, len(L), 10):
        R[i] = dict(L[i])  # trivial dupes
    F = features_frame(pd.DataFrame(L), pd.DataFrame(R), CFG)
    S = score_frame(F, CFG)
    seen = set()
    for i, (a, b) in enumerate(zip(L, R, strict=True)):
        f = compute_features(a, b, CFG)
        ps = score_features(f, CFG)
        for k in FEATURE_NAMES:
            ref, got = f[k], F.iloc[i][k]
            assert (ref is None) == bool(np.isnan(got)), (i, k, ref, got)
            if ref is not None:
                assert abs(ref - got) < 1e-9, (i, k, ref, got)
        row = S.iloc[i]
        assert abs(ps.score - row["score"]) <= 1e-3, (i, ps, row.to_dict())
        assert ps.category == row["match_category"] and ps.match_type == row["match_type"], (i, ps, row.to_dict())
        assert ps.hard_conflict == bool(row["hard_conflict"])
        seen.add(ps.category)
    assert {"exact", "hard_conflict", "non_conflict", "high"} <= seen  # the sample exercises every rule path


def test_scores_are_chunk_invariant():
    L, R = _records(600, 3), _records(600, 4)
    whole = score_frame(features_frame(pd.DataFrame(L), pd.DataFrame(R), CFG), CFG)
    parts = [score_frame(features_frame(pd.DataFrame(L[i:i + 100]), pd.DataFrame(R[i:i + 100]), CFG), CFG) for i in range(0, 600, 100)]
    pd.testing.assert_frame_equal(whole.reset_index(drop=True), pd.concat(parts, ignore_index=True))
