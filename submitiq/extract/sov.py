"""Statement of values -> location candidates (table-aware, deterministic)."""
from __future__ import annotations

from ..coerce import parse_value
from ..documents import Document
from ..normalize import parse_int, parse_money
from ..result import Citation
from ..tables import get_table_extractor
from ..tables.vocab import SOV_COLUMNS
from .types import DocExtraction, Validation

LOCATION_FIELDS = ["street", "city", "state", "zip", "occupancy", "construction", "year_built", "stories",
                   "square_feet", "sprinklered", "sprinkler_pct", "protection_class", "roof_year",
                   "building_value", "contents_value", "bi_value", "tiv"]


def extract_sov(doc: Document, mode: str = "basic", tables: str | None = None) -> DocExtraction:
    ex = DocExtraction(doc.name, "sov", f"table_parser:{get_table_extractor(tables).name}")
    blocks = get_table_extractor(tables).blocks(doc, SOV_COLUMNS)
    stated_total = None
    for b in blocks:
        if b.kind == "text":
            low = b.text.lower()
            if low.startswith("statement of values") and " - " in b.text:
                ex.names.append((b.text.split(" - ", 1)[1].strip(), Citation(doc=doc.name, doc_type="sov", page=b.page,
                                                                             locator=b.locator, snippet=b.text)))
            if low.startswith("total"):
                money = b.cells.get("tiv") if b.cells else None
                stated_total = parse_money(money, "full") if money is not None else _last_money(b.text)
            continue
        if b.kind != "row":
            continue
        num = parse_int(b.cells.get("loc_number"))
        if num is None or num <= 0 or num > 500:
            continue
        cite = Citation(doc=doc.name, doc_type="sov", page=b.page, locator=b.locator, snippet=b.text[:300])
        for f in LOCATION_FIELDS:
            raw = b.cells.get(f)
            if raw is None:
                continue
            path = f"locations[{num}].{f}"
            ex.add(path, parse_value(path, raw, mode), cite, b.conf)

    nums = sorted({int(p.split("[")[1].split("]")[0]) for p in ex.candidates})
    tivs = [ex.candidates[f"locations[{n}].tiv"].value for n in nums if f"locations[{n}].tiv" in ex.candidates]
    if stated_total is not None:
        ex.stated["sov_stated_total_tiv"] = _cand(stated_total, ex, doc)
        ok = len(tivs) == len(nums) and abs(sum(tivs) - stated_total) <= max(1.0, 0.001 * stated_total)
        ex.validations.append(Validation("sov_total_reconciles", ok,
                                         f"sum of TIV column {sum(tivs):,.0f} vs stated total {stated_total:,.0f}",
                                         [f"locations[{n}].tiv" for n in nums]))
    for n in nums:
        parts = [ex.candidates.get(f"locations[{n}].{k}") for k in ("building_value", "contents_value", "bi_value")]
        tiv = ex.candidates.get(f"locations[{n}].tiv")
        if tiv and all(parts):
            ok = abs(sum(p.value for p in parts) - tiv.value) <= max(1.0, 0.001 * tiv.value)
            ex.validations.append(Validation("sov_row_adds_up", ok, f"location {n}: building+contents+BI vs TIV",
                                             [f"locations[{n}].{k}" for k in ("building_value", "contents_value", "bi_value", "tiv")]))
    if not nums:
        ex.ok = False
        ex.note = "no SOV rows recognised"
    return ex


def _cand(value, ex: DocExtraction, doc: Document):
    from ..result import Candidate
    return Candidate(value=value, extractor=ex.extractor, citation=Citation(doc=doc.name, doc_type="sov"), confidence=0.9)


def _last_money(text: str):
    for tok in reversed(text.replace(":", " ").split()):
        v = parse_money(tok, "full")
        if v is not None:
            return v
    return None
