"""Run every pipeline variant on dev and test and write a comparison table.

    python scripts/run_all_evals.py [--backend replay] [--pipelines baseline,v1_tables]

Output: evals/results/experiments_<backend>.md and .json (the source of the tables
in README.md and docs/experiment_log.md).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals import run as eval_run  # noqa: E402
from submitiq.pipeline import ORDER  # noqa: E402

COLS = [
    ("field F1", lambda m: m["fields"]["overall"]["f1"]),
    ("critical F1", lambda m: m["fields"]["critical"]["f1"]),
    ("decision acc.", lambda m: m["decision"]["accuracy"]),
    ("review rate", lambda m: m["review"]["review_rate"]),
    ("silent crit. err.", lambda m: m["review"]["silent_critical_error_rate"]),
    ("conflict F1", lambda m: m["conflicts"]["f1"]),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="replay")
    ap.add_argument("--pipelines", default=",".join(ORDER))
    ap.add_argument("--splits", default="dev,test")
    args = ap.parse_args()
    rows = []
    for name in args.pipelines.split(","):
        for split in args.splits.split(","):
            payload = eval_run.main(["--pipeline", name, "--split", split, "--backend", args.backend, "--quiet"])
            m = payload["metrics"]
            rows.append({"pipeline": name, "split": split, **{c: f(m) for c, f in COLS},
                         "usd/sub": m["cost"]["usd_per_submission"], "p50 ms": m["latency_ms"]["p50"],
                         "llm sources": m["cost"]["llm_calls_by_source"], "git": payload["meta"]["git_sha"]})
            print(f"{name:16} {split:5} F1={m['fields']['overall']['f1']:.3f} dec={m['decision']['accuracy']:.3f}")
    out = ROOT / "evals" / "results" / f"experiments_{args.backend}"
    out.with_suffix(".json").write_text(json.dumps(rows, indent=1))
    hdr = ["pipeline", "split"] + [c for c, _ in COLS] + ["usd/sub", "p50 ms"]
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for r in rows:
        cells = [r["pipeline"], r["split"]] + [f"{100 * r[c]:.1f}" for c, _ in COLS] + [f"{r['usd/sub']:.4f}", f"{r['p50 ms']:.0f}"]
        lines.append("| " + " | ".join(cells) + " |")
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
