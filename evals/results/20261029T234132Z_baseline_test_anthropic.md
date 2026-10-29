# Eval: `baseline` on `test` (40 submissions)

backend `anthropic` · model `claude-haiku-5-5` · git `455650f` · 20261029T234132Z
LLM calls by source: {'live': 40}
LLM calls by task: {'baseline_extract': 40}

| metric | value |
|---|---|
| field precision | 100.0 |
| field recall | 71.4 |
| **field F1** | **83.3** |
| critical-field F1 | 84.0 |
| **decision accuracy** | **65.0** |
| decisions abstained | 12 |
| declines predicted as accept | 0 |
| review-queue rate | 30.0 |
| degraded (model unavailable) | 30.0 |
| silent critical-error rate | 5.0 |
| wrong values stated / flagged | 0 / n/a |
| flag recall of all field errors (incl. blanks) | 0.0 |
| flag precision | 0.0 |
| conflict detection P / R | 0.0 / 0.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 19283 / 31174 |
| LLM latency, recorded (ms/sub) | 17588 |
| cost per submission (USD) | 0.0032 |
| est. prompt tokens / submission | 4251 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 100.0 | 69.5 | 82.0 | 449 | 0 | 197 |
| broker | 100.0 | 70.0 | 82.3 | 112 | 0 | 48 |
| policy | 100.0 | 69.2 | 81.8 | 166 | 0 | 74 |
| coverage | 100.0 | 69.1 | 81.7 | 248 | 0 | 111 |
| locations | 100.0 | 73.0 | 84.4 | 1847 | 0 | 683 |
| claims | 100.0 | 71.7 | 83.5 | 301 | 0 | 119 |
| loss_years | 100.0 | 70.0 | 82.3 | 560 | 0 | 240 |
| totals | 100.0 | 70.0 | 82.3 | 112 | 0 | 48 |

## F1 by application template

| template | F1 |
|---|---|
| A | 78.7 |
| B | 78.6 |
| C | 96.3 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `insured.employee_count` | 78.7 | 0 | 13 |
| `insured.entity_type` | 78.8 | 0 | 14 |
| `policy.quote_needed_by` | 78.8 | 0 | 14 |
| `coverage.business_income_limit` | 80.6 | 0 | 13 |
| `coverage.earthquake_requested` | 80.6 | 0 | 13 |
| `coverage.flood_requested` | 80.6 | 0 | 13 |
| `locations[].alarm_type` | 81.1 | 0 | 28 |
| `locations[].roof_type` | 81.1 | 0 | 28 |
| `insured.website` | 81.2 | 0 | 12 |
| `coverage.coinsurance_pct` | 81.8 | 0 | 12 |

## Decision confusion (gold->pred)

accept->accept: 6, accept->none: 5, accept->refer: 2, decline->decline: 6, decline->none: 3, refer->none: 4, refer->refer: 14
