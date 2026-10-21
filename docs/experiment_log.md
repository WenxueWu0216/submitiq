# Experiment log

Each entry covers one change, measured with the same harness (`evals/run.py`) on
the same data (dev = 80, test = 40; application template C appears only in test).
I tune on dev and report test.

**How to read the numbers.** This environment has no Anthropic API key and no
AWS credentials, so every run here uses the `replay` backend. A replay miss
*abstains*: it returns nothing and never invents an answer. The numbers marked
**offline** therefore measure only the parts that run without a model (parsers,
normalization, consistency checks, routing, rules). Every number that needs Claude
is marked **PENDING**, together with the command that produces it. Nothing in
this file was typed in by hand. Each figure comes from `evals/results/experiments_replay.json`
or the timestamped run files next to it.

---

## Stage 3: Baseline (one Claude call)

**What:** classify documents (keyword rules, LLM fallback) → pdfplumber text, Tesseract
OCR for image-only pages (orientation via OSD, projection-profile deskew) → all
document text plus the appetite guidelines in **one** prompt → JSON record **and**
the appetite decision from the model. No tool use, no citations, no cross-checks.

| split | field F1 | decision acc. | review rate | notes |
|---|---|---|---|---|
| dev (offline) | 0.0 | 0.0 | 100.0 | 80/80 extraction calls were replay misses → abstained |
| test (offline) | 0.0 | 0.0 | 100.0 | 40/40 replay misses |
| dev / test (Claude) | **PENDING** | **PENDING** | **PENDING** | `make eval-live` |

**What it shows offline:** the harness and plumbing work end to end. Document
classification by keyword rules alone is 100% on all 120 packages, with no LLM
fallback calls needed. The average prompt is about 4.3K tokens (chars/4 estimate). The
pipeline-only latency is p50 0.13 s, p95 8.4 s, and the p95 is dominated by OCR on
scanned pages. `tests/test_baseline_pipeline.py` checks that a correct model answer
round-trips to F1 = 1.0 through prompt → JSON → coercion → scoring, and that a
missing answer routes the submission to review instead of producing an empty
"accept".

**What I expect when it runs for real (hypotheses to check, not results):** good
on clean text-layer applications; weaker on long SOVs (row drift) and on split
loss-run tables; no way to tell which value came from which page, so every
error is silent.

**What broke on the way:** the first full eval ran 8 workers with Tesseract's
default OpenMP threading on a 4-core box. The load average hit 32, single pages
spun for 5+ CPU-minutes, and the run never finished. Fix: `OMP_THREAD_LIMIT=1`
per process, parallelism across documents only, and an OCR cache keyed by file hash.
The cache stores the original OCR duration, so the latency numbers still include OCR.
A full 120-package run dropped to 54 s cold.

---

## Stage 4a: Table-aware parsing for SOVs and loss runs

**What:** a local table extractor (`submitiq/tables/local.py`) rebuilds tables
from word positions. It works the same way on pdfplumber words and on Tesseract
words. Headers are found from a vocabulary of column spellings (`tables/vocab.py`),
longest phrase first, with tolerance for one-letter OCR slips. Each column owns an x-band, so
right-aligned numbers and multi-word cells land in the right column. The bands
carry over page breaks, so tables split across pages without a repeated header
still parse. Spreadsheets use the same vocabulary on cell text. Domain parsers
(`extract/sov.py`, `extract/loss_run.py`) turn rows into cited candidates and
run **reconciliation checks**: SOV TIV column vs printed total, building +
contents + BI = TIV per row, paid + reserve = incurred, and each policy year's
claim count and incurred vs the printed period total. An Amazon Textract backend
(`tables/textract.py`) sits behind the same interface (`SUBMITIQ_TABLES=textract`).
Its response parsing is unit-tested, but it has not run against AWS here.
The parsed tables take precedence over the LLM for location, claim and loss-year fields.

| split | field F1 | critical F1 | locations F1 | claims F1 | loss-years F1 | totals F1 |
|---|---|---|---|---|---|---|
| dev (offline) | 0.0 → **81.6** | 0.0 → 92.2 | 0 → 87.7* | 0 → 100.0 | 0 → 100.0 | 0 → 94.1* |
| test (offline) | 0.0 → **80.2** | 0.0 → 90.0 | 0 → 92.8 | 0 → 100.0 | 0 → 100.0 | 0 → 97.1 |
| with Claude | PENDING | PENDING | | | | |

\*dev figures before the dataset fix below were 87.7 / 94.1. The headline dev F1 is after the fix.
Precision on the parsed groups is ≥ 99.9%. When a parser can't read a cell, the cell comes
out empty. The parser does not guess. Insured/broker/policy/coverage stay at 0 offline because only the
(abstaining) LLM extracts them in this variant.

**What still misses (dev, by field):** `construction` 89.1 F1 (broker
abbreviations such as "JM", "ISO 4", "Metal Bldg"), `sprinklered` 88.1 ("Yes", "100%"),
money in "$1.25M" form, and `roof_type`/`alarm_type` (they appear only on the
application's premises table, which this variant doesn't parse). Normalization in 4c targets these.

**What broke:**
1. *Fuzzy header matching shifted two columns.* "Sprinklered" + "%" fuzzily
   matched the two-word synonym "sprinkler %". That consumed the next column's
   header and pushed every value one column right. Fix: try exact phrases first
   and use fuzzy matching only as a fallback (`tests/test_tables.py`).
2. *Dataset bug, now fixed:* in the SOV PDF renderer, a long header ("Location No.") overflowed its
   narrow column, and pdfplumber interleaved the overlapping characters ("NAo.ddress"). So
   the location number column vanished, and location 1 was lost in about 15% of PDF SOVs.
   Fix: the renderer now never lets a header overprint its neighbour. I
   regenerated the dataset (same seed) and re-ran every variant above on the new data.
