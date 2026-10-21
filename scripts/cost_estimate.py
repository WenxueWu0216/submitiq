"""Monthly AWS cost estimate for N submissions, using an eval result for the token profile.

    python scripts/cost_estimate.py [evals/results/<run>.json] [--n 1000] [--model claude-opus-5-5]

If the run used a live model (or replay of recorded live calls), the token counts
are MEASURED. Otherwise prompt tokens come from the chars/4 estimate recorded
per call, output tokens use OUTPUT_TOKENS_PER_CALL, and the table says so.
Prices are list prices as of 2026-10. Check them before quoting a client.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from submitiq.llm.pricing import PRICES  # noqa: E402

OUTPUT_TOKENS_PER_CALL = 2500          # assumption: tool JSON with evidence quotes + adaptive thinking
LLM_CALLS_ASSUMED = 3.0                 # application + email + summary (+ rare SOV/loss-run fallback)

# Lambda GB-seconds per submission: (memory GB, seconds) per state; seconds are assumptions
# (OCR p95 ~8 s measured locally; Bedrock waits dominate extract/summarize).
LAMBDA = {"start": (0.25, 0.3), "classify": (2.0, 6.0), "extract": (1.5, 40.0), "validate": (1.0, 3.0),
          "rules": (0.5, 1.0), "summarize": (1.0, 15.0)}
LAMBDA_GBS_PRICE = 0.0000166667        # x86, per GB-second
LAMBDA_REQ_PRICE = 0.20 / 1_000_000
SFN_TRANSITION_PRICE = 0.025 / 1000     # standard workflows
SFN_TRANSITIONS = 8
S3_GB_MONTH, MB_PER_SUBMISSION = 0.023, 0.6
S3_REQUESTS_PER_SUB, S3_REQ_PRICE = 120, 0.005 / 1000
DDB_WRITE_PRICE, DDB_WRITES = 1.25 / 1_000_000, 2
KMS_KEY_MONTH, KMS_REQ_PRICE, KMS_REQS = 1.00, 0.03 / 10_000, 150
CW_LOG_GB, CW_LOG_PRICE, CW_METRICS, CW_METRIC_PRICE, CW_DASHBOARD, CW_ALARMS = 0.00005, 0.50, 10, 0.30, 3.00, 3 * 0.10
ECR_GB, ECR_PRICE = 1.0, 0.10


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("result", nargs="?")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--model", default="claude-opus-5-5")
    args = ap.parse_args()
    runs = glob.glob(str(ROOT / "evals/results/*_final_test_*.json")) + glob.glob(str(ROOT / "evals/results/*_v5_rules_test_*.json"))
    path = args.result or sorted(runs, key=lambda p: Path(p).name)[-1]
    run = json.loads(Path(path).read_text())
    cost = run["metrics"]["cost"]
    sources = cost["llm_calls_by_source"]
    measured = any(k in sources for k in ("live", "replay:recorded"))
    n_sub = run["meta"]["n"]
    calls = sum(sources.values()) / n_sub if n_sub else LLM_CALLS_ASSUMED
    if measured:
        tin, tout = cost["input_tokens_per_submission"], cost["output_tokens_per_submission"]
        basis = f"MEASURED token usage from {Path(path).name}"
    else:
        tin, tout = cost["est_prompt_tokens_per_submission"], calls * OUTPUT_TOKENS_PER_CALL
        basis = (f"ESTIMATED: prompt tokens = chars/4 recorded by the harness ({tin:,.0f}/submission over "
                 f"{calls:.1f} calls), output = {OUTPUT_TOKENS_PER_CALL} tokens/call assumed")
    pin, pout = PRICES[args.model]
    llm_per = (tin * pin + tout * pout) / 1e6
    n = args.n
    lines = {
        f"Bedrock {args.model} tokens (1P list price as proxy)": llm_per * n,
        "Lambda compute + requests": n * (sum(m * s for m, s in LAMBDA.values()) * LAMBDA_GBS_PRICE + len(LAMBDA) * LAMBDA_REQ_PRICE),
        "Step Functions (standard)": n * SFN_TRANSITIONS * SFN_TRANSITION_PRICE,
        "S3 storage (first month) + requests": n * MB_PER_SUBMISSION / 1024 * S3_GB_MONTH + n * S3_REQUESTS_PER_SUB * S3_REQ_PRICE,
        "DynamoDB on-demand": n * DDB_WRITES * DDB_WRITE_PRICE,
        "KMS key + requests": KMS_KEY_MONTH + n * KMS_REQS * KMS_REQ_PRICE,
        "CloudWatch logs, EMF metrics, dashboard, alarms": n * CW_LOG_GB * CW_LOG_PRICE + CW_METRICS * CW_METRIC_PRICE + CW_DASHBOARD + CW_ALARMS,
        "ECR image storage": ECR_GB * ECR_PRICE,
    }
    total = sum(lines.values())
    print(f"Basis: {basis}\n")
    print(f"| item ({n:,} submissions/month) | USD/month |\n|---|---|")
    for k, v in lines.items():
        print(f"| {k} | {v:,.2f} |")
    print(f"| **total** | **{total:,.2f}** |")
    print(f"\nper submission: ${total / n:.3f} (model share {100 * lines[next(iter(lines))] / total:.0f}%)")
    for other in PRICES:
        if other != args.model:
            o_in, o_out = PRICES[other]
            print(f"  with {other}: model ${(tin * o_in + tout * o_out) / 1e6 * n:,.2f}/month")
    print(f"  optional Textract TABLES for scanned pages (~30% of packages x 3 pages x $0.015): ${n * 0.3 * 3 * 0.015:,.2f}/month")


if __name__ == "__main__":
    main()
