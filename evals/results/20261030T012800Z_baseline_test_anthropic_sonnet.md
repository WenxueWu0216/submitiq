# Eval: `baseline` on `test` (40 submissions)

backend `anthropic` · model `claude-sonnet-5-5` · git `d18252c` · 20261030T012800Z
LLM calls by source: {'live': 22, 'replay:recorded': 18}
LLM calls by task: {'baseline_extract': 40}

| metric | value |
|---|---|
| field precision | 99.9 |
| field recall | 95.9 |
| **field F1** | **97.9** |
| critical-field F1 | 98.1 |
| **decision accuracy** | **85.0** |
| decisions abstained | 2 |
| declines predicted as accept | 0 |
| review-queue rate | 5.0 |
| degraded (model unavailable) | 5.0 |
| silent critical-error rate | 5.0 |
| wrong values stated / flagged | 3 / 0.0 |
| flag recall of all field errors (incl. blanks) | 0.0 |
| flag precision | 0.0 |
| conflict detection P / R | 0.0 / 0.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 8712 / 19928 |
| LLM latency, recorded (ms/sub) | 12037 |
| cost per submission (USD) | 0.0382 |
| est. prompt tokens / submission | 4251 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 99.8 | 94.6 | 97.1 | 611 | 1 | 35 |
| broker | 100.0 | 95.0 | 97.4 | 152 | 0 | 8 |
| policy | 100.0 | 94.6 | 97.2 | 227 | 0 | 13 |
| coverage | 100.0 | 94.2 | 97.0 | 338 | 0 | 21 |
| locations | 99.9 | 96.9 | 98.4 | 2452 | 2 | 78 |
| claims | 100.0 | 96.7 | 98.3 | 406 | 0 | 14 |
| loss_years | 100.0 | 95.0 | 97.4 | 760 | 0 | 40 |
| totals | 100.0 | 95.0 | 97.4 | 152 | 0 | 8 |

## F1 by application template

| template | F1 |
|---|---|
| A | 96.8 |
| B | 99.9 |
| C | 95.5 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `insured.contact_email` | 94.9 | 1 | 3 |
| `insured.employee_count` | 95.8 | 0 | 3 |
| `coverage.business_income_limit` | 96.1 | 0 | 3 |
| `coverage.earthquake_requested` | 96.1 | 0 | 3 |
| `coverage.flood_requested` | 96.1 | 0 | 3 |
| `insured.entity_type` | 96.1 | 0 | 3 |
| `policy.quote_needed_by` | 96.1 | 0 | 3 |
| `locations[].construction` | 97.1 | 2 | 6 |
| `insured.website` | 97.3 | 0 | 2 |
| `coverage.coinsurance_pct` | 97.4 | 0 | 2 |

## Decision confusion (gold->pred)

accept->accept: 10, accept->none: 1, accept->refer: 2, decline->decline: 8, decline->refer: 1, refer->decline: 1, refer->none: 1, refer->refer: 16
