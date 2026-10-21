"""Fake LLM clients for tests."""
from __future__ import annotations

import json
from typing import Callable

from submitiq.llm import LLMRequest, LLMResponse


class FakeClient:
    def __init__(self, handler: Callable[[LLMRequest], LLMResponse | None]):
        self.handler = handler
        self.requests: list[LLMRequest] = []

    def complete(self, req: LLMRequest) -> LLMResponse:
        self.requests.append(req)
        resp = self.handler(req)
        return resp or LLMResponse(source="replay:miss", error="replay miss")


def baseline_answer_from(gt) -> Callable[[LLMRequest], LLMResponse | None]:
    """Pretend to be a perfect model for the baseline task."""
    def handler(req: LLMRequest):
        if req.task != "baseline_extract":
            return None
        payload = {"record": json.loads(gt.record.model_dump_json()), "appetite_decision": gt.meta.expected_decision,
                   "decision_reasons": gt.meta.expected_reasons}
        return LLMResponse(text="Here is the JSON:\n" + json.dumps(payload), model="fake", source="live")
    return handler


def _leaf(v, page=1):
    if hasattr(v, "isoformat"):
        v = v.isoformat()
    if hasattr(v, "value") and not isinstance(v, (int, float, str)):
        v = v.value
    return {"value": v, "page": page, "evidence": None if v is None else str(v)[:40]}


def tool_answers_from(gt) -> Callable[[LLMRequest], LLMResponse | None]:
    """Pretend to be a perfect model for the per-document tool-use tasks."""
    rec = gt.record

    def group(obj, names, rename=None):
        rename = rename or {}
        return {n: _leaf(getattr(obj, rename.get(n, n))) for n in names}

    def handler(req: LLMRequest):
        from submitiq.extract import llm_docs as L
        if req.task == "extract_application":
            ins = rec.insured
            insured = {k: _leaf(getattr(ins.mailing_address, k[8:]) if k.startswith("mailing_") else getattr(ins, k))
                       for k in L.APP_INSURED}
            data = {"insured": insured, "broker": group(rec.broker, L.APP_BROKER),
                    "policy": group(rec.policy, L.APP_POLICY), "coverage": group(rec.coverage, L.APP_COVERAGE),
                    "stated_total_tiv": _leaf(rec.totals.total_tiv), "stated_location_count": _leaf(rec.totals.location_count),
                    "premises": [{"loc_number": l.loc_number, **group(l, L.PREMISES)} for l in rec.locations[:3]]}
        elif req.task == "extract_email":
            data = {"insured_name": _leaf(rec.insured.named_insured), "effective_date": _leaf(rec.policy.effective_date),
                    "quote_needed_by": _leaf(rec.policy.quote_needed_by), "producer_name": _leaf(rec.broker.producer_name),
                    "producer_email": _leaf(rec.broker.producer_email), "producer_phone": _leaf(rec.broker.producer_phone),
                    "agency_name": _leaf(rec.broker.agency_name), "approximate_total_tiv": _leaf(None)}
        elif req.task == "extract_loss_run":
            years = [ly for ly in rec.loss_years if (ly.carrier or "").upper() in req.user.upper()]
            data = {"carrier": _leaf(years[0].carrier if years else None), "insured_name": _leaf(rec.insured.named_insured),
                    "policy_years": [{"policy_year": ly.policy_year, "earned_premium": _leaf(ly.earned_premium),
                                      "claims": [group(c, L.CLAIM) for c in rec.claims if c.policy_year == ly.policy_year]}
                                     for ly in years]}
        elif req.task == "extract_sov":
            data = {"insured_name": _leaf(rec.insured.named_insured), "stated_total_tiv": _leaf(rec.totals.total_tiv),
                    "locations": [{"loc_number": l.loc_number, **group(l, L.SOV_LOC)} for l in rec.locations]}
        elif req.task == "appetite_decision":
            return LLMResponse(tool_input={"decision": gt.meta.expected_decision, "reasons": []}, model="fake")
        else:
            return None
        return LLMResponse(tool_input=json.loads(json.dumps(data, default=str)), model="fake", source="live")
    return handler
