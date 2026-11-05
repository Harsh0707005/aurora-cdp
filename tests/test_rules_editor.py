"""matcher.rules: an ordered, user-authored deterministic rule list (Amperity Rules Editor), first match wins."""

from __future__ import annotations

import pandas as pd
import pytest

from aurora_cdp.config import load_config
from aurora_cdp.stitch.features import compute_features, features_frame
from aurora_cdp.stitch.matcher import compile_rules, default_rules, score_features, score_frame

CFG = load_config(use_last_best=False).matcher
A = {"given_name_canon": "amy", "given_name_norm": "amy", "surname_norm": "chen", "email_norm": "amy@x.org", "phone_match": "2065550101", "postal_norm": "98101"}
B = {"given_name_canon": "amy", "given_name_norm": "amy", "surname_norm": "chen", "email_norm": "amy@x.org", "phone_match": "2065550101", "postal_norm": "98101"}
C = {"given_name_canon": "bob", "given_name_norm": "bob", "surname_norm": "lee", "email_norm": "amy@x.org", "phone_match": "2065550101", "postal_norm": "98101"}


def test_default_list_reproduces_the_built_in_order():
    names = [r["name"] for r in compile_rules(CFG)]
    assert names == ["ck_exact", "loy_exact", "email_with_name", "phone_with_name", "email_no_name"]
    assert [r["name"] for r in default_rules({})] == names[:-1]  # no identifier-only rule without its score


def test_authored_rules_replace_the_list_and_fire_in_order():
    cfg = {**CFG, "rules": [
        {"name": "phone_zip_name", "when": {"phone_exact": 1, "postal_exact": 1, "names_agree": True}, "score": 4.2},
        {"name": "email_any", "when": {"email_exact": 1}, "score": 3.9, "category": "high"},
    ]}
    f_ab = compute_features(A, B, cfg)
    f_ab["trivial_dupe"] = 0.0  # look at the rules, not the dupe shortcut
    s = score_features(f_ab, cfg)
    assert (s.match_type, s.score) == ("deterministic", 4.2)
    s2 = score_features(compute_features(A, C, cfg), cfg)  # names disagree -> second rule
    assert (s2.match_type, s2.score, s2.category) == ("deterministic", 3.9, "high")


def test_operators_and_presence():
    cfg = {**CFG, "rules": [{"name": "near_email", "when": {"email_sim": {"gte": 0.9}, "surname_sim": {"present": True}}, "score": 4.4}]}
    f = compute_features({"surname_norm": "chen", "email_norm": "amy.chen@x.org"}, {"surname_norm": "chen", "email_norm": "amy.chem@x.org"}, cfg)
    assert score_features(f, cfg).score == 4.4
    f2 = compute_features({"email_norm": "amy.chen@x.org"}, {"email_norm": "amy.chem@x.org"}, cfg)  # surname missing -> no fire
    assert score_features(f2, cfg).match_type == "scored"


def test_vectorised_agrees_with_reference_on_authored_rules():
    cfg = {**CFG, "rules": [
        {"name": "phone_zip_name", "when": {"phone_exact": 1, "postal_exact": 1, "names_agree": True}, "score": 4.2},
        {"name": "email_any", "when": {"email_exact": 1}, "score": 3.9, "category": "high"},
    ]}
    L, R = pd.DataFrame([A, A, {"email_norm": "amy@x.org"}]), pd.DataFrame([B, C, {"email_norm": "z@x.org"}])
    F = features_frame(L, R, cfg)
    F["trivial_dupe"] = 0.0
    S = score_frame(F, cfg)
    ref = [score_features({k: (None if pd.isna(v) else v) for k, v in row.items()}, cfg) for row in F.to_dict("records")]
    assert S["score"].tolist() == [r.score for r in ref]
    assert S["match_type"].tolist() == [r.match_type for r in ref]
    assert S["match_category"].tolist() == [r.category for r in ref]


def test_invalid_rules_are_rejected_loudly():
    with pytest.raises(ValueError):
        compile_rules({**CFG, "rules": [{"name": "x", "when": {"no_such_feature": 1}, "score": 4.0}]})
    with pytest.raises(ValueError):
        compile_rules({**CFG, "rules": [{"name": "x", "when": {"email_exact": {"between": 1}}, "score": 4.0}]})
    with pytest.raises(ValueError):
        compile_rules({**CFG, "rules": [{"name": "x", "when": {"email_exact": 1}, "score": 7.0}]})
