"""Normalisation helpers for emails, phones, names and addresses.

All functions are pure, null-safe and return ``None`` for empty input so the
same code can be used from pandas, plain Python and Spark UDFs.
"""

from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]")
_DIGITS = re.compile(r"\D+")
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "jr.", "sr."}
_TITLES = {"mr", "mrs", "ms", "miss", "dr", "prof", "sir", "madam"}
_STREET_ABBR = {
    "street": "st", "st.": "st", "avenue": "ave", "ave.": "ave", "road": "rd", "rd.": "rd",
    "drive": "dr", "dr.": "dr", "lane": "ln", "ln.": "ln", "boulevard": "blvd", "court": "ct",
    "place": "pl", "apartment": "apt", "suite": "ste", "north": "n", "south": "s", "east": "e",
    "west": "w",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _is_null(value: object) -> bool:
    return value is None or (isinstance(value, float) and value != value)


def clean_text(value: str | None) -> str | None:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    if _is_null(value):
        return None
    s = _strip_accents(str(value)).lower().strip()
    s = _NON_ALNUM.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s or None


def normalize_email(value: str | None) -> str | None:
    """Lowercase + trim. Returns None if not shaped like an email."""
    if _is_null(value):
        return None
    s = str(value).strip().lower()
    if "@" not in s or s.startswith("@") or s.endswith("@"):
        return None
    return s


def canonical_email(value: str | None) -> str | None:
    """Canonical form: strip ``+tag`` and dots in gmail-style local parts."""
    s = normalize_email(value)
    if s is None:
        return None
    local, _, domain = s.partition("@")
    local = local.split("+", 1)[0]
    if domain in {"gmail.com", "googlemail.com"}:
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}" if local else None


def normalize_phone(value: str | None, default_country: str = "1") -> str | None:
    """Digits only, E.164-ish (no '+'). 10-digit NANP numbers get the country code."""
    if _is_null(value):
        return None
    digits = _DIGITS.sub("", str(value))
    if not digits:
        return None
    if len(digits) == 10:
        digits = default_country + digits
    if len(digits) < 10 or len(digits) > 15:
        return None
    return digits


def normalize_name(value: str | None, nicknames: dict[str, str] | None = None) -> str | None:
    """Clean a name token; expand nicknames when a table is supplied."""
    s = clean_text(value)
    if s is None:
        return None
    parts = [p for p in s.split(" ") if p not in _SUFFIXES and p not in _TITLES]
    if not parts:
        return None
    if nicknames:
        parts = [nicknames.get(p, p) for p in parts]
    return " ".join(parts)


def split_full_name(value: str | None) -> tuple[str | None, str | None]:
    """Split 'Given [Middle] Surname [Suffix]' into (given, surname)."""
    s = clean_text(value)
    if not s:
        return None, None
    parts = [p for p in s.split(" ") if p not in _SUFFIXES and p not in _TITLES]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[-1]


def normalize_street(value: str | None) -> str | None:
    s = clean_text(value)
    if s is None:
        return None
    return " ".join(_STREET_ABBR.get(tok, tok) for tok in s.split(" "))


def house_number(street: str | None) -> str | None:
    s = clean_text(street)
    if not s:
        return None
    first = s.split(" ", 1)[0]
    return first if first.isdigit() else None


def normalize_postal(value: str | None) -> str | None:
    if _is_null(value):
        return None
    s = re.sub(r"[^a-z0-9]", "", str(value).lower())
    if not s:
        return None
    return s[:5] if s.isdigit() and len(s) >= 5 else s


def normalize_dob(value: str | None) -> str | None:
    """Accept ISO yyyy-mm-dd, yyyymmdd or mm/dd/yyyy; return ISO or None."""
    if _is_null(value):
        return None
    s = str(value).strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return s
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}"
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}"
    return None
