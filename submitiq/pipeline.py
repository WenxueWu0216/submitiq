"""Pipeline variants. Each variant is one row of docs/experiment_log.md.

    baseline    classify -> text/OCR -> one Claude call returns JSON (+ decision)
    v1_tables   + deterministic table-aware parsing of SOVs and loss runs
    v2_tooluse  per-document extraction: layout parsers + Claude tool use with strict schemas
                (LLM on SOV / loss runs only when the table parser fails its own checks)
    v3a_consistency_raw   + cross-document consistency checks, exact matching
    v3_consistency        + entity normalization and full value normalization
    v4_confidence         + field confidence, validation and review routing
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from . import consistency
from .assemble import assemble, extraction_from_record
from .classify import classify
from .confidence import score_and_route
from .coerce import coerce_submission
from .documents import Document, load_package
from .extract import baseline as baseline_extract
from .extract.application_form import extract_application_form
from .extract.email_parser import extract_email_headers
from .extract.llm_decision import decide as llm_decide
from .extract.llm_docs import extract_with_llm
from .extract.loss_run import extract_loss_run
from .extract.sov import extract_sov
from .extract.types import DocExtraction
from .fields import flatten
from .llm import LLMClient, get_client
from .llm.base import call_record
from .result import PipelineResult
from .schema import Submission


@dataclass(frozen=True)
class PipelineConfig:
    name: str
    extraction: str = "baseline"        # baseline | per_doc
    tables: bool = False                # 4a: table-aware SOV / loss-run parsing
    llm_tables: str = "fallback"        # 4b: LLM on SOV/loss runs: fallback (parser failed) | always | never
    normalization: str = "basic"        # basic | full (4c)
    consistency: bool = False           # 4c: cross-document checks
    confidence: bool = False            # 4d: confidence scoring + routing
    decision: str = "llm"               # llm | rules


VARIANTS: dict[str, PipelineConfig] = {
    "baseline": PipelineConfig("baseline"),
    "v1_tables": PipelineConfig("v1_tables", tables=True),
    "v2_tooluse": PipelineConfig("v2_tooluse", extraction="per_doc", tables=True),
    "v3a_consistency_raw": PipelineConfig("v3a_consistency_raw", extraction="per_doc", tables=True, consistency=True),
    "v3_consistency": PipelineConfig("v3_consistency", extraction="per_doc", tables=True, consistency=True,
                                     normalization="full"),
    "v4_confidence": PipelineConfig("v4_confidence", extraction="per_doc", tables=True, consistency=True,
                                    normalization="full", confidence=True),
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
        if self.cfg.extraction == "baseline":
            extractions += self._extract_baseline(docs, res)
        else:
            extractions += self._extract_per_doc(docs, res)
        if self.cfg.tables:
            extractions += self._extract_tables(docs)
            if self.cfg.extraction == "per_doc":
                extractions += self._llm_table_fallback(docs, extractions, res)
        res.record, res.provenance = assemble(sub_id, extractions)
        res.timings_ms["extract"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        values = flatten(res.record)
        if self.cfg.consistency:
            conflicts = consistency.check(res.provenance, values, extractions, self.cfg.normalization)
            if not self.cfg.confidence:
                res.review_reasons += conflicts
                res.needs_review = res.needs_review or bool(conflicts)
        if self.cfg.confidence:
            needs, reasons = score_and_route(res.provenance, values, extractions, docs)
            res.review_reasons += reasons
            res.needs_review = res.needs_review or needs
        res.timings_ms["validate"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        if self.cfg.extraction != "baseline" and self.cfg.decision == "llm":
            req, resp, outcome = llm_decide(res.record, self.llm)
            res.llm_calls.append(call_record(req, resp))
            if outcome:
                res.decision.outcome, res.decision.source = outcome, "llm"  # type: ignore[assignment]
        if res.decision.outcome is None:
            res.degraded_reasons.append("no appetite decision (model unavailable)")
        res.timings_ms["decision"] = (time.perf_counter() - t0) * 1000

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
        mode = self.cfg.normalization
        for d in docs:
            if d.doc_type == "sov":
                out.append(extract_sov(d, mode=mode))
            elif d.doc_type == "loss_run":
                out.append(extract_loss_run(d, mode=mode))
        return out

    # ------------------------------------------------------------------ 4b per document
    def _llm(self, doc: Document, res: PipelineResult) -> list[DocExtraction]:
        req, resp, ex = extract_with_llm(doc, self.llm, self.cfg.normalization)
        res.llm_calls.append(call_record(req, resp))
        if ex is None:
            res.degraded_reasons.append(f"{doc.name}: LLM extraction unavailable ({resp.error or 'no tool call'})")
            return []
        return [ex]

    def _extract_per_doc(self, docs: list[Document], res: PipelineResult) -> list[DocExtraction]:
        out: list[DocExtraction] = []
        for d in docs:
            if d.doc_type == "application":
                form = extract_application_form(d, mode=self.cfg.normalization)
                out.append(form)
                if not form.ok:
                    res.review_reasons.append(f"{d.name}: {form.note}")
                out += self._llm(d, res)
            elif d.doc_type == "email":
                out.append(extract_email_headers(d))
                out += self._llm(d, res)
        return out

    def _llm_table_fallback(self, docs: list[Document], extractions: list[DocExtraction],
                            res: PipelineResult) -> list[DocExtraction]:
        """Spend an LLM call on a schedule only when the deterministic parser could not vouch for it."""
        if self.cfg.llm_tables == "never":
            return []
        by_doc = {e.doc: e for e in extractions if e.extractor.startswith("table_parser")}
        out: list[DocExtraction] = []
        for d in docs:
            if d.doc_type not in ("sov", "loss_run"):
                continue
            parsed = by_doc.get(d.name)
            failed = parsed is None or not parsed.ok or any(not v.passed for v in parsed.validations)
            if self.cfg.llm_tables == "always" or failed:
                out += self._llm(d, res)
        return out


def build_pipeline(name: str, backend: str = "replay"):
    if name == "null":
        return NullPipeline()
    if name not in VARIANTS:
        raise ValueError(f"unknown pipeline {name!r}; choose from {sorted(VARIANTS)}")
    return Pipeline(VARIANTS[name], get_client(backend))
