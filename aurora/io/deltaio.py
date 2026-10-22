"""Spark session factory and Delta/Parquet table I/O with graceful fallback.

Delta is preferred. If the Delta jars cannot be resolved (offline laptop, no
Ivy cache) the session silently falls back to Parquet and records the choice
in ``LakeIO.format`` so the pipeline can report it. The API never needs Spark:
``read_table_pandas`` reads the latest snapshot with pyarrow, parsing the
Delta transaction log when present.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from aurora.config.schema import TenantConfig

DELTA_SESSION_FAILED: str | None = None


def build_spark(cfg: TenantConfig):
    """Build a SparkSession; try Delta first, fall back to Parquet."""
    global DELTA_SESSION_FAILED
    from pyspark.sql import SparkSession

    master = os.environ.get("AURORA_SPARK_MASTER", cfg.spark.master)
    builder = (
        SparkSession.builder.appName(cfg.spark.app_name)
        .master(master)
        .config("spark.sql.shuffle.partitions", str(cfg.spark.shuffle_partitions))
        .config("spark.driver.memory", cfg.spark.driver_memory)
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
    )
    for k, v in cfg.spark.extra.items():
        builder = builder.config(k, v)
    fmt = cfg.storage.format
    if fmt == "delta":
        try:
            from delta import configure_spark_with_delta_pip

            b2 = builder.config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension").config(
                "spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"
            )
            spark = configure_spark_with_delta_pip(b2).getOrCreate()
            probe = Path(".tmp/delta_probe")
            shutil.rmtree(probe, ignore_errors=True)
            spark.createDataFrame([(1,)], ["x"]).write.format("delta").mode("overwrite").save(str(probe))
            shutil.rmtree(probe, ignore_errors=True)
            return spark, "delta"
        except Exception as exc:  # noqa: BLE001 - any failure means "no delta"
            DELTA_SESSION_FAILED = f"{type(exc).__name__}: {str(exc)[:200]}"
            try:
                SparkSession.getActiveSession() and SparkSession.getActiveSession().stop()
            except Exception:  # noqa: BLE001
                pass
    return builder.getOrCreate(), "parquet"


class LakeIO:
    """Thin writer/reader over ``<lake_root>/<table>``."""

    def __init__(self, spark, lake_root: str | Path, fmt: str) -> None:
        self.spark = spark
        self.root = Path(lake_root)
        self.format = fmt
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, table: str) -> Path:
        return self.root / table

    def write(self, df, table: str, mode: str = "overwrite", partition_by: list[str] | None = None) -> Path:
        p = self.path(table)
        w = df.write.format(self.format).mode(mode)
        if self.format == "delta":
            w = w.option("overwriteSchema", "true") if mode == "overwrite" else w.option("mergeSchema", "true")
        if partition_by:
            w = w.partitionBy(*partition_by)
        w.save(str(p))
        return p

    def write_pandas(self, pdf: pd.DataFrame, table: str, mode: str = "overwrite") -> Path:
        from pyspark.sql import functions as F
        from pyspark.sql import types as T

        sdf = self.spark.createDataFrame(pdf.astype(object).where(pd.notna(pdf), None))
        # all-null pandas columns arrive as NullType; Delta refuses to append void columns later
        for f in sdf.schema.fields:
            if isinstance(f.dataType, T.NullType):
                sdf = sdf.withColumn(f.name, F.col(f.name).cast("string"))
        return self.write(sdf, table, mode=mode)

    def read(self, table: str):
        return self.spark.read.format(self.format).load(str(self.path(table)))

    def exists(self, table: str) -> bool:
        return self.path(table).exists() and any(self.path(table).iterdir())


# ------------------------------------------------------------------ Spark-free readers


def _delta_active_files(table_dir: Path) -> list[Path] | None:
    """Replay the Delta log (checkpoint + json commits) to list live data files."""
    log = table_dir / "_delta_log"
    if not log.exists():
        return None
    active: set[str] = set()
    start = 0
    last_cp = log / "_last_checkpoint"
    if last_cp.exists():
        version = json.loads(last_cp.read_text())["version"]
        for cp in sorted(log.glob(f"{version:020d}.checkpoint*.parquet")):
            t = pq.read_table(cp).to_pandas()
            if "add" in t:
                for a in t["add"].dropna():
                    if a and a.get("path"):
                        active.add(a["path"])
            if "remove" in t:
                for r in t["remove"].dropna():
                    if r and r.get("path"):
                        active.discard(r["path"])
        start = version + 1
    for commit in sorted(log.glob("*.json")):
        if int(commit.stem) < start:
            continue
        for line in commit.read_text().splitlines():
            if not line.strip():
                continue
            action = json.loads(line)
            if "add" in action:
                active.add(action["add"]["path"])
            elif "remove" in action:
                active.discard(action["remove"]["path"])
    return [table_dir / p for p in sorted(active)]


def read_table_pandas(lake_root: str | Path, table: str, columns: list[str] | None = None) -> pd.DataFrame:
    """Read the latest snapshot of a lake table without Spark."""
    d = Path(lake_root) / table
    if not d.exists():
        return pd.DataFrame()
    files = _delta_active_files(d)
    if files is None:
        files = sorted(p for p in d.rglob("*.parquet") if not p.name.startswith("_"))
    if not files:
        return pd.DataFrame()
    frames = [pq.read_table(f, columns=columns).to_pandas() for f in files]
    return pd.concat(frames, ignore_index=True)


def table_exists(lake_root: str | Path, table: str) -> bool:
    return (Path(lake_root) / table).exists()
