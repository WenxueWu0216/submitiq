"""Export the contracts the .NET service shares with the Python pipeline.

    python scripts/export_contracts.py

Writes dotnet-api/contracts/:
  field_registry.json   field kind, group and 'critical' flag per generic path (from submitiq/fields.py)
  pipeline_results/     a few real PipelineResult JSON files (final pipeline, replay backend),
                        the payload POST /submissions accepts; used by the .NET tests

Python stays the source of truth; tests/test_contracts.py fails if these files go stale.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from submitiq.fields import all_specs  # noqa: E402

OUT = ROOT / "dotnet-api" / "contracts"
SAMPLES = ["SUB-0003", "SUB-0010", "SUB-0038", "SUB-0059", "SUB-0082"]


def registry() -> dict:
    return {path: {"group": s.group, "kind": s.kind, "critical": s.critical} for path, s in sorted(all_specs().items())}


def write_registry() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "field_registry.json"
    path.write_text(json.dumps(registry(), indent=1) + "\n")
    return path


def write_samples() -> list[Path]:
    from submitiq.pipeline import build_pipeline
    pipe = build_pipeline("final", backend="replay")
    out = []
    (OUT / "pipeline_results").mkdir(parents=True, exist_ok=True)
    for sid in SAMPLES:
        pkg = next((ROOT / "data" / "submissions").glob(f"*/{sid}"))
        res = pipe.run(pkg)
        res.timings_ms = {}          # machine-dependent; keep the files stable across runs
        p = OUT / "pipeline_results" / f"{sid}.json"
        p.write_text(res.model_dump_json(indent=1) + "\n")
        out.append(p)
    return out


if __name__ == "__main__":
    print(write_registry().relative_to(ROOT))
    for p in write_samples():
        print(p.relative_to(ROOT), f"{p.stat().st_size // 1024} KB")
