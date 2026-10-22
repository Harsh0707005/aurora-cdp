"""Preprocessing / normalisation for matching (Amperity: Unified Preprocessed Raw, internals §2.3).

- email: lowercase, local@domain only, strip `+tag` (configurable), optional gmail dot folding (off by
  default), junk local parts NULLed.
- phone: E.164 via `phonenumbers`; the match key is the last 10 digits.
- names: uppercase, strip punctuation; given-name nickname canonicalisation (stub table).
- address: uppercase, strip punctuation, expand common abbreviations. TODO: unit/suite parsing,
  PO Box detection, libpostal-style tokenisation.
- postal: first 5 digits for US-style codes; alphanumerics uppercased otherwise.
- birthdate: parse to YYYY-MM-DD when possible.
"""

from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
import phonenumbers
from dateutil import parser as dateparser

from aurora_cdp.config import Config

# Minimal nickname table; Amperity ships thousands in `stitch_nicknames`. TODO: load from a CSV table.
NICKNAMES: dict[str, str] = {
    "MIKE": "MICHAEL",
    "MICK": "MICHAEL",
    "BILL": "WILLIAM",
    "WILL": "WILLIAM",
    "BILLY": "WILLIAM",
    "BOB": "ROBERT",
    "ROB": "ROBERT",
    "BOBBY": "ROBERT",
    "JIM": "JAMES",
    "JIMMY": "JAMES",
    "LIZ": "ELIZABETH",
    "BETH": "ELIZABETH",
    "BETTY": "ELIZABETH",
    "KATE": "KATHERINE",
    "KATHY": "KATHERINE",
    "KATIE": "KATHERINE",
    "TOM": "THOMAS",
    "TOMMY": "THOMAS",
    "DAVE": "DAVID",
    "DAN": "DANIEL",
    "DANNY": "DANIEL",
    "CHRIS": "CHRISTOPHER",
    "JOE": "JOSEPH",
    "JOEY": "JOSEPH",
    "TONY": "ANTHONY",
    "STEVE": "STEVEN",
    "JEN": "JENNIFER",
    "JENNY": "JENNIFER",
    "SUE": "SUSAN",
    "SUSIE": "SUSAN",
    "PEGGY": "MARGARET",
    "MAGGIE": "MARGARET",
    "RICK": "RICHARD",
    "DICK": "RICHARD",
    "RICH": "RICHARD",
    "ANDY": "ANDREW",
    "DREW": "ANDREW",
    "MATT": "MATTHEW",
    "NICK": "NICHOLAS",
    "ALEX": "ALEXANDER",
    "SAM": "SAMUEL",
    "BEN": "BENJAMIN",
    "ED": "EDWARD",
    "EDDIE": "EDWARD",
    "TED": "EDWARD",
    "PAT": "PATRICIA",
    "PATTY": "PATRICIA",
    "TRISH": "PATRICIA",
    "BECKY": "REBECCA",
    "ABBY": "ABIGAIL",
    "ALLIE": "ALLISON",
    "CHARLIE": "CHARLES",
    "CHUCK": "CHARLES",
    "FRANK": "FRANCIS",
    "GREG": "GREGORY",
    "JACK": "JOHN",
    "JOHNNY": "JOHN",
    "JON": "JONATHAN",
    "LARRY": "LAWRENCE",
    "RON": "RONALD",
    "RONNIE": "RONALD",
    "TIM": "TIMOTHY",
    "WALT": "WALTER",
}

_GMAIL_LIKE = {"gmail.com", "googlemail.com"}
_NON_ALNUM = re.compile(r"[^A-Z0-9 ]+")
_WS = re.compile(r"\s+")


def canonical_name(value: str | None) -> str | None:
    if not value:
        return None
    s = _NON_ALNUM.sub(" ", str(value).upper())
    s = _WS.sub(" ", s).strip()
    return s or None


