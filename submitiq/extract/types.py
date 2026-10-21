"""Common output of every per-document extractor."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..result import Candidate, Citation


@dataclass
class Validation:
    name: str                 # e.g. sov_total_reconciles
    passed: bool
    detail: str
    paths: list[str] = field(default_factory=list)


@dataclass
class DocExtraction:
    doc: str
    doc_type: str
    extractor: str
    candidates: dict[str, Candidate] = field(default_factory=dict)   # flattened path -> candidate
    claim_numbers: dict[str, str] = field(default_factory=dict)      # claim key -> printed claim number
    validations: list[Validation] = field(default_factory=list)
    names: list[tuple[str, Citation]] = field(default_factory=list)  # insured names as printed
    stated: dict[str, Candidate] = field(default_factory=dict)       # stated totals (not record fields)
    ok: bool = True
    note: str = ""

    def add(self, path: str, value, citation: Citation, confidence: float) -> None:
        if value is None:
            return
        self.candidates[path] = Candidate(value=value, extractor=self.extractor, citation=citation, confidence=confidence)
