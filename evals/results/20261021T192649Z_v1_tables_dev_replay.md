# Eval: `v1_tables` on `dev` (80 submissions)

backend `replay` · model `claude-opus-5-5` · git `395f201` · 20261021T192649Z
LLM calls by source: {'replay:miss': 80}
> 80 LLM calls had no replay fixture and **abstained** (returned nothing). These numbers measure the non-LLM components only.

| metric | value |
|---|---|
| field precision | 100.0 |
| field recall | 68.9 |
| **field F1** | **81.6** |
| critical-field F1 | 92.2 |
| **decision accuracy** | **0.0** |
| decisions abstained | 80 |
| declines predicted as accept | 0 |
| review-queue rate | 100.0 |
| silent critical-error rate | 0.0 |
| flag recall of field errors | 0.0 |
| flag precision | 0.0 |
| conflict detection P / R | 0.0 / 0.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 168 / 8306 |
| LLM latency, recorded (ms/sub) | 0 |
| cost per submission (USD) | 0.0000 |
| est. prompt tokens / submission | 4275 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 0.0 | 0.0 | 0.0 | 0 | 0 | 1291 |
| broker | 0.0 | 0.0 | 0.0 | 0 | 0 | 320 |
| policy | 0.0 | 0.0 | 0.0 | 0 | 0 | 478 |
| coverage | 0.0 | 0.0 | 0.0 | 0 | 0 | 718 |
| locations | 100.0 | 88.9 | 94.1 | 5072 | 0 | 633 |
| claims | 100.0 | 100.0 | 100.0 | 665 | 0 | 0 |
| loss_years | 100.0 | 100.0 | 100.0 | 1600 | 0 | 0 |
| totals | 99.7 | 95.6 | 97.6 | 306 | 1 | 14 |

## F1 by application template

| template | F1 |
|---|---|
| A | 80.4 |
| B | 82.6 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `broker.agency_name` | 0.0 | 0 | 80 |
| `broker.producer_email` | 0.0 | 0 | 80 |
| `broker.producer_name` | 0.0 | 0 | 80 |
| `broker.producer_phone` | 0.0 | 0 | 80 |
| `coverage.bpp_limit` | 0.0 | 0 | 80 |
| `coverage.building_limit` | 0.0 | 0 | 80 |
| `coverage.business_income_limit` | 0.0 | 0 | 80 |
| `coverage.cause_of_loss_form` | 0.0 | 0 | 80 |
| `coverage.coinsurance_pct` | 0.0 | 0 | 78 |
| `coverage.deductible` | 0.0 | 0 | 80 |

## Decision confusion (gold->pred)

accept->none: 26, decline->none: 24, refer->none: 30
