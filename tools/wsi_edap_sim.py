"""Synthetic EDAP -> Amperity feeds in Williams-Sonoma shape, with ground truth, for an end-to-end test of Aurora.

Shapes follow the DDL shared on 2026-10-29 (EDAP to AMPERITY: ORDER_HEADER, ORDER_LINE, RETAIL_STORE_ESTIMATE_HEADER;
AMPERITY to EDAP: CUSTOMER). Only identity-bearing and aggregate-bearing columns are populated; the rest are omitted
or filled with NULL, the column *names* are kept so the mapping in tools/wsi_edap_eval.py reads like the real one.

What the generator models (all seeded):
- persons with households (shared address, mostly shared surname), 1-3 e-mails (brand-specific alternates),
  1-2 phones, moves, nicknames, typos, case/format variants, middle names, no date of birth (the EDAP feeds carry none)
- seven concepts (WS, PB, PK, PT, WE, MG, OB), channels WEB / CALL_CENTER (SOURCE_SYSTEM = OMS) and RETAIL (POS)
  with channel-specific PII capture: web orders are rich, POS orders often carry only an e-mail, a phone, a loyalty
  id, or nothing at all (anonymous)
- OMS account ids (CUSTOMER_ID, per brand, 15 % of people hold two), loyalty ids on members' orders, employee ids
- ORDER_LINE ship-to: the buyer (most lines) or a gift recipient (another person or a stranger); POS lines take-with
- RETAIL_STORE_ESTIMATE_HEADER clienteling estimates for a slice of people
- truth: every identity-bearing record -> person; anonymous POS records are their own "person" (unlinkable by any
  system); expected CUSTOMER rows computed from the truth (survivorship + purchase aggregates in the CUSTOMER DDL)

Usage: python tools/wsi_edap_sim.py --persons 60000 --seed 42 --out ~/Documents/aanya/datasets/wsi-edap-sim/p60k
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

CONCEPTS = ["WS", "PB", "PK", "PT", "WE", "MG", "OB"]
CONCEPT_W = [0.30, 0.28, 0.08, 0.05, 0.20, 0.04, 0.05]
BRAND_DOMAIN = {"WS": "williams-sonoma", "PB": "potterybarn", "PK": "pbkids", "PT": "pbteen", "WE": "westelm", "MG": "markandgraham", "OB": "rejuvenation"}
FIRST = ("james john robert michael william david richard joseph thomas charles christopher daniel matthew anthony mark donald steven "
         "paul andrew joshua kenneth kevin brian george timothy ronald edward jason jeffrey ryan jacob gary nicholas eric jonathan stephen "
         "larry justin scott brandon benjamin samuel gregory alexander patrick frank raymond jack dennis jerry tyler aaron jose adam nathan "
         "henry douglas zachary peter kyle noah ethan jeremy walter christian keith roger terry austin sean gerald carl harold dylan arthur "
         "mary patricia jennifer linda elizabeth barbara susan jessica sarah karen lisa nancy betty sandra margaret ashley kimberly emily "
         "donna michelle carol amanda melissa deborah stephanie dorothy rebecca sharon laura cynthia amy kathleen angela shirley brenda emma "
         "anna pamela nicole samantha katherine christine helen debra rachel carolyn janet maria catherine heather diane olivia julie joyce "
         "victoria ruth virginia lauren kelly christina joan evelyn judith andrea hannah megan cheryl jacqueline martha madison teresa gloria "
         "sara janice ann kathryn abigail sophia frances jean alice judy isabella julia grace amber denise danielle marilyn beverly charlotte "
         "natalie theresa diana brittany doris kayla alexis lori").split()
LAST = ("smith johnson williams brown jones garcia miller davis rodriguez martinez hernandez lopez gonzalez wilson anderson thomas taylor "
        "moore jackson martin lee perez thompson white harris sanchez clark ramirez lewis robinson walker young allen king wright scott "
        "torres nguyen hill flores green adams nelson baker hall rivera campbell mitchell carter roberts gomez phillips evans turner diaz "
        "parker cruz edwards collins reyes stewart morris morales murphy cook rogers gutierrez ortiz morgan cooper peterson bailey reed "
        "kelly howard ramos kim cox ward richardson watson brooks chavez wood james bennett gray mendoza ruiz hughes price alvarez castillo "
        "sanders patel myers long ross foster jimenez powell jenkins perry russell sullivan bell coleman butler henderson barnes gonzales "
        "fisher vasquez simmons romero jordan patterson alexander hamilton graham reynolds griffin wallace moreno west cole hayes bryant "
        "herrera gibson ellis tran medina aguilar stevens murray ford castro marshall owens harrison fernandez mcdonald woods washington "
        "kennedy wells vargas henry chen freeman webb tucker guzman burns crawford olson simpson porter hunter gordon mendez silva shaw "
        "snyder mason dixon munoz hunt hicks holmes palmer wagner black robertson boyd rose stone salazar fox warren mills meyer rice "
        "schmidt garza daniels ferguson nichols stephens soto weaver ryan gardner payne grant dunn kelley spencer hawkins arnold pierce "
        "vazquez hansen peters santos hart bradley knight elliott cunningham duncan armstrong hudson carroll lane riley andrews alvarado "
        "ray delgado berry perkins hoffman johnston matthews pena richards contreras willis carpenter lawrence sandoval guerrero george "
        "chapman rios estrada ortega watkins greene nunez wheeler valdez harper burke larson santiago maldonado morrison franklin carlson "
        "austin dominguez carr lawson jacobs ochoa madden fleming").split()
NICK = {"robert": ["bob", "rob", "bobby"], "william": ["bill", "will", "billy"], "elizabeth": ["liz", "beth", "betsy"], "michael": ["mike"],
        "katherine": ["kate", "katie", "kathy"], "james": ["jim", "jimmy"], "richard": ["rick", "dick", "rich"], "jennifer": ["jen", "jenny"],
        "margaret": ["maggie", "peggy", "meg"], "thomas": ["tom", "tommy"], "christopher": ["chris"], "joseph": ["joe", "joey"], "daniel": ["dan", "danny"],
        "matthew": ["matt"], "andrew": ["andy", "drew"], "patricia": ["pat", "patty", "tricia"], "susan": ["sue", "susie"], "deborah": ["deb", "debbie"],
        "rebecca": ["becky"], "charles": ["charlie", "chuck"], "edward": ["ed", "eddie"], "anthony": ["tony"], "steven": ["steve"], "kenneth": ["ken"],
        "timothy": ["tim"], "jonathan": ["jon"], "samuel": ["sam"], "benjamin": ["ben"], "nicholas": ["nick"], "alexander": ["alex"],
        "stephanie": ["steph"], "kimberly": ["kim"], "christine": ["chris", "christy"], "kathleen": ["kathy"], "jessica": ["jess"], "samantha": ["sam"],
        "victoria": ["vicky", "tori"], "abigail": ["abby"], "isabella": ["bella"], "alexis": ["lexi"], "theresa": ["terry"], "jacqueline": ["jackie"]}
STREETS = "Main Oak Pine Maple Cedar Elm Washington Lake Hill Park Sunset Ridge Valley Forest River Meadow Highland Spring Church Mill Willow Chestnut Walnut Cherry Birch Lincoln Jefferson Madison Jackson Franklin Market Union Center Broad High Water Grove Orchard Prospect Summit".split()
STYPES = [("Street", "St"), ("Avenue", "Ave"), ("Road", "Rd"), ("Drive", "Dr"), ("Lane", "Ln"), ("Court", "Ct"), ("Boulevard", "Blvd"), ("Way", "Way"), ("Place", "Pl"), ("Circle", "Cir")]
CITIES = [("San Francisco", "CA", "94110"), ("Oakland", "CA", "94610"), ("San Jose", "CA", "95110"), ("Los Angeles", "CA", "90210"), ("San Diego", "CA", "92101"),
          ("Seattle", "WA", "98101"), ("Portland", "OR", "97201"), ("Denver", "CO", "80202"), ("Phoenix", "AZ", "85001"), ("Austin", "TX", "78701"),
          ("Dallas", "TX", "75201"), ("Houston", "TX", "77002"), ("Chicago", "IL", "60601"), ("Minneapolis", "MN", "55401"), ("Atlanta", "GA", "30301"),
          ("Miami", "FL", "33101"), ("Tampa", "FL", "33602"), ("Charlotte", "NC", "28202"), ("Raleigh", "NC", "27601"), ("Nashville", "TN", "37201"),
          ("Boston", "MA", "02108"), ("New York", "NY", "10001"), ("Brooklyn", "NY", "11201"), ("Philadelphia", "PA", "19103"), ("Washington", "DC", "20001"),
          ("Baltimore", "MD", "21201"), ("Columbus", "OH", "43215"), ("Detroit", "MI", "48201"), ("Indianapolis", "IN", "46204"), ("Kansas City", "MO", "64105"),
          ("St Louis", "MO", "63101"), ("Salt Lake City", "UT", "84101"), ("Las Vegas", "NV", "89101"), ("Sacramento", "CA", "95814"), ("Scottsdale", "AZ", "85251"),
          ("Bellevue", "WA", "98004"), ("Pasadena", "CA", "91101"), ("Greenwich", "CT", "06830"), ("Princeton", "NJ", "08540"), ("Naperville", "IL", "60540")]
DOMAINS = ["gmail.com", "gmail.com", "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com", "comcast.net", "me.com"]
STORES = {c: [f"{c}{n:03d}" for n in range(1, 61)] for c in CONCEPTS}
END_DT = date(2026, 9, 30)
START_DT = END_DT - timedelta(days=730)


def zipf_choice(rng: random.Random, items: list[str], s: float = 1.0) -> str:
    n = len(items)
    w = [1.0 / (i + 1) ** s for i in range(n)]
    return rng.choices(items, weights=w, k=1)[0]


def _typo(s: str, rng: random.Random) -> str:
    if len(s) < 4:
        return s
    i = rng.randrange(1, len(s) - 1)
    k = rng.random()
    if k < 0.4:
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if k < 0.7:
        return s[:i] + s[i + 1:]
    return s[:i] + rng.choice("aeioustnrl") + s[i:]


@dataclass
class Address:
    line1: str
    line2: str
    city: str
    state: str
    postal: str

    def render(self, rng: random.Random) -> tuple[str, str, str, str, str]:
        l1 = self.line1
        full, abbr = next(t for t in STYPES if t[0] in l1)
        r = rng.random()
        if r < 0.45:
            l1 = l1.replace(full, abbr)
        if rng.random() < 0.03:
            l1 = _typo(l1, rng)
        l2 = self.line2 if (self.line2 and rng.random() < 0.8) else ""
        if rng.random() < 0.15 and l2:
            l1, l2 = f"{l1} {l2}", ""
        case = rng.random()
        if case < 0.3:
            l1, l2, city = l1.upper(), l2.upper(), self.city.upper()
        elif case < 0.4:
            l1, l2, city = l1.lower(), l2.lower(), self.city.lower()
        else:
            city = self.city
        return l1, l2, city, self.state, self.postal


@dataclass
class Person:
    pid: str
    first: str
    last: str
    middle: str
    emails: list[str]
    phones: list[str]
    addresses: list[tuple[date, Address]]  # (from_date, address)
    household: str
    brands: list[str]
    loyalty_id: str | None
    employee_id: str | None
    oms_accounts: dict[str, list[str]] = field(default_factory=dict)
    clienteling_id: str | None = None

    def address_at(self, d: date) -> Address:
        cur = self.addresses[0][1]
        for frm, a in self.addresses:
            if d >= frm:
                cur = a
        return cur


def make_address(rng: random.Random) -> Address:
    city, state, postal = rng.choice(CITIES)
    postal = f"{int(postal[:3]):03d}{rng.randrange(0, 100):02d}"
    st = rng.choice(STREETS)
    typ = rng.choice(STYPES)[0]
    line2 = f"Apt {rng.randrange(1, 40)}{rng.choice(['', 'A', 'B'])}" if rng.random() < 0.22 else ""
    return Address(f"{rng.randrange(1, 9999)} {st} {typ}", line2, city, state, postal)


_EMAILS_SEEN: set[str] = set()


def _email_key(e: str) -> str:
    local, dom = e.lower().split("@")
    return f"{local.split('+')[0]}@{dom}"


_SALT: int | None = None  # batch salt: every e-mail of a batch gets a number from its own range, so batches never collide


def make_email(first: str, last: str, rng: random.Random, brand: str | None = None) -> str:
    """A person's e-mail; unique across persons after plus-tag stripping (two people never share a mailbox here;
    shared family mailboxes are a real phenomenon but are deliberately not modelled)."""
    for _ in range(50):
        e = _make_email(first, last, rng, brand)
        if _SALT is not None:
            local, dom = e.split("@")
            tag = ""
            if "+" in local:
                local, tag = local.split("+", 1)
                tag = "+" + tag
            e = f"{local}{_SALT * 100000 + rng.randrange(0, 100000)}{tag}@{dom}"
        k = _email_key(e)
        if k not in _EMAILS_SEEN:
            _EMAILS_SEEN.add(k)
            return e
    e = _make_email(first, last, rng, brand).replace("@", f"{rng.randrange(1000, 99999)}@")
    _EMAILS_SEEN.add(_email_key(e))
    return e


def _make_email(first: str, last: str, rng: random.Random, brand: str | None = None) -> str:
    pat = rng.random()
    dom = rng.choice(DOMAINS)
    if pat < 0.3:
        local = f"{first}.{last}"
    elif pat < 0.5:
        local = f"{first[0]}{last}"
    elif pat < 0.65:
        local = f"{first}{last}{rng.randrange(1, 99)}"
    elif pat < 0.8:
        local = f"{last}.{first}{rng.randrange(1970, 2005)}"
    else:
        local = f"{rng.choice(['the', 'real', 'its', ''])}{first}{rng.randrange(1, 999)}"
    if brand and rng.random() < 0.3:
        local = f"{local}+{brand.lower()}"
    return f"{local}@{dom}"


def make_people(n: int, rng: random.Random, pid_offset: int = 0, hh_offset: int = 0) -> list[Person]:
    people: list[Person] = []
    hh_counter = hh_offset
    i = 0
    while i < n:
        hh_counter += 1
        hh = f"HH{hh_counter:09d}"
        size = 1
        r = rng.random()
        if r < 0.25:
            size = 2
        elif r < 0.33:
            size = 3
        addr = make_address(rng)
        base_last = zipf_choice(rng, LAST, 0.9)
        shared_phone = f"{rng.randrange(201, 989)}{rng.randrange(200, 999)}{rng.randrange(1000, 9999)}" if rng.random() < 0.4 else None
        for k in range(size):
            if i >= n:
                break
            first = zipf_choice(rng, FIRST, 0.8)
            last = base_last if (k == 0 or rng.random() < 0.7) else zipf_choice(rng, LAST, 0.9)
            middle = zipf_choice(rng, FIRST, 0.8) if rng.random() < 0.35 else ""
            brands = rng.choices(CONCEPTS, weights=CONCEPT_W, k=rng.choice([1, 1, 1, 2, 2, 3]))
            brands = sorted(set(brands))
            emails = [make_email(first, last, rng)]
            if rng.random() < 0.35:
                emails.append(make_email(first, last, rng, brand=rng.choice(brands)))
            if rng.random() < 0.1:
                emails.append(make_email(first, last, rng))
            phones = [shared_phone] if (shared_phone and rng.random() < 0.6) else []
            phones.append(f"{rng.randrange(201, 989)}{rng.randrange(200, 999)}{rng.randrange(1000, 9999)}")
            if rng.random() < 0.15:
                phones.append(f"{rng.randrange(201, 989)}{rng.randrange(200, 999)}{rng.randrange(1000, 9999)}")
            addresses = [(START_DT - timedelta(days=3650), addr)]
            if rng.random() < 0.18:  # mover during the window (the whole household does not necessarily move)
                addresses.append((START_DT + timedelta(days=rng.randrange(60, 700)), make_address(rng)))
            pid = f"P{pid_offset + i + 1:09d}"
            loy = f"LOY{rng.randrange(10**8, 10**9)}" if rng.random() < 0.35 else None
            emp = f"E{rng.randrange(10**5, 10**6)}" if rng.random() < 0.02 else None
            p = Person(pid, first, last, middle, emails, phones, addresses, hh, brands, loy, emp)
            for b in brands:
                if rng.random() < 0.9:
                    p.oms_accounts[b] = [f"{b}-{rng.randrange(10**7, 10**8)}"]
                    if rng.random() < 0.15:
                        p.oms_accounts[b].append(f"{b}-{rng.randrange(10**7, 10**8)}")
            if rng.random() < 0.06:
                p.clienteling_id = f"CL{rng.randrange(10**6, 10**7)}"
            people.append(p)
            i += 1
    return people


def render_name(p: Person, rng: random.Random) -> tuple[str, str, str]:
    first, last, middle = p.first, p.last, p.middle
    r = rng.random()
    if first in NICK and r < 0.12:
        first = rng.choice(NICK[first])
    elif r < 0.16:
        first = first[0]  # initial only
    if rng.random() < 0.03:
        first = _typo(first, rng)
    if rng.random() < 0.03:
        last = _typo(last, rng)
    case = rng.random()
    if case < 0.35:
        first, last, middle = first.upper(), last.upper(), middle.upper()
    elif case < 0.9:
        first, last, middle = first.title(), last.title(), middle.title()
    mid = middle if (middle and rng.random() < 0.4) else ""
    return first, last, mid


def fmt_phone(d: str, rng: random.Random) -> str:
    if rng.random() < 0.03:
        d = d[:-1] + str((int(d[-1]) + 1) % 10)
    r = rng.random()
    if r < 0.4:
        return f"({d[:3]}) {d[3:6]}-{d[6:]}"
    if r < 0.7:
        return f"{d[:3]}-{d[3:6]}-{d[6:]}"
    if r < 0.85:
        return d
    return f"+1{d}"


def render_email(e: str, rng: random.Random) -> str:
    if rng.random() < 0.02:
        local, dom = e.split("@")
        e = f"{_typo(local, rng)}@{dom}"
    r = rng.random()
    return e.upper() if r < 0.15 else (e.title() if r < 0.2 else e)


def gen(persons: int, seed: int, batch: int = 0):
    """One batch: ids carry the batch number so batches generated in parallel never collide."""
    global _SALT
    rng = random.Random(seed)
    _EMAILS_SEEN.clear()
    _SALT = batch if batch else None
    people = make_people(persons, rng, pid_offset=batch * 10_000_000, hh_offset=batch * 10_000_000)
    by_pid = {p.pid: p for p in people}
    headers, lines, estimates, truth = [], [], [], []
    expected_src: dict[str, list[dict]] = defaultdict(list)  # pid -> linkable orders
    pii_obs: dict[str, list[dict]] = defaultdict(list)       # pid -> observed pii per record (for survivorship truth)
    oid = batch * 100_000_000
    lid = batch * 1_000_000_000
    est_id = batch * 10_000_000
    for p in people:
        r = rng.random()
        n_orders = 1 if r < 0.45 else (rng.randrange(2, 4) if r < 0.75 else (rng.randrange(4, 9) if r < 0.93 else rng.randrange(9, 31)))
        dates = sorted(START_DT + timedelta(days=rng.randrange(0, 730)) for _ in range(n_orders))
        for od in dates:
            oid += 1
            brand = rng.choice(p.brands) if rng.random() < 0.85 else rng.choices(CONCEPTS, weights=CONCEPT_W, k=1)[0]
            ch = rng.random()
            channel = "WEB" if ch < 0.55 else ("RETAIL" if ch < 0.9 else "CALL_CENTER")
            src = "POS" if channel == "RETAIL" else "OMS"
            store = rng.choice(STORES[brand]) if channel == "RETAIL" else None
            addr = p.address_at(od)
            first, last, mid = render_name(p, rng)
            email = render_email(rng.choice(p.emails), rng) if p.emails else ""
            phone = fmt_phone(rng.choice(p.phones), rng)
            l1, l2, city, state, postal = addr.render(rng)
            loy = p.loyalty_id if (p.loyalty_id and rng.random() < 0.7) else None
            acct = rng.choice(p.oms_accounts[brand]) if (src == "OMS" and brand in p.oms_accounts and rng.random() < 0.9) else None
            emp = p.employee_id if (p.employee_id and rng.random() < 0.5) else None
            # channel lens on bill-to PII
            if channel == "WEB":
                bill = dict(first=first, last=last, mid=mid, l1=l1, l2=l2, city=city, state=state, postal=postal, email=email,
                            phone=phone if rng.random() < 0.7 else "")
            elif channel == "CALL_CENTER":
                bill = dict(first=first, last=last, mid=mid, l1=l1, l2=l2, city=city, state=state, postal=postal,
                            email=email if rng.random() < 0.5 else "", phone=phone if rng.random() < 0.9 else "")
            else:
                k = rng.random()
                if k < 0.45:
                    bill = dict(first="", last="", mid="", l1="", l2="", city="", state="", postal="", email=email, phone="")
                elif k < 0.60:
                    bill = dict(first="", last="", mid="", l1="", l2="", city="", state="", postal="", email="", phone=phone)
                elif k < 0.70:
                    bill = dict(first=first if rng.random() < 0.5 else "", last=last if rng.random() < 0.5 else "", mid="", l1="", l2="", city="", state="", postal="", email="", phone="")
                    loy = p.loyalty_id or loy
                elif k < 0.85:
                    bill = dict(first=first, last=last, mid="", l1="", l2="", city="", state="", postal=postal, email=email, phone="")
                else:
                    bill = dict(first="", last="", mid="", l1="", l2="", city="", state="", postal="", email="", phone="")
                    loy, acct = None, None
                if rng.random() < 0.05:
                    bill.update(l1=l1, l2=l2, city=city, state=state, postal=postal, first=first, last=last)
            has_pii = any(bill[k] for k in ("first", "last", "email", "phone", "l1")) or loy or acct
            n_lines = rng.choice([1, 1, 1, 2, 2, 3, 4])
            subtotal = 0.0
            items = 0
            ohid = f"OH{oid:011d}"
            order_id = f"{brand}{src[0]}{oid:011d}"
            line_rows = []
            gift = channel != "RETAIL" and rng.random() < 0.10
            recipient = None
            if gift:
                recipient = rng.choice(people) if rng.random() < 0.6 else None  # None = stranger not in the base
            for li in range(n_lines):
                lid += 1
                qty = rng.choice([1, 1, 1, 2, 3])
                price = round(float(np.exp(rng.gauss(4.3, 0.9))), 2)
                ext = round(price * qty, 2)
                subtotal += ext
                items += qty
                if channel == "RETAIL" and rng.random() < 0.85:
                    ship = dict(first="", last="", mid="", l1="", l2="", city="", state="", postal="", email="", phone="", pid=None)
                elif gift:
                    if recipient is not None:
                        rf, rl, rm = render_name(recipient, rng)
                        ra = recipient.address_at(od)
                        rl1, rl2, rc, rs, rp = ra.render(rng)
                        ship = dict(first=rf, last=rl, mid=rm, l1=rl1, l2=rl2, city=rc, state=rs, postal=rp, email="", phone=fmt_phone(rng.choice(recipient.phones), rng) if rng.random() < 0.3 else "", pid=recipient.pid)
                    else:
                        sa = make_address(rng)
                        sl1, sl2, sc, ss, sp = sa.render(rng)
                        ship = dict(first=zipf_choice(rng, FIRST, 0.8).title(), last=zipf_choice(rng, LAST, 0.9).title(), mid="", l1=sl1, l2=sl2, city=sc, state=ss, postal=sp, email="", phone="", pid=f"stranger:{ohid}")
                else:
                    ship = dict(first=first, last=last, mid=mid, l1=l1, l2=l2, city=city, state=state, postal=postal,
                                email=email if rng.random() < 0.8 else "", phone=phone if rng.random() < 0.6 else "", pid=p.pid)
                line_rows.append({
                    "ORDER_LINE_KEY": lid, "ORDER_LINE_ID": f"OL{lid:012d}", "ORDER_HEADER_KEY": oid, "SOURCE_SYSTEM": src, "ORDER_DT": od,
                    "PRIME_LINE_SEQ_NBR": li + 1, "ORDER_ITEM_ID": f"SKU{rng.randrange(10**5, 10**6)}", "ORDER_QTY": qty,
                    "ACT_SALE_UNIT_PRICE_AMT": price, "EXTENDED_AMT": ext, "LINE_TOTAL_AMT": ext, "GIFT_FLAG": "Y" if gift else "N",
                    "SHIP_TO_CUSTOMER_ID": (acct if ship.get("pid") == p.pid else None),
                    "SHIP_TO_FIRST_NAME": ship["first"], "SHIP_TO_MIDDLE_NAME": ship["mid"], "SHIP_TO_LAST_NAME": ship["last"],
                    "SHIP_TO_ADDRESS_LINE_1": ship["l1"], "SHIP_TO_ADDRESS_LINE_2": ship["l2"], "SHIP_TO_CITY": ship["city"],
                    "SHIP_TO_STATE_OR_PROV": ship["state"], "SHIP_TO_POSTAL_CD": ship["postal"], "SHIP_TO_COUNTRY": "US" if ship["l1"] else "",
                    "SHIP_TO_EMAIL_ADDRESS": ship["email"], "SHIP_TO_PHONE_NBR": ship["phone"],
                    "DELIVERY_METHOD": "TAKE_WITH" if (channel == "RETAIL" and not ship["l1"]) else "SHIP",
                    "INSERT_TS": datetime.combine(od, datetime.min.time()), "UPDATE_TS": datetime.combine(od, datetime.min.time()),
                    "_ship_pid": ship.get("pid"),
                })
            tax = round(subtotal * 0.0825, 2)
            net = round(subtotal, 2)
            gross = round(subtotal + tax, 2)
            pid_truth = p.pid if has_pii else f"anon:{ohid}"
            headers.append({
                "ORDER_HEADER_KEY": oid, "ORDER_HEADER_ID": ohid, "SOURCE_SYSTEM": src, "ORDER_ID": order_id, "ORDER_TYPE_CD": "SALE",
                "ORDER_DT": od, "LOCATION_ID": store, "HOUSEHOLD_ID": None, "CONCEPT_CD": brand, "CURRENCY_CD": "USD",
                "LOYALTY_ACCOUNT_ID": loy, "CUSTOMER_ID": acct, "EMPLOYEE_ID": emp, "SUB_CHANNEL_TYPE_CD": channel,
                "ROLLUP_CHANNEL_NM": "RETAIL" if channel == "RETAIL" else "DTC", "FIRST_EFFECTIVE_TS": datetime.combine(od, datetime.min.time()),
                "LAST_EFFECTIVE_TS": datetime.combine(od, datetime.min.time()),
                "BILL_TO_FIRST_NAME": bill["first"], "BILL_TO_MIDDLE_NAME": bill["mid"], "BILL_TO_LAST_NAME": bill["last"],
                "BILL_TO_ADDRESS_LINE_1": bill["l1"], "BILL_TO_ADDRESS_LINE_2": bill["l2"], "BILL_TO_CITY": bill["city"],
                "BILL_TO_STATE_OR_PROV_CD": bill["state"], "BILL_TO_POSTAL_CD": bill["postal"], "BILL_TO_COUNTRY": "US" if bill["l1"] else "",
                "BILL_TO_EMAIL_ADDRESS": bill["email"], "BILL_TO_PHONE_NBR": bill["phone"], "CUSTOMER_TYPE_CD": "B2C",
                "GIFT_FLAG": "Y" if gift else "N", "SUBORDERS_CNT": 1, "GROSS_AMT": gross, "NET_AMT": net, "TAX_AMT": tax,
                "ORIGINAL_TOTAL_AMT": gross, "INSERT_TS": datetime.combine(od, datetime.min.time()), "UPDATE_TS": datetime.combine(od, datetime.min.time()),
            })
            truth.append({"record_id": ohid, "table": "ORDER_HEADER", "role": "bill_to", "person_id": pid_truth, "has_pii": bool(has_pii)})
            shipped = {}
            for lr in line_rows:
                if lr["_ship_pid"] and lr["SHIP_TO_ADDRESS_LINE_1"]:
                    key = (lr["_ship_pid"], lr["SHIP_TO_ADDRESS_LINE_1"].lower())
                    if key not in shipped:
                        shipped[key] = lr["ORDER_LINE_ID"]
                        truth.append({"record_id": lr["ORDER_LINE_ID"], "table": "ORDER_LINE", "role": "ship_to_gift" if lr["_ship_pid"] != p.pid else "ship_to_self", "person_id": lr["_ship_pid"], "has_pii": True})
                lr.pop("_ship_pid")
                lines.append(lr)
            if has_pii:
                expected_src[p.pid].append({"order_id": order_id, "brand": brand, "channel": channel, "store": store, "dt": od, "net": net, "gross": gross, "items": items, "emp": emp, "loy": loy})
                pii_obs[p.pid].append({"dt": od, "first": bill["first"], "last": bill["last"], "email": bill["email"], "phone": bill["phone"], "l1": bill["l1"], "l2": bill["l2"], "city": bill["city"], "state": bill["state"], "postal": bill["postal"]})
        if p.clienteling_id:
            for _ in range(rng.choice([1, 1, 2])):
                est_id += 1
                ed = START_DT + timedelta(days=rng.randrange(0, 730))
                first, last, mid = render_name(p, rng)
                addr = p.address_at(ed)
                l1, l2, city, state, postal = addr.render(rng)
                brand = rng.choice(p.brands)
                estimates.append({
                    "RETAIL_STORE_ESTIMATE_HEADER_KEY": est_id, "RETAIL_STORE_ESTIMATE_HEADER_ID": f"EST{est_id:010d}", "SOURCE_ESTIMATE_ID": est_id,
                    "MARKET_CD": "US", "ORDER_DT": ed, "CUSTOMER_ID": p.clienteling_id, "HOUSEHOLD_ID": None,
                    "FIRST_EFFECTIVE_TS": datetime.combine(ed, datetime.min.time()), "LAST_EFFECTIVE_TS": datetime.combine(ed, datetime.min.time()),
                    "ESTIMATE_TXN_TYPE_DESC": "ESTIMATE", "CURRENT_STATUS": rng.choice(["OPEN", "CONVERTED", "EXPIRED"]), "CLIENTELING_SALE_FLAG": "Y",
                    "CUSTOMER_FIRST_NAME": first, "CUSTOMER_LAST_NAME": last, "CUSTOMER_EMAIL_ID": render_email(rng.choice(p.emails), rng) if rng.random() < 0.8 else "",
                    "CUSTOMER_ADDRESSLINE": f"{l1} {l2}".strip() if rng.random() < 0.7 else "", "CUSTOMER_CITY": city, "CUSTOMER_STATE_CD": state,
                    "CUSTOMER_POSTAL_CD": postal, "CUSTOMER_COUNTRY_CD": "US", "CUSTOMER_DAY_PHONE_NBR": fmt_phone(rng.choice(p.phones), rng) if rng.random() < 0.7 else "",
                    "CUSTOMER_CLIENTELING_ID": p.clienteling_id, "TARGET_LOCATION_CONCEPT_CD": brand, "LOGGED_IN_LOCATION_ID": rng.choice(STORES[brand]),
                    "TOTAL_AMT_BEFORE_TAX": round(float(np.exp(rng.gauss(6.0, 0.8))), 2), "SOURCE": "CLIENTELING",
                    "INSERT_TS": datetime.combine(ed, datetime.min.time()), "UPDATE_TS": datetime.combine(ed, datetime.min.time()),
                })
                truth.append({"record_id": f"EST{est_id:010d}", "table": "RETAIL_STORE_ESTIMATE_HEADER", "role": "estimate", "person_id": p.pid, "has_pii": True})
                pii_obs[p.pid].append({"dt": ed, "first": first, "last": last, "email": estimates[-1]["CUSTOMER_EMAIL_ID"], "phone": estimates[-1]["CUSTOMER_DAY_PHONE_NBR"], "l1": l1, "l2": l2, "city": city, "state": state, "postal": postal})
    expected = [expected_customer(by_pid[pid], orders, pii_obs.get(pid, [])) for pid, orders in expected_src.items()]
    return people, pd.DataFrame(headers), pd.DataFrame(lines), pd.DataFrame(estimates), pd.DataFrame(truth), pd.DataFrame(expected)


def _norm(s: str) -> str:
    return " ".join(str(s or "").lower().split())


def aggregates(orders: list[dict], since: date | None, prefix: str) -> dict:
    sel = [o for o in orders if since is None or o["dt"] >= since]
    out: dict = {}
    if not sel:
        for k in ("BRANDS", "PREFERRED_BRAND", "CHANNELS", "PREFERRED_CHANNEL", "STORES", "PREFERRED_STORE_ID"):
            out[f"{prefix}_{k}"] = None
        for k in ("ORDER_NET_AMT", "ORDER_TOTAL_AMT", "ORDER_FREQUENCY", "TOTAL_ITEMS", "AVERAGE_ORDER_VALUE_AMT", "AVERAGE_ITEM_PRICE", "AVERAGE_NUM_ITEMS"):
            name = f"{prefix}_ORDER_TOTAL_ITEMS" if (k == "TOTAL_ITEMS" and prefix == "LIFETIME") else f"{prefix}_{k}"
            out[name] = 0 if "FREQUENCY" in k or "ITEMS" in k else 0.0
        return out
    net_by_brand = Counter()
    net_by_ch = Counter()
    net_by_store = Counter()
    for o in sel:
        net_by_brand[o["brand"]] += o["net"]
        net_by_ch[o["channel"]] += o["net"]
        if o["store"]:
            net_by_store[o["store"]] += o["net"]
    net = round(sum(o["net"] for o in sel), 2)
    tot = round(sum(o["gross"] for o in sel), 2)
    items = sum(o["items"] for o in sel)
    out[f"{prefix}_BRANDS"] = ",".join(sorted(net_by_brand))
    out[f"{prefix}_PREFERRED_BRAND"] = max(sorted(net_by_brand), key=lambda b: net_by_brand[b])
    out[f"{prefix}_CHANNELS"] = ",".join(sorted(net_by_ch))
    out[f"{prefix}_PREFERRED_CHANNEL"] = max(sorted(net_by_ch), key=lambda c: net_by_ch[c])
    out[f"{prefix}_STORES"] = ",".join(sorted(net_by_store)) or None
    out[f"{prefix}_PREFERRED_STORE_ID"] = (max(sorted(net_by_store), key=lambda s: net_by_store[s]) if net_by_store else None)
    out[f"{prefix}_ORDER_NET_AMT"] = net
    out[f"{prefix}_ORDER_TOTAL_AMT"] = tot
    out[f"{prefix}_ORDER_FREQUENCY"] = len(sel)
    out[f"{prefix}_{'ORDER_' if prefix == 'LIFETIME' else ''}TOTAL_ITEMS"] = items   # DDL: LIFETIME_ORDER_TOTAL_ITEMS, L12M_TOTAL_ITEMS, …
    out[f"{prefix}_AVERAGE_ORDER_VALUE_AMT"] = round(net / len(sel), 2)
    out[f"{prefix}_AVERAGE_ITEM_PRICE"] = round(net / items, 2) if items else 0.0
    out[f"{prefix}_AVERAGE_NUM_ITEMS"] = round(items / len(sel))
    return out


def expected_customer(p: Person | None, orders: list[dict], obs: list[dict], customer_id: str | None = None, household_id: str | None = None) -> dict:
    """CUSTOMER row from a set of orders + the PII observed on the records (shared by truth and the Aurora build)."""
    orders = sorted(orders, key=lambda o: (o["dt"], o["order_id"]))
    obs = sorted(obs, key=lambda o: o["dt"])
    def most_common(key):
        c = Counter(_norm(o[key]) for o in obs if o.get(key))
        return c.most_common(1)[0][0] if c else None
    def recent(key):
        for o in reversed(obs):
            if o.get(key):
                return _norm(o[key])
        return None
    latest_addr = next((o for o in reversed(obs) if o.get("l1")), None)
    row = {
        "CUSTOMER_ID": customer_id or (p.pid if p else None), "HOUSEHOLD_ID": household_id or (p.household if p else None),
        "FIRST_NAME": recent("first"), "LAST_NAME": recent("last"),
        "ADDRESS": _norm(latest_addr["l1"]) if latest_addr else None, "ADDRESS2": _norm(latest_addr["l2"]) if latest_addr else None,
        "CITY": _norm(latest_addr["city"]) if latest_addr else None, "STATE_CD": latest_addr["state"] if latest_addr else None,
        "POSTAL_CD": latest_addr["postal"] if latest_addr else None, "COUNTRY_CD": "US" if latest_addr else None,
        "PRIMARY_EMAIL_ID": most_common("email"), "RECENT_EMAIL_ID": recent("email"),
        "PRIMARY_PHONE": most_common("phone"), "RECENT_PHONE": recent("phone"), "DOB_DT": None,
        "CUSTOMER_PII_PRESENT_FLAG": "Y",
        "CURRENT_EMPLOYEE_FLAG": "Y" if any(o["emp"] for o in orders) else "N",
        "LOYALTY_MEMBER_FLAG": "Y" if any(o["loy"] for o in orders) else "N",
        "LOYALTY_ACCT_CNT": len({o["loy"] for o in orders if o["loy"]}),
    }
    for label, o in (("FIRST", orders[0] if orders else None), ("SECOND", orders[1] if len(orders) > 1 else None), ("LATEST", orders[-1] if orders else None)):
        row[f"{label}_ORDER_BRAND"] = o["brand"] if o else None
        row[f"{label}_ORDER_CHANNEL"] = o["channel"] if o else None
        row[f"{label}_ORDER_STORE_ID"] = o["store"] if o else None
        row[f"{label}_ORDER_ID"] = o["order_id"] if o else None
        row[f"{label}_ORDER_DATE"] = o["dt"].isoformat() if o else None
        row[f"{label}_ORDER_NET_AMT"] = o["net"] if o else None
        row[f"{label}_ORDER_TOTAL_AMT"] = o["gross"] if o else None
        row[f"{label}_ORDER_TOTAL_ITEMS"] = o["items"] if o else None
    row["FIRST_TO_SECOND_ORDER_DAYS"] = (orders[1]["dt"] - orders[0]["dt"]).days if len(orders) > 1 else None
    row["FIRST_TO_LATEST_ORDER_DAYS"] = (orders[-1]["dt"] - orders[0]["dt"]).days if orders else None
    row["DAYS_SINCE_LATEST_ORDER"] = (END_DT - orders[-1]["dt"]).days if orders else None
    row["ONE_AND_DONE"] = "Y" if len(orders) == 1 else "N"
    brands = {o["brand"] for o in orders}
    chans = {o["channel"] for o in orders}
    row["SINGLE_BRAND"], row["MULTI_BRAND"] = ("Y", "N") if len(brands) == 1 else ("N", "Y")
    row["SINGLE_CHANNEL"], row["MULTI_CHANNEL"] = ("Y", "N") if len(chans) == 1 else ("N", "Y")
    row["EARLY_REPEAT_PURCHASER"] = "Y" if (len(orders) > 1 and (orders[1]["dt"] - orders[0]["dt"]).days <= 90) else "N"
    row.update(aggregates(orders, None, "LIFETIME"))
    row["LIFETIME_LARGEST_ORDER_VALUE_AMT"] = max((o["net"] for o in orders), default=0.0)
    row.update(aggregates(orders, END_DT - timedelta(days=365), "L12M"))
    row.update(aggregates(orders, END_DT - timedelta(days=182), "L6M"))
    row.update(aggregates(orders, END_DT - timedelta(days=91), "L3M"))
    row.update(aggregates(orders, END_DT - timedelta(days=30), "L30D"))
    # simple RFM over L12M: recency (days since latest in L12M), frequency, monetary -> 1..5 buckets, segment label
    l12 = [o for o in orders if o["dt"] >= END_DT - timedelta(days=365)]
    if l12:
        rec_days = (END_DT - l12[-1]["dt"]).days
        r = 5 if rec_days <= 30 else 4 if rec_days <= 90 else 3 if rec_days <= 180 else 2 if rec_days <= 270 else 1
        f = min(5, len(l12))
        m_net = sum(o["net"] for o in l12)
        m = 5 if m_net >= 2000 else 4 if m_net >= 1000 else 3 if m_net >= 400 else 2 if m_net >= 150 else 1
        row["L12M_RECENCY"], row["L12M_FREQUENCY"], row["L12M_MONETARY"] = str(r), str(f), str(m)
        row["L12M_RFM_SCORE"] = r * 100 + f * 10 + m
        row["L12M_RFM_CUSTOMER_SEGMENT"] = ("CHAMPION" if r >= 4 and f >= 3 and m >= 4 else "LOYAL" if f >= 3 else "RECENT" if r >= 4 else "AT_RISK" if r <= 2 and f >= 2 else "OCCASIONAL")
    else:
        row["L12M_RECENCY"] = row["L12M_FREQUENCY"] = row["L12M_MONETARY"] = None
        row["L12M_RFM_SCORE"] = None
        row["L12M_RFM_CUSTOMER_SEGMENT"] = "LAPSED"
    row["RETAIL_FLAG"] = "Y" if any(o["channel"] == "RETAIL" for o in orders) else "N"
    return row


TABLES = ("ORDER_HEADER", "ORDER_LINE", "RETAIL_STORE_ESTIMATE_HEADER", "truth_records", "expected_CUSTOMER", "truth_persons")


def _run_batch(args: tuple) -> dict:
    batch, persons, seed, out = args
    people, oh, ol, est, truth, expected = gen(persons, seed, batch=batch)
    hh = pd.DataFrame([{"person_id": p.pid, "household_id": p.household, "first": p.first, "last": p.last, "loyalty_id": p.loyalty_id, "employee_id": p.employee_id} for p in people])
    for name, df in zip(TABLES, (oh, ol, est, truth, expected, hh)):
        d = Path(out) / name
        d.mkdir(parents=True, exist_ok=True)
        df.to_parquet(d / f"part-{batch:04d}.parquet", index=False)
    return {
        "batch": batch, "persons": persons, "orders": int(len(oh)), "order_lines": int(len(ol)), "estimates": int(len(est)),
        "identity_records": int(len(truth)), "records_by_role": truth["role"].value_counts().to_dict(),
        "anonymous_pos_orders": int(truth["person_id"].str.startswith("anon:").sum()),
        "gift_recipients_in_base": int(((truth["role"] == "ship_to_gift") & ~truth["person_id"].str.startswith("stranger:")).sum()),
        "persons_with_orders": int(expected["CUSTOMER_ID"].nunique()), "households": int(hh["household_id"].nunique()),
        "channels": oh["SUB_CHANNEL_TYPE_CD"].value_counts().to_dict(), "concepts": oh["CONCEPT_CD"].value_counts().to_dict(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--persons", type=int, default=60000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch-size", type=int, default=40000, help="persons per batch (each batch is one parquet part per table)")
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    sizes = [a.batch_size] * (a.persons // a.batch_size) + ([a.persons % a.batch_size] if a.persons % a.batch_size else [])
    jobs = [(b, n, a.seed * 1000 + b, str(out)) for b, n in enumerate(sizes)]
    if a.workers > 1 and len(jobs) > 1:
        from multiprocessing import Pool
        with Pool(a.workers) as pool:
            parts = list(pool.imap_unordered(_run_batch, jobs))
    else:
        parts = [_run_batch(j) for j in jobs]
    parts.sort(key=lambda d: d["batch"])
    agg: dict = {"generator": "tools/wsi_edap_sim.py", "seed": a.seed, "persons": a.persons, "batches": len(parts), "batch_size": a.batch_size,
                 "window": [START_DT.isoformat(), END_DT.isoformat()], "layout": "one parquet directory per table, part-<batch>.parquet"}
    for k in ("orders", "order_lines", "estimates", "identity_records", "anonymous_pos_orders", "gift_recipients_in_base", "persons_with_orders", "households"):
        agg[k] = sum(p[k] for p in parts)
    for k in ("records_by_role", "channels", "concepts"):
        c: Counter = Counter()
        for p in parts:
            c.update(p[k])
        agg[k] = dict(c)
    (out / "manifest.json").write_text(json.dumps(agg, indent=1))
    print(json.dumps(agg, indent=1))


if __name__ == "__main__":
    main()
