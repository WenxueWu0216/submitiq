# Eval: `baseline` on `all` (120 submissions)

backend `replay` · model `claude-opus-5-5` · git `05f4b45` · 20261021T191425Z
LLM calls by source: {'replay:miss': 120}
> 120 LLM calls had no replay fixture and **abstained** (returned nothing). These numbers measure the non-LLM components only.

| metric | value |
|---|---|
| field precision | 0.0 |
| field recall | 0.0 |
| **field F1** | **0.0** |
| critical-field F1 | 0.0 |
| **decision accuracy** | **0.0** |
| decisions abstained | 120 |
| declines predicted as accept | 0 |
| review-queue rate | 100.0 |
| silent critical-error rate | 0.0 |
| flag recall of field errors | 0.0 |
| flag precision | 0.0 |
| conflict detection P / R | 0.0 / 0.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 131 / 8405 |
| LLM latency, recorded (ms/sub) | 0 |
| cost per submission (USD) | 0.0000 |
| est. prompt tokens / submission | 4267 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 0.0 | 0.0 | 0.0 | 0 | 0 | 1937 |
| broker | 0.0 | 0.0 | 0.0 | 0 | 0 | 480 |
| policy | 0.0 | 0.0 | 0.0 | 0 | 0 | 718 |
| coverage | 0.0 | 0.0 | 0.0 | 0 | 0 | 1077 |
| locations | 0.0 | 0.0 | 0.0 | 0 | 0 | 8235 |
| claims | 0.0 | 0.0 | 0.0 | 0 | 0 | 1085 |
| loss_years | 0.0 | 0.0 | 0.0 | 0 | 0 | 2400 |
| totals | 0.0 | 0.0 | 0.0 | 0 | 0 | 480 |

## F1 by application template

| template | F1 |
|---|---|
| A | 0.0 |
| B | 0.0 |
| C | 0.0 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `broker.agency_name` | 0.0 | 0 | 120 |
| `broker.producer_email` | 0.0 | 0 | 120 |
| `broker.producer_name` | 0.0 | 0 | 120 |
| `broker.producer_phone` | 0.0 | 0 | 120 |
| `claims[].cause` | 0.0 | 0 | 155 |
| `claims[].date_of_loss` | 0.0 | 0 | 155 |
| `claims[].incurred` | 0.0 | 0 | 155 |
| `claims[].paid` | 0.0 | 0 | 155 |
| `claims[].policy_year` | 0.0 | 0 | 155 |
| `claims[].reserve` | 0.0 | 0 | 155 |

## Decision confusion (gold->pred)

accept->none: 39, decline->none: 33, refer->none: 48
