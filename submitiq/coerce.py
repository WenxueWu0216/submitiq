"""Turn loosely typed extractor output (LLM JSON, parser strings) into a valid Submission.

Bad values are dropped with an error message, never guessed: a field that
fails to parse ends up null, and review routing sees it as missing.
"""
from __future__ import annotations

import re
from typing import Any

from . import normalize as N
from .fields import spec
from .schema import Claim, Location, LossYear, Submission

_ENUM_FIELD = {"entity_type", "transaction_type", "valuation", "cause_of_loss_form", "roof_type", "alarm_type", "status"}


def parse_value(path: str, value: Any, mode: str = "basic") -> Any:
    """Parse one raw value for a flattened path. Returns None when it cannot be parsed."""
    if value is None or (isinstance(value, str) and value.strip() in ("", "-", "N/A", "n/a", "null", "None")):
        return None
    field = path.rsplit(".", 1)[-1]
    kind = spec(path).kind
    if field == "construction":
        return N.parse_construction(value, mode)
    if field in _ENUM_FIELD:
        return N.parse_enum(field, value, mode)
    if kind == "money":
        return N.parse_money(value, mode)
    if kind in ("int", "approx_int"):
        return N.parse_pct(value) if field in ("sprinkler_pct", "coinsurance_pct") else N.parse_int(value)
    if kind == "date":
        return N.parse_date(value, mode)
    if kind == "bool":
        return N.parse_bool(value, mode)
    if mode == "full" and isinstance(value, str):
        value = _ocr_clean(field, kind, value)
        if value is None:
            return None
    if kind in ("digits", "zip"):
        s = str(value).strip()
        if field == "naics_code":
            s = s.split(".")[0]
            return s if s.isdigit() and len(s) == 6 else None
        if field == "zip":
            s = s.split(".")[0]
            return s.zfill(5) if s.replace("-", "").isdigit() else None
        return s
    return str(value).strip()


def _ocr_clean(field: str, kind: str, s: str) -> str | None:
    """Undo common OCR artifacts: 'a.b @c.com', 'CO.', '_Los Angeles'."""
    s = s.strip()
    if kind == "email":
        return re.sub(r"\s+", "", s).lower()
    if kind == "state":
        letters = re.sub(r"[^A-Za-z]", "", s).upper()
        return letters if len(letters) == 2 else None
    if field in ("city", "street", "occupancy"):
        return re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9.)]+$", "", s) or None
    return s


def _group(data: dict, group: str, mode: str, errors: list[str]) -> dict:
    out: dict = {}
    for k, v in (data.get(group) or {}).items():
        if group == "insured" and k == "mailing_address" and isinstance(v, dict):
            out[k] = {kk: parse_value(f"insured.mailing_address.{kk}", vv, mode) for kk, vv in v.items()
                      if kk in ("street", "city", "state", "zip")}
            continue
        try:
            parsed = parse_value(f"{group}.{k}", v, mode)
        except KeyError:
            continue  # unknown field name from the model: ignore
        if v not in (None, "") and parsed is None:
            errors.append(f"{group}.{k}: could not parse {v!r}")
        out[k] = parsed
    return out


def coerce_submission(data: dict, submission_id: str, mode: str = "basic") -> tuple[Submission, list[str]]:
    errors: list[str] = []
    rec = Submission(submission_id=submission_id)
    for group in ("insured", "broker", "policy", "coverage", "totals"):
        vals = _group(data, group, mode, errors)
        try:
            setattr(rec, group, type(getattr(rec, group)).model_validate({k: v for k, v in vals.items() if v is not None}))
        except Exception as exc:  # pydantic validation of the whole group failed
            errors.append(f"{group}: {exc}")
    for raw in data.get("locations") or []:
        num = N.parse_int(raw.get("loc_number"))
        if num is None:
            errors.append(f"location without loc_number: {raw}")
            continue
        vals = {k: parse_value(f"locations[{num}].{k}", v, mode) for k, v in raw.items()
                if k != "loc_number" and k in Location.model_fields}
        rec.locations.append(Location(loc_number=num, **{k: v for k, v in vals.items() if v is not None}))
    for raw in data.get("claims") or []:
        number = str(raw.get("claim_number") or "").strip()
        if not number:
            errors.append(f"claim without number: {raw}")
            continue
        vals = {k: parse_value(f"claims[{number}].{k}", v, mode) for k, v in raw.items()
                if k != "claim_number" and k in Claim.model_fields}
        rec.claims.append(Claim(claim_number=number, **{k: v for k, v in vals.items() if v is not None}))
    for raw in data.get("loss_years") or []:
        year = N.parse_int(raw.get("policy_year"))
        if year is None:
            continue
        vals = {k: parse_value(f"loss_years[{year}].{k}", v, mode) for k, v in raw.items()
                if k != "policy_year" and k in LossYear.model_fields}
        rec.loss_years.append(LossYear(policy_year=year, **{k: v for k, v in vals.items() if v is not None}))
    return rec, errors
