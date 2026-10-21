"""One interface for every model backend.

    anthropic  Claude API (ANTHROPIC_API_KEY or an `ant auth login` profile)
    bedrock    Claude on Amazon Bedrock via boto3 (standard AWS credential chain)
    replay     responses saved on disk; runs offline and deterministically

Environment:
    SUBMITIQ_MODEL         default claude-opus-5-5
    SUBMITIQ_EFFORT        low | medium | high (default medium)
    SUBMITIQ_RECORD=1      wrap a live backend and save every response for replay
    SUBMITIQ_REPLAY_DIR    default fixtures/replay
    SUBMITIQ_REPLAY_MISS   abstain (default) | error
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional, Protocol

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "claude-opus-5-5"


class LLMRequest(BaseModel):
    task: str                      # baseline_extract | extract_application | classify | summary | ...
    prompt_version: str            # bump when the prompt or tool schema changes
    system: str
    user: str
    tool: Optional[dict[str, Any]] = None   # {"name", "description", "input_schema"}
    max_tokens: int = 32000
    key_material: str              # stable identity of the inputs (e.g. document sha256s)

    def cache_key(self) -> str:
        raw = f"{self.task}|{self.prompt_version}|{self.key_material}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def est_input_tokens(self) -> int:
        n = len(self.system) + len(self.user) + (len(json.dumps(self.tool)) if self.tool else 0)
        return n // 4


class LLMResponse(BaseModel):
    text: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = None
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    stop_reason: Optional[str] = None
    source: str = "live"           # live | replay:recorded | replay:hand_written | replay:miss
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and (self.text is not None or self.tool_input is not None)


class LLMClient(Protocol):
    def complete(self, req: LLMRequest) -> LLMResponse: ...


def replay_dir() -> Path:
    return Path(os.environ.get("SUBMITIQ_REPLAY_DIR", ROOT / "fixtures" / "replay"))


def get_client(backend: str | None = None) -> LLMClient:
    backend = backend or os.environ.get("SUBMITIQ_BACKEND", "replay")
    model = os.environ.get("SUBMITIQ_MODEL", DEFAULT_MODEL)
    if backend == "replay":
        from .replay import ReplayClient
        return ReplayClient(replay_dir(), miss_policy=os.environ.get("SUBMITIQ_REPLAY_MISS", "abstain"))
    if backend == "anthropic":
        from .anthropic_backend import AnthropicClient
        client: LLMClient = AnthropicClient(model=model, effort=os.environ.get("SUBMITIQ_EFFORT", "medium"))
    elif backend == "bedrock":
        from .bedrock_backend import BedrockClient
        client = BedrockClient(model_id=os.environ.get("SUBMITIQ_BEDROCK_MODEL_ID", f"anthropic.{model}"),
                               region=os.environ.get("AWS_REGION", "us-east-1"))
    else:
        raise ValueError(f"unknown backend {backend!r}")
    if os.environ.get("SUBMITIQ_RECORD") == "1":
        from .replay import RecordingClient
        client = RecordingClient(client, replay_dir())
    return client


def call_record(req: LLMRequest, resp: LLMResponse):
    """Bookkeeping entry for one call (tokens, latency, cost, replay source)."""
    from ..result import LLMCallRecord
    from .pricing import cost_usd
    return LLMCallRecord(task=req.task, source=resp.source, model=resp.model, input_tokens=resp.input_tokens,
                         output_tokens=resp.output_tokens, latency_ms=resp.latency_ms,
                         cost_usd=cost_usd(resp.model, resp.input_tokens, resp.output_tokens),
                         est_input_tokens=req.est_input_tokens())
