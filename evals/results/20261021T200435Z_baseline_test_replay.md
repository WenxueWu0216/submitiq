# Eval: `baseline` on `test` (40 submissions)

backend `replay` · model `claude-opus-5-5` · git `e384c5f` · 20261021T200435Z
LLM calls by source: {'replay:miss': 40}
LLM calls by task: {'baseline_extract': 40}
> 40 LLM calls had no replay fixture and **abstained** (returned nothing). These numbers measure the non-LLM components only.

| metric | value |
|---|---|
| field precision | 0.0 |
| field recall | 0.0 |
| **field F1** | **0.0** |
| critical-field F1 | 0.0 |
| **decision accuracy** | **0.0** |
| decisions abstained | 40 |
| declines predicted as accept | 0 |
| review-queue rate | 100.0 |
| degraded (model unavailable) | 100.0 |
| silent critical-error rate | 0.0 |
| wrong values stated / flagged | 0 / n/a |
| flag recall of all field errors (incl. blanks) | 0.0 |
| flag precision | 0.0 |
| conflict detection P / R | 0.0 / 0.0 |
| document classification acc. | 100.0 |
| latency p50 / p95 (ms, pipeline) | 167 / 9103 |
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
| locations | 0.0 | 0.0 | 0.0 | 0 | 0 | 2530 |
| claims | 0.0 | 0.0 | 0.0 | 0 | 0 | 420 |
| loss_years | 0.0 | 0.0 | 0.0 | 0 | 0 | 800 |
| totals | 0.0 | 0.0 | 0.0 | 0 | 0 | 160 |

## F1 by application template

| template | F1 |
|---|---|
| A | 0.0 |
| B | 0.0 |
| C | 0.0 |

## Weakest fields (≥5 gold values)

| field | F1 | FP | FN |
|---|---|---|---|
| `broker.agency_name` | 0.0 | 0 | 40 |
| `broker.producer_email` | 0.0 | 0 | 40 |
| `broker.producer_name` | 0.0 | 0 | 40 |
| `broker.producer_phone` | 0.0 | 0 | 40 |
| `claims[].cause` | 0.0 | 0 | 60 |
| `claims[].date_of_loss` | 0.0 | 0 | 60 |
| `claims[].incurred` | 0.0 | 0 | 60 |
| `claims[].paid` | 0.0 | 0 | 60 |
| `claims[].policy_year` | 0.0 | 0 | 60 |
| `claims[].reserve` | 0.0 | 0 | 60 |

## Decision confusion (gold->pred)

accept->none: 13, decline->none: 9, refer->none: 18
