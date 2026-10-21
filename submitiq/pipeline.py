"""Pipeline variants. Each variant is one row of docs/experiment_log.md.

    baseline    classify -> text/OCR -> one Claude call returns JSON (+ decision)
    v1_tables   + deterministic table-aware parsing of SOVs and loss runs
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .assemble import assemble, extraction_from_record
from .classify import classify
from .coerce import coerce_submission
from .documents import Document, load_package
from .extract import baseline as baseline_extract
from .extract.loss_run import extract_loss_run
from .extract.sov import extract_sov
from .extract.types import DocExtraction
from .llm import LLMClient, get_client
from .llm.base import call_record
from .result import PipelineResult
from .schema import Submission


@dataclass(frozen=True)
class PipelineConfig:
    name: str
    extraction: str = "baseline"        # baseline | per_doc
    tables: bool = False                # 4a: table-aware SOV / loss-run parsing
    decision: str = "llm"               # llm | rules


VARIANTS: dict[str, PipelineConfig] = {
    "baseline": PipelineConfig("baseline"),
    "v1_tables": PipelineConfig("v1_tables", tables=True),
}
ORDER = list(VARIANTS)
VARIANTS["final"] = PipelineConfig(**{**asdict(VARIANTS[ORDER[-1]]), "name": "final"})


class NullPipeline:
    """Predicts nothing. Used to sanity-check the harness (F1 must be 0)."""
    name = "null"

    def run(self, pkg: Path) -> PipelineResult:
        res = PipelineResult(submission_id=pkg.name, pipeline=self.name, record=Submission(submission_id=pkg.name))
        res.timings_ms["total"] = 0.0
        return res


class Pipeline:
    def __init__(self, cfg: PipelineConfig, llm: LLMClient):
        self.cfg = cfg
        self.llm = llm

    def run(self, pkg: Path) -> PipelineResult:
        t_start = time.perf_counter()
        sub_id = pkg.name
        res = PipelineResult(submission_id=sub_id, pipeline=self.cfg.name, record=Submission(submission_id=sub_id))

        docs = load_package(pkg)
        res.timings_ms["text_extraction"] = sum(d.timings_ms.get("text", 0.0) for d in docs)
        res.timings_ms["ocr"] = sum(d.timings_ms.get("ocr", 0.0) for d in docs)

        t0 = time.perf_counter()
        for d in docs:
            d.doc_type, _, _ = classify(d, self.llm, res.llm_calls)
            res.doc_types[d.name] = d.doc_type
        res.timings_ms["classify"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        extractions: list[DocExtraction] = []
        extractions += self._extract_baseline(docs, res)
        if self.cfg.tables:
            extractions += self._extract_tables(docs)
        res.record, res.provenance = assemble(sub_id, extractions)
        res.timings_ms["extract"] = (time.perf_counter() - t0) * 1000

        # Wall-clock of everything except OCR, which is reported at its originally measured cost.
        res.timings_ms["other"] = max(0.0, (time.perf_counter() - t_start) * 1000 - sum(res.timings_ms.values()))
        return res

    # ------------------------------------------------------------------ baseline
    def _extract_baseline(self, docs: list[Document], res: PipelineResult) -> list[DocExtraction]:
        req, resp, parsed = baseline_extract.run(docs, self.llm)
        res.llm_calls.append(call_record(req, resp))
        if parsed is None:
            res.needs_review = True
            res.review_reasons.append(f"extraction model returned no usable output ({resp.error or 'unparseable'})")
            return []
        rec, errors = coerce_submission(parsed.get("record") or {}, res.submission_id, mode="basic")
        res.errors += errors
        decision = parsed.get("appetite_decision")
        if decision in ("accept", "refer", "decline"):
            res.decision.outcome = decision
            res.decision.source = "llm"
        return [extraction_from_record(rec, "(package)", "package", "llm:baseline", 0.6)]

    # ------------------------------------------------------------------ 4a tables
    def _extract_tables(self, docs: list[Document]) -> list[DocExtraction]:
        out = []
        for d in docs:
            if d.doc_type == "sov":
                out.append(extract_sov(d, mode="basic"))
            elif d.doc_type == "loss_run":
                out.append(extract_loss_run(d, mode="basic"))
        return out


def build_pipeline(name: str, backend: str = "replay"):
    if name == "null":
        return NullPipeline()
    if name not in VARIANTS:
        raise ValueError(f"unknown pipeline {name!r}; choose from {sorted(VARIANTS)}")
    return Pipeline(VARIANTS[name], get_client(backend))
