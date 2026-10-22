"""Synthesize a small multi-source customer dataset with ground-truth labels and run it end to end.

Sources (each with its own schema, mapped via semantics):
- crm/customers      full profile, some typos, update timestamps
- ecommerce/accounts nicknames, alternate emails, duplicate accounts, fk to loyalty
- loyalty/members    customer key (ck), full name, email, phone, birthdate
- pos/customers      name + phone/postal only
- pos/orders         interaction feed: fk-pos -> pos customer, feeds the profile timeline

Every profile row carries `truth_id` (the simulated person) for tuning/evaluation only; it is not a
semantic and never reaches matching. A second "late" batch (new people + updates) is ingested
incrementally so the demo exercises stable IDs and the jitter report across two Stitch runs.
"""

from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml

from aurora_cdp.config import Config, load_config
from aurora_cdp.orchestration.pipeline import PipelineResult, append_run_history, run_pipeline
from aurora_cdp.storage.duck import connect, init_schema

FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "William", "Elizabeth",
         "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen",
         "Christopher", "Nancy", "Daniel", "Margaret", "Matthew", "Lisa", "Anthony", "Betty", "Andrew", "Sandra",
         "Steven", "Ashley", "Edward", "Kimberly", "Katherine", "Rebecca", "Timothy", "Abigail", "Ronald", "Allison"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
        "Nguyen", "Chen", "Patel", "Kim", "Okafor", "Singh", "Rossi", "Novak", "Schmidt", "Dubois"]
NICK = {"James": "Jim", "Robert": "Bob", "John": "Jack", "Michael": "Mike", "William": "Bill", "Elizabeth": "Liz",
        "Richard": "Rick", "Joseph": "Joe", "Thomas": "Tom", "Christopher": "Chris", "Daniel": "Dan", "Matthew": "Matt",
        "Anthony": "Tony", "Andrew": "Andy", "Steven": "Steve", "Edward": "Ed", "Katherine": "Kate", "Rebecca": "Becky",
        "Timothy": "Tim", "Abigail": "Abby", "Ronald": "Ron", "Allison": "Allie", "Margaret": "Peggy", "Patricia": "Pat",
        "Jennifer": "Jen", "Susan": "Sue", "Charles": "Chuck", "Edward": "Ted"}
STREETS = ["Elm St", "Main St", "Oak Ave", "Pine Rd", "Maple Dr", "Cedar Ln", "1st Ave", "Lake Blvd", "Hill Ct", "Park Ave"]
CITIES = [("Seattle", "WA", "98101"), ("Portland", "OR", "97201"), ("Austin", "TX", "78701"), ("Denver", "CO", "80202"),
          ("Boston", "MA", "02108"), ("Chicago", "IL", "60601"), ("Miami", "FL", "33101"), ("Phoenix", "AZ", "85001")]
DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "example.org", "mail.com"]


@dataclass
class Person:
    truth_id: str
    first: str
    last: str
    email: str
    alt_email: str
    phone: str
    street: str
    city: str
    state: str
    postal: str
    birthdate: str
    loyalty: str | None


def _typo(s: str, rng: random.Random) -> str:
    if len(s) < 4:
        return s
    i = rng.randrange(1, len(s) - 1)
    kind = rng.random()
    if kind < 0.4:
        return s[:i] + s[i + 1 :]  # deletion
    if kind < 0.8:
        return s[:i] + s[i + 1] + s[i] + s[i + 2 :]  # transposition
    return s[:i] + rng.choice("aeiou") + s[i + 1 :]  # substitution


def _fmt_phone(digits: str, rng: random.Random) -> str:
    styles = [
        lambda d: f"({d[:3]}) {d[3:6]}-{d[6:]}",
        lambda d: f"{d[:3]}-{d[3:6]}-{d[6:]}",
        lambda d: f"+1{d}",
        lambda d: d,
        lambda d: f"{d[:3]}.{d[3:6]}.{d[6:]}",
    ]
    return rng.choice(styles)(digits)