def canonical_given_name(value: str | None) -> str | None:
    """Nickname-aware canonical form (first token only; stub for a full nickname table)."""
    n = canonical_name(value)
    if not n:
        return None
    first = n.split(" ")[0]
    return NICKNAMES.get(first, first)


def canonical_email(value: str | None, cfg: Config | dict) -> str | None:
    if not value:
        return None
    s = str(value).strip().lower()
    if "@" not in s:
        return None
    local, _, domain = s.rpartition("@")
    local = local.strip()
    domain = domain.strip()
    if not local or "." not in domain:
        return None
    if cfg.get("email_strip_plus_tag", True) and "+" in local:
        local = local.split("+", 1)[0]
    if cfg.get("email_strip_gmail_dots", False) and domain in _GMAIL_LIKE:
        local = local.replace(".", "")
    junk = {j.lower() for j in cfg.get("email_junk_local_parts", [])}
    if local in junk:
        return None
    return f"{local}@{domain}"


def canonical_phone(value: str | None, region: str = "US") -> tuple[str | None, str | None]:
    """Return (e164, last10) or (None, None) when unparseable."""
    if not value:
        return None, None
    raw = str(value).strip()
    try:
        num = phonenumbers.parse(raw, region)
        if not phonenumbers.is_possible_number(num):
            return None, None
        e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 10:
            return None, None
        e164 = "+" + digits
    digits = re.sub(r"\D", "", e164)
    return e164, digits[-10:]


def canonical_address(value: str | None, abbreviations: dict[str, str] | None = None) -> str | None:
    """Uppercase, strip punctuation, expand abbreviations. TODO: unit parsing, PO Box, directional suffixes."""
    if not value:
        return None
    s = _NON_ALNUM.sub(" ", str(value).upper().replace(".", "").replace(",", " "))
    tokens = [t for t in _WS.split(s) if t]
    abbr = {k.upper(): v.upper() for k, v in (abbreviations or {}).items()}
    tokens = [abbr.get(t, t) for t in tokens]
    return " ".join(tokens) or None


def canonical_postal(value: str | None) -> str | None:
    if not value:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()
    if not s:
        return None
    if s.isdigit():
        return s[:5].zfill(5) if len(s) >= 5 else s.zfill(5)
    return s


def canonical_birthdate(value: str | None) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    try:
        return dateparser.parse(s, default=datetime(1900, 1, 1)).strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None


def preprocess_records(raw: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """silver_unified_raw rows -> silver_unified_preprocessed rows."""
    ncfg = cfg.normalize
    abbr = ncfg.get("address_abbreviations", {})
    region = ncfg.get("default_region", "US")
    out = pd.DataFrame(index=raw.index)
    out["datasource"] = raw["datasource"]
    out["pk"] = raw["pk"]
    out["ck"] = raw["ck"]
    out["given_name_norm"] = raw["given_name"].map(canonical_name)
    out["given_name_canon"] = raw["given_name"].map(canonical_given_name)
    out["surname_norm"] = raw["surname"].map(canonical_name)
    out["email_norm"] = raw["email"].map(lambda v: canonical_email(v, ncfg))
    phones = raw["phone"].map(lambda v: canonical_phone(v, region))
    out["phone_e164"] = phones.map(lambda t: t[0])
    out["phone_match"] = phones.map(lambda t: t[1])
    out["address_norm"] = raw["address"].map(lambda v: canonical_address(v, abbr))
    out["postal_norm"] = raw["postal"].map(canonical_postal)
    out["birthdate_norm"] = raw["birthdate"].map(canonical_birthdate)
    out["loy_id_norm"] = raw["loy_id"].map(lambda v: canonical_name(v).replace(" ", "") if v else None)
    out["fk_json"] = raw["fk_json"]
    out["update_dt"] = raw["update_dt"]
    out["batch_id"] = raw["batch_id"]
    out["preprocessed_at"] = datetime.utcnow()
    return out.reset_index(drop=True)
