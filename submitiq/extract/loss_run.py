"""Carrier loss run -> claims and policy-year candidates (table-aware, deterministic)."""
from __future__ import annotations

import re

from ..coerce import parse_value
from ..documents import Document
from ..fields import claim_key
from ..normalize import parse_date, parse_money
from ..result import Citation
from ..tables import get_table_extractor
from ..tables.vocab import LOSS_COLUMNS
from .types import DocExtraction, Validation

PERIOD = re.compile(r"policy\s*period[:;]?\s*(\S+)\s*[-–]\s*(\S+)", re.I)
PREMIUM = re.compile(r"earned\s*premium[:;]?\s*(\S+)", re.I)
PERIOD_TOTAL = re.compile(r"period\s*total[:;]?\s*(\d+)\s*claim.*?incurred[:;]?\s*(\S+)", re.I)
CARRIER_HINT = re.compile(r"insurance|mutual|indemnity|casualty|assurance|company|\bco\b", re.I)


def extract_loss_run(doc: Document, mode: str = "basic", tables: str | None = None) -> DocExtraction:
    tx = get_table_extractor(tables)
    ex = DocExtraction(doc.name, "loss_run", f"table_parser:{tx.name}")
    blocks = tx.blocks(doc, LOSS_COLUMNS)
    carrier = None
    year: int | None = None
    year_claims: dict[int, list[str]] = {}
    stated_year_totals: dict[int, tuple[int, float | None]] = {}
    for b in blocks:
        cite = Citation(doc=doc.name, doc_type="loss_run", page=b.page, locator=b.locator, snippet=b.text[:300])
        if b.kind == "text":
            t = b.text.strip()
            if carrier is None and CARRIER_HINT.search(t) and not t.lower().startswith(("insured", "policy")):
                carrier = t.strip().title()
                carrier_cite = cite
            if t.lower().startswith("insured"):
                ex.names.append((t.split(":", 1)[-1].strip(), cite))
            m = PERIOD.search(t)
            if m:
                start = parse_date(m.group(1), mode) or parse_date(m.group(1), "full")
                year = start.year if start else None
                if year is not None:
                    year_claims.setdefault(year, [])
                    pm = PREMIUM.search(t)
                    if pm:
                        ex.add(f"loss_years[{year}].earned_premium", parse_money(pm.group(1).rstrip(","), mode), cite, b.conf)
                    if carrier:
                        ex.add(f"loss_years[{year}].carrier", carrier, carrier_cite, b.conf)
            if year is not None and "no losses reported" in t.lower():
                stated_year_totals[year] = (0, 0.0)
            pt = PERIOD_TOTAL.search(t)
            if pt and year is not None:
                stated_year_totals[year] = (int(pt.group(1)), parse_money(pt.group(2), "full"))
            continue
        if b.kind != "row":
            continue
        number = (b.cells.get("claim_number") or "").strip()
        if not number or len(number) < 5 or year is None:
            continue
        key = claim_key(number)
        ex.claim_numbers[key] = number
        year_claims.setdefault(year, []).append(key)
        ex.add(f"claims[{key}].policy_year", year, cite, b.conf)
        for f in ("date_of_loss", "cause", "status", "paid", "reserve", "incurred"):
            raw = b.cells.get(f)
            if raw is not None:
                path = f"claims[{key}].{f}"
                ex.add(path, parse_value(path, raw, mode), cite, b.conf)

    for y, keys in year_claims.items():
        inc = [ex.candidates[f"claims[{k}].incurred"].value for k in keys if f"claims[{k}].incurred" in ex.candidates]
        cite = Citation(doc=doc.name, doc_type="loss_run", locator=f"policy year {y}")
        ex.add(f"loss_years[{y}].claim_count", len(keys), cite, 0.9)
        ex.add(f"loss_years[{y}].total_incurred", round(sum(inc), 2), cite, 0.9)
        if y in stated_year_totals:
            n, total = stated_year_totals[y]
            ok = n == len(keys) and (total is None or abs(total - sum(inc)) <= 1.0)
            ex.validations.append(Validation(
                "loss_year_reconciles", ok,
                f"{y}: parsed {len(keys)} claims / ${sum(inc):,.2f} vs stated {n} / ${total or 0:,.2f}",
                [f"loss_years[{y}].claim_count", f"loss_years[{y}].total_incurred"]
                + [f"claims[{k}].{f}" for k in keys for f in ("paid", "reserve", "incurred")]))
    for k in ex.claim_numbers:
        parts = [ex.candidates.get(f"claims[{k}].{f}") for f in ("paid", "reserve", "incurred")]
        if all(parts):
            ok = abs(parts[0].value + parts[1].value - parts[2].value) <= 1.0
            ex.validations.append(Validation("claim_paid_plus_reserve", ok, f"claim {ex.claim_numbers[k]}",
                                             [f"claims[{k}].{f}" for f in ("paid", "reserve", "incurred")]))
    if not year_claims:
        ex.ok = False
        ex.note = "no policy periods recognised"
    return ex


