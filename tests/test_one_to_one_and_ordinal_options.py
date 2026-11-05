"""One-to-one (ck) mode, 5-level ordinal models, the Γ cost matrix and client-key labelling."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aurora_cdp.adapters import resolve_records
from aurora_cdp.config import load_config
from aurora_cdp.stitch.ordinal import ALL_FEATURE_NAMES, fit_ordinal, label_values, parse_cost_matrix, weak_labels

CFG = load_config(use_last_best=False)


def _recs():
    return pd.DataFrame([
        {"source_record_id": "a", "datasource": "crm", "given_name": "Amy", "surname": "Chen", "email": "amy@x.org", "ck": "C1"},
        {"source_record_id": "b", "datasource": "web", "given_name": "Amy", "surname": "Chen", "email": "amy@x.org", "ck": "C2"},
        {"source_record_id": "c", "datasource": "pos", "given_name": "A", "surname": "Chen", "email": "other@x.org", "ck": "C1"},
    ])


def _ids(res):
    return {r.pk: r.unified_id for r in res.assignments.itertuples()}


def test_default_mode_merges_on_email_and_name_despite_different_ck():
    ids = _ids(resolve_records(_recs()))
    assert ids["a"] == ids["b"] == ids["c"]


def test_one_to_one_keeps_customer_keys_apart_and_together():
    ids = _ids(resolve_records(_recs(), config={"matcher": {"one_to_one": True}}))
    assert ids["a"] == ids["c"]  # same ck -> same id (ck_exact rule)
    assert ids["a"] != ids["b"]  # different ck -> never merged, even with e-mail + name agreeing


def test_label_values_and_client_key_negatives():
    assert label_values(3) == (2, 0, 0) and label_values(5) == (4, 1, 0)
    F = pd.DataFrame([{f: np.nan for f in ALL_FEATURE_NAMES} for _ in range(3)])
    F.loc[0, ["given_sim", "surname_sim", "name_both_present", "email_exact"]] = [1.0, 1.0, 1.0, 1.0]   # rule positive
    F.loc[1, ["given_sim", "surname_sim", "name_both_present", "ck_exact"]] = [1.0, 1.0, 1.0, 0.0]      # authoritative key disagrees
    F.loc[2, ["given_sim", "surname_sim", "name_both_present"]] = [1.0, 1.0, 1.0]                      # nothing decisive
    F[["birthdate_conflict", "trivial_dupe"]] = 0.0
    cfg3 = {**CFG.matcher, "ordinal": {**CFG.matcher["ordinal"], "levels": 3}}
    assert weak_labels(F, cfg3).tolist() == [2, 0, -1]
    cfg5 = {**CFG.matcher, "ordinal": {**CFG.matcher["ordinal"], "levels": 5}}
    assert weak_labels(F, cfg5).tolist() == [4, 1, -1]


def _toy(n=600, seed=3):
    rng = np.random.default_rng(seed)
    F = pd.DataFrame({f: np.nan for f in ALL_FEATURE_NAMES}, index=range(n))
    z = rng.normal(size=n)
    F["given_sim"] = np.clip(0.5 + 0.2 * z + rng.normal(0, 0.05, n), 0, 1)
    F["email_sim"] = np.clip(0.5 + 0.25 * z + rng.normal(0, 0.05, n), 0, 1)
    y = np.digitize(z, [-1.0, -0.3, 0.3, 1.0])  # 5 ordered labels
    return F, y


def test_five_level_fit_orders_thresholds_and_maps_to_the_documented_scale():
    F, y = _toy()
    m = fit_ordinal(F, y, levels=5, epochs=200, feature_names=["given_sim", "email_sim"])
    assert len(m.thresholds) == 4 and np.all(np.diff(m.thresholds) > 0)
    z = np.linspace(m.thresholds[0] - 3, m.thresholds[-1] + 3, 200)
    s = m.score(z)
    assert np.all(np.diff(s) >= -1e-9) and s.min() >= 0.0 and s.max() <= 5.0
    for k in range(4):  # each learned threshold anchors the floor of band k+1 (1 weak, 2 moderate, 3 high, 4 excellent)
        assert abs(float(m.score(np.array([float(m.thresholds[k])]))[0]) - (k + 1)) < 1e-6


def test_cost_matrix_changes_the_fit_and_is_recorded():
    F, y = _toy()
    base = fit_ordinal(F, y, levels=5, epochs=150, feature_names=["given_sim", "email_sim"])
    gam = fit_ordinal(F, y, levels=5, epochs=150, feature_names=["given_sim", "email_sim"], cost_matrix={"3,4": 5.0})
    assert gam.meta["cost_matrix"] == {"3,4": 5.0}
    assert not np.allclose(base.thresholds, gam.thresholds)
    # penalising "predict 3 when the truth is 4" pushes the top threshold down relative to the rest: more pairs reach level 4
    assert (gam.thresholds[-1] - gam.thresholds[-2]) < (base.thresholds[-1] - base.thresholds[-2])
    G = parse_cost_matrix({(1, 2): 2.0, "0,4": 3.0}, 5)
    assert G[1, 2] == 2.0 and G[0, 4] == 3.0 and G[2, 2] == 1.0
