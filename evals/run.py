"""Evaluation harness.

    python -m evals.run --pipeline final --split test --backend replay
    python -m evals.run --pipeline oracle --split dev          # harness self-check, must be 1.0

Writes evals/results/<timestamp>_<pipeline>_<split>_<backend>.json (full detail)
and a .md summary next to it, then prints the summary.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.metrics import aggregate, score  # noqa: E402
from evals.report import to_markdown  # noqa: E402
from submitiq.result import PipelineResult  # noqa: E402
from submitiq.schema import GroundTruth  # noqa: E402

DATA = ROOT / "data" / "submissions"
RESULTS = ROOT / "evals" / "results"


def list_packages(split: str) -> list[Path]:
    splits = ["dev", "test"] if split == "all" else [split]
    out: list[Path] = []
    for sp in splits:
        out += sorted(p for p in (DATA / sp).iterdir() if p.is_dir())
    return out


def load_gt(pkg: Path) -> GroundTruth:
    return GroundTruth.model_validate_json((pkg / "ground_truth.json").read_text())


def _run_one(args: tuple[str, str, str]) -> str:
    pipeline_name, backend, pkg = args
    pkg_path = Path(pkg)
    if pipeline_name == "oracle":
        gt = load_gt(pkg_path)
        res = PipelineResult(submission_id=gt.record.submission_id, pipeline="oracle", record=gt.record,
                             doc_types={k: v for k, v in gt.meta.doc_types.items()})
        res.decision.outcome = gt.meta.expected_decision  # type: ignore[assignment]
        res.timings_ms["total"] = 0.0
        return res.model_dump_json()
    from submitiq.pipeline import build_pipeline
    pipe = build_pipeline(pipeline_name, backend=backend)
    t0 = time.perf_counter()
    try:
        res = pipe.run(pkg_path)
    except Exception as exc:  # a crash is a result too: empty record, flagged for review
        from submitiq.schema import Submission
        res = PipelineResult(submission_id=pkg_path.name, pipeline=pipeline_name,
                             record=Submission(submission_id=pkg_path.name), needs_review=True,
                             review_reasons=[f"pipeline error: {exc!r}"], errors=[repr(exc)])
        res.timings_ms["total"] = (time.perf_counter() - t0) * 1000
    return res.model_dump_json()


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", default="final")
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--backend", default=os.environ.get("SUBMITIQ_BACKEND", "replay"),
                    choices=["replay", "anthropic", "bedrock"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 2))
    ap.add_argument("--out", default=str(RESULTS))
    ap.add_argument("--tag", default="")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    pkgs = list_packages(args.split)[: args.limit]
    jobs = [(args.pipeline, args.backend, str(p)) for p in pkgs]
    started = time.perf_counter()
    if args.workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            outputs = list(ex.map(_run_one, jobs))
    else:
        outputs = [_run_one(j) for j in jobs]
    wall = time.perf_counter() - started

    results = [PipelineResult.model_validate_json(o) for o in outputs]
    scores = [score(load_gt(p), r) for p, r in zip(pkgs, results)]
    agg = aggregate(scores)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    meta = {
        "pipeline": args.pipeline, "split": args.split, "backend": args.backend, "tag": args.tag,
        "timestamp": stamp, "git_sha": _git_sha(), "n": len(pkgs), "wall_seconds": round(wall, 1),
        "model": os.environ.get("SUBMITIQ_MODEL", "claude-opus-5-5"),
        "replay_miss_policy": os.environ.get("SUBMITIQ_REPLAY_MISS", "abstain"),
    }
    per_sub = [{
        "id": s.submission_id, "template": s.template, "f1": s.overall.prf()["f1"],
        "decision_gold": s.decision_gold, "decision_pred": s.decision_pred, "needs_review": s.needs_review,
        "critical_error": s.critical_error, "wrong": s.wrong_paths[:40], "missed": s.missed_paths[:40],
        "review_reasons": r.review_reasons[:20], "errors": r.errors,
    } for s, r in zip(scores, results)]
    payload = {"meta": meta, "metrics": agg, "submissions": per_sub}
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"{stamp}_{args.pipeline}_{args.split}_{args.backend}{('_' + args.tag) if args.tag else ''}"
    base.with_suffix(".json").write_text(json.dumps(payload, indent=1, default=str))
    md = to_markdown(payload)
    base.with_suffix(".md").write_text(md)
    if not args.quiet:
        print(md)
        print(f"\nwrote {base.with_suffix('.json')}")
    return payload


if __name__ == "__main__":
    main()
