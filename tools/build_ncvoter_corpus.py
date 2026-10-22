"""Build a real-PII evaluation corpus from North Carolina voter-registration snapshots.

Source: https://www.ncsbe.gov/results-data/voter-registration-data (public record; statewide point-in-time
snapshots `VR_Snapshot_YYYYMMDD.zip`, UTF-16LE tab-delimited). Each snapshot becomes one *source*; a voter's NCID is
the ground-truth person id, so the corpus tests the engine on real names, real street addresses, real households and
real year-over-year drift (moves, name changes, corrections). What it cannot test: e-mail (absent) and exact birth
dates (only age at snapshot is published, so `dob` is `(snapshot year - age)-01-01`, i.e. year granularity with a
±1-year wobble between snapshots).

Usage (files already converted to UTF-8, see tools/ncvoter_fetch.sh):
    python tools/build_ncvoter_corpus.py --tsv vr2023=VR_Snapshot_20230101.tsv --tsv vr2024=... --tsv vr2025=... \
        --out ~/data/aurora-testdata/ncvoter-7m --target-profiles 7000000 --seed 42 --window-days 365
Writes profiles/truth parquet + manifest.json in the aurora-eval-harness format (its `public_datasets` helpers).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

from aurora_eval.public_datasets import sample_by_person, to_dataset, write  # harness helpers (installed in its venv)

ADDRESS_PARTS = ["house_num", "half_code", "street_dir", "street_name", "street_type_cd", "street_sufx_cd", "unit_designator", "unit_num"]


def load_snapshot(con: duckdb.DuckDBPyConnection, source: str, path: Path, statuses: list[str] | None = None) -> None:
    addr = " || ' ' || ".join(f"COALESCE(NULLIF(TRIM({c}), ''), '')" for c in ADDRESS_PARTS)
    status_filter = ""
    if statuses:
        quoted = ", ".join("'" + x.upper().replace("'", "") + "'" for x in statuses)
        status_filter = f"AND upper(TRIM(voter_status_desc)) IN ({quoted})"
    con.execute(
        f"""
        INSERT INTO profiles
        SELECT '{source}' || ':' || TRIM(ncid) || ':' || TRIM(county_id) || ':' || TRIM(voter_reg_num) AS profile_id,
               '{source}' AS source,
               CAST(snapshot_dt AS DATE) AS created_at,
               NULLIF(TRIM(first_name), '') AS first_name,
               NULLIF(TRIM(last_name), '') AS last_name,
               '' AS email,
               CASE WHEN length(regexp_replace(COALESCE(area_cd, '') || COALESCE(phone_num, ''), '[^0-9]', '', 'g')) = 10
                    THEN regexp_replace(COALESCE(area_cd, '') || COALESCE(phone_num, ''), '[^0-9]', '', 'g') ELSE '' END AS phone,
               CASE WHEN TRY_CAST(TRIM(age) AS INTEGER) BETWEEN 17 AND 120
                    THEN CAST(year(CAST(snapshot_dt AS DATE)) - CAST(TRIM(age) AS INTEGER) AS VARCHAR) || '-01-01' ELSE '' END AS dob,
               NULLIF(TRIM(regexp_replace({addr}, ' +', ' ', 'g')), '') AS address,
               NULLIF(TRIM(res_city_desc), '') AS city,
               NULLIF(substr(TRIM(zip_code), 1, 5), '') AS postal_code,
               TRIM(ncid) AS person_id,
               NULLIF(TRIM(voter_status_desc), '') AS status,
               NULLIF(TRIM(county_desc), '') AS county
        FROM read_csv('{path}', delim='\\t', header=true, quote='', escape='', all_varchar=true, ignore_errors=true,
                      strict_mode=false, null_padding=true)
        WHERE ncid IS NOT NULL AND TRIM(ncid) <> '' {status_filter}
        """
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tsv", action="append", required=True, help="source=path, e.g. vr2023=/data/VR_Snapshot_20230101.tsv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-profiles", type=int, default=None, help="seeded whole-person sample down to ~this many rows")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--window-days", type=int, default=365, help="one harness window per snapshot (snapshots a year apart)")
    ap.add_argument("--db", default=None, help="DuckDB file to use as scratch (default: in-memory)")
    ap.add_argument("--statuses", default="ACTIVE,INACTIVE",
                    help="voter_status_desc values to keep (comma list; 'all' keeps REMOVED/DENIED/TEMPORARY too). Removed voters "
                         "keep a frozen record in every later snapshot, which only adds identical cross-snapshot pairs")
    a = ap.parse_args()

    con = duckdb.connect(a.db or ":memory:")
    con.execute("CREATE TABLE profiles (profile_id VARCHAR, source VARCHAR, created_at DATE, first_name VARCHAR, last_name VARCHAR, "
                "email VARCHAR, phone VARCHAR, dob VARCHAR, address VARCHAR, city VARCHAR, postal_code VARCHAR, person_id VARCHAR, "
                "status VARCHAR, county VARCHAR)")
    sources = []
    for spec in a.tsv:
        source, path = spec.split("=", 1)
        statuses = None if a.statuses.strip().lower() == "all" else [x.strip() for x in a.statuses.split(",") if x.strip()]
        load_snapshot(con, source, Path(path).expanduser(), statuses)
        n = con.execute("SELECT COUNT(*) FROM profiles WHERE source = ?", [source]).fetchone()[0]
        print(f"{source}: {n:,} rows from {path}", flush=True)
        sources.append(source)
    df = con.execute("SELECT * FROM profiles").df()
    print(f"total {len(df):,} rows, {df['person_id'].nunique():,} persons", flush=True)
    if a.target_profiles:
        df = sample_by_person(df, "person_id", a.target_profiles, a.seed)
        print(f"sampled {len(df):,} rows, {df['person_id'].nunique():,} persons (seed {a.seed})", flush=True)
    person = df.pop("person_id")
    for c in ("first_name", "last_name", "address", "city", "postal_code", "phone", "dob", "email"):
        df[c] = df[c].fillna("")
    status_counts = df["status"].value_counts().to_dict()
    ds = to_dataset(
        "ncvoter", df, person,
        extras={"source_snapshots": sources, "seed": a.seed, "target_profiles": a.target_profiles, "statuses": a.statuses,
                "notes": "NC voter registration snapshots; person = NCID; dob = snapshot year - age (year granularity); no e-mail",
                "license": "North Carolina public record (NCSBE)"},
        counts_extra={"status": status_counts, "records_with_phone": int((df["phone"] != "").sum()),
                      "records_with_dob": int((df["dob"] != "").sum()), "records_with_address": int((df["address"] != "").sum())},
    )
    ds.manifest["window_days"] = a.window_days
    ds.manifest["n_windows_at_30d"] = None
    ds.manifest["n_windows"] = int(ds.manifest["timeline_days"] // a.window_days) + 1
    out = write(ds, Path(a.out).expanduser(), fmt="parquet")
    print(json.dumps(ds.manifest["counts"], indent=1)[:1500])
    print("->", out)


if __name__ == "__main__":
    main()
