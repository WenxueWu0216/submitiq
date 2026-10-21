# Eval: `v2_tooluse` on `dev` (80 submissions)

backend `replay` · model `claude-opus-5-5` · git `a8db849` · 20261021T193658Z
LLM calls by source: {'replay:miss': 253}
LLM calls by task: {'appetite_decision': 80, 'extract_application': 80, 'extract_email': 80, 'extract_sov': 13}
> 253 LLM calls had no replay fixture and **abstained** (returned nothing). These numbers measure the non-LLM components only.

| metric | value |
|---|---|
| field precision | 99.8 |
| field recall | 96.1 |
| **field F1** | **98.0** |
| critical-field F1 | 97.7 |
| **decision accuracy** | **0.0** |
| decisions abstained | 80 |
| declines predicted as accept | 0 |
| review-queue rate | 0.0 |
| degraded (model unavailable) | 100.0 |
| silent critical-error rate | 40.0 |
| wrong values stated / flagged | 17 / 0.0 |
| flag recall of all field errors (incl. blanks) | 0.0 |
| flag precision | 0.0 |
| conflict detection P / R | 0.0 / 0.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 189 / 8315 |
| LLM latency, recorded (ms/sub) | 0 |
| cost per submission (USD) | 0.0000 |
| est. prompt tokens / submission | 7832 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 99.5 | 98.8 | 99.2 | 1276 | 6 | 15 |
| broker | 97.2 | 97.2 | 97.2 | 311 | 9 | 9 |
| policy | 100.0 | 75.7 | 86.2 | 362 | 0 | 116 |
| coverage | 100.0 | 90.8 | 95.2 | 652 | 0 | 66 |
| locations | 100.0 | 96.2 | 98.0 | 5486 | 0 | 219 |
| claims | 100.0 | 100.0 | 100.0 | 665 | 0 | 0 |
| loss_years | 100.0 | 100.0 | 100.0 | 1600 | 0 | 0 |
| totals | 99.4 | 98.4 | 98.9 | 315 | 2 | 5 |

## F1 by application template

| template | F1 |
|---|---|
| A | 97.6 |
| B | 98.3 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `policy.quote_needed_by` | 0.0 | 0 | 80 |
| `coverage.flood_requested` | 85.7 | 0 | 20 |
| `policy.effective_date` | 85.7 | 0 | 20 |
| `coverage.building_limit` | 88.1 | 0 | 17 |
| `broker.producer_email` | 88.8 | 9 | 9 |
| `policy.expiration_date` | 88.9 | 0 | 16 |
| `locations[].alarm_type` | 91.1 | 0 | 30 |
| `coverage.earthquake_requested` | 91.2 | 0 | 13 |
| `insured.contact_email` | 92.5 | 6 | 6 |
| `locations[].construction` | 92.9 | 0 | 42 |

## Decision confusion (gold->pred)

accept->none: 26, decline->none: 24, refer->none: 30
