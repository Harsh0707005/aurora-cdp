"""Ground-truth-free evaluation of the pairwise scorer by feature signatures (Amperity US10509809 / US11308130).

``sample``: group every scored pair of a run by its *feature signature* (each pairwise feature discretised to
missing / none / low / mid / high / exact), take up to ``--per-signature`` pairs from each signature, and write
them with both records' PII for a human to label (``label`` column: match / non-match).

``evaluate``: given the labelled sample, estimate P(match | signature) per signature and roll it up over the whole
pair population by signature frequency: precision and recall of the scorer's decisions (``is_edge``) and of
every score band, without ever labelling the whole pair space.

The run must have been stored with ``matcher.persist_features: true`` (the signature is computed from
``stitch_scores.features_json``).

    python tools/signature_samples.py sample   --db .aurora/aurora.duckdb [--run RUN] --per-signature 5 --out samples.csv
    python tools/signature_samples.py evaluate --db .aurora/aurora.duckdb [--run RUN] --labels samples_labelled.csv [--out eval.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aurora_cdp.stitch.features import FEATURE_NAMES  # noqa: E402

PII = ["given_name_norm", "surname_norm", "email_norm", "phone_match", "address_norm", "postal_norm", "birthdate_norm", "loy_id_norm", "ck"]


def bucket(name: str, v) -> str:
    if v is None:
        return "na"
    v = float(v)
    if name in ("birthdate_conflict", "trivial_dupe", "name_both_present") or v in (0.0, 1.0):
        return "1" if v == 1.0 else "0"
    return "lo" if v < 0.6 else ("mid" if v < 0.9 else "hi")


def signature(features: dict) -> str:
    return "|".join(f"{n}={bucket(n, features.get(n))}" for n in FEATURE_NAMES)


def load_scores(con, run_id: str | None) -> pd.DataFrame:
    if run_id is None:
        run_id = con.execute("SELECT run_id FROM stitch_runs WHERE status='succeeded' ORDER BY started_at DESC LIMIT 1").fetchone()[0]
    df = con.execute(
        "SELECT left_datasource, left_pk, right_datasource, right_pk, score, match_category, match_type, is_edge, features_json "
        "FROM stitch_scores WHERE run_id = ?", [run_id]).df()
    if df.empty:
        raise SystemExit(f"no stitch_scores rows for run {run_id!r}")
    if df["features_json"].isna().all():
        raise SystemExit("features_json is empty: rerun with matcher.persist_features: true")
    df = df[df["features_json"].notna()].copy()
    df["signature"] = [signature(json.loads(f)) for f in df["features_json"]]
    df.attrs["run_id"] = run_id
    return df


def cmd_sample(a) -> None:
    con = duckdb.connect(a.db, read_only=True)
    df = load_scores(con, a.run)
    freq = df.groupby("signature").size().rename("signature_pairs")
    sample = (df.sample(frac=1.0, random_state=a.seed).groupby("signature", group_keys=False).head(a.per_signature)
              .merge(freq, left_on="signature", right_index=True))
    pre = con.execute(f"SELECT datasource, pk, {', '.join(PII)} FROM silver_unified_preprocessed").df()
    pre = pre.drop_duplicates(["datasource", "pk"], keep="last")
    for side in ("left", "right"):
        sided = pre.rename(columns={c: f"{side}_{c}" for c in PII}).rename(columns={"datasource": f"{side}_datasource", "pk": f"{side}_pk"})
        sample = sample.merge(sided, on=[f"{side}_datasource", f"{side}_pk"], how="left")
    sample["label"] = ""
    cols = (["signature", "signature_pairs", "score", "match_category", "match_type", "is_edge"]
            + [f"{s}_{c}" for c in ("datasource", "pk", *PII) for s in ("left", "right")] + ["label"])
    sample = sample.sort_values(["signature_pairs", "signature"], ascending=[False, True])[cols]
    sample.to_csv(a.out, index=False)
    print(f"{len(sample):,} sample pairs over {sample['signature'].nunique():,} signatures (run {df.attrs['run_id']}, {len(df):,} scored pairs) -> {a.out}")


def cmd_evaluate(a) -> None:
    con = duckdb.connect(a.db, read_only=True)
    df = load_scores(con, a.run)
    lab = pd.read_csv(a.labels, dtype=str)
    lab = lab[lab["label"].fillna("").str.strip().str.lower().isin(["match", "non-match", "nonmatch", "no", "yes", "1", "0"])]
    if lab.empty:
        raise SystemExit("no labelled rows (label = match | non-match)")
    lab["y"] = lab["label"].str.strip().str.lower().isin(["match", "yes", "1"]).astype(int)
    p_sig = lab.groupby("signature")["y"].agg(["mean", "size"]).rename(columns={"mean": "p_match", "size": "labelled"})
    pop = df.groupby("signature").agg(pairs=("score", "size"), edges=("is_edge", "sum"), score_mean=("score", "mean"), band=("match_category", lambda s: s.mode().iat[0]))
    t = pop.join(p_sig, how="left")
    covered = t["p_match"].notna()
    cov_pairs = t.loc[covered, "pairs"].sum() / t["pairs"].sum()
    t_c = t[covered].copy()
    t_c["exp_matches"] = t_c["pairs"] * t_c["p_match"]
    t_c["exp_true_edges"] = t_c["edges"] * t_c["p_match"]
    tp = t_c["exp_true_edges"].sum(); pred = t_c["edges"].sum(); real = t_c["exp_matches"].sum()
    precision = tp / pred if pred else float("nan"); recall = tp / real if real else float("nan")
    lines = [f"# Signature-based evaluation — run `{df.attrs['run_id']}`", "",
             f"{len(lab):,} labelled pairs over {len(p_sig):,} signatures cover {cov_pairs:.1%} of {t['pairs'].sum():,} scored pairs.", "",
             f"**Estimated precision of the merge decision (is_edge): {precision:.4f}; recall: {recall:.4f}** (expected-value roll-up over covered signatures).", "",
             "| band | pairs | est. P(match) |", "|---|---|---|"]
    for band, g in t_c.groupby("band"):
        lines.append(f"| {band} | {int(g['pairs'].sum()):,} | {g['exp_matches'].sum() / g['pairs'].sum():.3f} |")
    lines += ["", "Most consequential signatures (pairs × |P(match) − decision|):", "", "| signature | pairs | decision | P(match) | labelled |", "|---|---|---|---|---|"]
    t_c["decision"] = (t_c["edges"] / t_c["pairs"]).round(2)
    t_c["impact"] = t_c["pairs"] * (t_c["p_match"] - t_c["decision"]).abs()
    for sig, r in t_c.sort_values("impact", ascending=False).head(15).iterrows():
        short = ",".join(x for x in sig.split("|") if not x.endswith("=na") and not x.endswith("=0"))
        lines.append(f"| {short} | {int(r['pairs']):,} | {r['decision']} | {r['p_match']:.2f} | {int(r['labelled'])} |")
    out = "\n".join(lines) + "\n"
    if a.out:
        Path(a.out).write_text(out)
    print(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample"); s.add_argument("--db", required=True); s.add_argument("--run"); s.add_argument("--per-signature", type=int, default=5)
    s.add_argument("--seed", type=int, default=0); s.add_argument("--out", required=True); s.set_defaults(fn=cmd_sample)
    e = sub.add_parser("evaluate"); e.add_argument("--db", required=True); e.add_argument("--run"); e.add_argument("--labels", required=True)
    e.add_argument("--out"); e.set_defaults(fn=cmd_evaluate)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
