"""Preprocessing / normalisation for matching (Amperity: Unified Preprocessed Raw, internals §2.3).

- email: lowercase, local@domain only, strip `+tag` (configurable), optional gmail dot folding (off by
  default), junk local parts NULLed.
- phone: E.164 via `phonenumbers`; the match key is the last 10 digits.
- names: uppercase, strip punctuation; given-name nickname canonicalisation (built-in table, optionally
  extended from a CSV via ``normalize.nickname_file``).
- address: uppercase, strip punctuation, expand common abbreviations. With ``normalize.address_parsing: true``
  (default off, output changes) unit designators (APT / STE / UNIT / # / FL / BLDG), PO Boxes and compound
  directionals (NE / NW / SE / SW, prefix or suffix) are parsed into a canonical form so "12 Main St Apt 4B" and
  "12 MAIN STREET #4B" normalise identically. libpostal-style probabilistic tokenisation is out of scope (see
  docs/feature-parity.md).
- postal: first 5 digits for US-style codes; alphanumerics uppercased otherwise.
- birthdate: parse to YYYY-MM-DD when possible.
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import phonenumbers
from dateutil import parser as dateparser

from aurora_cdp.config import Config

log = logging.getLogger(__name__)

# Built-in nickname table (Amperity ships thousands in `stitch_nicknames`); extend it with a CSV through
# ``normalize.nickname_file`` (see :func:`load_nicknames`).
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
_NICKNAME_CACHE: dict[str, dict[str, str]] = {}


def load_nicknames(path: str | Path | None) -> dict[str, str]:
    """Nickname table: the built-in dict extended by a CSV (``nickname,canonical`` columns, header optional).

    Rows are upper-cased; a CSV entry overrides the built-in one for the same nickname. The result is cached per
    path for the life of the process. A missing path is an error (a configured table must exist)."""
    if not path:
        return NICKNAMES
    key = str(Path(path).resolve())
    cached = _NICKNAME_CACHE.get(key)
    if cached is not None:
        return cached
    table = dict(NICKNAMES)
    with Path(path).open("r", encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.reader(fh) if r and any(c.strip() for c in r)]
    if rows and {c.strip().lower() for c in rows[0][:2]} <= {
        "nickname",
        "canonical",
        "name",
        "alias",
    }:
        rows = rows[1:]  # header
    added = 0
    for row in rows:
        if len(row) < 2:
            raise ValueError(
                f"nickname file {path}: every row needs two columns (nickname, canonical); got {row!r}"
            )
        nick, canon = canonical_name(row[0]), canonical_name(row[1])
        if nick and canon and nick != canon:
            table[nick] = canon
            added += 1
    log.info("loaded %d nickname rows from %s (%d total)", added, path, len(table))
    _NICKNAME_CACHE[key] = table
    return table


def _missing(value) -> bool:
    """True for None, NaN/NaT and blank strings (pandas leaks NaN into object columns)."""
    if value is None:
        return True
    if isinstance(value, float) and value != value:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


_NON_ALNUM = re.compile(r"[^A-Z0-9 ]+")
_WS = re.compile(r"\s+")


def canonical_name(value: str | None) -> str | None:
    if _missing(value):
        return None
    s = _NON_ALNUM.sub(" ", str(value).upper())
    s = _WS.sub(" ", s).strip()
    return s or None


def canonical_given_name(value: str | None, nicknames: dict[str, str] | None = None) -> str | None:
    """Nickname-aware canonical form of the first given-name token (``nicknames`` defaults to the built-in table)."""
    n = canonical_name(value)
    if not n:
        return None
    first = n.split(" ")[0]
    return (nicknames if nicknames is not None else NICKNAMES).get(first, first)


def canonical_email(value: str | None, cfg: Config | dict) -> str | None:
    if _missing(value):
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
    if _missing(value):
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


# --- address parsing (opt-in: normalize.address_parsing) -------------------------------------------------------
_UNIT_DESIGNATORS = {
    "APT": "UNIT",
    "APARTMENT": "UNIT",
    "STE": "UNIT",
    "SUITE": "UNIT",
    "UNIT": "UNIT",
    "#": "UNIT",
    "NO": "UNIT",
    "RM": "UNIT",
    "ROOM": "UNIT",
    "FL": "FLOOR",
    "FLR": "FLOOR",
    "FLOOR": "FLOOR",
    "BLDG": "BUILDING",
    "BUILDING": "BUILDING",
    "LOT": "LOT",
    "SPC": "SPACE",
    "SPACE": "SPACE",
    "TRLR": "TRAILER",
    "TRAILER": "TRAILER",
}
_DIRECTIONALS = {
    "N": "NORTH",
    "S": "SOUTH",
    "E": "EAST",
    "W": "WEST",
    "NE": "NORTHEAST",
    "NW": "NORTHWEST",
    "SE": "SOUTHEAST",
    "SW": "SOUTHWEST",
    "NORTH": "NORTH",
    "SOUTH": "SOUTH",
    "EAST": "EAST",
    "WEST": "WEST",
    "NORTHEAST": "NORTHEAST",
    "NORTHWEST": "NORTHWEST",
    "SOUTHEAST": "SOUTHEAST",
    "SOUTHWEST": "SOUTHWEST",
}
_PO_BOX = re.compile(r"^(?:P\s*O\s*B(?:OX)?|POST\s+OFFICE\s+BOX|POB)\s*#?\s*([A-Z0-9-]+)\b")
_UNIT_GLUED = re.compile(r"^(APT|STE|UNIT|RM|FL|BLDG|LOT)([0-9][A-Z0-9-]*)$")  # APT4B -> APT 4B
_HASH_GLUED = re.compile(r"^#([A-Z0-9-]+)$")


def _basic_tokens(value: str, abbreviations: dict[str, str] | None) -> list[str]:
    s = _NON_ALNUM.sub(" ", str(value).upper().replace(".", "").replace(",", " "))
    tokens = [t for t in _WS.split(s) if t]
    abbr = {k.upper(): v.upper() for k, v in (abbreviations or {}).items()}
    return [abbr.get(t, t) for t in tokens]


def parse_address(
    value: str | None, abbreviations: dict[str, str] | None = None
) -> dict[str, str | None]:
    """Split a free-text street address into components (all upper-cased, punctuation stripped).

    Returns ``house_number``, ``street`` (name + type, directionals expanded), ``unit`` (designator + value, e.g.
    ``UNIT 4B`` / ``FLOOR 2``), ``po_box`` (box number) and ``canonical`` (the re-assembled string, see
    :func:`canonical_address`). Unknown layouts fall back to the plain token stream: nothing is dropped.
    """
    out: dict[str, str | None] = {
        "house_number": None,
        "street": None,
        "unit": None,
        "po_box": None,
        "canonical": None,
    }
    if _missing(value):
        return out
    raw = str(value).upper()
    # keep '#' long enough to recognise '#4B' as a unit, then strip punctuation like the basic path
    raw = re.sub(r"\s*#\s*", " # ", raw)
    s = re.sub(r"[^A-Z0-9# ]+", " ", raw.replace(".", "").replace(",", " "))
    tokens = [t for t in _WS.split(s) if t]
    abbr = {k.upper(): v.upper() for k, v in (abbreviations or {}).items()}
    m = _PO_BOX.match(" ".join(tokens))
    if m:
        out["po_box"] = m.group(1)
        rest = " ".join(tokens)[m.end() :].strip()
        out["canonical"] = f"PO BOX {m.group(1)}" + (f" {rest}" if rest else "")
        return out
    # split glued forms: APT4B -> APT 4B, #4B -> # 4B
    split: list[str] = []
    for t in tokens:
        g = _UNIT_GLUED.match(t) or _HASH_GLUED.match(t)
        if g and g.re is _UNIT_GLUED:
            split += [g.group(1), g.group(2)]
        elif g:
            split += ["#", g.group(1)]
        else:
            split.append(t)
    tokens = split
    # unit: first designator token followed by a value; everything after the unit value is kept as-is
    unit_parts: list[str] = []
    street_tokens: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in _UNIT_DESIGNATORS and i + 1 < len(tokens) and i > 0 and not unit_parts:
            unit_parts = [_UNIT_DESIGNATORS[t], tokens[i + 1]]
            i += 2
            continue
        street_tokens.append(t)
        i += 1
    if street_tokens and street_tokens[0].isdigit():
        out["house_number"] = street_tokens[0]
        body = street_tokens[1:]
    else:
        body = street_tokens
    # directionals: expand compound/single forms at either end of the street body (or anywhere, like the
    # abbreviation table does for N/S/E/W) and apply the configured abbreviations to the rest
    expanded = []
    for j, t in enumerate(body):
        if t in _DIRECTIONALS and (j == 0 or j == len(body) - 1 or t in ("N", "S", "E", "W")):
            expanded.append(_DIRECTIONALS[t])
        else:
            expanded.append(abbr.get(t, t))
    out["street"] = " ".join(expanded) or None
    out["unit"] = " ".join(unit_parts) or None
    parts = [p for p in (out["house_number"], out["street"], out["unit"]) if p]
    out["canonical"] = " ".join(parts) or None
    return out


def canonical_address(
    value: str | None, abbreviations: dict[str, str] | None = None, parse: bool = False
) -> str | None:
    """Uppercase, strip punctuation, expand abbreviations.

    ``parse=True`` (``normalize.address_parsing``) additionally canonicalises unit/suite designators, PO Boxes
    and compound directionals through :func:`parse_address`; the default keeps the historical token stream.
    """
    if _missing(value):
        return None
    if parse:
        return parse_address(value, abbreviations)["canonical"]
    return " ".join(_basic_tokens(str(value), abbreviations)) or None


def canonical_postal(value: str | None) -> str | None:
    if _missing(value):
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()
    if not s:
        return None
    if s.isdigit():
        return s[:5].zfill(5) if len(s) >= 5 else s.zfill(5)
    return s


def canonical_birthdate(value: str | None) -> str | None:
    if _missing(value):
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
    parse_addr = bool(ncfg.get("address_parsing", False))
    nicknames = load_nicknames(ncfg.get("nickname_file"))
    out = pd.DataFrame(index=raw.index)
    out["datasource"] = raw["datasource"]
    out["pk"] = raw["pk"]
    out["ck"] = raw["ck"]
    out["given_name_norm"] = raw["given_name"].map(canonical_name)
    out["given_name_canon"] = raw["given_name"].map(lambda v: canonical_given_name(v, nicknames))
    out["surname_norm"] = raw["surname"].map(canonical_name)
    out["email_norm"] = raw["email"].map(lambda v: canonical_email(v, ncfg))
    phones = raw["phone"].map(lambda v: canonical_phone(v, region))
    out["phone_e164"] = phones.map(lambda t: t[0])
    out["phone_match"] = phones.map(lambda t: t[1])
    out["address_norm"] = raw["address"].map(lambda v: canonical_address(v, abbr, parse_addr))
    out["postal_norm"] = raw["postal"].map(canonical_postal)
    out["birthdate_norm"] = raw["birthdate"].map(canonical_birthdate)
    out["loy_id_norm"] = raw["loy_id"].map(
        lambda v: (canonical_name(v) or "").replace(" ", "") or None
    )
    out["fk_json"] = raw["fk_json"]
    out["update_dt"] = raw["update_dt"]
    out["batch_id"] = raw["batch_id"]
    out["preprocessed_at"] = datetime.utcnow()
    return out.reset_index(drop=True)
