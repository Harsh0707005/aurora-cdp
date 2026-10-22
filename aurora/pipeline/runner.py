"""End-to-end identity run (one "Stitch" pass).

Stages: read raw -> standardise + blocklist -> blocking -> pairwise features
-> ordinal scoring -> keep edges -> union-find + hygiene -> stable IDs ->
Unified tables, Merged_Customers, Customer360 -> CDC tables + events ->
run summary (``data/runs/<job_id>/summary.json``).

Blocking, pairwise feature extraction and scoring run inside Spark; only the
kept edges (bounded by blocking) are collected to the driver for clustering.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql import types as T

from aurora.blocking.strategies import candidate_pairs
from aurora.config.schema import TenantConfig, load_config
from aurora.data.schemas import PAIR_FEATURE_COLUMNS, SEMANTIC_COLUMNS, STD_COLUMNS, TABLES
from aurora.features.pairwise import SIDE_COLUMNS, features_frame
from aurora.graph.components import apply_hygiene
from aurora.graph.edges import keep_edges
from aurora.graph.stable_id import assign_stable_ids
from aurora.io.deltaio import DELTA_SESSION_FAILED, LakeIO, build_spark
from aurora.pipeline.cdc import JsonlSink, KafkaSink, build_change_tables, emit_events
from aurora.scoring.ordinal import build_scorer
from aurora.utils.ids import new_job_id


@dataclass
class RunSummary:
    job_id: str
    tenant: str
    records: int
    pairs: int
    edges: int
    clusters: int
    jitter: dict
    hygiene: dict
    storage_format: str
    duration_s: float
    cdc_events: int
    blocking: list[dict]
    lake_root: str
    delta_error: str | None = None

    def jitter_line(self) -> str:
        j = self.jitter
        return (
            f"JITTER SUMMARY: added={j['added']} deleted={j['deleted']} merged={j['merged']} "
            f"recognized={j['recognized']} split={j['split']} split_merged={j['split_merged']} "
            f"percent={j['percent']:.1f}%"
        )


# ------------------------------------------------------------------ preprocessing


def preprocess(raw: DataFrame, cfg: TenantConfig) -> DataFrame:
    """Standardise semantic columns and strip blocklisted values (flag ``has_blv``)."""
    nick = dict(cfg.nicknames)
    bl = cfg.blocklist.model_dump()
    schema = T.StructType(
        raw.schema.fields
        + [T.StructField(c, T.StringType(), True) for c in STD_COLUMNS]
        + [T.StructField("has_blv", T.BooleanType(), False)]
    )

    def _batch(it: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        from aurora.utils import standardize as S

        bl_emails, bl_phones = set(bl["emails"]), set(bl["phones"])
        bl_names, bl_domains = set(bl["names"]), set(bl["email_domains"])
        for pdf in it:
            out = pdf.copy()
            pdf = pdf.astype(object).where(pd.notna(pdf), None)  # Arrow nulls arrive as NaN floats
            rows = []
            for r in pdf.to_dict("records"):
                given, surname = r.get("given_name"), r.get("surname")
                if (not given or not surname) and r.get("full_name"):
                    g2, s2 = S.split_full_name(r["full_name"])
                    given, surname = given or g2, surname or s2
                email = S.normalize_email(r.get("email"))
                phone = S.normalize_phone(r.get("phone"))
                gstd = S.normalize_name(given)
                sstd = S.normalize_name(surname)
                blv = False
                if email and (email in bl_emails or email.split("@")[-1] in bl_domains):
                    email, blv = None, True
                if phone and phone[-10:] in bl_phones:
                    phone, blv = None, True
                if gstd in bl_names or sstd in bl_names:
                    gstd = None if gstd in bl_names else gstd
                    sstd = None if sstd in bl_names else sstd
                    blv = True
                rows.append(
                    {
                        "email_std": email,
                        "email_canon": S.canonical_email(email),
                        "phone_std": phone,
                        "given_std": gstd,
                        "surname_std": sstd,
                        "given_nick": S.normalize_name(gstd, nick) if gstd else None,
                        "street_std": S.normalize_street(r.get("address")),
                        "house_no": S.house_number(r.get("address")),
                        "postal_std": S.normalize_postal(r.get("postal")),
                        "dob_std": S.normalize_dob(r.get("birthdate")),
                        "has_blv": blv,
                    }
                )
            extra = pd.DataFrame(rows, index=out.index)
            yield pd.concat([out, extra], axis=1)

    return raw.mapInPandas(_batch, schema=schema)


# ------------------------------------------------------------------ scoring in Spark


def score_pairs(pairs: DataFrame, std: DataFrame, cfg: TenantConfig) -> DataFrame:
    """Join both sides of each candidate pair and compute features + ordinal score."""
    left = std.select(F.col("rid").alias("rid_l"), *[F.col(c).alias(f"l_{c}") for c in SIDE_COLUMNS])
    right = std.select(F.col("rid").alias("rid_r"), *[F.col(c).alias(f"r_{c}") for c in SIDE_COLUMNS])
    joined = pairs.join(left, "rid_l").join(right, "rid_r")
    scoring_cfg = cfg.scoring
    schema = T.StructType(
        [
            T.StructField("rid_l", T.LongType()),
            T.StructField("rid_r", T.LongType()),
            T.StructField("strategies", T.ArrayType(T.StringType())),
        ]
        + [T.StructField(c, T.FloatType()) for c in PAIR_FEATURE_COLUMNS]
        + [
            T.StructField("raw_score", T.DoubleType()),
            T.StructField("category", T.IntegerType()),
            T.StructField("score", T.DoubleType()),
            T.StructField("match_category", T.StringType()),
            T.StructField("match_type", T.StringType()),
        ]
    )

    def _batch(it: Iterator[pd.DataFrame]) -> Iterator[pd.DataFrame]:
        scorer = build_scorer(scoring_cfg)
        for pdf in it:
            if pdf.empty:
                continue
            lf = pdf[[f"l_{c}" for c in SIDE_COLUMNS]].rename(columns=lambda c: c[2:])
            rf = pdf[[f"r_{c}" for c in SIDE_COLUMNS]].rename(columns=lambda c: c[2:])
            feats = features_frame(lf, rf)
            scored = scorer.score(feats)
            out = pd.concat(
                [pdf[["rid_l", "rid_r", "strategies"]].reset_index(drop=True), feats, scored], axis=1
            )
            out["category"] = out["category"].astype("int32")
            yield out

    return joined.mapInPandas(_batch, schema=schema)


# ------------------------------------------------------------------ golden record


COMPLETENESS_COLS = ["email_std", "phone_std", "given_std", "surname_std", "street_std", "postal_std", "dob_std"]


def merged_customers(unified: DataFrame) -> DataFrame:
    """One row per aurora_id. Policy: most-complete row wins, ties -> most recent,
    then per-field first non-null in that order (coalescing survivorship)."""
    completeness = sum(F.when(F.col(c).isNotNull(), 1).otherwise(0) for c in COMPLETENESS_COLS)
    u = unified.withColumn("_completeness", completeness)
    w = (
        Window.partitionBy("aurora_id")
        .orderBy(F.desc("_completeness"), F.desc("updated_at"), F.asc("datasource"), F.asc("pk"))
        .rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)
    )
    fields = SEMANTIC_COLUMNS + STD_COLUMNS
    cols = [F.first(F.col(c), ignorenulls=True).over(w).alias(c) for c in fields]
    return (
        u.select(
            "aurora_id",
            F.first("datasource").over(w).alias("rep_ds"),
            F.first("pk").over(w).alias("rep_pk"),
            *cols,
            F.count("*").over(w).alias("record_count"),
            F.collect_set("datasource").over(w).alias("sources"),
        )
        .dropDuplicates(["aurora_id"])
    )


def customer360(merged: DataFrame, unified: DataFrame) -> DataFrame:
    agg = unified.groupBy("aurora_id").agg(
        F.min("updated_at").alias("first_seen"),
        F.max("updated_at").alias("last_seen"),
        F.collect_set("loyalty_id").alias("loyalty_ids"),
        F.collect_set("email_std").alias("emails"),
        F.collect_set("phone_std").alias("phones"),
        F.max(F.col("is_supersized").cast("int")).cast("boolean").alias("is_supersized"),
        F.max(F.col("has_blv").cast("int")).cast("boolean").alias("has_blv"),
    )
    return merged.join(agg, "aurora_id")


# ------------------------------------------------------------------ run


def run(cfg: TenantConfig, raw_path: str | Path, job_id: str | None = None, sink: str = "jsonl",
        tenant_name: str | None = None) -> RunSummary:
    t0 = time.time()
    job_id = job_id or new_job_id()
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    spark, fmt = build_spark(cfg)
    lake = LakeIO(spark, cfg.storage.lake_root, fmt)
    runs_dir = Path("data/runs") / job_id
    runs_dir.mkdir(parents=True, exist_ok=True)

    # -- previous assignments (before we overwrite anything)
    prev_pks: pd.DataFrame | None = None
    if lake.exists(TABLES["unified_customer"]):
        prev_pks = lake.read(TABLES["unified_customer"]).select("datasource", "pk", "aurora_id").toPandas()
        prev_pks.to_parquet(runs_dir / "prev_assignments.parquet", index=False)

    # -- read + preprocess
    raw = spark.read.parquet(str(raw_path))
    for c in SEMANTIC_COLUMNS + ["truth_id"]:
        if c not in raw.columns:
            raw = raw.withColumn(c, F.lit(None).cast("string"))
    raw = raw.withColumn("rid", F.row_number().over(Window.orderBy("datasource", "pk")).cast("long"))
    std = preprocess(raw, cfg).persist()
    n_records = std.count()
    lake.write(std.withColumn("job_id", F.lit(job_id)), TABLES["unified_preprocessed_raw"])

    # -- blocking
    pairs, bstats = candidate_pairs(std, cfg.blocking)
    pairs = pairs.limit(cfg.blocking.max_pairs).persist()
    n_pairs = pairs.count()
    bstats_pdf = bstats.toPandas()
    lake.write_pandas(bstats_pdf.assign(job_id=job_id), TABLES["blocking_stats"])

    # -- scoring
    scored = score_pairs(pairs, std, cfg).persist()
    rid_map = std.select("rid", "datasource", "pk")
    stitch = (
        scored.join(rid_map.select(F.col("rid").alias("rid_l"), F.col("datasource").alias("datasource_l"),
                                   F.col("pk").alias("pk_l")), "rid_l")
        .join(rid_map.select(F.col("rid").alias("rid_r"), F.col("datasource").alias("datasource_r"),
                             F.col("pk").alias("pk_r")), "rid_r")
        .withColumn("job_id", F.lit(job_id))
    )
    lake.write(stitch, TABLES["stitch_scores"])

    # -- edges -> driver
    edges_pdf = scored.where(F.col("score") >= cfg.scoring.edge_keep_threshold).select(
        "rid_l", "rid_r", "score", "category", "match_type"
    ).toPandas()
    edges_pdf = keep_edges(edges_pdf, cfg.scoring)
    nodes = [int(r) for r in std.select("rid").toPandas()["rid"]]
    hyg = apply_hygiene(edges_pdf, nodes, cfg.hygiene)

    # -- stable ids
    assign = pd.DataFrame({"rid": list(hyg.assignment), "cluster_id": list(hyg.assignment.values())})
    pk_pdf = std.select("rid", "datasource", "pk").toPandas()
    assign = assign.merge(pk_pdf, on="rid")
    sid = assign_stable_ids(prev_pks, assign, cfg.stable_id.namespace, cfg.stable_id.hungarian_max_nodes)
    assign["aurora_id"] = assign["cluster_id"].map(sid.cluster_to_id)
    assign["supersized_id"] = assign["rid"].map(hyg.supersized)
    assign["is_supersized"] = assign["supersized_id"].notna()
    assign["supersized_id"] = assign["supersized_id"].astype("Int64")
    seeds = assign.sort_values(["cluster_id", "datasource", "pk"]).drop_duplicates("cluster_id")
    assign = assign.merge(seeds[["cluster_id", "datasource", "pk"]].rename(
        columns={"datasource": "rep_ds", "pk": "rep_pk"}), on="cluster_id")

    a_sdf = spark.createDataFrame(
        assign[["rid", "cluster_id", "aurora_id", "is_supersized", "supersized_id", "rep_ds", "rep_pk"]]
        .astype({"rid": "int64", "cluster_id": "int64"}).astype(object).where(lambda d: pd.notna(d), None),
        schema="rid long, cluster_id long, aurora_id string, is_supersized boolean, supersized_id long, rep_ds string, rep_pk string",
    )
    unified = std.join(a_sdf, "rid").withColumn("component_id", F.col("cluster_id")).withColumn("job_id", F.lit(job_id)).persist()

    # -- CDC (computed before any serving table is overwritten, so a failed run cannot lose the previous state)
    new_pks = assign[["datasource", "pk", "aurora_id"]]
    clusters_tbl, pks_tbl = build_change_tables(sid.events, prev_pks, new_pks, job_id)
    moved = int((pks_tbl["change_type"] == "moved").sum())
    sid.jitter["moved_records"] = moved
    sid.jitter["percent"] = round(100.0 * moved / n_records, 3) if prev_pks is not None else sid.jitter["percent"]
    # -- serving tables
    lake.write(unified, TABLES["unified_coalesced"])
    lake.write(unified.select("datasource", "pk", "aurora_id", "cluster_id", "truth_id", "job_id",
                              *SEMANTIC_COLUMNS, *STD_COLUMNS, "is_supersized", "has_blv"),
               TABLES["unified_customer"])
    merged = merged_customers(unified).persist()
    lake.write(merged, TABLES["merged_customers"])
    lake.write(customer360(merged, unified), TABLES["customer360"])
    lake.write_pandas(clusters_tbl, TABLES["unified_changes_clusters"], mode="append")
    if not pks_tbl.empty:
        lake.write_pandas(pks_tbl, TABLES["unified_changes_pks"], mode="append")
    mapping = sid.events[sid.events["current_id"].notna()][["cluster_id", "current_id", "previous_id", "change_type"]]
    mapping = mapping.rename(columns={"current_id": "aurora_id"}).assign(job_id=job_id)
    mapping["cluster_id"] = mapping["cluster_id"].astype("int64")
    for c in ("overlap", "new_size", "previous_size", "fragments", "absorbed"):
        clusters_tbl[c] = clusters_tbl[c].fillna(0).astype("int64")
    lake.write_pandas(mapping, TABLES["stable_id_mapping"], mode="append")
    lineage = assign[["aurora_id", "datasource", "pk", "cluster_id", "supersized_id"]].assign(job_id=job_id)
    lineage["lineage"] = "lineage:" + job_id + ":" + lineage["aurora_id"]
    lake.write_pandas(lineage, TABLES["lineage"], mode="append")

    s = JsonlSink(cfg.storage.cdc_root, job_id) if sink == "jsonl" else KafkaSink()
    n_events = emit_events(s, clusters_tbl, pks_tbl, job_id)
    s.close()

    summary = RunSummary(
        job_id=job_id, tenant=tenant_name or cfg.tenant, records=n_records, pairs=n_pairs,
        edges=len(edges_pdf), clusters=len(sid.cluster_to_id), jitter=sid.jitter, hygiene=hyg.stats,
        storage_format=fmt, duration_s=round(time.time() - t0, 1), cdc_events=n_events,
        blocking=bstats_pdf.to_dict("records"), lake_root=str(lake.root), delta_error=DELTA_SESSION_FAILED,
    )
    (runs_dir / "summary.json").write_text(json.dumps(summary.__dict__, indent=2, default=str))
    sid.events.to_csv(runs_dir / "jitter.csv", index=False)
    (Path("data/runs") / "LATEST").write_text(job_id)
    spark.stop()
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Run one Aurora identity pass")
    ap.add_argument("--config", default="configs/tenants/demo.yaml")
    ap.add_argument("--raw", default="data/raw/run1", help="directory or parquet file with raw records")
    ap.add_argument("--job-id", default=None)
    ap.add_argument("--sink", default="jsonl", choices=["jsonl", "kafka"])
    ap.add_argument("--format", default=None, choices=[None, "delta", "parquet"])
    args = ap.parse_args()
    overrides = {"storage": {"format": args.format}} if args.format else None
    cfg = load_config(args.config, overrides)
    summary = run(cfg, args.raw, job_id=args.job_id, sink=args.sink)
    print(f"job_id={summary.job_id} records={summary.records} pairs={summary.pairs} edges={summary.edges} "
          f"clusters={summary.clusters} format={summary.storage_format} cdc_events={summary.cdc_events} "
          f"hygiene={summary.hygiene} duration={summary.duration_s}s")
    if summary.delta_error:
        print(f"note: Delta unavailable, fell back to Parquet ({summary.delta_error})")
    print(summary.jitter_line())


if __name__ == "__main__":
    main()
