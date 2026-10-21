"""Merge candidates from every extractor into one record with provenance.

Source-of-truth order (docs/underwriting_workflow.md section 5):
  location values   SOV table > application premises > LLM readings
  claims / years    loss-run table > LLM reading of the loss run
  totals            derived from the SOV / loss runs > figures stated on the application
  entity / policy   application > email
Within one source, a deterministic parser is listed before the LLM reading of the
same document. The other readings stay attached as alternatives, so consistency
checks and the reviewer can see them.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .extract.types import DocExtraction
from .fields import claim_key, flatten
from .result import Candidate, Citation, FieldProvenance
from .schema import Submission

ORDER: dict[str, list[str]] = {
    "locations": ["table_parser", "form_parser:premises", "llm:sov", "llm:application", "llm:baseline"],
    "claims": ["table_parser", "llm:loss_run", "llm:baseline"],
    "loss_years": ["table_parser", "llm:loss_run", "llm:baseline"],
    "totals": ["derived", "form_parser", "llm:application", "llm:email", "llm:baseline"],
    "default": ["form_parser", "llm:application", "email_parser", "llm:email", "llm:baseline"],
}
_PATH = re.compile(r"^(\w+)(?:\[([^\]]+)\])?\.(.+)$")


def _rank(path: str, cand: Candidate) -> int:
    group = path.split("[")[0].split(".")[0]
    order = ORDER.get(group, ORDER["default"])
    for i, prefix in enumerate(order):
        if cand.extractor.startswith(prefix):
            return i
    return len(order)


def record_from_values(sub_id: str, values: dict[str, object], claim_numbers: dict[str, str]) -> Submission:
    data: dict = {"submission_id": sub_id, "insured": {"mailing_address": {}}, "broker": {}, "policy": {},
                  "coverage": {}, "totals": {}}
    locs: dict[int, dict] = defaultdict(dict)
    claims: dict[str, dict] = defaultdict(dict)
    years: dict[int, dict] = defaultdict(dict)
    for path, v in values.items():
        if v is None:
            continue
        m = _PATH.match(path)
        if not m:
            continue
        group, key, rest = m.groups()
        if group == "locations":
            locs[int(key)][rest] = v
        elif group == "claims":
            claims[key][rest] = v
        elif group == "loss_years":
            years[int(key)][rest] = v
        elif rest.startswith("mailing_address."):
            data["insured"]["mailing_address"][rest.split(".", 1)[1]] = v
        else:
            data[group][rest] = v
    data["locations"] = [{"loc_number": n, **f} for n, f in sorted(locs.items())]
    data["claims"] = [{"claim_number": claim_numbers.get(k, k), **f} for k, f in claims.items()]
    data["loss_years"] = [{"policy_year": y, **f} for y, f in sorted(years.items())]
    return Submission.model_validate(data)


def extraction_from_record(rec: Submission, doc: str, doc_type: str, extractor: str, confidence: float) -> DocExtraction:
    """Wrap a whole-record extractor (the baseline LLM call) as a DocExtraction."""
    ex = DocExtraction(doc, doc_type, extractor)
    cite = Citation(doc=doc, doc_type=doc_type)
    for cl in rec.claims:
        ex.claim_numbers[claim_key(cl.claim_number)] = cl.claim_number
    for path, v in flatten(rec).items():
        ex.add(path, v, cite, confidence)
    return ex


def derive_totals(values: dict[str, Candidate], extractions: list[DocExtraction]) -> dict[str, Candidate]:
    """Totals computed from the schedules, cited to the documents they came from."""
    out: dict[str, Candidate] = {}
    loc_tiv = {p: c for p, c in values.items() if p.startswith("locations[") and p.endswith(".tiv")}
    loc_nums = {p.split("]")[0] for p in values if p.startswith("locations[")}
    sov_docs = [e for e in extractions if e.doc_type == "sov" and e.candidates]
    if loc_tiv and len(loc_tiv) == len(loc_nums):
        src = next((c.citation for c in loc_tiv.values()), None)
        cite = Citation(doc=src.doc if src else "", doc_type=src.doc_type if src else "", page=src.page if src else None,
                        locator="sum of location TIV", snippet=f"{len(loc_tiv)} locations")
        out["totals.total_tiv"] = Candidate(value=round(sum(c.value for c in loc_tiv.values()), 2), extractor="derived",
                                            citation=cite, confidence=min(c.confidence for c in loc_tiv.values()))
    if sov_docs and loc_nums:
        out["totals.location_count"] = Candidate(value=len(loc_nums), extractor="derived",
                                                 citation=Citation(doc=sov_docs[0].doc, doc_type="sov", locator="row count"),
                                                 confidence=0.9)
    years = {p: c for p, c in values.items() if p.startswith("loss_years[") and p.endswith(".earned_premium")}
    year_keys = {p.split("]")[0] for p in values if p.startswith("loss_years[")}
    lr_docs = [e for e in extractions if e.doc_type == "loss_run" and e.candidates]
    if lr_docs and year_keys:
        cite = Citation(doc=", ".join(e.doc for e in lr_docs), doc_type="loss_run", locator="sum of claims")
        inc = [c.value for p, c in values.items() if p.startswith("claims[") and p.endswith(".incurred")]
        out["totals.five_year_incurred"] = Candidate(value=round(sum(inc), 2), extractor="derived", citation=cite, confidence=0.9)
        if len(years) == len(year_keys):
            out["totals.five_year_premium"] = Candidate(value=round(sum(c.value for c in years.values()), 2), extractor="derived",
                                                        citation=cite, confidence=0.9)
    return out


def assemble(sub_id: str, extractions: list[DocExtraction]) -> tuple[Submission, dict[str, FieldProvenance]]:
    by_path: dict[str, list[Candidate]] = defaultdict(list)
    claim_numbers: dict[str, str] = {}
    for ex in extractions:
        claim_numbers.update({k: v for k, v in ex.claim_numbers.items() if k not in claim_numbers})
        for path, cand in ex.candidates.items():
            if cand.value is not None:
                by_path[path].append(cand)
    winners: dict[str, Candidate] = {}
    for path, cands in by_path.items():
        winners[path] = sorted(cands, key=lambda c: _rank(path, c))[0]
    for path, cand in derive_totals(winners, extractions).items():
        by_path[path].append(cand)
        winners[path] = sorted(by_path[path], key=lambda c: _rank(path, c))[0]
    # Stated totals (e.g. the SOV's printed total) are alternatives for the consistency checks.
    for ex in extractions:
        for name, cand in ex.stated.items():
            if name == "sov_stated_total_tiv":
                by_path["totals.total_tiv"].append(cand)

    prov: dict[str, FieldProvenance] = {}
    for path, win in winners.items():
        prov[path] = FieldProvenance(
            path=path, confidence=win.confidence, extractor=win.extractor, citations=[win.citation],
            alternatives=[c for c in by_path[path] if c is not win])
    rec = record_from_values(sub_id, {p: c.value for p, c in winners.items()}, claim_numbers)
    return rec, prov
