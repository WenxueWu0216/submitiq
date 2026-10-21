# Eval: `v3_consistency` on `dev` (80 submissions)

backend `replay` · model `claude-opus-5-5` · git `a8db849` · 20261021T193709Z
LLM calls by source: {'replay:miss': 242}
LLM calls by task: {'appetite_decision': 80, 'extract_application': 80, 'extract_email': 80, 'extract_sov': 2}
> 242 LLM calls had no replay fixture and **abstained** (returned nothing). These numbers measure the non-LLM components only.

| metric | value |
|---|---|
| field precision | 100.0 |
| field recall | 98.5 |
| **field F1** | **99.2** |
| critical-field F1 | 99.7 |
| **decision accuracy** | **0.0** |
| decisions abstained | 80 |
| declines predicted as accept | 0 |
| review-queue rate | 35.0 |
| degraded (model unavailable) | 100.0 |
| silent critical-error rate | 1.2 |
| wrong values stated / flagged | 4 / 100.0 |
| flag recall of all field errors (incl. blanks) | 2.4 |
| flag precision | 11.1 |
| conflict detection P / R | 88.9 / 82.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 212 / 8328 |
| LLM latency, recorded (ms/sub) | 0 |
| cost per submission (USD) | 0.0000 |
| est. prompt tokens / submission | 7563 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 100.0 | 100.0 | 100.0 | 1291 | 0 | 0 |
| broker | 99.4 | 99.4 | 99.4 | 318 | 2 | 2 |
| policy | 100.0 | 83.3 | 90.9 | 398 | 0 | 80 |
| coverage | 100.0 | 100.0 | 100.0 | 718 | 0 | 0 |
| locations | 100.0 | 98.5 | 99.2 | 5619 | 0 | 86 |
| claims | 100.0 | 100.0 | 100.0 | 665 | 0 | 0 |
| loss_years | 100.0 | 100.0 | 100.0 | 1600 | 0 | 0 |
| totals | 99.4 | 99.4 | 99.4 | 318 | 2 | 2 |

## F1 by application template

| template | F1 |
|---|---|
| A | 99.0 |
| B | 99.4 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `policy.quote_needed_by` | 0.0 | 0 | 80 |
| `locations[].alarm_type` | 91.1 | 0 | 30 |
| `locations[].sprinkler_pct` | 96.7 | 0 | 20 |
| `broker.producer_email` | 97.5 | 2 | 2 |
| `locations[].bi_value` | 98.6 | 0 | 9 |
| `totals.location_count` | 98.8 | 1 | 1 |
| `totals.total_tiv` | 98.8 | 1 | 1 |
| `locations[].contents_value` | 99.2 | 0 | 5 |
| `locations[].tiv` | 99.2 | 0 | 5 |
| `locations[].protection_class` | 99.4 | 0 | 4 |

## Decision confusion (gold->pred)

accept->none: 26, decline->none: 24, refer->none: 30
