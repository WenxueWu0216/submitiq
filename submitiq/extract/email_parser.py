"""Broker email: deterministic header and signature parsing.

Body facts (requested dates, quote deadline, how the broker names the insured)
are free text and go to the LLM extractor.
"""
from __future__ import annotations

import re
from email.utils import parseaddr, parsedate_to_datetime

from ..documents import Document
from ..result import Citation
from .types import DocExtraction

PHONE = re.compile(r"^\(?\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}$")


def extract_email_headers(doc: Document) -> DocExtraction:
    ex = DocExtraction(doc.name, "email", "email_parser")
    text = doc.raw_text or ""
    head, _, body = text.partition("\n\n")
    for n, line in enumerate(head.splitlines(), start=1):
        cite = Citation(doc=doc.name, doc_type="email", locator=f"header line {n}", snippet=line[:200])
        if line.lower().startswith("from:"):
            name, addr = parseaddr(line.split(":", 1)[1])
            if name:
                ex.add("broker.producer_name", name.strip(), cite, 1.0)
            if addr:
                ex.add("broker.producer_email", addr.strip().lower(), cite, 1.0)
        elif line.lower().startswith("date:"):
            try:
                ex.add("policy.submission_received_date", parsedate_to_datetime(line.split(":", 1)[1].strip()).date(), cite, 1.0)
            except (TypeError, ValueError):
                pass
    # Signature: the lines after a sign-off, e.g. "Thanks,\nName\nAgency\nPhone\nEmail"
    lines = [l.strip() for l in body.splitlines()]
    for i, l in enumerate(lines):
        if re.match(r"^(thanks|thank you|best|regards|best regards|cheers),?$", l, re.I):
            sig = [x for x in lines[i + 1:i + 6] if x]
            for j, s in enumerate(sig):
                cite = Citation(doc=doc.name, doc_type="email", locator=f"signature line {j + 1}", snippet=s)
                if PHONE.match(s):
                    ex.add("broker.producer_phone", s, cite, 1.0)
                elif j == 1 and "@" not in s:
                    ex.add("broker.agency_name", s, cite, 1.0)
            break
    return ex
