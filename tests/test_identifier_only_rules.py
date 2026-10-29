"""Exact identifier with no name evidence on one side: POS receipt-e-mail records must link to the account that owns the e-mail."""

from __future__ import annotations

import pandas as pd

from aurora_cdp.config import load_config
from aurora_cdp.stitch.features import compute_features, features_frame
from aurora_cdp.stitch.matcher import score_features, score_frame

CFG = load_config(use_last_best=False).matcher
WEB = {"given_name_canon": "daniel", "given_name_norm": "daniel", "surname_norm": "smith", "email_norm": "daniel.smith@gmail.com",
       "phone_match": "9725550101", "address_norm": "9726 RIDGE WAY", "postal_norm": "46250"}
POS_EMAIL = {"email_norm": "daniel.smith@gmail.com"}
POS_PHONE = {"phone_match": "9725550101"}
POS_EMAIL_OTHER_NAME = {"given_name_canon": "maria", "given_name_norm": "maria", "surname_norm": "lopez", "email_norm": "daniel.smith@gmail.com"}


def _score(a, b, cfg=CFG):
    return score_features(compute_features(a, b, cfg), cfg)


def test_email_only_record_links_with_the_default_rule():
    s = _score(WEB, POS_EMAIL)
    assert s.match_type == "deterministic" and s.score == 4.0 and s.score >= CFG["match_threshold"]


def test_phone_only_record_does_not_link_by_default():
    s = _score(WEB, POS_PHONE)
    assert s.match_type == "scored" and s.score < CFG["match_threshold"]


def test_phone_only_rule_can_be_enabled():
    cfg = {**CFG, "deterministic": {**CFG["deterministic"], "phone_exact_no_name_score": 3.5}}
    s = _score(WEB, POS_PHONE, cfg)
    assert s.match_type == "deterministic" and s.score == 3.5


def test_rule_does_not_fire_when_both_sides_carry_names():
    # a shared e-mail with two different names is left to the probabilistic model (and the blocklist), not forced
    s = _score(WEB, POS_EMAIL_OTHER_NAME)
    assert s.match_type == "scored"


def test_vectorised_path_agrees():
    L = pd.DataFrame([WEB, WEB, WEB]); R = pd.DataFrame([POS_EMAIL, POS_PHONE, POS_EMAIL_OTHER_NAME])
    S = score_frame(features_frame(L, R, CFG), CFG)
    assert S["match_type"].tolist() == ["deterministic", "scored", "scored"]
    assert S["score"].tolist()[0] == 4.0
