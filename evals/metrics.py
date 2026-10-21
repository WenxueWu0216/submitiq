"""Scoring one PipelineResult against ground truth, and aggregating over a split.

Field-level counting (standard for information extraction):
  TP  predicted non-null and matches gold
  FP  predicted non-null and gold is null, or predicted != gold
  FN  gold non-null and predicted null, or predicted != gold
A wrong value therefore counts as both FP and FN. A hallucinated value
(gold null) is an FP. Abstaining on a field that has a gold value is an FN only.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from submitiq.fields import GROUPS, flatten, generic, spec
from submitiq.result import PipelineResult
from submitiq.schema import GroundTruth

from .matching import align, values_match


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, other: "Counts") -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn

    def prf(self) -> dict[str, float]:
        p = self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0
        r = self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
                "tp": self.tp, "fp": self.fp, "fn": self.fn}


@dataclass
class SubmissionScore:
    submission_id: str
    template: str
    overall: Counts = field(default_factory=Counts)
    critical: Counts = field(default_factory=Counts)
    by_group: dict[str, Counts] = field(default_factory=lambda: defaultdict(Counts))
    by_field: dict[str, Counts] = field(default_factory=lambda: defaultdict(Counts))
    wrong_paths: list[str] = field(default_factory=list)         # pred non-null and wrong
    missed_paths: list[str] = field(default_factory=list)        # gold non-null, pred null
    flagged_wrong: int = 0
    flagged_wrong_values: int = 0
    flagged_total: int = 0
    critical_error: bool = False
    any_error: bool = False
    decision_gold: str = ""
    decision_pred: str | None = None
    needs_review: bool = False
    conflicts: Counts = field(default_factory=Counts)
    doc_correct: int = 0
    doc_total: int = 0
    latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    cost_usd: float = 0.0
    llm_sources: Counter = field(default_factory=Counter)
    llm_tasks: Counter = field(default_factory=Counter)
    input_tokens: int = 0
    output_tokens: int = 0
    est_input_tokens: int = 0
    summary_valid: bool | None = None
    degraded: bool = False


def score(gt: GroundTruth, res: PipelineResult) -> SubmissionScore:
    s = SubmissionScore(gt.record.submission_id, gt.meta.template)
    pred_rec = align(gt.record, res.record)
    gold = flatten(gt.record)
    pred = flatten(pred_rec)
    flagged = res.flagged_paths()
    # Provenance keys use the pipeline's own claim/location keys; re-key through alignment.
    remap = _key_remap(res, pred_rec)
    flagged = {remap.get(p, p) for p in flagged}
    for path in sorted(set(gold) | set(pred)):
        g, p = gold.get(path), pred.get(path)
        c = Counts()
        if p is not None and g is not None and values_match(path, g, p):
            c.tp = 1
        else:
            if p is not None:
                c.fp = 1
            if g is not None:
                c.fn = 1
        if c.tp == 0 and (c.fp or c.fn):
            if p is not None:
                s.wrong_paths.append(path)
            elif g is not None:
                s.missed_paths.append(path)
        sp = spec(path)
        s.overall.add(c)
        s.by_group[sp.group].add(c)
        s.by_field[generic(path)].add(c)
        if sp.critical:
            s.critical.add(c)
            if c.fp or c.fn:
                s.critical_error = True
        if c.fp or c.fn:
            s.any_error = True
    s.flagged_total = len(flagged)
    s.flagged_wrong = len(flagged & (set(s.wrong_paths) | set(s.missed_paths)))
    s.flagged_wrong_values = len(flagged & set(s.wrong_paths))

    s.decision_gold = gt.meta.expected_decision
    s.decision_pred = res.decision.outcome
    s.needs_review = res.needs_review

    exp = set(gt.meta.expected_conflicts)
    got = {remap.get(p, p) for p in res.conflict_paths()}
    s.conflicts = Counts(tp=len(exp & got), fp=len(got - exp), fn=len(exp - got))

    for name, dt in gt.meta.doc_types.items():
        s.doc_total += 1
        s.doc_correct += int(res.doc_types.get(name) == dt)

    s.latency_ms = sum(res.timings_ms.values())
    for call in res.llm_calls:
        s.llm_latency_ms += call.latency_ms
        s.cost_usd += call.cost_usd
        s.llm_sources[call.source] += 1
        s.llm_tasks[call.task] += 1
        s.input_tokens += call.input_tokens
        s.output_tokens += call.output_tokens
        s.est_input_tokens += call.est_input_tokens
    s.summary_valid = res.summary_citations_valid
    s.degraded = bool(res.degraded_reasons)
    return s


def _key_remap(res: PipelineResult, aligned) -> dict[str, str]:
    """Map provenance paths written with the pipeline's keys onto the aligned (gold) keys."""
    from submitiq.fields import claim_key
    remap: dict[str, str] = {}
    for before, after in zip(res.record.claims, aligned.claims):
        b, a = claim_key(before.claim_number), claim_key(after.claim_number)
        if b != a:
            for p in res.provenance:
                if p.startswith(f"claims[{b}]."):
                    remap[p] = p.replace(f"claims[{b}]", f"claims[{a}]", 1)
    for before, after in zip(res.record.locations, aligned.locations):
        if before.loc_number != after.loc_number:
            for p in res.provenance:
                if p.startswith(f"locations[{before.loc_number}]."):
                    remap[p] = p.replace(f"locations[{before.loc_number}]", f"locations[{after.loc_number}]", 1)
    return remap


