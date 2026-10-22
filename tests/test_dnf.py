"""Learned DNF blocking: predicates, greedy cover, graceful fallback, and the dnf strategy type in blocking."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from aurora_cdp.config import load_config
from aurora_cdp.stitch.blocking import build_blocks
from aurora_cdp.stitch.dnf import (
    conjunction_key,
    derive_columns,
    evaluate_strategies,
    learn_dnf,
    self_label_positives,
    soundex,
    truth_positives,
)

CFG = load_config(use_last_best=False)


def _corpus(persons: int = 300, copies: int = 4, seed: int = 3) -> tuple[pd.DataFrame, np.ndarray]:
    """Synthetic people whose copies share a surname prefix + postal or an e-mail local part, with noise."""
    rng = random.Random(seed)
    given = [
        "michael",
        "sarah",
        "robert",
        "linda",
        "david",
        "susan",
        "james",
        "karen",
        "daniel",
        "nancy",
    ]
    sur = ["chen", "patel", "novak", "rossi", "garcia", "miller", "okafor", "lee", "weber", "silva"]
    rows, truth = [], []
    for p in range(persons):
        g, s = rng.choice(given), rng.choice(sur) + str(p)
        postal = f"{rng.randrange(90000, 99999)}"
        email = f"{g[0]}{s}@example.org"
        for c in range(copies):
            r = {
                "datasource": "s",
                "pk": f"{p}-{c}",
                "given_name_canon": g if rng.random() > 0.2 else g[:1] + ".",
                "surname_norm": s if rng.random() > 0.15 else s[:-1] + "x",
                "email_norm": email if rng.random() > 0.3 else None,
                "phone_match": None,
                "postal_norm": postal if rng.random() > 0.3 else None,
                "birthdate_norm": None,
                "address_norm": None,
                "loy_id_norm": None,
                "ck": None,
            }
            rows.append(r)
            truth.append(f"p{p}")
    return derive_columns(pd.DataFrame(rows)), np.array(truth, dtype=object)


def test_soundex_and_keys():
    assert (
        soundex("Robert") == soundex("Rupert") == "R163"
        and soundex("Tymczak") == "T522"
        and soundex("") is None
    )
    terms = [
        {"attr": "surname_norm", "transform": "prefix3"},
        {"attr": "postal_norm", "transform": "exact"},
    ]
    assert conjunction_key({"surname_norm": "hunter", "postal_norm": "98101"}, terms) == "hun:98101"
    assert conjunction_key({"surname_norm": "hunter"}, terms) is None


def test_learner_covers_positives_within_budget():
    df, truth = _corpus()
    rng = np.random.default_rng(0)
    pos = truth_positives(truth, 5000, rng)
    res = learn_dnf(
        df, pos, {**CFG.blocking["dnf"], "target_pc": 0.9, "pairs_per_record_budget": 20}
    )
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
    assert all(
        truth[a] == truth[b] for a, b in pos
    )  # rules-only positives are clean on this fixture


def test_dnf_strategy_runs_through_zero_discard_blocking(tmp_path):
    df, truth = _corpus(persons=60)
    pos = truth_positives(truth, 5000, np.random.default_rng(0))
    res = learn_dnf(df, pos, {**CFG.blocking["dnf"], "target_pc": 0.8})
    overlay = {"strategies": res.strategies}
    (tmp_path / "learned.yaml").write_text(yaml.safe_dump(overlay))
    records = {
        f"{r['datasource']}|{r['pk']}": r
        for r in df.drop(columns=["email_local", "house_no", "given_sdx", "surname_sdx"])
        .astype(object)
        .where(df.notna(), None)
        .to_dict("records")
    }
    cfg = {
        **CFG.blocking,
        "strategies": res.strategies,
        "block_size_limit": 5,
        "max_pairs_per_block": 50,
    }
    out = build_blocks(records, cfg)
    assert out.pair_count > 0 and out.skipped == [] and out.stats.records_dropped_by_blocking == 0
    covered = sum(
        1
        for a, b in pos
        if (min(f"s|{df.pk[a]}", f"s|{df.pk[b]}"), max(f"s|{df.pk[a]}", f"s|{df.pk[b]}"))
        in out.pairs
    ) / len(pos)
    assert covered >= 0.7


# ----------------------------------------------------------------------------------------- beam / loader / wiring
def test_beam_search_is_bounded_and_deterministic():
    df, truth = _corpus()
    pos = truth_positives(truth, 5000, np.random.default_rng(0))
    base = {**CFG.blocking["dnf"], "target_pc": 0.9, "pairs_per_record_budget": 20, "max_terms": 3}
    beamed = learn_dnf(df, pos, {**base, "beam_width": 3})
    again = learn_dnf(df, pos, {**base, "beam_width": 3})
    assert beamed.fallback_reason is None and beamed.pc >= 0.9 and beamed.cost <= beamed.budget
    assert [s["name"] for s in beamed.strategies] == [s["name"] for s in again.strategies]
    assert all(
        len(s["terms"]) <= 3 and len({t["attr"] for t in s["terms"]}) == len(s["terms"])
        for s in beamed.strategies
    )
    exhaustive = learn_dnf(df, pos, base)
    assert exhaustive.pc >= beamed.pc - 0.05  # the beam gives up at most a little completeness


def test_learned_file_loader_validates(tmp_path):
    from aurora_cdp.stitch.dnf import (
        load_learned_strategies,
        strategies_document,
        validate_strategy,
    )

    good = [
        {
            "name": "dnf_x",
            "type": "dnf",
            "terms": [{"attr": "surname_norm", "transform": "prefix3"}],
        }
    ]
    f = tmp_path / "ok.yaml"
    f.write_text(yaml.safe_dump(strategies_document(good, labels="self")))
    strategies, reason = load_learned_strategies(f)
    assert reason is None and strategies == good
    assert load_learned_strategies(None)[1].startswith(
        "blocking.learned_strategies_file is not set"
    )
    assert "does not exist" in load_learned_strategies(tmp_path / "missing.yaml")[1]
    (tmp_path / "empty.yaml").write_text("")
    assert "contains no strategies" in load_learned_strategies(tmp_path / "empty.yaml")[1]
    (tmp_path / "none.yaml").write_text(yaml.safe_dump({"strategies": []}))
    assert "contains no strategies" in load_learned_strategies(tmp_path / "none.yaml")[1]
    (tmp_path / "bad.yaml").write_text(
        yaml.safe_dump({"strategies": [{"name": "x", "type": "email"}]})
    )
    assert "malformed" in load_learned_strategies(tmp_path / "bad.yaml")[1]
    (tmp_path / "badtr.yaml").write_text(
        yaml.safe_dump(
            {"strategies": [{"type": "dnf", "terms": [{"attr": "a", "transform": "nope"}]}]}
        )
    )
    assert "malformed" in load_learned_strategies(tmp_path / "badtr.yaml")[1]
    (tmp_path / "syntax.yaml").write_text("strategies: [\n")
    assert "not valid YAML" in load_learned_strategies(tmp_path / "syntax.yaml")[1]
    with pytest.raises(ValueError):
        validate_strategy({"type": "dnf", "terms": []})


def _learned_file(tmp_path, n: int = 2):
    from aurora_cdp.stitch.dnf import strategies_document

    learned = [
        {
            "name": "dnf_surname_norm.prefix3_postal_norm.exact",
            "type": "dnf",
            "terms": [
                {"attr": "surname_norm", "transform": "prefix3"},
                {"attr": "postal_norm", "transform": "exact"},
            ],
        },
        {
            "name": "dnf_email_local.exact",
            "type": "dnf",
            "terms": [{"attr": "email_local", "transform": "exact"}],
        },
    ][:n]
    f = tmp_path / "learned.strategies.yaml"
    f.write_text(yaml.safe_dump(strategies_document(learned, labels="self")))
    return f, learned


def test_resolve_strategies_learned_union_and_fallback(tmp_path, caplog):
    from aurora_cdp.stitch.run import resolve_strategies

    f, learned = _learned_file(tmp_path)
    fixed = CFG.blocking["strategies"]
    fixed_names = [s["name"] for s in fixed]
    cfg = load_config(
        use_last_best=False,
        overrides={"blocking": {"strategy_source": "learned", "learned_strategies_file": str(f)}},
    )
    bcfg, info = resolve_strategies(cfg)
    kept = {s["type"] for s in bcfg["strategies"] if s["type"] != "dnf"}
    assert (
        kept == set(CFG.blocking["learned_keep_types"])
        and info["blocking_strategy_source"] == "learned"
    )
    assert [s["name"] for s in bcfg["strategies"] if s["type"] == "dnf"] == [
        s["name"] for s in learned
    ]
    assert (
        info["blocking_learned_strategies"] == 2
        and info["blocking_learned_fallback_reason"] is None
    )
    cfg = load_config(
        use_last_best=False,
        overrides={"blocking": {"strategy_source": "union", "learned_strategies_file": str(f)}},
    )
    bcfg, info = resolve_strategies(cfg)
    assert [s["name"] for s in bcfg["strategies"]] == fixed_names + [s["name"] for s in learned]
    assert info["blocking_strategy_source"] == "union"
    # fixed is untouched
    bcfg, info = resolve_strategies(CFG)
    assert [s["name"] for s in bcfg["strategies"]] == fixed_names and info[
        "blocking_strategy_source"
    ] == "fixed"
    # missing file / empty file / unset path -> fixed strategies + logged warning, never a crash
    for overlay in (
        {"learned_strategies_file": str(tmp_path / "nope.yaml")},
        {"learned_strategies_file": None},
    ):
        caplog.clear()
        with caplog.at_level("WARNING", logger="aurora_cdp.stitch.run"):
            bcfg, info = resolve_strategies(
                load_config(
                    use_last_best=False,
                    overrides={"blocking": {"strategy_source": "learned", **overlay}},
                )
            )
        assert [s["name"] for s in bcfg["strategies"]] == fixed_names and info[
            "blocking_strategy_source"
        ] == "fixed"
        assert info["blocking_learned_fallback_reason"].endswith("using the fixed strategies")
        assert any("using the fixed strategies" in r.getMessage() for r in caplog.records)
    (tmp_path / "empty.yaml").write_text("strategies: []\n")
    bcfg, info = resolve_strategies(
        load_config(
            use_last_best=False,
            overrides={
                "blocking": {
                    "strategy_source": "union",
                    "learned_strategies_file": str(tmp_path / "empty.yaml"),
                }
            },
        )
    )
    assert [
        s["name"] for s in bcfg["strategies"]
    ] == fixed_names and "contains no strategies" in info["blocking_learned_fallback_reason"]
    with pytest.raises(ValueError):
        resolve_strategies(
            load_config(use_last_best=False, overrides={"blocking": {"strategy_source": "magic"}})
        )


def test_relative_learned_path_resolves_against_cwd(tmp_path, monkeypatch):
    from aurora_cdp.stitch.run import learned_strategies_path, resolve_strategies

    f, _ = _learned_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = load_config(
        use_last_best=False,
        overrides={"blocking": {"strategy_source": "learned", "learned_strategies_file": f.name}},
    )
    assert learned_strategies_path(f.name, cfg) == tmp_path / f.name
    assert resolve_strategies(cfg)[1]["blocking_learned_strategies"] == 2


def _semantic_csv(path, persons: int = 300, copies: int = 4, seed: int = 3):
    rng = random.Random(seed)
    given = [
        "Michael",
        "Sarah",
        "Robert",
        "Linda",
        "David",
        "Susan",
        "James",
        "Karen",
        "Daniel",
        "Nancy",
    ]
    sur = ["Chen", "Patel", "Novak", "Rossi", "Garcia", "Miller", "Okafor", "Lee", "Weber", "Silva"]
    rows = []
    for p in range(persons):
        g, s = rng.choice(given), rng.choice(sur) + str(p)
        postal, email, phone = (
            f"{rng.randrange(90000, 99999)}",
            f"{g[0]}{s}@example.org".lower(),
            f"206555{p:04d}",
        )
        for c in range(copies):
            rows.append(
                {
                    "source_record_id": f"{p}-{c}",
                    "datasource": "crm" if c % 2 else "web",
                    "truth_id": f"p{p}",
                    "given_name": g if rng.random() > 0.2 else g[:1] + ".",
                    "surname": s if rng.random() > 0.15 else s[:-1] + "x",
                    "email": email if rng.random() > 0.3 else "",
                    "phone": phone if rng.random() > 0.5 else "",
                    "postal": postal if rng.random() > 0.3 else "",
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)
    return pd.DataFrame(rows)


def test_cli_writes_strategies_that_run_loads_end_to_end(tmp_path):
    import subprocess
    import sys

    from aurora_cdp.adapters import resolve_records
    from aurora_cdp.stitch.dnf import LEARNED_FILE_VERSION, load_learned_strategies
    from aurora_cdp.stitch.run import resolve_strategies

    csv_path = tmp_path / "records.csv"
    records = _semantic_csv(csv_path)
    cfg_overlay = tmp_path / "learn.yaml"
    cfg_overlay.write_text(
        yaml.safe_dump(
            {
                "blocking": {
                    "dnf": {
                        "min_positive_pairs": 50,
                        "target_pc": 0.9,
                        "pairs_per_record_budget": 20,
                    }
                }
            }
        )
    )
    overlay = tmp_path / "learned" / "dnf.yaml"
    repo = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        str(repo / "tools" / "learn_dnf.py"),
        "--csv",
        str(csv_path),
        "--overlay",
        str(overlay),
        "--labels",
        "self",
        "--seed",
        "0",
        "--config",
        str(cfg_overlay),
        "--out",
        str(tmp_path / "report"),
    ]
    run = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp_path)
    assert run.returncode == 0, run.stderr
    strategies_file = overlay.with_suffix(".strategies.yaml")
    assert (
        strategies_file.exists()
        and (tmp_path / "report" / "dnf.md").exists()
        and (tmp_path / "report" / "dnf.json").exists()
    )
    doc = yaml.safe_load(strategies_file.read_text())
    assert (
        doc["schema_version"] == LEARNED_FILE_VERSION
        and doc["labels"] == "self"
        and doc["seed"] == 0
        and doc["train"]["kind"] == "csv"
    )
    assert doc["fallback_reason"] is None and doc["strategies"]
    ov = yaml.safe_load(overlay.read_text())
    assert (
        ov["blocking"]["strategy_source"] == "learned"
        and Path(ov["blocking"]["learned_strategies_file"]).is_absolute()
    )
    strategies, reason = load_learned_strategies(ov["blocking"]["learned_strategies_file"])
    assert reason is None and strategies == doc["strategies"]
    # determinism: a second run with the same seed writes the same strategies
    run2 = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp_path)
    assert (
        run2.returncode == 0
        and yaml.safe_load(strategies_file.read_text())["strategies"] == doc["strategies"]
    )
    # run.py picks the file up through the overlay ...
    cfg = load_config(str(overlay), use_last_best=False)
    bcfg, info = resolve_strategies(cfg)
    assert info["blocking_strategy_source"] == "learned" and info[
        "blocking_learned_strategies"
    ] == len(doc["strategies"])
    # ... and a full resolve through the adapter reports the learned source and keeps zero-discard blocking
    res = resolve_records(
        records.drop(columns=["truth_id"]), config=str(overlay), workspace=tmp_path / "ws"
    )
    assert (
        res.metrics["blocking_strategy_source"] == "learned"
        and res.metrics["blocking_learned_fallback_reason"] is None
    )
    assert res.metrics["records_dropped_by_blocking"] == 0 and res.metrics["clusters"] < len(
        records
    )
    # a run against a missing file falls back to the fixed strategies instead of crashing
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        yaml.safe_dump(
            {
                "blocking": {
                    "strategy_source": "learned",
                    "learned_strategies_file": str(tmp_path / "gone.yaml"),
                }
            }
        )
    )
    res2 = resolve_records(
        records.drop(columns=["truth_id"]).head(40), config=str(broken), workspace=tmp_path / "ws2"
    )
    assert (
        res2.metrics["blocking_strategy_source"] == "fixed"
        and "does not exist" in res2.metrics["blocking_learned_fallback_reason"]
    )
