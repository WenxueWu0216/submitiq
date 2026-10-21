"""Value parsing and entity normalization.

Two levels, so the experiment log can measure what normalization buys:
  basic  the formats a clean agency system prints (and what the LLM is told to emit)
  full   plus the variants brokers actually send: "$1.25M", "ISO 4", "MNC",
         "Jan 5, 2027", "Yes"/"Partial", and entity-name canonicalization.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional

Mode = str  # "basic" | "full"

_MONEY_BASIC = re.compile(r"^\$?\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?$")
_MONEY_SUFFIX = re.compile(r"^\$?\s*(\d+(?:\.\d+)?)\s*(m|mm|mil|million|k|thousand)$", re.I)


def parse_money(v: Any, mode: Mode = "basic") -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("USD", "").strip()
    s = s.replace(" ", "") if mode == "full" else s
    m = _MONEY_BASIC.match(s)
    if m:
        return float(s.replace("$", "").replace(",", "").strip())
    if mode == "full":
        s2 = s.replace("S", "$", 1) if s.startswith("S") else s   # OCR reads '$' as 'S'
        m = _MONEY_BASIC.match(s2)
        if m:
            return float(s2.replace("$", "").replace(",", ""))
        m = _MONEY_SUFFIX.match(s2)
        if m:
            mult = 1_000_000 if m.group(2).lower().startswith("m") else 1_000
            return round(float(m.group(1)) * mult, 2)
    return None


def parse_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace(",", "").rstrip("%")
    return int(s) if re.fullmatch(r"-?\d+", s) else None


_DATE_FMTS_BASIC = ["%m/%d/%Y", "%Y-%m-%d"]
_DATE_FMTS_FULL = _DATE_FMTS_BASIC + ["%B %d, %Y", "%b %d, %Y", "%d-%b-%Y", "%m/%d/%y", "%m-%d-%Y",
                                      "%A, %B %d, %Y", "%d %b %Y"]


def parse_date(v: Any, mode: Mode = "basic") -> Optional[date]:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = re.sub(r"\s+", " ", str(v).strip().rstrip("."))
    for fmt in (_DATE_FMTS_FULL if mode == "full" else _DATE_FMTS_BASIC):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


_CONSTRUCTION_BASIC = {
    "frame": "frame", "joistedmasonry": "joisted_masonry", "noncombustible": "non_combustible",
    "masonrynoncombustible": "masonry_non_combustible", "modifiedfireresistive": "modified_fire_resistive",
    "fireresistive": "fire_resistive",
}
_CONSTRUCTION_FULL = {
    **_CONSTRUCTION_BASIC,
    "woodframe": "frame", "iso1": "frame", "frame1": "frame", "fr1": "frame",
    "jm": "joisted_masonry", "iso2": "joisted_masonry", "brickjoisted": "joisted_masonry",
    "noncomb": "non_combustible", "iso3": "non_combustible", "metalbldg": "non_combustible", "nc": "non_combustible",
    "mnc": "masonry_non_combustible", "iso4": "masonry_non_combustible", "masonrynoncomb": "masonry_non_combustible",
    "mfr": "modified_fire_resistive", "iso5": "modified_fire_resistive", "modfireresistive": "modified_fire_resistive",
    "fr": "fire_resistive", "iso6": "fire_resistive",
}


def parse_construction(v: Any, mode: Mode = "basic") -> Optional[str]:
    if v is None or v == "":
        return None
    k = _key(str(v))
    table = _CONSTRUCTION_FULL if mode == "full" else _CONSTRUCTION_BASIC
    if k in table:
        return table[k]
    return str(v) if str(v) in _CONSTRUCTION_BASIC.values() else None


def parse_bool(v: Any, mode: Mode = "basic") -> Optional[bool]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    k = _key(str(v))
    if k in ("y", "true"):
        return True
    if k in ("n", "false"):
        return False
    if mode == "full":
        if k in ("yes", "100", "partial", "full") or (k.isdigit() and int(k) > 0):
            return True
        if k in ("no", "none", "0"):
            return False
    return None


def parse_pct(v: Any) -> Optional[int]:
    return parse_int(str(v).replace("%", "")) if v not in (None, "") else None


_ENUMS: dict[str, dict[str, str]] = {
    "entity_type": {"llc": "llc", "corporation": "corporation", "partnership": "partnership",
                    "individual": "sole_proprietor", "notforprofit": "nonprofit", "soleproprietor": "sole_proprietor",
                    "nonprofit": "nonprofit"},
    "transaction_type": {"new": "new", "renewal": "renewal"},
    "valuation": {"replacementcost": "replacement_cost", "actualcashvalue": "actual_cash_value",
                  "rc": "replacement_cost", "acv": "actual_cash_value"},
    "cause_of_loss_form": {"special": "special", "broad": "broad", "basic": "basic"},
    "roof_type": {"asphaltshingle": "asphalt_shingle", "metal": "metal", "builtup": "built_up",
                  "membranetpo": "membrane", "membrane": "membrane", "tile": "tile"},
    "alarm_type": {"none": "none", "local": "local", "centralstation": "central_station"},
    "status": {"open": "open", "closed": "closed", "reopened": "open"},
}
_ENUMS_FULL_EXTRA: dict[str, dict[str, str]] = {
    "entity_type": {"inc": "corporation", "corp": "corporation", "lp": "partnership", "soleprop": "sole_proprietor",
                    "nonprofitcorporation": "nonprofit", "501c3": "nonprofit"},
    "transaction_type": {"newbusiness": "new", "rewrite": "renewal"},
    "roof_type": {"tpo": "membrane", "epdm": "membrane", "shingle": "asphalt_shingle"},
    "alarm_type": {"central": "central_station", "centralstn": "central_station"},
}


def parse_enum(field: str, v: Any, mode: Mode = "basic") -> Optional[str]:
    if v is None or v == "":
        return None
    k = _key(str(v))
    table = dict(_ENUMS[field])
    if mode == "full":
        table.update(_ENUMS_FULL_EXTRA.get(field, {}))
    if k in table:
        return table[k]
    values = set(_ENUMS[field].values())
    return str(v) if str(v) in values else None


# ---------------------------------------------------------------- entity names

_LEGAL = {"llc", "l l c", "inc", "incorporated", "corp", "corporation", "co", "company", "lp", "llp", "ltd",
          "partners", "the"}
_GENERIC = {"holdings", "group", "enterprises", "international"}


def core_name(name: str) -> set[str]:
    """Tokens that identify an organisation, without legal suffixes and generic words."""
    s = name.lower().replace("&", " and ")
    s = re.sub(r"l\.\s*l\.\s*c\.?", "llc", s)
    tokens = [t for t in re.sub(r"[^a-z0-9 ]+", " ", s).split() if t not in _LEGAL and t not in _GENERIC and t != "and"]
    return set(tokens)


def same_entity(a: str, b: str) -> bool:
    """'Acme Logistics LLC' ~ 'ACME LOGISTICS, L.L.C.' ~ 'Acme Holdings'; not ~ 'Acme Distribution Inc.'"""
    ca, cb = core_name(a), core_name(b)
    if not ca or not cb:
        return False
    if ca <= cb or cb <= ca:
        return True
    return len(ca & cb) / len(ca | cb) >= 0.75


def norm_street(s: str) -> str:
    s = s.lower()
    for long, short in (("street", "st"), ("avenue", "ave"), ("road", "rd"), ("boulevard", "blvd"),
                        ("drive", "dr"), ("parkway", "pkwy"), ("lane", "ln")):
        s = re.sub(rf"\b{long}\b", short, s)
    return re.sub(r"[^a-z0-9 ]", "", s).strip()
