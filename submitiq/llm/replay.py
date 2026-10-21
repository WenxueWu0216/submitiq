"""Replay backend: answer from responses saved on disk.

Fixture layout: fixtures/replay/<task>/<cache_key>.json
    {"task", "prompt_version", "key_material", "source": "recorded" | "hand_written", "response": {...}}

A miss never invents an answer. With the default policy it *abstains* (returns
an empty response marked replay:miss), so callers treat it like a model that
declined to answer and route the affected fields to review.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .base import LLMClient, LLMRequest, LLMResponse


class ReplayMiss(RuntimeError):
    pass


def fixture_path(root: Path, req: LLMRequest) -> Path:
    return root / req.task / f"{req.cache_key()}.json"


class ReplayClient:
    def __init__(self, root: Path, miss_policy: str = "abstain"):
        self.root = root
        self.miss_policy = miss_policy

    def complete(self, req: LLMRequest) -> LLMResponse:
        path = fixture_path(self.root, req)
        if not path.exists():
            if self.miss_policy == "error":
                raise ReplayMiss(f"no replay fixture for task={req.task} key={req.cache_key()}")
            return LLMResponse(source="replay:miss", error="replay miss")
        data = json.loads(path.read_text())
        resp = LLMResponse.model_validate(data["response"])
        resp.source = f"replay:{data.get('source', 'recorded')}"
        return resp


class RecordingClient:
    """Wraps a live client and saves each successful response as a replay fixture."""

    def __init__(self, inner: LLMClient, root: Path):
        self.inner = inner
        self.root = root

    def complete(self, req: LLMRequest) -> LLMResponse:
        resp = self.inner.complete(req)
        if resp.ok:
            path = fixture_path(self.root, req)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "task": req.task, "prompt_version": req.prompt_version, "key_material": req.key_material,
                "source": "recorded", "recorded_at": datetime.now(timezone.utc).isoformat(),
                "response": resp.model_dump(exclude={"source"}),
            }, indent=1))
        return resp
