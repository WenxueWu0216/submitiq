"""What a pipeline run returns: the record plus everything needed to trust it."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .schema import Submission

FieldStatus = Literal["ok", "low_confidence", "conflict", "missing", "invalid"]


class Citation(BaseModel):
    doc: str                       # file name inside the package
    doc_type: str
    page: Optional[int] = None     # 1-based page (PDF) or None
    locator: Optional[str] = None  # e.g. "Sheet1!R7", "row 4", "line 12"
    snippet: Optional[str] = None


class Candidate(BaseModel):
    """One extractor's reading of one field."""
    value: Any
    extractor: str                 # form_parser | table_parser:sov | llm:application | ...
    citation: Citation
    confidence: float = 0.8


class FieldProvenance(BaseModel):
    path: str
    confidence: Optional[float] = None
    status: FieldStatus = "ok"
    extractor: Optional[str] = None
    citations: list[Citation] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    alternatives: list[Candidate] = Field(default_factory=list)


class RuleHit(BaseModel):
    rule_id: str
    outcome: Literal["accept", "refer", "decline"]
    message: str
    fields: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    outcome: Optional[Literal["accept", "refer", "decline"]] = None
    source: Literal["rules", "llm", "none"] = "none"
    reasons: list[RuleHit] = Field(default_factory=list)


class LLMCallRecord(BaseModel):
    task: str
    source: str                    # live | replay:recorded | replay:hand_written | replay:miss
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    est_input_tokens: int = 0      # chars/4 estimate of the prompt, recorded even on a replay miss


class PipelineResult(BaseModel):
    submission_id: str
    pipeline: str
    record: Submission
    provenance: dict[str, FieldProvenance] = Field(default_factory=dict)
    decision: Decision = Field(default_factory=Decision)
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    doc_types: dict[str, str] = Field(default_factory=dict)
    llm_calls: list[LLMCallRecord] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)
    summary: Optional[str] = None
    summary_source: Optional[str] = None   # llm | template
    summary_citations_valid: Optional[bool] = None
    errors: list[str] = Field(default_factory=list)

    def flagged_paths(self) -> set[str]:
        return {p for p, fp in self.provenance.items() if fp.status != "ok"}

    def conflict_paths(self) -> set[str]:
        return {p for p, fp in self.provenance.items() if fp.status == "conflict"}