def make_people(n: int, rng: random.Random) -> list[Person]:
    people = []
    for i in range(n):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        city, state, postal = rng.choice(CITIES)
        dom = rng.choice(DOMAINS)
        email = f"{first.lower()}.{last.lower()}{rng.randrange(1, 999)}@{dom}"
        alt = f"{first[0].lower()}{last.lower()}{rng.randrange(1, 99)}@{rng.choice(DOMAINS)}"
        phone = f"{rng.randrange(201, 989)}{rng.randrange(200, 999)}{rng.randrange(1000, 9999)}"
        bd = datetime(rng.randrange(1945, 2004), rng.randrange(1, 13), rng.randrange(1, 29)).strftime("%Y-%m-%d")
        loyalty = f"LOY{100000 + i}" if rng.random() < 0.6 else None
        people.append(Person(f"P{i:05d}", first, last, email, alt, phone, f"{rng.randrange(1, 9999)} {rng.choice(STREETS)}", city, state, postal, bd, loyalty))
    return people


def synthesize(people: list[Person], rng: random.Random, start_dt: datetime) -> dict[str, pd.DataFrame]:
    crm, ecom, loy, pos, orders = [], [], [], [], []
    for p in people:
        if rng.random() < 0.9:
            first = _typo(p.first, rng) if rng.random() < 0.08 else p.first
            last = _typo(p.last, rng) if rng.random() < 0.06 else p.last
            crm.append({
                "customer_id": f"C{rng.randrange(10**6, 10**7)}", "first_name": first, "last_name": last,
                "email_address": p.email if rng.random() < 0.9 else "", "mobile": _fmt_phone(p.phone, rng) if rng.random() < 0.8 else "",
                "addr1": p.street, "city": p.city, "state": p.state, "zip": p.postal,
                "dob": p.birthdate if rng.random() < 0.7 else "", "loyalty_no": p.loyalty or "",
                "updated_at": (start_dt - timedelta(days=rng.randrange(0, 400))).isoformat(), "truth_id": p.truth_id,
            })
        if rng.random() < 0.7:
            n_accounts = 2 if rng.random() < 0.15 else 1
            for k in range(n_accounts):
                use_nick = rng.random() < 0.3
                ecom.append({
                    "account_id": f"E{rng.randrange(10**6, 10**7)}", "name_first": NICK.get(p.first, p.first) if use_nick else p.first,
                    "name_last": p.last, "login_email": p.email if k == 0 and rng.random() < 0.85 else p.alt_email,
                    "phone_number": _fmt_phone(p.phone, rng) if rng.random() < 0.5 else "",
                    "ship_address": p.street.replace("St", "Street").replace("Ave", "Avenue") if rng.random() < 0.5 else p.street,
                    "ship_zip": p.postal if rng.random() < 0.85 else "", "ship_city": p.city, "ship_state": p.state,
                    "loyalty_number": p.loyalty if (p.loyalty and rng.random() < 0.4) else "",
                    "last_login": (start_dt - timedelta(days=rng.randrange(0, 200))).isoformat(), "truth_id": p.truth_id,
                })
        if p.loyalty and rng.random() < 0.9:
            loy.append({
                "member_id": p.loyalty, "full_first": p.first, "full_last": p.last, "email": p.email if rng.random() < 0.8 else p.alt_email,
                "phone": _fmt_phone(p.phone, rng), "birth_date": p.birthdate, "postal_code": p.postal,
                "enrolled_at": (start_dt - timedelta(days=rng.randrange(0, 900))).isoformat(), "truth_id": p.truth_id,
            })
        if rng.random() < 0.6:
            pos_id = f"POS{rng.randrange(10**5, 10**6)}"
            pos.append({
                "pos_customer_no": pos_id, "fname": p.first.upper(), "lname": p.last.upper(),
                "tel": _fmt_phone(p.phone, rng) if rng.random() < 0.75 else "", "zipcode": p.postal if rng.random() < 0.8 else "",
                "email": p.email if rng.random() < 0.3 else "", "truth_id": p.truth_id,
            })
            for _ in range(rng.randrange(0, 4)):
                orders.append({
                    "order_id": f"O{rng.randrange(10**7, 10**8)}", "pos_customer_no": pos_id,
                    "order_ts": (start_dt - timedelta(days=rng.randrange(0, 365), hours=rng.randrange(0, 24))).isoformat(),
                    "amount": round(rng.uniform(5, 400), 2), "store": rng.choice(["S01", "S02", "S03"]),
                })
    # a few junk / shared-email rows to exercise the blocklist and junk-email rules
    for i in range(5):
        crm.append({"customer_id": f"CJUNK{i}", "first_name": rng.choice(FIRST), "last_name": rng.choice(LAST), "email_address": "info@example.org",
                    "mobile": "", "addr1": "", "city": "", "state": "", "zip": "", "dob": "", "loyalty_no": "", "updated_at": start_dt.isoformat(), "truth_id": f"J{i}"})
    return {
        "crm_customers": pd.DataFrame(crm), "ecommerce_accounts": pd.DataFrame(ecom), "loyalty_members": pd.DataFrame(loy),
        "pos_customers": pd.DataFrame(pos), "pos_orders": pd.DataFrame(orders),
    }


