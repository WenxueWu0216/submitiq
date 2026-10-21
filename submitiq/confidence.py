"""Field confidence, validation, and review routing.

confidence = prior(extractor) x reading_quality^2, then adjusted:
  + an independent reading (another document or extractor) agrees  -> noisy-OR boost
  - a reading from the *same* document disagrees (parser vs LLM)     -> x0.5
  - the field is in a failed reconciliation (SOV totals, loss year)  -> x0.5, status invalid
  - the value is implausible (roof older than building, PPC 11, ...) -> x0.3, status invalid
  - an LLM value whose evidence quote is not in the document text    -> x0.6
Fields below THRESHOLD become low_confidence. Critical fields the rules need
but nobody could read are added as `missing`.

Routing: a submission goes to human review if any critical field is flagged,
or any field anywhere is in conflict or invalid. A low-confidence non-critical
field (a website, a contact phone) is highlighted in the UI but does not block.
The priors and the threshold were tuned on dev only (docs/experiment_log.md, 4d).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from .consistency import same_value
from .documents import Document
from .extract.types import DocExtraction
from .fields import spec
from .guidelines import load_rules
from .result import FieldProvenance

PRIORS = [  # (extractor prefix, prior); first match wins
    ("derived", 0.95), ("table_parser", 0.95), ("email_parser", 0.95), ("form_parser:premises", 0.90),
    ("form_parser", 0.92), ("llm:baseline", 0.60), ("llm:", 0.85),
]
THRESHOLD = 0.80
OCR_EXPONENT = 1.0
VALIDATED_BOOST = 0.85   # a passed reconciliation is independent evidence the value was read correctly
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC "
                "ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())


def prior(extractor: str | None) -> float:
    for prefix, p in PRIORS:
        if extractor and extractor.startswith(prefix):
            return p
    return 0.5


def plausibility(path: str, v: Any, values: dict[str, Any]) -> str | None:
    """Return a reason string if the value cannot be right."""
    field = path.rsplit(".", 1)[-1]
    eff = values.get("policy.effective_date")
    eff_year = eff.year if isinstance(eff, date) else date.today().year
    loc = path.split("]")[0] + "]" if path.startswith("locations[") else None
    if field == "year_built" and not 1800 <= v <= eff_year + 1:
        return f"year built {v} outside 1800-{eff_year + 1}"
    if field == "roof_year":
        yb = values.get(f"{loc}.year_built") if loc else None
        if not 1900 <= v <= eff_year + 1 or (isinstance(yb, int) and v < yb):
            return f"roof year {v} implausible (built {yb})"
    if field == "protection_class" and not 1 <= v <= 10:
        return f"protection class {v} outside 1-10"
    if field in ("sprinkler_pct", "coinsurance_pct") and not 0 <= v <= 100:
        return f"{field} {v} outside 0-100"
    if field == "sprinkler_pct" and loc and values.get(f"{loc}.sprinklered") is False and v > 0:
        return "marked unsprinklered but sprinkler % > 0"
    if field == "stories" and not 1 <= v <= 150:
        return f"{v} stories"
    if spec(path).kind == "money" and v < 0:
        return "negative amount"
    if field in ("producer_email", "contact_email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", str(v)):
        return f"not a valid email address: {v!r}"
    if field in ("producer_phone", "contact_phone") and len(re.sub(r"\D", "", str(v))) != 10:
        return f"not a 10-digit phone number: {v!r}"
    if field == "fein" and len(re.sub(r"\D", "", str(v))) != 9:
        return f"FEIN must have 9 digits: {v!r}"
    if field == "state" and str(v) not in US_STATES:
        return f"unknown state {v!r}"
    if field == "zip" and not re.fullmatch(r"\d{5}", str(v)):
        return f"bad ZIP {v!r}"
    if field == "naics_code" and not re.fullmatch(r"\d{6}", str(v)):
        return f"NAICS must have 6 digits: {v!r}"
    if path == "policy.expiration_date" and isinstance(eff, date) and v <= eff:
        return "expiration not after effective date"
    if field == "date_of_loss" and path.startswith("claims["):
        py = values.get(path.replace("date_of_loss", "policy_year"))
        if isinstance(py, int) and not py <= v.year <= py + 1:
            return f"loss date {v} outside policy year {py}"
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _required_paths(values: dict[str, Any]) -> list[str]:
    req = load_rules()["required_fields"]
    paths = list(req["account"]) + ["insured.named_insured", "policy.effective_date", "totals.total_tiv"]
    loc_keys = sorted({p.split("]")[0] + "]" for p in values if p.startswith("locations[")})
    for k in loc_keys:
        paths += [f"{k}.{f}" for f in req["location"]]
    return paths


def score_and_route(prov: dict[str, FieldProvenance], values: dict[str, Any], extractions: list[DocExtraction],
                    docs: list[Document], threshold: float = THRESHOLD,
                    ocr_exponent: float = OCR_EXPONENT) -> tuple[bool, list[str]]:
    doc_text = {d.name: _norm(d.text()) for d in docs}
    failed: dict[str, list[str]] = {}
    passed: set[str] = set()
    for ex in extractions:
        for v in ex.validations:
            for p in v.paths:
                if v.passed:
                    passed.add(p)
                else:
                    failed.setdefault(p, []).append(f"{v.name}: {v.detail}")

    for path, fp in prov.items():
        value = values.get(path)
        win_doc = fp.citations[0].doc if fp.citations else None
        quality = min(1.0, max(0.0, fp.confidence if fp.confidence is not None else 1.0))
        c = prior(fp.extractor) * quality ** ocr_exponent
        if path in passed and path not in failed:
            c = 1 - (1 - c) * (1 - VALIDATED_BOOST)
        for alt in fp.alternatives:
            if alt.extractor == fp.extractor and alt.citation.doc == win_doc:
                continue
            agrees = value is not None and same_value(path, value, alt.value, "full")
            if agrees:
                c = 1 - (1 - c) * (1 - prior(alt.extractor) * alt.confidence ** ocr_exponent * 0.8)
            elif alt.citation.doc == win_doc:
                c *= 0.5
                fp.reasons.append(f"{alt.extractor} read {alt.value!r} from the same document")
        if fp.extractor and fp.extractor.startswith("llm:") and fp.citations:
            ev = fp.citations[0].snippet
            if ev and _norm(ev) and _norm(ev)[:60] not in doc_text.get(fp.citations[0].doc, ""):
                c *= 0.6
                fp.reasons.append("LLM evidence quote not found in the document")
        if path in failed:
            c *= 0.5
            fp.status = "invalid" if fp.status == "ok" else fp.status
            fp.reasons += failed[path]
        if value is not None:
            try:
                why = plausibility(path, value, values)
            except (TypeError, ValueError):
                why = f"unexpected value type {type(value).__name__}"
            if why:
                c *= 0.3
                fp.status = "invalid" if fp.status == "ok" else fp.status
                fp.reasons.append(why)
        fp.confidence = round(min(c, 0.99), 3)
        if fp.status == "ok" and fp.confidence < threshold:
            fp.status = "low_confidence"
            fp.reasons.append(f"confidence {fp.confidence:.2f} < {threshold}")

    for path in _required_paths(values):
        if values.get(path) is None:
            prov[path] = FieldProvenance(path=path, confidence=0.0, status="missing",
                                         reasons=["required for the appetite rules but not found in any document"])

    reasons: list[str] = []
    for path, fp in sorted(prov.items()):
        if fp.status == "ok":
            continue
        critical = spec(path).critical
        if critical or fp.status in ("conflict", "invalid"):
            reasons.append(f"{path}: {fp.status} ({'; '.join(fp.reasons[-2:])})")
    return bool(reasons), reasons
