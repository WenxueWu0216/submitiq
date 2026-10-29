"""Claude API backend (official anthropic SDK)."""
from __future__ import annotations

import logging
import os
import time

import anthropic

from .base import LLMRequest, LLMResponse

log = logging.getLogger(__name__)
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def parse_message(msg, tool_name: str | None) -> tuple[str | None, dict | None]:
    text_parts, tool_input = [], None
    for block in msg.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use" and (tool_name is None or block.name == tool_name):
            tool_input = dict(block.input)
    return ("".join(text_parts) or None), tool_input


class AnthropicClient:
    def __init__(self, model: str, effort: str = "medium"):
        self.model = model
        self.effort = effort
        self.client = anthropic.Anthropic(max_retries=4)
        # Server-side refusal fallback; set SUBMITIQ_FALLBACKS=0 to turn it off.
        self.use_fallbacks = os.environ.get("SUBMITIQ_FALLBACKS", "1") == "1"
        # Tools whose schema the API refused in strict mode; later calls skip the doomed strict attempt.
        self.non_strict_tools: set[str] = set()

    def _kwargs(self, req: LLMRequest, user: str) -> dict:
        kw: dict = {
            "model": self.model, "max_tokens": req.max_tokens, "system": req.system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": self.effort},
        }
        if req.tool:
            # Forced tool_choice is rejected on current models: use auto + strict schema + instruction.
            strict = req.tool["name"] not in self.non_strict_tools
            kw["tools"] = [{**req.tool, "strict": True} if strict else dict(req.tool)]
            kw["tool_choice"] = {"type": "auto"}
        return kw

    def _call(self, kw: dict):
        try:
            return self._call_once(kw)
        except anthropic.BadRequestError as exc:
            if not any(t.get("strict") for t in kw.get("tools", [])):
                raise
            # Strict mode limits schema complexity; keep going without it (pydantic validates downstream).
            log.warning("strict tool schema rejected (%s); retrying without strict", exc)
            self.non_strict_tools.update(t["name"] for t in kw["tools"])
            return self._call_once({**kw, "tools": [{k: v for k, v in t.items() if k != "strict"} for t in kw["tools"]]})

    def _call_once(self, kw: dict):
        if self.use_fallbacks:
            try:
                with self.client.beta.messages.stream(**kw, betas=[FALLBACK_BETA], fallbacks="default") as s:
                    return s.get_final_message()
            except anthropic.BadRequestError as exc:
                if "fallback" not in str(exc).lower():
                    raise          # e.g. a schema error: not the fallback's fault, keep fallbacks on
                log.warning("request with fallbacks rejected (%s); retrying without", exc)
                self.use_fallbacks = False
        with self.client.messages.stream(**kw) as s:
            return s.get_final_message()

    def complete(self, req: LLMRequest) -> LLMResponse:
        t0 = time.perf_counter()
        user = req.user
        in_tok = out_tok = 0
        for attempt in range(2):
            try:
                msg = self._call(self._kwargs(req, user))
            except anthropic.RateLimitError as exc:
                return LLMResponse(error=f"rate limited: {exc}", latency_ms=(time.perf_counter() - t0) * 1000)
            except anthropic.APIStatusError as exc:
                return LLMResponse(error=f"api error {exc.status_code}: {exc}", latency_ms=(time.perf_counter() - t0) * 1000)
            except anthropic.APIConnectionError as exc:
                return LLMResponse(error=f"connection error: {exc}", latency_ms=(time.perf_counter() - t0) * 1000)
            in_tok += msg.usage.input_tokens
            out_tok += msg.usage.output_tokens
            if msg.stop_reason == "refusal":
                return LLMResponse(error="refusal", stop_reason="refusal", model=msg.model, input_tokens=in_tok,
                                   output_tokens=out_tok, latency_ms=(time.perf_counter() - t0) * 1000)
            text, tool_input = parse_message(msg, req.tool["name"] if req.tool else None)
            if req.tool and tool_input is None and attempt == 0:
                user = req.user + f"\n\nYou must answer by calling the `{req.tool['name']}` tool."
                continue
            err = "max_tokens" if msg.stop_reason == "max_tokens" else None
            return LLMResponse(text=text, tool_input=tool_input, model=msg.model, input_tokens=in_tok,
                               output_tokens=out_tok, stop_reason=msg.stop_reason, error=err,
                               latency_ms=(time.perf_counter() - t0) * 1000)
        return LLMResponse(error="no tool call", model=self.model, input_tokens=in_tok, output_tokens=out_tok,
                           latency_ms=(time.perf_counter() - t0) * 1000)
