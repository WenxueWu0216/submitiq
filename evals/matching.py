"""Value comparison and record alignment for field-level scoring.

Matching is tolerant of formatting ("$1,250,000" vs 1250000.0, "St" vs "Street",
case and punctuation) and strict about meaning (a different year, a different
enum, a different company). Each rule is listed here so it can be reviewed.
"""
from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from typing import Any

from submitiq.fields import claim_key, spec
from submitiq.schema import Submission

_STREET = {"street": "st", "avenue": "ave", "road": "rd", "boulevard": "blvd", "drive": "dr",
           "parkway": "pkwy", "lane": "ln", "suite": "ste"}


def norm_text(s: str) -> str:
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = [_STREET.get(w, w) for w in s.split()]
    return " ".join(words)


def _digits(s: Any) -> str:
    return re.sub(r"\D", "", str(s))


def values_match(path: str, gold: Any, pred: Any) -> bool:
    if gold is None or pred is None:
        return gold is None and pred is None
    kind = spec(path).kind
    try:
        if kind in ("text", "state"):
            return norm_text(str(gold)) == norm_text(str(pred))
        if kind == "fuzzy":
            a, b = norm_text(str(gold)), norm_text(str(pred))
            return a == b or SequenceMatcher(None, a, b).ratio() >= 0.85
        if kind == "money":
            g, p = float(gold), float(pred)
            return abs(g - p) <= max(1.0, 0.005 * abs(g))
        if kind == "int":
            return int(gold) == int(pred)
        if kind == "approx_int":
            return abs(int(gold) - int(pred)) <= max(1, int(0.01 * abs(int(gold))))
        if kind == "date":
            g = gold if isinstance(gold, date) else date.fromisoformat(str(gold))
            p = pred if isinstance(pred, date) else date.fromisoformat(str(pred))
            return g == p
        if kind in ("enum",):
            return str(gold).lower() == str(pred).lower()
        if kind == "bool":
            return bool(gold) == bool(pred)
        if kind in ("phone", "digits"):
            return _digits(gold) == _digits(pred) and _digits(gold) != ""
        if kind == "email":
            return str(gold).strip().lower() == str(pred).strip().lower()
        if kind == "url":
            strip = lambda u: re.sub(r"^(https?://)?(www\.)?", "", str(u).strip().lower()).rstrip("/")
            return strip(gold) == strip(pred)
        if kind == "zip":
            return _digits(gold)[:5] == _digits(pred)[:5]
    except (TypeError, ValueError):
        return False
    raise ValueError(f"unknown kind {kind} for {path}")


def align(gold: Submission, pred: Submission) -> Submission:
    """Re-key predicted locations/claims onto the gold keys where they clearly correspond.

    Locations: same loc_number, else same normalized street.
    Claims: same normalized claim number, else same date of loss and incurred within 1%.
    Unmatched predictions keep their own keys (and count as false positives).
    """
    pred = pred.model_copy(deep=True)
    gold_locs = {l.loc_number: l for l in gold.locations}
    by_street = {norm_text(l.street or ""): l.loc_number for l in gold.locations if l.street}
    used: set[int] = set()
    for loc in pred.locations:
        if loc.loc_number in gold_locs and loc.loc_number not in used:
            used.add(loc.loc_number)
            continue
        alt = by_street.get(norm_text(loc.street or ""))
        if alt is not None and alt not in used:
            loc.loc_number = alt
            used.add(alt)

    gold_claims = {claim_key(c.claim_number): c for c in gold.claims}
    used_c: set[str] = set()
    for cl in pred.claims:
        k = claim_key(cl.claim_number)
        if k in gold_claims and k not in used_c:
            used_c.add(k)
            continue
        for gk, gc in gold_claims.items():
            if gk in used_c or gc.date_of_loss is None or cl.date_of_loss != gc.date_of_loss:
                continue
            if cl.incurred is None or gc.incurred is None or abs(cl.incurred - gc.incurred) <= max(1.0, 0.01 * gc.incurred):
                cl.claim_number = gc.claim_number
                used_c.add(gk)
                break
    return pred
