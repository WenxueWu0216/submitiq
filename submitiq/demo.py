"""`make demo`: run the final pipeline on one package and print what an underwriter would see.

    python -m submitiq.demo [SUB-0003] [--backend replay|anthropic|bedrock]
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from .fields import flatten, spec
from .pipeline import build_pipeline

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", nargs="?", default="SUB-0003")
    ap.add_argument("--backend", default="replay")
    args = ap.parse_args()
    pkg = next((ROOT / "data" / "submissions").glob(f"*/{args.submission}"))
    res = build_pipeline("final", backend=args.backend).run(pkg)

    print(f"\n=== {res.submission_id}: {res.record.insured.named_insured} ===")
    print("documents:", ", ".join(f"{n} -> {t}" for n, t in res.doc_types.items()))
    print("LLM calls:", ", ".join(f"{c.task} [{c.source}]" for c in res.llm_calls) or "none")
    if any(c.source == "replay:miss" for c in res.llm_calls):
        print("  (replay:miss = no recorded answer offline; the step abstained and deterministic parsers carried on)")
    if any(c.source == "replay:hand_written" for c in res.llm_calls):
        print("  (replay:hand_written = demo fixture written by hand from the documents, NOT model output)")

    print(f"\nrecommendation: {res.decision.outcome.upper() if res.decision.outcome else 'none'} (source: {res.decision.source})")
    for h in res.decision.reasons:
        print(f"  - {h.rule_id} ({h.outcome}): {h.message}")
    print(f"\nreview queue: {'YES' if res.needs_review else 'no'}")
    for r in res.review_reasons[:8]:
        print("  -", textwrap.shorten(r, 150))

    values = flatten(res.record)
    print("\nkey fields (value · confidence · source):")
    for p in ["insured.named_insured", "insured.naics_code", "policy.effective_date", "policy.quote_needed_by",
              "totals.total_tiv", "totals.five_year_incurred", "locations[1].construction", "locations[1].roof_year"]:
        fp = res.provenance.get(p)
        if fp is None:
            continue
        c = fp.citations[0] if fp.citations else None
        where = f"{c.doc}{f' p.{c.page}' if c and c.page else ''}" if c else "-"
        val = values.get(p)
        crit = "*" if spec(p).critical else " "
        print(f" {crit} {p:28} {str(val):38.38} {fp.confidence if fp.confidence is not None else '-':>5} {fp.status:15} {where}")

    print(f"\n--- triage summary ({res.summary_source}; citations valid: {res.summary_citations_valid}) ---")
    print(res.summary)
    print(f"\npipeline time {sum(res.timings_ms.values()):.0f} ms (OCR at original cost). "
          "Review UI: make seed && make serve -> http://localhost:8000")


if __name__ == "__main__":
    main()