SEMANTICS = {
    "crm": {"pk": "customer_id", "fields": {"first_name": "given_name", "last_name": "surname", "email_address": "email", "mobile": "phone",
                                            "addr1": "address", "city": "city", "state": "state", "zip": "postal", "dob": "birthdate",
                                            "loyalty_no": "loy_id", "updated_at": "update_dt"}},
    "ecommerce": {"pk": "account_id", "fields": {"name_first": "given_name", "name_last": "surname", "login_email": "email", "phone_number": "phone",
                                                 "ship_address": "address", "ship_zip": "postal", "ship_city": "city", "ship_state": "state",
                                                 "loyalty_number": "loy_id", "last_login": "update_dt"}, "fk": {"loyalty_number": "loyalty"}},
    "loyalty": {"pk": "member_id", "ck": "member_id", "fields": {"full_first": "given_name", "full_last": "surname", "email": "email", "phone": "phone",
                                                                "birth_date": "birthdate", "postal_code": "postal", "enrolled_at": "update_dt"}},
    "pos": {"pk": "pos_customer_no", "fields": {"fname": "given_name", "lname": "surname", "tel": "phone", "zipcode": "postal", "email": "email"}},
}

SEGMENT = {
    "name": "engaged_buyers",
    "match": "all",
    "filters": [{"field": "email", "op": "is_not_null"}, {"field": "order_count", "op": ">=", "value": 1}],
}


def write_demo_data(data_dir: Path, people_n: int, seed: int = 7) -> tuple[list[Path], list[Path]]:
    """Write batch 1 (initial) and batch 2 (late arrivals + updates) CSVs. Returns (batch1_files, batch2_files)."""
    rng = random.Random(seed)
    data_dir.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 10, 1)
    people = make_people(people_n, rng)
    cut = int(len(people) * 0.85)
    batch1 = synthesize(people[:cut], rng, start)
    late = synthesize(people[cut:], rng, start + timedelta(days=7))
    # updates: re-send some batch-1 crm rows with refreshed timestamps / corrected emails
    upd = batch1["crm_customers"].sample(frac=0.1, random_state=seed).copy()
    upd["updated_at"] = (start + timedelta(days=7)).isoformat()
    upd["email_address"] = upd["email_address"].where(upd["email_address"] != "", upd["first_name"].str.lower() + "@mail.com")
    late["crm_customers"] = pd.concat([late["crm_customers"], upd], ignore_index=True)
    files1, files2 = [], []
    for name, df in batch1.items():
        p = data_dir / f"{name}.csv"
        df.to_csv(p, index=False)
        files1.append(p)
    for name, df in late.items():
        p = data_dir / f"{name}_batch2.csv"
        df.to_csv(p, index=False)
        files2.append(p)
    truth = pd.concat(
        [batch1[k].assign(datasource=k.split("_")[0]) for k in batch1 if k != "pos_orders"]
        + [late[k].assign(datasource=k.split("_")[0]) for k in late if k != "pos_orders"]
    )
    pk_cols = {"crm": "customer_id", "ecommerce": "account_id", "loyalty": "member_id", "pos": "pos_customer_no"}
    truth["pk"] = [row[pk_cols[row["datasource"]]] for _, row in truth.iterrows()]
    truth[["datasource", "pk", "truth_id"]].to_csv(data_dir / "labels.csv", index=False)
    return files1, files2


