"""Claude on Amazon Bedrock via boto3 InvokeModel (Anthropic Messages body).

boto3 is already in the Lambda runtime, so the deployed workers need no extra
SDK. `strict` tool schemas and `output_config` are left out here because
support differs by Bedrock model version. Outputs are validated with pydantic
downstream either way.
"""
from __future__ import annotations

import json
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .base import LLMRequest, LLMResponse


class BedrockClient:
    def __init__(self, model_id: str, region: str):
        self.model_id = model_id
        self.rt = boto3.client("bedrock-runtime", region_name=region)

    def complete(self, req: LLMRequest) -> LLMResponse:
        body: dict = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": req.max_tokens,
            "system": req.system,
            "messages": [{"role": "user", "content": req.user}],
        }
        if req.tool:
            body["tools"] = [req.tool]
            body["tool_choice"] = {"type": "auto"}
        t0 = time.perf_counter()
        try:
            out = self.rt.invoke_model(modelId=self.model_id, body=json.dumps(body),
                                       contentType="application/json", accept="application/json")
        except (ClientError, BotoCoreError) as exc:
            return LLMResponse(error=f"bedrock error: {exc}", latency_ms=(time.perf_counter() - t0) * 1000)
        msg = json.loads(out["body"].read())
        latency = (time.perf_counter() - t0) * 1000
        text = "".join(b.get("text", "") for b in msg.get("content", []) if b.get("type") == "text") or None
        tool_input = next((b.get("input") for b in msg.get("content", [])
                           if b.get("type") == "tool_use" and req.tool and b.get("name") == req.tool["name"]), None)
        usage = msg.get("usage", {})
        stop = msg.get("stop_reason")
        err = {"refusal": "refusal", "max_tokens": "max_tokens"}.get(stop or "")
        if req.tool and tool_input is None and err is None:
            err = "no tool call"
        return LLMResponse(text=text, tool_input=tool_input, model=self.model_id, stop_reason=stop, error=err,
                           input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0),
                           latency_ms=latency)
