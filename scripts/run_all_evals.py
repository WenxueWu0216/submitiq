"""Run every pipeline variant on dev and test and write a comparison table.

    python scripts/run_all_evals.py [--backend replay] [--pipelines baseline,v1_tables]
        [--splits test] [--limit 5] [--models baseline=claude-haiku-5-5,final=claude-sonnet-5-5]

--models picks a model per pipeline (others use SUBMITIQ_MODEL); --limit caps submissions per split.

Output: evals/results/experiments_<backend>.md and .json (the source of the tables
in README.md and docs/experiment_log.md).
"""
from __future__ import annotations

import argparse
import json
import os
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
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", default="", help="suffix on result files; tagged runs stay out of the README table")
    ap.add_argument("--models", default="", help="pipeline=model,... (others use SUBMITIQ_MODEL)")
    args = ap.parse_args()
    models = dict(kv.split("=", 1) for kv in args.models.split(",") if kv)
    default_model = os.environ.get("SUBMITIQ_MODEL")
    rows, spent = [], 0.0
    for name in args.pipelines.split(","):
        # Worker processes inherit os.environ, so setting it here picks the model for this pipeline.
        if name in models:
            os.environ["SUBMITIQ_MODEL"] = models[name]
        elif default_model:
            os.environ["SUBMITIQ_MODEL"] = default_model
        else:
            os.environ.pop("SUBMITIQ_MODEL", None)
        for split in args.splits.split(","):
            argv = ["--pipeline", name, "--split", split, "--backend", args.backend, "--quiet"]
            if args.tag:
                argv += ["--tag", args.tag]
            if args.limit:
                argv += ["--limit", str(args.limit)]
            payload = eval_run.main(argv)
            m = payload["metrics"]
            run_usd = m["cost"]["usd_per_submission"] * payload["meta"]["n"]
            spent += run_usd
            rows.append({"pipeline": name, "split": split, **{c: f(m) for c, f in COLS},
                         "usd/sub": m["cost"]["usd_per_submission"], "p50 ms": m["latency_ms"]["p50"],
                         "llm sources": m["cost"]["llm_calls_by_source"], "git": payload["meta"]["git_sha"]})
            print(f"{name:16} {split:5} {payload['meta']['model']:18} F1={m['fields']['overall']['f1']:.3f} "
                  f"dec={m['decision']['accuracy']:.3f} usd/sub={m['cost']['usd_per_submission']:.4f} "
                  f"run=${run_usd:.2f} total=${spent:.2f}")
    out = ROOT / "evals" / "results" / f"experiments_{args.backend}{('_' + args.tag) if args.tag else ''}"
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
