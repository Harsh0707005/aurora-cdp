"""Synthetic generator: determinism and planted structure."""

from aurora.synth.generator import SynthParams, apply_drift, generate


def test_generate_is_deterministic():
    a = generate(SynthParams(size=200, seed=3))
    b = generate(SynthParams(size=200, seed=3))
    assert a.equals(b)
    assert a["truth_id"].nunique() == 200
    assert set(a["datasource"]) <= {"web", "store", "loyalty"}
    assert a[["datasource", "pk"]].drop_duplicates().shape[0] == len(a)


def test_duplicates_and_drift():
    df = generate(SynthParams(size=300, seed=5, dup_rate=0.8))
    assert len(df) > 300  # duplicates across sources
    drifted = apply_drift(df, seed=9)
    assert drifted["truth_id"].str.startswith("N").any()  # new customers
    assert len(set(df["pk"]) - set(drifted["pk"])) > 0  # some rows dropped
