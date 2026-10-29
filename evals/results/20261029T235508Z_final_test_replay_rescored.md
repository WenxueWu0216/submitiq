# Eval: `final` on `test` (40 submissions)

backend `replay` · model `claude-opus-5-5` · git `455650f` · 20261029T235508Z
LLM calls by source: {'replay:recorded': 121}
LLM calls by task: {'extract_application': 40, 'extract_email': 40, 'extract_sov': 1, 'summary': 40}

| metric | value |
|---|---|
| field precision | 100.0 |
| field recall | 99.6 |
| **field F1** | **99.8** |
| critical-field F1 | 100.0 |
| **decision accuracy** | **100.0** |
| decisions abstained | 0 |
| declines predicted as accept | 0 |
| review-queue rate | 67.5 |
| degraded (model unavailable) | 0.0 |
| silent critical-error rate | 0.0 |
| wrong values stated / flagged | 2 / 50.0 |
| flag recall of all field errors (incl. blanks) | 9.1 |
| flag precision | 2.0 |
| conflict detection P / R | 65.5 / 95.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 198 / 9166 |
| LLM latency, recorded (ms/sub) | 22909 |
| cost per submission (USD) | 0.0727 |
| est. prompt tokens / submission | 7537 |
| summary citation validity | 100.0 |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 99.8 | 99.7 | 99.8 | 644 | 1 | 2 |
| broker | 99.4 | 99.4 | 99.4 | 159 | 1 | 1 |
| policy | 100.0 | 100.0 | 100.0 | 240 | 0 | 0 |
| coverage | 100.0 | 99.2 | 99.6 | 356 | 0 | 3 |
| locations | 100.0 | 99.4 | 99.7 | 2514 | 0 | 16 |
| claims | 100.0 | 100.0 | 100.0 | 420 | 0 | 0 |
| loss_years | 100.0 | 100.0 | 100.0 | 800 | 0 | 0 |
| totals | 100.0 | 100.0 | 100.0 | 160 | 0 | 0 |

## F1 by application template

| template | F1 |
|---|---|
| A | 99.7 |
| B | 99.8 |
| C | 99.8 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `locations[].sprinkler_pct` | 96.3 | 0 | 10 |
| `broker.producer_name` | 97.5 | 1 | 1 |
| `insured.contact_email` | 97.5 | 1 | 1 |
| `insured.employee_count` | 98.6 | 0 | 1 |
| `coverage.business_income_limit` | 98.7 | 0 | 1 |
| `coverage.earthquake_requested` | 98.7 | 0 | 1 |
| `coverage.flood_requested` | 98.7 | 0 | 1 |
| `locations[].bi_value` | 99.3 | 0 | 2 |
| `locations[].contents_value` | 99.3 | 0 | 2 |
| `locations[].protection_class` | 99.6 | 0 | 1 |

## Decision confusion (gold->pred)

accept->accept: 13, decline->decline: 9, refer->refer: 18
