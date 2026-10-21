"""Sweep the confidence threshold and OCR exponent on the DEV split only.

    python scripts/tune_routing.py
Prints review rate, silent critical-error rate and flag recall for each setting.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import submitiq.confidence as C  # noqa: E402
from evals.metrics import aggregate, score  # noqa: E402
from evals.run import list_packages, load_gt  # noqa: E402
from submitiq.pipeline import build_pipeline  # noqa: E402


def main() -> None:
    pkgs = list_packages("dev")
    gts = [load_gt(p) for p in pkgs]
    print("threshold exponent  review  silent  flag_recall  flag_precision")
    for exp in (1.0, 2.0):
        for th in (0.6, 0.7, 0.75, 0.8, 0.85, 0.9):
            C.THRESHOLD, C.OCR_EXPONENT = th, exp
            # score_and_route reads its defaults at call time via the module globals
            C.score_and_route.__defaults__ = (th, exp)
            pipe = build_pipeline("v4_confidence")
            agg = aggregate([score(g, pipe.run(p)) for p, g in zip(pkgs, gts)])
            r = agg["review"]
            print(f"{th:9.2f} {exp:8.1f}  {100 * r['review_rate']:6.1f}  {100 * r['silent_critical_error_rate']:6.1f}"
                  f"  {100 * r['flag_recall_of_errors']:11.1f}  {100 * r['flag_precision']:14.1f}")


if __name__ == "__main__":
    main()
