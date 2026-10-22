"""Learned DNF blocking: predicates, greedy cover, graceful fallback, and the dnf strategy type in blocking."""

from __future__ import annotations

import random

import numpy as np
import pandas as pd
import yaml

from aurora_cdp.config import load_config
from aurora_cdp.stitch.blocking import build_blocks
from aurora_cdp.stitch.dnf import (
    conjunction_key, derive_columns, evaluate_strategies, learn_dnf, self_label_positives, soundex, truth_positives,
)

CFG = load_config(use_last_best=False)


def _corpus(persons: int = 300, copies: int = 4, seed: int = 3) -> tuple[pd.DataFrame, np.ndarray]:
    """Synthetic people whose copies share a surname prefix + postal or an e-mail local part, with noise."""
    rng = random.Random(seed)
    given = ["michael", "sarah", "robert", "linda", "david", "susan", "james", "karen", "daniel", "nancy"]
    sur = ["chen", "patel", "novak", "rossi", "garcia", "miller", "okafor", "lee", "weber", "silva"]
    rows, truth = [], []
    for p in range(persons):
        g, s = rng.choice(given), rng.choice(sur) + str(p)
        postal = f"{rng.randrange(90000, 99999)}"
        email = f"{g[0]}{s}@example.org"
        for c in range(copies):
            r = {"datasource": "s", "pk": f"{p}-{c}", "given_name_canon": g if rng.random() > 0.2 else g[:1] + "." , "surname_norm": s if rng.random() > 0.15 else s[:-1] + "x",
                 "email_norm": email if rng.random() > 0.3 else None, "phone_match": None, "postal_norm": postal if rng.random() > 0.3 else None,
                 "birthdate_norm": None, "address_norm": None, "loy_id_norm": None, "ck": None}
            rows.append(r)
            truth.append(f"p{p}")
    return derive_columns(pd.DataFrame(rows)), np.array(truth, dtype=object)


def test_soundex_and_keys():
    assert soundex("Robert") == soundex("Rupert") == "R163" and soundex("Tymczak") == "T522" and soundex("") is None
    terms = [{"attr": "surname_norm", "transform": "prefix3"}, {"attr": "postal_norm", "transform": "exact"}]
    assert conjunction_key({"surname_norm": "hunter", "postal_norm": "98101"}, terms) == "hun:98101"
    assert conjunction_key({"surname_norm": "hunter"}, terms) is None


def test_learner_covers_positives_within_budget():
    df, truth = _corpus()
    rng = np.random.default_rng(0)
    pos = truth_positives(truth, 5000, rng)
    res = learn_dnf(df, pos, {**CFG.blocking["dnf"], "target_pc": 0.9, "pairs_per_record_budget": 20})
    assert res.fallback_reason is None, res.fallback_reason
    assert res.pc >= 0.9 and res.cost <= res.budget
    assert res.strategies and all(s["type"] == "dnf" for s in res.strategies)
    attrs = {t["attr"] for s in res.strategies for t in s["terms"]}
    assert attrs & {"surname_norm", "email_local", "email_norm", "postal_norm", "given_name_canon"}
    assert all(p.pc <= 1.0 for p in res.predicates) and any(p.pruned for p in res.predicates)
    # learned-vs-fixed comparison on the same sample
    fixed = evaluate_strategies(df, pos, CFG.blocking["strategies"])
    learned = evaluate_strategies(df, pos, res.strategies)
    assert learned["pc"] >= res.pc - 1e-6 and learned["pc"] > fixed["pc"] - 1e-6


def test_fallback_when_too_few_positives():
    df, truth = _corpus(persons=20)
    pos = truth_positives(truth, 5000, np.random.default_rng(0))
    res = learn_dnf(df, pos, {**CFG.blocking["dnf"], "min_positive_pairs": 10_000})
    assert res.strategies == [] and res.fallback_reason.startswith("insufficient positives")
    assert res.as_metrics()["dnf_fallback_reason"]


def test_self_labelling_finds_deterministic_positives():
    df, truth = _corpus()
    pos = self_label_positives(df, CFG.matcher, 5000, np.random.default_rng(0))
    assert len(pos) > 50
    assert all(truth[a] == truth[b] for a, b in pos)  # rules-only positives are clean on this fixture


def test_dnf_strategy_runs_through_zero_discard_blocking(tmp_path):
    df, truth = _corpus(persons=60)
    pos = truth_positives(truth, 5000, np.random.default_rng(0))
    res = learn_dnf(df, pos, {**CFG.blocking["dnf"], "target_pc": 0.8})
    overlay = {"strategies": res.strategies}
    (tmp_path / "learned.yaml").write_text(yaml.safe_dump(overlay))
    records = {f"{r['datasource']}|{r['pk']}": r for r in df.drop(columns=["email_local", "house_no", "given_sdx", "surname_sdx"]).astype(object).where(df.notna(), None).to_dict("records")}
    cfg = {**CFG.blocking, "strategies": res.strategies, "block_size_limit": 5, "max_pairs_per_block": 50}
    out = build_blocks(records, cfg)
    assert out.pair_count > 0 and out.skipped == [] and out.stats.records_dropped_by_blocking == 0
    covered = sum(1 for a, b in pos if (min(f"s|{df.pk[a]}", f"s|{df.pk[b]}"), max(f"s|{df.pk[a]}", f"s|{df.pk[b]}")) in out.pairs) / len(pos)
    assert covered >= 0.7
