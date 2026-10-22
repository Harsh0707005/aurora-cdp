"""Normalisation extensions: nickname CSV loader and opt-in address parsing (default output unchanged)."""

from __future__ import annotations

import pandas as pd
import pytest

from aurora_cdp.config import load_config
from aurora_cdp.ingestion.normalize import (
    NICKNAMES,
    canonical_address,
    canonical_given_name,
    load_nicknames,
    parse_address,
    preprocess_records,
)
from aurora_cdp.ingestion.semantics import RAW_COLUMNS

CFG = load_config(use_last_best=False)
ABBR = CFG.normalize["address_abbreviations"]


def _raw(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in RAW_COLUMNS:
        if c not in df.columns:
            df[c] = None
    df["batch_id"], df["row_hash"], df["tagged_at"] = "b1", "h", pd.Timestamp("2026-01-01")
    return df[RAW_COLUMNS]


# ----------------------------------------------------------------------------------------- nicknames
def test_builtin_nicknames_unchanged_without_file():
    assert load_nicknames(None) is NICKNAMES
    assert canonical_given_name("Mike") == "MICHAEL" and canonical_given_name("Zed") == "ZED"


def test_nickname_csv_extends_and_overrides(tmp_path):
    f = tmp_path / "nick.csv"
    f.write_text("nickname,canonical\nZed,Zedekiah\nmike,MIKAEL\n\n")
    table = load_nicknames(f)
    assert table["ZED"] == "ZEDEKIAH" and table["MIKE"] == "MIKAEL" and table["BOB"] == "ROBERT"
    assert NICKNAMES["MIKE"] == "MICHAEL", "the built-in table is never mutated"
    assert load_nicknames(f) is table, "cached per path"
    assert canonical_given_name("Zed Q", table) == "ZEDEKIAH"
    cfg = load_config(use_last_best=False, overrides={"normalize": {"nickname_file": str(f)}})
    pre = preprocess_records(_raw([{"datasource": "s", "pk": "1", "given_name": "zed"}]), cfg)
    assert pre.loc[0, "given_name_canon"] == "ZEDEKIAH"


def test_nickname_csv_without_header_and_bad_rows(tmp_path):
    f = tmp_path / "n.csv"
    f.write_text("Peg,Margaret\n")
    assert load_nicknames(f)["PEG"] == "MARGARET"
    bad = tmp_path / "bad.csv"
    bad.write_text("onlyone\n")
    with pytest.raises(ValueError):
        load_nicknames(bad)
    with pytest.raises(FileNotFoundError):
        load_nicknames(tmp_path / "missing.csv")


# ----------------------------------------------------------------------------------------- addresses
@pytest.mark.parametrize(
    "value, expected",
    [
        ("12 Main St Apt 4B", "12 MAIN STREET APARTMENT 4B"),
        ("12 MAIN STREET #4B", "12 MAIN STREET 4B"),
        ("P.O. Box 123", "PO BOX 123"),
        ("123 Main St NW", "123 MAIN STREET NW"),
        ("1 2nd Ave S", "1 SECOND AVENUE SOUTH"),
        (None, None),
        ("", None),
    ],
)
def test_default_address_normalisation_is_unchanged(value, expected):
    assert canonical_address(value, ABBR) == expected
    assert canonical_address(value, ABBR, parse=False) == expected


def test_address_parsing_canonicalises_units_po_box_and_directionals():
    same = [
        "12 Main St Apt 4B",
        "12 MAIN STREET #4B",
        "12 main st., apt. 4b",
        "12 Main Street Suite 4B",
        "12 Main St APT4B",
    ]
    assert {canonical_address(a, ABBR, parse=True) for a in same} == {"12 MAIN STREET UNIT 4B"}
    assert (
        canonical_address("P.O. Box 123", ABBR, parse=True)
        == canonical_address("POB 123", ABBR, parse=True)
        == "PO BOX 123"
    )
    assert canonical_address("Post Office Box 77", ABBR, parse=True) == "PO BOX 77"
    assert canonical_address("123 Main St NW", ABBR, parse=True) == canonical_address(
        "123 Main Street Northwest", ABBR, parse=True
    )
    assert canonical_address("123 N.W. Main St", ABBR, parse=True) == "123 NORTHWEST MAIN STREET"
    assert (
        canonical_address("123 main st nw ste 200", ABBR, parse=True)
        == "123 MAIN STREET NORTHWEST UNIT 200"
    )
    assert canonical_address("12 Main St Floor 3", ABBR, parse=True) == "12 MAIN STREET FLOOR 3"
    assert canonical_address(None, ABBR, parse=True) is None


def test_parse_address_components():
    p = parse_address("12 Main St NW Apt 4B", ABBR)
    assert p == {
        "house_number": "12",
        "street": "MAIN STREET NORTHWEST",
        "unit": "UNIT 4B",
        "po_box": None,
        "canonical": "12 MAIN STREET NORTHWEST UNIT 4B",
    }
    assert parse_address("PO Box 9", ABBR)["po_box"] == "9"
    assert parse_address("Main Street", ABBR)["house_number"] is None
    assert parse_address(None, ABBR)["canonical"] is None


def test_address_parsing_is_opt_in_through_config():
    rows = _raw([{"datasource": "s", "pk": "1", "address": "12 Main St #4B"}])
    assert preprocess_records(rows, CFG).loc[0, "address_norm"] == "12 MAIN STREET 4B"
    on = load_config(use_last_best=False, overrides={"normalize": {"address_parsing": True}})
    assert preprocess_records(rows, on).loc[0, "address_norm"] == "12 MAIN STREET UNIT 4B"
