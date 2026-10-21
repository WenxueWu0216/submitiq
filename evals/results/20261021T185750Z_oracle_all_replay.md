# Eval: `oracle` on `all` (120 submissions)

backend `replay` · model `claude-opus-5-5` · git `1fe71ae` · 20261021T185750Z
LLM calls by source: none

| metric | value |
|---|---|
| field precision | 100.0 |
| field recall | 100.0 |
| **field F1** | **100.0** |
| critical-field F1 | 100.0 |
| **decision accuracy** | **100.0** |
| decisions abstained | 0 |
| declines predicted as accept | 0 |
| review-queue rate | 0.0 |
| silent critical-error rate | 0.0 |
| flag recall of field errors | 0.0 |
| flag precision | 0.0 |
| conflict detection P / R | 0.0 / 0.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 0 / 0 |
| LLM latency, recorded (ms/sub) | 0 |
| cost per submission (USD) | 0.0000 |
| est. prompt tokens / submission | 0 |
| summary citation validity | n/a |

## F1 by field group

| group | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| insured | 100.0 | 100.0 | 100.0 | 1937 | 0 | 0 |
| broker | 100.0 | 100.0 | 100.0 | 480 | 0 | 0 |
| policy | 100.0 | 100.0 | 100.0 | 718 | 0 | 0 |
| coverage | 100.0 | 100.0 | 100.0 | 1077 | 0 | 0 |
| locations | 100.0 | 100.0 | 100.0 | 8235 | 0 | 0 |
| claims | 100.0 | 100.0 | 100.0 | 1085 | 0 | 0 |
| loss_years | 100.0 | 100.0 | 100.0 | 2400 | 0 | 0 |
| totals | 100.0 | 100.0 | 100.0 | 480 | 0 | 0 |

## F1 by application template

| template | F1 |
|---|---|
| A | 100.0 |
| B | 100.0 |
| C | 100.0 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `broker.agency_name` | 100.0 | 0 | 0 |
| `broker.producer_email` | 100.0 | 0 | 0 |
| `broker.producer_name` | 100.0 | 0 | 0 |
| `broker.producer_phone` | 100.0 | 0 | 0 |
| `claims[].cause` | 100.0 | 0 | 0 |
| `claims[].date_of_loss` | 100.0 | 0 | 0 |
| `claims[].incurred` | 100.0 | 0 | 0 |
| `claims[].paid` | 100.0 | 0 | 0 |
| `claims[].policy_year` | 100.0 | 0 | 0 |
| `claims[].reserve` | 100.0 | 0 | 0 |

## Decision confusion (gold->pred)

accept->accept: 39, decline->decline: 33, refer->refer: 48
