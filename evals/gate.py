"""CI regression gate.

    python -m evals.gate evals/results/<run>.json [--baseline evals/baseline.json] [--tolerance 2.0]

Fails (exit 1) if field F1 or decision accuracy is more than `tolerance`
percentage points below the reference stored for the same pipeline/split/backend.
Raising the reference is a deliberate act: `--update` rewrites the entry.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GATED = {"field_f1": ("fields", "overall", "f1"), "decision_accuracy": ("decision", "accuracy")}


def _get(metrics: dict, path: tuple[str, ...]) -> float:
    cur = metrics
    for k in path:
        cur = cur[k]
    return float(cur)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("result")
    ap.add_argument("--baseline", default=str(Path(__file__).with_name("baseline.json")))
    ap.add_argument("--tolerance", type=float, default=2.0, help="allowed drop, in percentage points")
    ap.add_argument("--update", action="store_true", help="write this run's metrics as the new reference")
    args = ap.parse_args(argv)

    run = json.loads(Path(args.result).read_text())
    meta = run["meta"]
    key = f"{meta['pipeline']}/{meta['split']}/{meta['backend']}"
    current = {name: _get(run["metrics"], path) for name, path in GATED.items()}
    base_path = Path(args.baseline)
    baseline = json.loads(base_path.read_text()) if base_path.exists() else {}

    if args.update:
        baseline[key] = {**current, "git_sha": meta["git_sha"], "timestamp": meta["timestamp"]}
        base_path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
        print(f"updated reference for {key}: {current}")
        return 0
    if key not in baseline:
        print(f"no reference for {key} in {base_path}; run with --update to create one")
        return 1
    failed = False
    for name, value in current.items():
        ref = float(baseline[key][name])
        drop = (ref - value) * 100
        status = "FAIL" if drop > args.tolerance else "ok"
        failed |= status == "FAIL"
        print(f"{status:4} {name:18} current {100 * value:6.2f}  reference {100 * ref:6.2f}  delta {-drop:+.2f} pts")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
