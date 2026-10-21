"""Field registry and flattening.

A flattened path addresses one scalar in a Submission:
    insured.named_insured
    insured.mailing_address.zip
    locations[3].year_built        (keyed by loc_number)
    claims[CMI-2023-00412].paid    (keyed by claim number)
    loss_years[2024].earned_premium

The eval harness, provenance, review routing and the UI all use these paths.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from .schema import Submission


@dataclass(frozen=True)
class FieldSpec:
    group: str
    kind: str          # text | fuzzy | money | int | approx_int | date | enum | bool | phone | digits | email | url | zip | state
    critical: bool = False


_SPECS: dict[str, FieldSpec] = {
    "insured.named_insured": FieldSpec("insured", "text", critical=True),
    "insured.dba": FieldSpec("insured", "text"),
    "insured.fein": FieldSpec("insured", "digits"),
    "insured.entity_type": FieldSpec("insured", "enum"),
    "insured.mailing_address.street": FieldSpec("insured", "text"),
    "insured.mailing_address.city": FieldSpec("insured", "text"),
    "insured.mailing_address.state": FieldSpec("insured", "state"),
    "insured.mailing_address.zip": FieldSpec("insured", "zip"),
    "insured.business_description": FieldSpec("insured", "fuzzy"),
    "insured.naics_code": FieldSpec("insured", "digits", critical=True),
    "insured.years_in_business": FieldSpec("insured", "int"),
    "insured.annual_revenue": FieldSpec("insured", "money"),
    "insured.employee_count": FieldSpec("insured", "int"),
    "insured.website": FieldSpec("insured", "url"),
    "insured.contact_name": FieldSpec("insured", "text"),
    "insured.contact_phone": FieldSpec("insured", "phone"),
    "insured.contact_email": FieldSpec("insured", "email"),
    "broker.agency_name": FieldSpec("broker", "text"),
    "broker.producer_name": FieldSpec("broker", "text"),
    "broker.producer_email": FieldSpec("broker", "email"),
    "broker.producer_phone": FieldSpec("broker", "phone"),
    "policy.effective_date": FieldSpec("policy", "date", critical=True),
    "policy.expiration_date": FieldSpec("policy", "date"),
    "policy.transaction_type": FieldSpec("policy", "enum"),
    "policy.prior_carrier": FieldSpec("policy", "text"),
    "policy.quote_needed_by": FieldSpec("policy", "date"),
    "policy.submission_received_date": FieldSpec("policy", "date"),
    "coverage.building_limit": FieldSpec("coverage", "money"),
    "coverage.bpp_limit": FieldSpec("coverage", "money"),
    "coverage.business_income_limit": FieldSpec("coverage", "money"),
    "coverage.deductible": FieldSpec("coverage", "money"),
    "coverage.valuation": FieldSpec("coverage", "enum"),
    "coverage.coinsurance_pct": FieldSpec("coverage", "int"),
    "coverage.cause_of_loss_form": FieldSpec("coverage", "enum"),
    "coverage.flood_requested": FieldSpec("coverage", "bool"),
    "coverage.earthquake_requested": FieldSpec("coverage", "bool"),
    "locations[].street": FieldSpec("locations", "text"),
    "locations[].city": FieldSpec("locations", "text"),
    "locations[].state": FieldSpec("locations", "state"),
    "locations[].zip": FieldSpec("locations", "zip", critical=True),
    "locations[].occupancy": FieldSpec("locations", "fuzzy"),
    "locations[].construction": FieldSpec("locations", "enum", critical=True),
    "locations[].year_built": FieldSpec("locations", "int", critical=True),
    "locations[].stories": FieldSpec("locations", "int"),
    "locations[].square_feet": FieldSpec("locations", "approx_int"),
    "locations[].sprinklered": FieldSpec("locations", "bool", critical=True),
    "locations[].sprinkler_pct": FieldSpec("locations", "int"),
    "locations[].protection_class": FieldSpec("locations", "int", critical=True),
    "locations[].roof_type": FieldSpec("locations", "enum"),
    "locations[].roof_year": FieldSpec("locations", "int", critical=True),
    "locations[].alarm_type": FieldSpec("locations", "enum"),
    "locations[].building_value": FieldSpec("locations", "money"),
    "locations[].contents_value": FieldSpec("locations", "money"),
    "locations[].bi_value": FieldSpec("locations", "money"),
    "locations[].tiv": FieldSpec("locations", "money", critical=True),
    "claims[].policy_year": FieldSpec("claims", "int"),
    "claims[].date_of_loss": FieldSpec("claims", "date"),
    "claims[].cause": FieldSpec("claims", "fuzzy"),
    "claims[].status": FieldSpec("claims", "enum"),
    "claims[].paid": FieldSpec("claims", "money"),
    "claims[].reserve": FieldSpec("claims", "money"),
    "claims[].incurred": FieldSpec("claims", "money", critical=True),
    "loss_years[].carrier": FieldSpec("loss_years", "text"),
    "loss_years[].earned_premium": FieldSpec("loss_years", "money", critical=True),
    "loss_years[].claim_count": FieldSpec("loss_years", "int"),
    "loss_years[].total_incurred": FieldSpec("loss_years", "money"),
    "totals.total_tiv": FieldSpec("totals", "money", critical=True),
    "totals.location_count": FieldSpec("totals", "int"),
    "totals.five_year_incurred": FieldSpec("totals", "money"),
    "totals.five_year_premium": FieldSpec("totals", "money"),
}

GROUPS = ["insured", "broker", "policy", "coverage", "locations", "claims", "loss_years", "totals"]
_INDEX = re.compile(r"\[[^\]]*\]")


def generic(path: str) -> str:
    """locations[3].year_built -> locations[].year_built"""
    return _INDEX.sub("[]", path)


def spec(path: str) -> FieldSpec:
    return _SPECS[generic(path)]


def all_specs() -> dict[str, FieldSpec]:
    return dict(_SPECS)


def claim_key(number: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", number.upper())


def _scalar(v: Any) -> Any:
    if isinstance(v, Enum):
        return v.value
    return v


def flatten(rec: Submission) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for group in ("insured", "broker", "policy", "coverage", "totals"):
        obj = getattr(rec, group)
        for name, value in obj:
            if name == "mailing_address":
                for k, v in value:
                    out[f"insured.mailing_address.{k}"] = _scalar(v)
            else:
                out[f"{group}.{name}"] = _scalar(value)
    seen: set[str] = set()
    for loc in rec.locations:
        key = f"locations[{loc.loc_number}]"
        if key in seen:
            continue
        seen.add(key)
        for name, value in loc:
            if name != "loc_number":
                out[f"{key}.{name}"] = _scalar(value)
    for cl in rec.claims:
        key = f"claims[{claim_key(cl.claim_number)}]"
        if key in seen:
            continue
        seen.add(key)
        for name, value in cl:
            if name != "claim_number":
                out[f"{key}.{name}"] = _scalar(value)
    for ly in rec.loss_years:
        key = f"loss_years[{ly.policy_year}]"
        if key in seen:
            continue
        seen.add(key)
        for name, value in ly:
            if name != "policy_year":
                out[f"{key}.{name}"] = _scalar(value)
    return {k: v for k, v in out.items() if generic(k) in _SPECS}


def as_jsonable(v: Any) -> Any:
    if isinstance(v, date):
        return v.isoformat()
    return _scalar(v)
