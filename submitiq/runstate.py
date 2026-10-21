"""State carried between pipeline steps, and its JSON form for Step Functions / S3.

Documents are not serialized: each step re-opens the package. The OCR cache
(SUBMITIQ_CACHE) is shared between steps, so each scanned page is OCR'd once.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .coerce import parse_value
from .documents import Document
from .extract.types import DocExtraction, Validation
from .result import Candidate, Citation, PipelineResult


@dataclass
class RunState:
    pkg: Path
    res: PipelineResult
    extractions: list[DocExtraction] = field(default_factory=list)
    docs: list[Document] | None = None
    t_start: float | None = None


def _retype(path: str, value: Any) -> Any:
    """JSON turns dates into strings; parse values back to their schema types."""
    try:
        parsed = parse_value(path, value, "full")
    except KeyError:
        return value
    return value if parsed is None else parsed


def _cand_in(path: str, d: dict) -> Candidate:
    c = Candidate.model_validate(d)
    c.value = _retype(path, c.value)
    return c


def extraction_to_dict(ex: DocExtraction) -> dict:
    return {
        "doc": ex.doc, "doc_type": ex.doc_type, "extractor": ex.extractor, "ok": ex.ok, "note": ex.note,
        "candidates": {p: json.loads(c.model_dump_json()) for p, c in ex.candidates.items()},
        "claim_numbers": ex.claim_numbers,
        "validations": [v.__dict__ for v in ex.validations],
        "names": [[n, json.loads(c.model_dump_json())] for n, c in ex.names],
        "stated": {k: json.loads(c.model_dump_json()) for k, c in ex.stated.items()},
    }


def extraction_from_dict(d: dict) -> DocExtraction:
    ex = DocExtraction(d["doc"], d["doc_type"], d["extractor"], ok=d["ok"], note=d["note"])
    ex.candidates = {p: _cand_in(p, c) for p, c in d["candidates"].items()}
    ex.claim_numbers = d["claim_numbers"]
    ex.validations = [Validation(**v) for v in d["validations"]]
    ex.names = [(n, Citation.model_validate(c)) for n, c in d["names"]]
    ex.stated = {k: Candidate.model_validate(c) for k, c in d["stated"].items()}
    return ex


def dump_state(st: RunState) -> str:
    return json.dumps({"pkg": str(st.pkg), "res": json.loads(st.res.model_dump_json()),
                       "extractions": [extraction_to_dict(e) for e in st.extractions]})


def load_state(raw: str, pkg: Path | None = None) -> RunState:
    d = json.loads(raw)
    res = PipelineResult.model_validate(d["res"])
    for path, fp in res.provenance.items():
        for alt in fp.alternatives:
            alt.value = _retype(path, alt.value)
    return RunState(pkg=pkg or Path(d["pkg"]), res=res,
                    extractions=[extraction_from_dict(e) for e in d["extractions"]])
