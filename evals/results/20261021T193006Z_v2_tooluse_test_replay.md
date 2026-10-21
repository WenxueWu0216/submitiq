# Eval: `v2_tooluse` on `test` (40 submissions)

backend `replay` · model `claude-opus-5-5` · git `0aef363` · 20261021T193006Z
LLM calls by source: {'replay:miss': 128}
LLM calls by task: {'appetite_decision': 40, 'extract_application': 40, 'extract_email': 40, 'extract_sov': 8}
> 128 LLM calls had no replay fixture and **abstained** (returned nothing). These numbers measure the non-LLM components only.

| metric | value |
|---|---|
| field precision | 99.8 |
| field recall | 88.9 |
| **field F1** | **94.0** |
| critical-field F1 | 94.8 |
| **decision accuracy** | **0.0** |
| decisions abstained | 40 |
| declines predicted as accept | 0 |
| review-queue rate | 0.0 |
| degraded (model unavailable) | 100.0 |
| silent critical-error rate | 67.5 |
| flag recall of field errors | 0.0 |
| flag precision | 0.0 |
| conflict detection P / R | 0.0 / 0.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 199 / 8637 |
| LLM latency, recorded (ms/sub) | 0 |
| cost per submission (USD) | 0.0000 |
| est. prompt tokens / submission | 7793 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 99.6 | 74.3 | 85.1 | 480 | 2 | 166 |
| broker | 96.9 | 96.9 | 96.9 | 155 | 5 | 5 |
| policy | 100.0 | 56.2 | 72.0 | 135 | 0 | 105 |
| coverage | 100.0 | 65.5 | 79.1 | 235 | 0 | 124 |
| locations | 100.0 | 92.7 | 96.2 | 2345 | 1 | 185 |
| claims | 100.0 | 100.0 | 100.0 | 420 | 0 | 0 |
| loss_years | 100.0 | 100.0 | 100.0 | 800 | 0 | 0 |
| totals | 100.0 | 96.9 | 98.4 | 155 | 0 | 5 |

## F1 by application template

| template | F1 |
|---|---|
| A | 96.9 |
| B | 97.3 |
| C | 82.6 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `policy.quote_needed_by` | 0.0 | 0 | 40 |
| `policy.expiration_date` | 54.5 | 0 | 25 |
| `policy.effective_date` | 66.7 | 0 | 20 |
| `coverage.earthquake_requested` | 68.8 | 0 | 19 |
| `coverage.flood_requested` | 71.0 | 0 | 18 |
| `coverage.building_limit` | 75.0 | 0 | 16 |
| `coverage.business_income_limit` | 75.0 | 0 | 16 |
| `locations[].alarm_type` | 75.2 | 0 | 35 |
| `coverage.bpp_limit` | 76.9 | 0 | 15 |
| `insured.annual_revenue` | 76.9 | 0 | 15 |

## Decision confusion (gold->pred)

accept->none: 13, decline->none: 9, refer->none: 18
