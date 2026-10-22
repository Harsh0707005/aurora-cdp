"""Synthetic multi-source customer generator with planted ground truth.

Each base customer gets a ``truth_id``; records for that customer are emitted
into one or more sources (web, store, loyalty) with controlled noise: typos,
nickname swaps, missing fields, alternate emails/phones, bad placeholder values.
Some pairs of distinct customers are made to *look* alike (shared household
address, family surname) to exercise the over-merge guard. The generator is
fully seeded for reproducibility.

The second-run "drift" variant (``apply_drift``) mutates a base dataset so the
evaluation suite can measure stable-ID churn between two runs.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from faker import Faker

PLACEHOLDER_EMAILS = ["test@test.com", "noemail@noemail.com", "none@none.com", "na@na.com"]
PLACEHOLDER_PHONES = ["0000000000", "1111111111", "1234567890", "9999999999"]
NICKS = {
    "william": "bill", "robert": "bob", "elizabeth": "liz", "james": "jim", "michael": "mike",
    "katherine": "kate", "thomas": "tom", "richard": "rick", "christopher": "chris",
    "jennifer": "jen", "daniel": "dan", "joseph": "joe", "samuel": "sam", "alexander": "alex",
    "andrew": "andy", "nicholas": "nick", "anthony": "tony", "patricia": "pat", "susan": "sue",
    "margaret": "peggy",
}


@dataclass
class SynthParams:
    size: int = 100_000
    seed: int = 42
    dup_rate: float = 0.55  # fraction of customers that appear in >1 source
    noise_rate: float = 0.25
    missing_rate: float = 0.12
    placeholder_rate: float = 0.02
    household_rate: float = 0.03  # distinct people sharing address+surname (hard negatives)


def _typo(s: str, rng: random.Random) -> str:
    if len(s) < 3:
        return s
    i = rng.randrange(len(s) - 1)
    op = rng.random()
    if op < 0.4:
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if op < 0.7:
        return s[:i] + s[i + 1:]
    return s[:i] + rng.choice("abcdefghijklmnopqrstuvwxyz") + s[i:]


def _base_customers(n: int, rng: random.Random, fake: Faker, p: SynthParams) -> list[dict]:
    customers = []
    for i in range(n):
        given = fake.first_name().lower()
        surname = fake.last_name().lower()
        customers.append(
            {
                "truth_id": f"T{i:07d}",
                "given_name": given,
                "surname": surname,
                "email": f"{given}.{surname}{rng.randrange(1000)}@{fake.free_email_domain()}",
                "phone": fake.numerify("##########"),
                "address": fake.street_address(),
                "city": fake.city(),
                "state": fake.state_abbr(),
                "postal": fake.postcode(),
                "country": "US",
                "birthdate": fake.date_of_birth(minimum_age=18, maximum_age=85).isoformat(),
                "gender": rng.choice(["F", "M", None]),
                "loyalty_id": f"L{rng.randrange(10**8):08d}" if rng.random() < 0.4 else None,
            }
        )
    # Households: distinct people sharing surname + address (+ sometimes phone).
    n_house = int(n * p.household_rate)
    for _ in range(n_house):
        a, b = rng.sample(range(n), 2)
        customers[b]["surname"] = customers[a]["surname"]
        customers[b]["address"] = customers[a]["address"]
        customers[b]["postal"] = customers[a]["postal"]
        customers[b]["city"] = customers[a]["city"]
        if rng.random() < 0.5:
            customers[b]["phone"] = customers[a]["phone"]
    return customers


def _emit_record(c: dict, source: str, idx: int, rng: random.Random, p: SynthParams) -> dict:
    r = dict(c)
    r["datasource"] = source
    r["pk"] = f"{source}-{idx:08d}"
    r["full_name"] = None
    r["updated_at"] = f"2026-{rng.randrange(1, 10):02d}-{rng.randrange(1, 28):02d}"
    if source == "web":
        r["loyalty_id"] = r["loyalty_id"] if rng.random() < 0.3 else None
        r["address"] = r["address"] if rng.random() < 0.6 else None
    if source == "store":
        r["email"] = r["email"] if rng.random() < 0.55 else None
        r["birthdate"] = r["birthdate"] if rng.random() < 0.4 else None
        r["loyalty_id"] = r["loyalty_id"] if rng.random() < 0.6 else None
    if source == "loyalty":
        r["loyalty_id"] = c["loyalty_id"] or f"L{rng.randrange(10**8):08d}"
    # Random noise
    if rng.random() < p.noise_rate:
        which = rng.random()
        if which < 0.3 and r["given_name"] in NICKS:
            r["given_name"] = NICKS[r["given_name"]]
        elif which < 0.55:
            r["surname"] = _typo(r["surname"], rng)
        elif which < 0.75 and r["email"]:
            local, _, dom = r["email"].partition("@")
            r["email"] = f"{local}+{rng.randrange(99)}@{dom}" if rng.random() < 0.5 else _typo(local, rng) + "@" + dom
        elif which < 0.9 and r["phone"]:
            r["phone"] = "(" + r["phone"][:3] + ") " + r["phone"][3:6] + "-" + r["phone"][6:]
        else:
            r["full_name"] = f"{r['given_name']} {r['surname']}".title()
            r["given_name"] = None
            r["surname"] = None
    for col in ("email", "phone", "birthdate", "postal", "address"):
        if r.get(col) and rng.random() < p.missing_rate:
            r[col] = None
    if rng.random() < p.placeholder_rate:
        r["email"] = rng.choice(PLACEHOLDER_EMAILS)
    if rng.random() < p.placeholder_rate:
        r["phone"] = rng.choice(PLACEHOLDER_PHONES)
    return r


def generate(p: SynthParams) -> pd.DataFrame:
    """Return a DataFrame of source records with ``truth_id`` ground truth."""
    rng = random.Random(p.seed)
    fake = Faker("en_US")
    Faker.seed(p.seed)
    customers = _base_customers(p.size, rng, fake, p)
    rows: list[dict] = []
    counters = {"web": 0, "store": 0, "loyalty": 0}
    for c in customers:
        sources = [rng.choice(["web", "store", "loyalty"])]
        if rng.random() < p.dup_rate:
            extra = rng.sample(["web", "store", "loyalty"], rng.choice([1, 2]))
            sources = list(dict.fromkeys(sources + extra))
        if rng.random() < 0.08:  # same-source duplicate
            sources.append(sources[0])
        for s in sources:
            counters[s] += 1
            rows.append(_emit_record(c, s, counters[s], rng, p))
    df = pd.DataFrame(rows)
    cols = ["datasource", "pk", "given_name", "surname", "full_name", "email", "phone", "address",
            "city", "state", "postal", "country", "birthdate", "loyalty_id", "gender", "updated_at",
            "truth_id"]
    return df[cols].astype(object).where(pd.notna(df[cols]), None)


def apply_drift(df: pd.DataFrame, seed: int = 7, add_frac: float = 0.03, drop_frac: float = 0.02,
                mutate_frac: float = 0.03) -> pd.DataFrame:
    """Simulate a later load: drop some rows, add new customers, mutate some fields."""
    rng = random.Random(seed)
    fake = Faker("en_US")
    Faker.seed(seed)
    df = df.copy()
    keep = df.sample(frac=1 - drop_frac, random_state=seed)
    n_new = int(len(df) * add_frac)
    p = SynthParams(size=n_new, seed=seed + 1)
    new_customers = _base_customers(n_new, rng, fake, p)
    counters = {"web": 0, "store": 0, "loyalty": 0}
    start = {s: int(df[df.datasource == s].pk.str[-8:].astype(int).max()) + 1 for s in counters}
    new_rows = []
    for i, c in enumerate(new_customers):
        c["truth_id"] = f"N{i:07d}"
        s = rng.choice(list(counters))
        counters[s] += 1
        new_rows.append(_emit_record(c, s, start[s] + counters[s], rng, p))
    out = pd.concat([keep, pd.DataFrame(new_rows)], ignore_index=True)
    idx = out.sample(frac=mutate_frac, random_state=seed + 2).index
    for i in idx:
        if out.at[i, "email"]:
            out.at[i, "email"] = fake.email()
        elif out.at[i, "phone"]:
            out.at[i, "phone"] = fake.numerify("##########")
    return out.astype(object).where(pd.notna(out), None)


def write(df: pd.DataFrame, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "records.parquet"
    df.to_parquet(path, index=False)
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic multi-source customer data")
    ap.add_argument("--size", type=int, default=100_000, help="number of base customers")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/raw/run1")
    ap.add_argument("--drift-out", default="data/raw/run2", help="also write a drifted copy")
    args = ap.parse_args()
    df = generate(SynthParams(size=args.size, seed=args.seed))
    path = write(df, Path(args.out))
    print(f"wrote {len(df)} records for {args.size} customers -> {path}")
    if args.drift_out:
        d = apply_drift(df, seed=args.seed + 100)
        path2 = write(d, Path(args.drift_out))
        print(f"wrote drifted copy ({len(d)} records) -> {path2}")


if __name__ == "__main__":
    main()
