import anthropic
import httpx

from submitiq.llm.anthropic_backend import AnthropicClient


def _bad_request(msg):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.BadRequestError(msg, response=httpx.Response(400, request=req), body=None)


def test_schema_error_keeps_fallbacks_on_and_skips_strict_next_time(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    client = AnthropicClient(model="claude-haiku-5-5")
    seen = []

    def fake_call_once(kw):
        strict = kw["tools"][0].get("strict", False)
        seen.append(strict)
        if strict:
            raise _bad_request("Schemas contains too many parameters with union types")
        return "msg"

    monkeypatch.setattr(client, "_call_once", fake_call_once)
    from submitiq.llm.base import LLMRequest
    req = LLMRequest(task="t", prompt_version="v1", system="s", user="u", key_material="k",
                     tool={"name": "extract", "description": "d", "input_schema": {"type": "object"}})
    assert client._call(client._kwargs(req, "u")) == "msg"
    assert client._call(client._kwargs(req, "u")) == "msg"
    assert seen == [True, False, False]          # strict tried once, then skipped
    assert client.use_fallbacks                   # a schema error must not switch fallbacks off
