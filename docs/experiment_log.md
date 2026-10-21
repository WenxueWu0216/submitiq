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
