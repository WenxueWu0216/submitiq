"""Cross-document consistency checks.

The assembled record already holds the source-of-truth winner for each field.
This step compares the winner with every reading from a *different document*
(the application's year built vs the SOV's, the application's stated TIV vs the
SOV total, the email's effective date vs the application's) and with every
insured name printed anywhere in the package. A disagreement never changes
the chosen value. It marks the field `conflict`, records both readings, and
sends the submission to review.
"""
from __future__ import annotations

from typing import Any

from .extract.types import DocExtraction
from .fields import spec
from .normalize import core_name, norm_street, same_entity
from .result import Candidate, FieldProvenance

MONEY_TOLERANCE = {"totals.total_tiv": 0.02}   # stated totals are often rounded


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def same_value(path: str, a: Any, b: Any, mode: str) -> bool:
    kind = spec(path).kind
    if kind == "money":
        x, y = _num(a), _num(b)
        if x is None or y is None:
            return False
        tol = MONEY_TOLERANCE.get(path, 0.005)
        return abs(x - y) <= max(1.0, tol * max(abs(x), abs(y)))
    if kind in ("text", "fuzzy", "state"):
        sa, sb = str(a), str(b)
        if mode == "full":
            if path.endswith(".street"):
                return norm_street(sa) == norm_street(sb)
            return core_name(sa) == core_name(sb) if path.endswith(("named_insured", "carrier", "agency_name")) \
                else sa.strip().lower() == sb.strip().lower()
        return sa.strip() == sb.strip()
    if kind in ("phone", "digits", "zip"):
        return "".join(ch for ch in str(a) if ch.isdigit()) == "".join(ch for ch in str(b) if ch.isdigit())
    if kind == "email":
        return str(a).strip().lower() == str(b).strip().lower()
    return a == b


def _conflict(fp: FieldProvenance, other: Candidate, reason: str) -> None:
    fp.status = "conflict"
    fp.reasons.append(reason)
    if other.citation not in fp.citations:
        fp.citations.append(other.citation)


def check(prov: dict[str, FieldProvenance], values: dict[str, Any], extractions: list[DocExtraction],
          mode: str) -> list[str]:
    """Mark conflicting fields in place. Returns human-readable review reasons."""
    reasons: list[str] = []
    for path, fp in prov.items():
        win_doc = fp.citations[0].doc if fp.citations else None
        for alt in fp.alternatives:
            if alt.citation.doc == win_doc or alt.extractor == "derived":
                continue
            if not same_value(path, values.get(path), alt.value, mode):
                msg = (f"{path}: {fp.citations[0].doc if fp.citations else '?'} says {values.get(path)!r}, "
                       f"{alt.citation.doc} says {alt.value!r} (kept the {fp.extractor} value per source-of-truth rules)")
                _conflict(fp, alt, msg)
                reasons.append(msg)
                break

    name_fp = prov.get("insured.named_insured")
    legal = values.get("insured.named_insured")
    if name_fp and legal:
        for ex in extractions:
            for printed, cite in ex.names:
                if mode == "full":
                    if same_entity(legal, printed):
                        if core_name(legal) != core_name(printed):
                            name_fp.reasons.append(f"name variant on {cite.doc}: {printed!r} (treated as the same entity)")
                        continue
                elif printed.strip() == str(legal).strip():
                    continue
                msg = f"insured.named_insured: application says {legal!r}, {cite.doc} says {printed!r}"
                _conflict(name_fp, Candidate(value=printed, extractor=ex.extractor, citation=cite), msg)
                reasons.append(msg)
    return reasons

