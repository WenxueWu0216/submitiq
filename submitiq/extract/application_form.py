"""Deterministic parser for 'Label: value' application forms, plus the premises table.

The label dictionary was written from the dev-split templates (A and B). It is
deliberately not taught template C, the held-out boxed layout with labels above
values and no colons: that gap is what the test split measures, and it is the
job the LLM extractor exists for.
"""
from __future__ import annotations

import re
from difflib import get_close_matches

from ..coerce import parse_value
from ..documents import Document
from ..normalize import parse_int
from ..result import Citation
from ..tables import get_table_extractor
from ..tables.vocab import PREMISES_COLUMNS
from .types import DocExtraction

LABELS: dict[str, str] = {
    # template A
    "agency": "broker.agency_name", "producer": "broker.producer_name", "producerphone": "broker.producer_phone",
    "produceremail": "broker.producer_email", "namedinsured": "insured.named_insured", "dba": "insured.dba",
    "fein": "insured.fein", "entitytype": "insured.entity_type", "mailingaddress": "insured.mailing_address",
    "natureofbusiness": "insured.business_description", "naicscode": "insured.naics_code",
    "yearsinbusiness": "insured.years_in_business", "annualrevenue": "insured.annual_revenue",
    "numberofemployees": "insured.employee_count", "website": "insured.website", "contactname": "insured.contact_name",
    "contactphone": "insured.contact_phone", "contactemail": "insured.contact_email",
    "proposedeffectivedate": "policy.effective_date", "proposedexpirationdate": "policy.expiration_date",
    "transaction": "policy.transaction_type", "priorcarrier": "policy.prior_carrier",
    "buildinglimit": "coverage.building_limit", "businesspersonalpropertylimit": "coverage.bpp_limit",
    "businessincomelimit": "coverage.business_income_limit", "deductible": "coverage.deductible",
    "valuation": "coverage.valuation", "coinsurance": "coverage.coinsurance_pct",
    "causesoflossform": "coverage.cause_of_loss_form", "floodcoveragerequested": "coverage.flood_requested",
    "earthquakecoveragerequested": "coverage.earthquake_requested",
    "totalinsuredvaluealllocations": "totals.total_tiv", "numberoflocations": "totals.location_count",
    # template B
    "applicantname": "insured.named_insured", "dbatradename": "insured.dba", "feintaxid": "insured.fein",
    "businessentity": "insured.entity_type", "street": "insured.mailing_address.street",
    "city": "insured.mailing_address.city", "state": "insured.mailing_address.state", "zip": "insured.mailing_address.zip",
    "descriptionofoperations": "insured.business_description", "naics": "insured.naics_code",
    "yrsinbus": "insured.years_in_business", "grossrevenue": "insured.annual_revenue", "employees": "insured.employee_count",
    "webaddress": "insured.website", "primarycontact": "insured.contact_name", "effectivedate": "policy.effective_date",
    "expirationdate": "policy.expiration_date", "newrenewal": "policy.transaction_type", "currentcarrier": "policy.prior_carrier",
    "building": "coverage.building_limit", "businesspersonalproperty": "coverage.bpp_limit",
    "businessincome": "coverage.business_income_limit", "causeofloss": "coverage.cause_of_loss_form",
    "flood": "coverage.flood_requested", "earthquake": "coverage.earthquake_requested", "totaltiv": "totals.total_tiv",
    "agencyname": "broker.agency_name", "producername": "broker.producer_name",
}
_ADDRESS = re.compile(r"^(?P<street>.+?),\s*(?P<city>[^,]+),\s*(?P<state>[A-Z]{2})\s+(?P<zip>\d{5})(?:-\d{4})?$")
PREMISES_FIELDS = ["street", "city", "state", "zip", "construction", "year_built", "stories", "square_feet",
                   "sprinklered", "protection_class", "roof_type", "roof_year", "alarm_type"]


def _label_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]", "", label.lower())


def _lookup(label: str, fuzzy: bool) -> str | None:
    key = _label_key(label)
    if key in LABELS:
        return LABELS[key]
    if fuzzy and len(key) >= 5:
        hit = get_close_matches(key, LABELS.keys(), n=1, cutoff=0.88)
        return LABELS[hit[0]] if hit else None
    return None


def extract_application_form(doc: Document, mode: str = "basic") -> DocExtraction:
    ex = DocExtraction(doc.name, "application", "form_parser")
    for page in doc.pages:
        for n, line in enumerate(page.lines, start=1):
            text = line.text()
            for seg in re.split(r"\s{3,}", text):
                m = re.match(r"^([^:]{2,50}):\s*(.*)$", seg.strip())
                if not m:
                    continue
                path = _lookup(m.group(1), fuzzy=page.ocr)
                raw = m.group(2).strip()
                if not path or not raw:
                    continue
                cite = Citation(doc=doc.name, doc_type="application", page=page.number,
                                locator=f"page {page.number} line {n}", snippet=seg.strip()[:200])
                conf = line.conf if page.ocr else 1.0   # reading quality; priors live in confidence.py
                if path == "insured.mailing_address":
                    am = _ADDRESS.match(raw)
                    if am:
                        for k in ("street", "city", "state", "zip"):
                            p = f"insured.mailing_address.{k}"
                            ex.add(p, parse_value(p, am.group(k), mode), cite, conf)
                    continue
                if path in ex.candidates:
                    continue  # first occurrence wins (e.g. 'Producer Phone' vs a later 'Phone')
                ex.add(path, parse_value(path, raw, mode), cite, conf)
    _premises(doc, ex, mode)
    if not ex.candidates:
        ex.ok = False
        ex.note = "no known form labels found (unfamiliar layout?)"
    return ex


def _premises(doc: Document, ex: DocExtraction, mode: str) -> None:
    for b in get_table_extractor("local").blocks(doc, PREMISES_COLUMNS):
        if b.kind != "row":
            continue
        num = parse_int(b.cells.get("loc_number"))
        if num is None or not 0 < num < 500:
            continue
        cite = Citation(doc=doc.name, doc_type="application", page=b.page, locator=b.locator, snippet=b.text[:200])
        for f in PREMISES_FIELDS:
            raw = b.cells.get(f)
            if raw is None:
                continue
            path = f"locations[{num}].{f}"
            val = parse_value(path, raw, mode)
            if val is not None:
                ex.candidates[path] = ex.candidates.get(path) or _cand(val, cite, b.conf)


def _cand(value, cite: Citation, conf: float):
    from ..result import Candidate
    return Candidate(value=value, extractor="form_parser:premises", citation=cite, confidence=conf)
