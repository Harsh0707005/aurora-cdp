"""Blocking strategies: keys, guard, pair dedup. Uses a local SparkSession."""

import os
import sys

import pytest
from pyspark.sql import SparkSession

from aurora.blocking.strategies import candidate_pairs
from aurora.config.schema import BlockingConfig, BlockingStrategy


@pytest.fixture(scope="module")
def spark():
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    s = (SparkSession.builder.master("local[2]").appName("aurora-test")
         .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "2").getOrCreate())
    yield s
    s.stop()


def _std(spark):
    rows = [
        (1, "a@x.com", "a@x.com", "15551110000", "jon", "jonathan", "smith", "1 main st", "1", "02134", None),
        (2, "a@x.com", "a@x.com", None, "jonathan", "jonathan", "smith", None, None, None, "L1"),
        (3, None, None, "15551110000", "mary", "mary", "jones", "9 elm st", "9", "02134", "L1"),
        (4, "z@y.com", "z@y.com", "15559990000", "mary", "mary", "jones", "1 main st", "1", "02134", None),
        (5, "q@y.com", "q@y.com", None, "bob", "robert", "brown", None, None, None, None),
    ]
    cols = ["rid", "email_std", "email_canon", "phone_std", "given_std", "given_nick", "surname_std",
            "street_std", "house_no", "postal_std", "loyalty_id"]
    return spark.createDataFrame(rows, cols)


def test_pairs_from_multiple_strategies(spark):
    cfg = BlockingConfig(strategies=[
        BlockingStrategy(name="email", kind="email_exact"),
        BlockingStrategy(name="phone", kind="phone_e164"),
        BlockingStrategy(name="addr", kind="address"),
        BlockingStrategy(name="fk", kind="fk", params={"column": "loyalty_id"}),
        BlockingStrategy(name="name", kind="name_prefix", params={"given_prefix": 3}),
    ])
    pairs, stats = candidate_pairs(_std(spark), cfg)
    got = {(r.rid_l, r.rid_r): set(r.strategies) for r in pairs.collect()}
    assert got[(1, 2)] == {"email", "name"}
    assert got[(1, 3)] == {"phone"}
    assert got[(2, 3)] == {"fk"}
    assert got[(1, 4)] == {"addr"}
    assert got[(3, 4)] == {"name"}
    assert (4, 5) not in got and (1, 5) not in got
    st = {r.strategy: r for r in stats.collect()}
    assert st["email"].pairs == 1 and st["email"].skipped_blocks == 0


def test_block_size_guard_skips_large_blocks(spark):
    cfg = BlockingConfig(strategies=[BlockingStrategy(name="name", kind="name_prefix", max_block_size=1)])
    pairs, stats = candidate_pairs(_std(spark), cfg)
    assert pairs.count() == 0
    assert stats.collect()[0].skipped_blocks == 2  # jon|smith and mar|jones blocks of size 2
