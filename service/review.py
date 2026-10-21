"""Human review: apply corrections and approvals to a PipelineResult (pure functions, easy to test)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from submitiq.assemble import record_from_values
from submitiq.coerce import parse_value
from submitiq.fields import as_jsonable, claim_key, flatten, spec
from submitiq.result import FieldProvenance, PipelineResult
from submitiq.rules_engine import RulesEngine
from submitiq.schema import GroundTruth, GroundTruthMeta
from submitiq.summary import template_summary


@dataclass
class Correction:
    path: str
    value: Any
    comment: str | None = None


@dataclass
class AppliedCorrection:
    path: str
    old_value: Any
    new_value: Any
    field_status: str
    extractor: str | None
    comment: str | None


class InvalidCorrection(ValueError):
    pass


def _refresh(res: PipelineResult) -> None:
    res.decision = RulesEngine().evaluate(res.record, res.provenance)
    res.summary = template_summary(res.record, res.decision, res.provenance)
    res.summary_source = "template (after review)"
    res.needs_review = any(fp.status != "ok" for fp in res.provenance.values())


def apply_corrections(res: PipelineResult, corrections: list[Correction], reviewer: str) -> tuple[PipelineResult, list[AppliedCorrection]]:
    res = res.model_copy(deep=True)
    values = flatten(res.record)
    claim_numbers = {claim_key(c.claim_number): c.claim_number for c in res.record.claims}
    applied: list[AppliedCorrection] = []
    for c in corrections:
        try:
            spec(c.path)
        except KeyError as exc:
            raise InvalidCorrection(f"unknown field {c.path!r}") from exc
        raw = c.value.strip() if isinstance(c.value, str) else c.value
        new = None if raw in (None, "") else parse_value(c.path, raw, "full")
        if raw not in (None, "") and new is None:
            raise InvalidCorrection(f"{c.path}: cannot parse {c.value!r}")
        old = values.get(c.path)
        prev = res.provenance.get(c.path)
        values[c.path] = new
        res.provenance[c.path] = FieldProvenance(
            path=c.path, confidence=1.0, status="ok", extractor=f"human:{reviewer}",
            citations=prev.citations if prev else [],
            reasons=[f"corrected by {reviewer}: {as_jsonable(old)!r} -> {as_jsonable(new)!r}" + (f" ({c.comment})" if c.comment else "")],
            alternatives=prev.alternatives if prev else [])
        applied.append(AppliedCorrection(c.path, as_jsonable(old), as_jsonable(new), prev.status if prev else "missing",
                                         prev.extractor if prev else None, c.comment))
    res.record = record_from_values(res.submission_id, values, claim_numbers)
    _refresh(res)
    return res, applied


def approve(res: PipelineResult, reviewer: str) -> PipelineResult:
    """Reviewer confirms every remaining flagged value as correct (or as legitimately missing)."""
    res = res.model_copy(deep=True)
    for fp in res.provenance.values():
        if fp.status != "ok":
            fp.reasons.append(f"{fp.status} confirmed by {reviewer}")
            fp.status = "ok"
    _refresh(res)
    res.needs_review = False
    return res


def to_eval_case(res: PipelineResult) -> GroundTruth:
    """A reviewed submission becomes a ground-truth case for the eval set."""
    decision = RulesEngine().evaluate(res.record)
    return GroundTruth(record=res.record, meta=GroundTruthMeta(
        split="reviewed", template="unknown", doc_types=dict(res.doc_types),  # type: ignore[arg-type]
        expected_conflicts=[], expected_decision=decision.outcome or "refer",
        expected_reasons=sorted({h.rule_id for h in decision.reasons}), mess=["from_human_review"]))
