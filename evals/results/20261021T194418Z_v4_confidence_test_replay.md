# Eval: `v4_confidence` on `test` (40 submissions)

backend `replay` · model `claude-opus-5-5` · git `96cec24` · 20261021T194418Z
LLM calls by source: {'replay:miss': 121}
LLM calls by task: {'appetite_decision': 40, 'extract_application': 40, 'extract_email': 40, 'extract_sov': 1}
> 121 LLM calls had no replay fixture and **abstained** (returned nothing). These numbers measure the non-LLM components only.

| metric | value |
|---|---|
| field precision | 100.0 |
| field recall | 92.5 |
| **field F1** | **96.1** |
| critical-field F1 | 98.9 |
| **decision accuracy** | **0.0** |
| decisions abstained | 40 |
| declines predicted as accept | 0 |
| review-queue rate | 57.5 |
| degraded (model unavailable) | 100.0 |
| silent critical-error rate | 0.0 |
| wrong values stated / flagged | 2 / 50.0 |
| flag recall of all field errors (incl. blanks) | 8.0 |
| flag precision | 49.2 |
| conflict detection P / R | 90.9 / 50.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 202 / 8618 |
| LLM latency, recorded (ms/sub) | 0 |
| cost per submission (USD) | 0.0000 |
| est. prompt tokens / submission | 7459 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 99.8 | 75.2 | 85.8 | 486 | 1 | 160 |
| broker | 99.4 | 99.4 | 99.4 | 159 | 1 | 1 |
| policy | 100.0 | 66.7 | 80.0 | 160 | 0 | 80 |
| coverage | 100.0 | 74.9 | 85.7 | 269 | 0 | 90 |
| locations | 100.0 | 97.2 | 98.6 | 2460 | 0 | 70 |
| claims | 100.0 | 100.0 | 100.0 | 420 | 0 | 0 |
| loss_years | 100.0 | 100.0 | 100.0 | 800 | 0 | 0 |
| totals | 100.0 | 100.0 | 100.0 | 160 | 0 | 0 |

## F1 by application template

| template | F1 |
|---|---|
| A | 99.0 |
| B | 99.3 |
| C | 84.5 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `policy.quote_needed_by` | 0.0 | 0 | 40 |
| `locations[].alarm_type` | 75.2 | 0 | 35 |
| `insured.dba` | 81.8 | 0 | 4 |
| `insured.contact_email` | 82.9 | 1 | 11 |
| `coverage.coinsurance_pct` | 85.3 | 0 | 10 |
| `insured.years_in_business` | 85.3 | 0 | 10 |
| `coverage.bpp_limit` | 85.7 | 0 | 10 |
| `coverage.building_limit` | 85.7 | 0 | 10 |
| `coverage.business_income_limit` | 85.7 | 0 | 10 |
| `coverage.cause_of_loss_form` | 85.7 | 0 | 10 |

## Decision confusion (gold->pred)

accept->none: 13, decline->none: 9, refer->none: 18
