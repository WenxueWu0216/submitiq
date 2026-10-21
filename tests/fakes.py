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