def _pct(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))
    return xs[k]


def aggregate(scores: list[SubmissionScore]) -> dict[str, Any]:
    n = len(scores)
    overall, critical, conflicts = Counts(), Counts(), Counts()
    groups: dict[str, Counts] = defaultdict(Counts)
    fields_: dict[str, Counts] = defaultdict(Counts)
    by_template: dict[str, Counts] = defaultdict(Counts)
    confusion: Counter = Counter()
    sources: Counter = Counter()
    tasks: Counter = Counter()
    for s in scores:
        overall.add(s.overall)
        critical.add(s.critical)
        conflicts.add(s.conflicts)
        by_template[s.template].add(s.overall)
        for g, c in s.by_group.items():
            groups[g].add(c)
        for f, c in s.by_field.items():
            fields_[f].add(c)
        confusion[(s.decision_gold, s.decision_pred or "none")] += 1
        sources.update(s.llm_sources)
        tasks.update(s.llm_tasks)

    correct = sum(1 for s in scores if s.decision_pred == s.decision_gold)
    reviewed = [s for s in scores if s.needs_review]
    with_err = [s for s in scores if s.critical_error]
    wrong_total = sum(len(s.wrong_paths) + len(s.missed_paths) for s in scores)
    wrong_values = sum(len(s.wrong_paths) for s in scores)
    flagged_total = sum(s.flagged_total for s in scores)
    flagged_wrong = sum(s.flagged_wrong for s in scores)
    lat = [s.latency_ms for s in scores]
    summaries = [s.summary_valid for s in scores if s.summary_valid is not None]
    return {
        "n_submissions": n,
        "fields": {
            "overall": overall.prf(),
            "critical": critical.prf(),
            "by_group": {g: groups[g].prf() for g in GROUPS if g in groups},
            "by_template": {t: c.prf() for t, c in sorted(by_template.items())},
            "by_field": {f: c.prf() for f, c in sorted(fields_.items())},
        },
        "decision": {
            "accuracy": round(correct / n, 4) if n else 0.0,
            "abstained": sum(1 for s in scores if s.decision_pred is None),
            "declines_predicted_accept": sum(1 for s in scores if s.decision_gold == "decline" and s.decision_pred == "accept"),
            "confusion": {f"{g}->{p}": c for (g, p), c in sorted(confusion.items())},
        },
        "review": {
            "review_rate": round(len(reviewed) / n, 4) if n else 0.0,
            "submissions_with_critical_error": len(with_err),
            "silent_critical_error_rate": round(sum(1 for s in with_err if not s.needs_review) / n, 4) if n else 0.0,
            "flag_precision": round(flagged_wrong / flagged_total, 4) if flagged_total else 0.0,
            "flag_recall_of_errors": round(flagged_wrong / wrong_total, 4) if wrong_total else 0.0,
            # Of the values the pipeline *stated* that were wrong, how many did it flag? (silent-wrong-value guard)
            "wrong_values": wrong_values,
            "flag_recall_of_wrong_values": round(sum(s.flagged_wrong_values for s in scores) / wrong_values, 4) if wrong_values else None,
            "flagged_fields_per_submission": round(flagged_total / n, 2) if n else 0.0,
            "degraded_rate": round(sum(1 for s in scores if s.degraded) / n, 4) if n else 0.0,
        },
        "conflicts": conflicts.prf(),
        "documents": {
            "classification_accuracy": round(sum(s.doc_correct for s in scores) / max(1, sum(s.doc_total for s in scores)), 4),
        },
        "latency_ms": {
            "mean": round(statistics.mean(lat), 1) if lat else 0.0,
            "p50": round(_pct(lat, 0.5), 1), "p95": round(_pct(lat, 0.95), 1),
            "llm_recorded_mean": round(statistics.mean([s.llm_latency_ms for s in scores]), 1) if n else 0.0,
        },
        "cost": {
            "usd_per_submission": round(sum(s.cost_usd for s in scores) / n, 5) if n else 0.0,
            "input_tokens_per_submission": round(sum(s.input_tokens for s in scores) / n, 1) if n else 0.0,
            "output_tokens_per_submission": round(sum(s.output_tokens for s in scores) / n, 1) if n else 0.0,
            "est_prompt_tokens_per_submission": round(sum(s.est_input_tokens for s in scores) / n, 1) if n else 0.0,
            "llm_calls_by_source": dict(sorted(sources.items())),
            "llm_calls_by_task": dict(sorted(tasks.items())),
        },
        "summary": {
            "citation_valid_rate": round(sum(summaries) / len(summaries), 4) if summaries else None,
        },
    }