def pipeline_spec(data_dir: Path, outputs_dir: Path, batch: int = 1, mode: str = "full") -> dict:
    suffix = "" if batch == 1 else "_batch2"
    load_mode = "full" if batch == 1 else "incremental"
    feeds = []
    for source, feed, fname in [("crm", "customers", "crm_customers"), ("ecommerce", "accounts", "ecommerce_accounts"),
                                ("loyalty", "members", "loyalty_members"), ("pos", "customers", "pos_customers")]:
        feeds.append({"source": source, "feed": feed, "path": str(data_dir / f"{fname}{suffix}.csv"), "load_mode": load_mode, "semantics": SEMANTICS[source]})
    feeds.append({"source": "pos", "feed": "orders", "path": str(data_dir / f"pos_orders{suffix}.csv"), "load_mode": load_mode})
    return {
        "name": f"demo-batch{batch}",
        "databases": ["init"],
        "feeds": feeds,
        "stitch": {"mode": mode},
        "profile": True,
        "segments": [SEGMENT],
        "destinations": [{"segment": SEGMENT["name"], "kind": "csv", "dir": str(outputs_dir)}],
    }


EVENTS_CFG = [{"source": "pos", "feed": "orders", "fk_column": "pos_customer_no", "fk_namespace": "pos", "event_type": "order", "ts_column": "order_ts", "amount_column": "amount"}]


def run_demo(cfg: Config | None = None, people: int = 700, fast: bool = False, reset: bool = True, seed: int = 7) -> dict:
    cfg = cfg or load_config()
    cfg = Config({**cfg, "events": EVENTS_CFG})
    if fast:
        people = min(people, 150)
    ws = cfg.workspace_path
    data_dir = ws / "demo"
    if reset and ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    write_demo_data(data_dir, people, seed)
    spec1 = pipeline_spec(data_dir, cfg.outputs_path, batch=1, mode="full")
    spec2 = pipeline_spec(data_dir, cfg.outputs_path, batch=2, mode="incremental")
    with (ws / "pipeline.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(spec1, fh, sort_keys=False)
    with (ws / "pipeline_batch2.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(spec2, fh, sort_keys=False)
    with (ws / "aurora.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump({"events": EVENTS_CFG}, fh, sort_keys=False)

    con = connect(cfg.db_path)
    try:
        init_schema(con)
        r1: PipelineResult = run_pipeline(con, cfg, spec1)
        append_run_history(cfg, r1)
        r2: PipelineResult = run_pipeline(con, cfg, spec2)
        append_run_history(cfg, r2)
        profiles = con.execute("SELECT COUNT(*) FROM customer_360").fetchone()[0]
    finally:
        con.close()
    return {
        "workspace": str(ws), "db": str(cfg.db_path), "data_dir": str(data_dir), "labels": str(data_dir / "labels.csv"),
        "run1": r1.as_dict(), "run2": r2.as_dict(), "profiles": profiles, "outputs": r1.outputs + r2.outputs,
        "export": r2.outputs[-1] if r2.outputs else None,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, default=str))
