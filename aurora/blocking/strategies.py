"""DNF-style blocking strategies producing candidate pairs in Spark.

Each strategy derives a ``block_key`` column from the standardised record
frame. Candidate pairs are built with a self-join on the key inside each
strategy, guarded by ``max_block_size`` (buckets larger than this are skipped
and reported in the blocking diagnostics). Pairs are deduplicated across
strategies and canonically ordered (``left < right`` by ``(datasource, pk)``).
"""

from __future__ import annotations

from collections.abc import Callable

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from aurora.config.schema import BlockingConfig, BlockingStrategy

KeyBuilder = Callable[[DataFrame, dict], Column]


def _email_exact(df: DataFrame, params: dict) -> Column:
    return F.col("email_std")


def _email_canonical(df: DataFrame, params: dict) -> Column:
    return F.col("email_canon")


def _name_prefix(df: DataFrame, params: dict) -> Column:
    n = int(params.get("given_prefix", 3))
    return F.when(
        F.col("given_nick").isNotNull() & F.col("surname_std").isNotNull(),
        F.concat_ws("|", F.substring(F.col("given_nick"), 1, n), F.col("surname_std")),
    )


def _phone_e164(df: DataFrame, params: dict) -> Column:
    return F.col("phone_std")


def _phone_prefix(df: DataFrame, params: dict) -> Column:
    n = int(params.get("digits", 8))
    return F.substring(F.col("phone_std"), 1, n)


def _address(df: DataFrame, params: dict) -> Column:
    return F.when(
        F.col("postal_std").isNotNull() & F.col("house_no").isNotNull(),
        F.concat_ws("|", F.col("postal_std"), F.col("house_no")),
    )


def _fk(df: DataFrame, params: dict) -> Column:
    col = params.get("column", "loyalty_id")
    namespace = params.get("namespace", col)
    return F.when(F.col(col).isNotNull(), F.concat_ws(":", F.lit(namespace), F.col(col)))


BUILDERS: dict[str, KeyBuilder] = {
    "email_exact": _email_exact,
    "email_canonical": _email_canonical,
    "name_prefix": _name_prefix,
    "phone_e164": _phone_e164,
    "phone_prefix": _phone_prefix,
    "address": _address,
    "fk": _fk,
}


def register_strategy(kind: str, builder: KeyBuilder) -> None:
    """Custom hook: register a new key builder under ``kind``."""
    BUILDERS[kind] = builder


def block_keys(df: DataFrame, strategy: BlockingStrategy) -> DataFrame:
    """Return (rid, strategy, block_key) for non-null keys."""
    key = BUILDERS[strategy.kind](df, strategy.params)
    return (
        df.select("rid", key.alias("block_key"))
        .where(F.col("block_key").isNotNull())
        .withColumn("strategy", F.lit(strategy.name))
    )


def candidate_pairs(df: DataFrame, cfg: BlockingConfig) -> tuple[DataFrame, DataFrame]:
    """Build deduplicated candidate pairs ``(rid_l, rid_r, strategies)`` and stats.

    ``rid`` must be a monotonically comparable integer id on ``df``.
    """
    enabled = [s for s in cfg.strategies if s.enabled]
    if not enabled:
        raise ValueError("no blocking strategies enabled")
    keyed = None
    for s in enabled:
        k = block_keys(df, s).withColumn("max_block_size", F.lit(s.max_block_size))
        keyed = k if keyed is None else keyed.unionByName(k)
    assert keyed is not None
    sizes = keyed.groupBy("strategy", "block_key", "max_block_size").agg(F.count("*").alias("n"))
    stats = sizes.groupBy("strategy").agg(
        F.count("*").alias("blocks"),
        F.sum("n").alias("keyed_records"),
        F.sum(F.when(F.col("n") > F.col("max_block_size"), 1).otherwise(0)).alias("skipped_blocks"),
        F.sum(F.when(F.col("n") <= F.col("max_block_size"), (F.col("n") * (F.col("n") - 1)) / 2)
              .otherwise(0)).alias("pairs"),
        F.max("n").alias("largest_block"),
    )
    ok = sizes.where((F.col("n") > 1) & (F.col("n") <= F.col("max_block_size"))).select(
        "strategy", "block_key"
    )
    keyed_ok = keyed.join(ok, ["strategy", "block_key"])
    a = keyed_ok.select(F.col("rid").alias("rid_l"), "strategy", "block_key")
    b = keyed_ok.select(F.col("rid").alias("rid_r"), "strategy", "block_key")
    pairs = (
        a.join(b, ["strategy", "block_key"])
        .where(F.col("rid_l") < F.col("rid_r"))
        .groupBy("rid_l", "rid_r")
        .agg(F.collect_set("strategy").alias("strategies"))
    )
    return pairs, stats
