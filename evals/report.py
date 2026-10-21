"""Render an eval result payload as a short markdown report."""
from __future__ import annotations

from typing import Any


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}"


def to_markdown(payload: dict[str, Any]) -> str:
    m, meta = payload["metrics"], payload["meta"]
    f = m["fields"]
    src = m["cost"]["llm_calls_by_source"]
    lines = [
        f"# Eval: `{meta['pipeline']}` on `{meta['split']}` ({meta['n']} submissions)",
        "",
        f"backend `{meta['backend']}` · model `{meta['model']}` · git `{meta['git_sha']}` · {meta['timestamp']}",
        f"LLM calls by source: {src or 'none'}",
    ]
    if src.get("replay:miss"):
        lines.append(f"> {src['replay:miss']} LLM calls had no replay fixture and **abstained** "
                     f"(returned nothing). These numbers measure the non-LLM components only.")
    lines += [
        "",
        "| metric | value |", "|---|---|",
        f"| field precision | {_pct(f['overall']['precision'])} |",
        f"| field recall | {_pct(f['overall']['recall'])} |",
        f"| **field F1** | **{_pct(f['overall']['f1'])}** |",
        f"| critical-field F1 | {_pct(f['critical']['f1'])} |",
        f"| **decision accuracy** | **{_pct(m['decision']['accuracy'])}** |",
        f"| decisions abstained | {m['decision']['abstained']} |",
        f"| declines predicted as accept | {m['decision']['declines_predicted_accept']} |",
        f"| review-queue rate | {_pct(m['review']['review_rate'])} |",
        f"| silent critical-error rate | {_pct(m['review']['silent_critical_error_rate'])} |",
        f"| flag recall of field errors | {_pct(m['review']['flag_recall_of_errors'])} |",
        f"| flag precision | {_pct(m['review']['flag_precision'])} |",
        f"| conflict detection P / R | {_pct(m['conflicts']['precision'])} / {_pct(m['conflicts']['recall'])} |",
        f"| document classification acc. | {_pct(m['documents']['classification_accuracy'])} |",
        f"| latency p50 / p95 (ms, pipeline) | {m['latency_ms']['p50']:.0f} / {m['latency_ms']['p95']:.0f} |",
        f"| LLM latency, recorded (ms/sub) | {m['latency_ms']['llm_recorded_mean']:.0f} |",
        f"| cost per submission (USD) | {m['cost']['usd_per_submission']:.4f} |",
        f"| est. prompt tokens / submission | {m['cost']['est_prompt_tokens_per_submission']:.0f} |",
        f"| summary citation validity | {_pct(m['summary']['citation_valid_rate'])} |",
        "",
        "## F1 by field group", "", "| group | P | R | F1 | TP | FP | FN |", "|---|---|---|---|---|---|---|",
    ]
    for g, c in f["by_group"].items():
        lines.append(f"| {g} | {_pct(c['precision'])} | {_pct(c['recall'])} | {_pct(c['f1'])} | {c['tp']} | {c['fp']} | {c['fn']} |")
    lines += ["", "## F1 by application template", "", "| template | F1 |", "|---|---|"]
    for t, c in f["by_template"].items():
        lines.append(f"| {t} | {_pct(c['f1'])} |")
    worst = sorted(((k, v) for k, v in f["by_field"].items() if v["tp"] + v["fn"] >= 5), key=lambda kv: kv[1]["f1"])[:10]
    lines += ["", "## Weakest fields (≥5 gold values)", "", "| field | F1 | FP | FN |", "|---|---|---|---|"]
    for k, v in worst:
        lines.append(f"| `{k}` | {_pct(v['f1'])} | {v['fp']} | {v['fn']} |")
    lines += ["", "## Decision confusion (gold->pred)", "", ", ".join(f"{k}: {v}" for k, v in m["decision"]["confusion"].items())]
    return "\n".join(lines) + "\n"
