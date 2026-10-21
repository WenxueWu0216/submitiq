"""Pre-rules-engine appetite decision: ask Claude, given the extracted record and the guidelines.

Used by variants v1-v4 only. Stage 5 replaces it with the deterministic rules engine.
"""
from __future__ import annotations

import hashlib

from ..guidelines import rules_text
from ..llm import LLMClient, LLMRequest, LLMResponse
from ..schema import Submission

TOOL = {
    "name": "record_decision",
    "description": "Record the appetite decision for a submission.",
    "input_schema": {
        "type": "object",
        "properties": {"decision": {"type": "string", "enum": ["accept", "refer", "decline"]},
                       "reasons": {"type": "array", "items": {"type": "string"}}},
        "required": ["decision", "reasons"],
        "additionalProperties": False,
    },
}


def decide(rec: Submission, llm: LLMClient) -> tuple[LLMRequest, LLMResponse, str | None]:
    record_json = rec.model_dump_json(exclude_none=True)
    req = LLMRequest(
        task="appetite_decision", prompt_version="v1",
        system="You are a commercial property underwriter applying written appetite guidelines exactly.",
        user=f"<guidelines>\n{rules_text()}\n</guidelines>\n\n<submission>\n{record_json}\n</submission>\n\n"
             "Apply the guidelines to this submission and call record_decision.",
        tool=TOOL, max_tokens=8000, key_material=hashlib.sha256(record_json.encode()).hexdigest())
    resp = llm.complete(req)
    out = resp.tool_input.get("decision") if resp.ok and resp.tool_input else None
    return req, resp, out if out in ("accept", "refer", "decline") else None
