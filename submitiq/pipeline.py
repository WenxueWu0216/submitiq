"""Pipeline registry. Each variant is one row of docs/experiment_log.md."""
from __future__ import annotations

import time
from pathlib import Path

from .result import PipelineResult
from .schema import Submission


class NullPipeline:
    """Predicts nothing. Used to sanity-check the harness (F1 must be 0)."""
    name = "null"

    def run(self, pkg: Path) -> PipelineResult:
        t0 = time.perf_counter()
        res = PipelineResult(submission_id=pkg.name, pipeline=self.name, record=Submission(submission_id=pkg.name))
        res.timings_ms["total"] = (time.perf_counter() - t0) * 1000
        return res


def build_pipeline(name: str, backend: str = "replay"):
    if name == "null":
        return NullPipeline()
    raise ValueError(f"unknown pipeline {name!r}")
