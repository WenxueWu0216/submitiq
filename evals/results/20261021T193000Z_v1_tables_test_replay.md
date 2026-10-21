# Eval: `v1_tables` on `test` (40 submissions)

backend `replay` · model `claude-opus-5-5` · git `0aef363` · 20261021T193000Z
LLM calls by source: {'replay:miss': 40}
LLM calls by task: {'baseline_extract': 40}
> 40 LLM calls had no replay fixture and **abstained** (returned nothing). These numbers measure the non-LLM components only.

| metric | value |
|---|---|
| field precision | 100.0 |
| field recall | 67.0 |
| **field F1** | **80.2** |
| critical-field F1 | 90.0 |
| **decision accuracy** | **0.0** |
| decisions abstained | 40 |
| declines predicted as accept | 0 |
| review-queue rate | 100.0 |
| degraded (model unavailable) | 100.0 |
| silent critical-error rate | 0.0 |
| flag recall of field errors | 0.0 |
| flag precision | 0.0 |
| conflict detection P / R | 0.0 / 0.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 147 / 8598 |
| LLM latency, recorded (ms/sub) | 0 |
| cost per submission (USD) | 0.0000 |
| est. prompt tokens / submission | 4251 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 0.0 | 0.0 | 0.0 | 0 | 0 | 646 |
| broker | 0.0 | 0.0 | 0.0 | 0 | 0 | 160 |
| policy | 0.0 | 0.0 | 0.0 | 0 | 0 | 240 |
| coverage | 0.0 | 0.0 | 0.0 | 0 | 0 | 359 |
| locations | 100.0 | 86.6 | 92.8 | 2190 | 1 | 340 |
| claims | 100.0 | 100.0 | 100.0 | 420 | 0 | 0 |
| loss_years | 100.0 | 100.0 | 100.0 | 800 | 0 | 0 |
| totals | 100.0 | 94.4 | 97.1 | 151 | 0 | 9 |

## F1 by application template

| template | F1 |
|---|---|
| A | 76.8 |
| B | 82.9 |
| C | 79.8 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `broker.agency_name` | 0.0 | 0 | 40 |
| `broker.producer_email` | 0.0 | 0 | 40 |
| `broker.producer_name` | 0.0 | 0 | 40 |
| `broker.producer_phone` | 0.0 | 0 | 40 |
| `coverage.bpp_limit` | 0.0 | 0 | 40 |
| `coverage.building_limit` | 0.0 | 0 | 40 |
| `coverage.business_income_limit` | 0.0 | 0 | 40 |
| `coverage.cause_of_loss_form` | 0.0 | 0 | 40 |
| `coverage.coinsurance_pct` | 0.0 | 0 | 39 |
| `coverage.deductible` | 0.0 | 0 | 40 |

## Decision confusion (gold->pred)

accept->none: 13, decline->none: 9, refer->none: 18
