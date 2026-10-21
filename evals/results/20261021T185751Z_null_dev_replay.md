# Eval: `null` on `dev` (80 submissions)

backend `replay` · model `claude-opus-5-5` · git `1fe71ae` · 20261021T185751Z
LLM calls by source: none

| metric | value |
|---|---|
| field precision | 0.0 |
| field recall | 0.0 |
| **field F1** | **0.0** |
| critical-field F1 | 0.0 |
| **decision accuracy** | **0.0** |
| decisions abstained | 80 |
| declines predicted as accept | 0 |
| review-queue rate | 0.0 |
| silent critical-error rate | 100.0 |
| flag recall of field errors | 0.0 |
| flag precision | 0.0 |
| conflict detection P / R | 0.0 / 0.0 |
| document classification acc. | 0.0 |
| latency p50 / p95 (ms, pipeline) | 0 / 0 |
| LLM latency, recorded (ms/sub) | 0 |
| cost per submission (USD) | 0.0000 |
| est. prompt tokens / submission | 0 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 0.0 | 0.0 | 0.0 | 0 | 0 | 1291 |
| broker | 0.0 | 0.0 | 0.0 | 0 | 0 | 320 |
| policy | 0.0 | 0.0 | 0.0 | 0 | 0 | 478 |
| coverage | 0.0 | 0.0 | 0.0 | 0 | 0 | 718 |
| locations | 0.0 | 0.0 | 0.0 | 0 | 0 | 5705 |
| claims | 0.0 | 0.0 | 0.0 | 0 | 0 | 665 |
| loss_years | 0.0 | 0.0 | 0.0 | 0 | 0 | 1600 |
| totals | 0.0 | 0.0 | 0.0 | 0 | 0 | 320 |

## F1 by application template

| template | F1 |
|---|---|
| A | 0.0 |
| B | 0.0 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `broker.agency_name` | 0.0 | 0 | 80 |
| `broker.producer_email` | 0.0 | 0 | 80 |
| `broker.producer_name` | 0.0 | 0 | 80 |
| `broker.producer_phone` | 0.0 | 0 | 80 |
| `claims[].cause` | 0.0 | 0 | 95 |
| `claims[].date_of_loss` | 0.0 | 0 | 95 |
| `claims[].incurred` | 0.0 | 0 | 95 |
| `claims[].paid` | 0.0 | 0 | 95 |
| `claims[].policy_year` | 0.0 | 0 | 95 |
| `claims[].reserve` | 0.0 | 0 | 95 |

## Decision confusion (gold->pred)

accept->none: 26, decline->none: 24, refer->none: 30
