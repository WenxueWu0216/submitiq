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
| dev (offline) | 0.0 → **81.6** | 0.0 → 92.2 | 0 → 94.1 | 0 → 100.0 | 0 → 100.0 | 0 → 97.6 |
| test (offline) | 0.0 → **80.2** | 0.0 → 90.0 | 0 → 92.8 | 0 → 100.0 | 0 → 100.0 | 0 → 97.1 |
| with Claude | PENDING | PENDING | | | | |

All figures are after the dataset fix described below. Before it, dev locations F1 was 87.7.
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

---

## Stage 4b: Per-document extraction with Claude tool use and strict schemas

**What:** the single prompt is replaced by one extractor per document type, and each one
produces cited candidates:

* **application:** a deterministic `Label: value` form parser (labels written
  from the dev templates A/B only) plus the premises table, **and** a Claude call
  with the `record_application` tool.
* **email:** deterministic header/signature parsing plus a Claude call (`record_email`)
  for the free-text facts: quote-needed-by date, requested effective date, the insured's name as the broker wrote it.
* **SOV / loss run:** the 4a table parsers. Claude (`record_sov`, `record_loss_run`)
  runs **only when the parser fails its own reconciliation checks**, which is a cost lever.
* **decision:** a separate Claude call over the assembled record (the rules engine replaces it in Stage 5).

Every tool schema is strict (`strict: true`, `additionalProperties: false`, every
property required, nullable values). Every leaf is `{value, page, evidence}`, so
each LLM value carries a page and a verbatim quote. Current Claude models reject forced
`tool_choice`, so the call uses `auto` plus an explicit instruction, with one
re-prompt if no tool call comes back. If the API rejects the strict schema, the
call retries once without `strict`. pydantic validates the output either way.

| split | field F1 | critical F1 | template A | template B | template C (held out) |
|---|---|---|---|---|---|
| dev (offline) | 81.6 → **98.0** | 92.2 → 97.7 | 97.6 | 98.3 | – |
| test (offline) | 80.2 → **94.0** | 90.0 → 94.8 | 96.9 | 97.3 | **82.6** |
| with Claude | PENDING | PENDING | PENDING | PENDING | PENDING |

LLM calls per submission (all 120): 1 application + 1 email + 1 decision, plus
21 SOV fallbacks (17.5% of SOVs failed reconciliation under basic normalization). That
is 3.2 calls per submission, about 7.8K prompt tokens (chars/4 estimate). Offline, all of them abstained.

**Reading this honestly:**
* The offline dev number (98.0) mostly measures a parser I wrote against templates
  I also wrote. **Template C is the honest test**: an unseen boxed layout with labels
  above values and no colons. The label parser extracts nothing from it, so insured/policy/coverage
  recall collapses (test: insured 74.3 R, policy 56.2 R, coverage 65.5 R) and
  template C sits at 82.6 F1. Closing that gap is exactly the job of the
  `record_application` call. **That number is PENDING a live run.**
* `policy.quote_needed_by` exists only in the email body, so offline it is 0 (40/40 FN on test).
* `tests/test_per_doc_extraction.py` drives the tool-use path with a fake "perfect"
  model. On a template-C package it lifts F1 from the offline value to ≥ 97% and gets the
  decision right. That proves the plumbing (schema → candidates → merge), *not* model quality.

**What broke:** OCR'd emails on scanned applications split `grace.hughes @tidewaterrisk.com`
at the `@`. The form parser keeps the broken value, which gives 9 producer-email false positives on dev.
That is a precision error the parser cannot see on its own. 4d's validation checks catch it.

---

## Stage 4c: Cross-document consistency checks and entity normalization

**What:** two separate changes, so I measured them separately.

* **v3a, consistency checks with exact matching.** After merging, every chosen value is
  compared with the readings from *other documents*: application vs SOV for location
  COPE, the stated application TIV and the SOV's printed total vs the TIV derived from the SOV rows,
  stated location count vs rows, email vs application dates, and every printed insured name
  vs the legal name. A disagreement never changes the chosen value (the source-of-truth
  rules still decide). It marks the field `conflict`, keeps both readings with citations,
  and routes the submission to review.
* **v3, plus normalization.** Value synonyms ("JM", "ISO 4", "Metal Bldg", "Yes",
  "100%", "$1.25M", "Jan 5, 2027"), OCR clean-up (`grace.hughes @x.com`, `CO.`,
  `_Los Angeles`, `S12,500`), and **entity matching** for names: legal suffixes and generic words
  ("Holdings", "Group") are dropped, and two names are the same entity when one name's tokens are a
  subset of the other's or the overlap is ≥ 75%.

| variant | split | field F1 | crit. F1 | review rate | silent crit. err. | conflict P / R | SOV LLM fallbacks |
|---|---|---|---|---|---|---|---|
| v2 (no checks) | dev | 98.0 | 97.7 | 0.0 | **40.0** | – | 13 |
| v3a raw checks | dev | 98.0 | 97.7 | 95.0 | 3.8 | 26.7 / 82.0 | 13 |
| v3 + normalization | dev | **99.2** | **99.7** | **35.0** | 1.2 | **88.9** / 82.0 | 8 |
| v2 (no checks) | test | 94.0 | 94.8 | 0.0 | **67.5** | – | 8 |
| v3a raw checks | test | 94.0 | 94.8 | 72.5 | 25.0 | 23.1 / 45.0 | 8 |
| v3 + normalization | test | **96.1** | **98.9** | **25.0** | 27.5 | **90.9** / 50.0 | 5 |

All offline. Template C (test) goes from 82.6 to 84.5. The decision model calls still abstain.

**What the numbers say:**
1. **v2 fails silently.** 40% of dev and 67.5% of test submissions had a wrong or missing
   critical field and nothing flagged them. This is the main failure the project has to fix.
2. **Checks without normalization are useless in practice.** They flagged 95% of dev submissions,
   and 73% of the flags were false alarms ("ACME HOLDINGS" vs "Acme Logistics LLC",
   "Harbor Point" vs "Harbor Point Logistics LLC"). An underwriter would learn to
   ignore that queue.
3. **Normalization made the flags trustworthy.** Conflict precision went from 26.7% to 88.9% and review rate
   from 95% to 35%. F1 improved because synonyms now parse, and SOV reconciliation failures (and so
   LLM fallback calls) fell by a third.
4. **Most remaining "false positive" conflicts are real.** On dev, 15 of the 20 non-planted
   conflicts were OCR misreads that the cross-check *caught* (a broken email address, `CO.`, a
   dropped SOV row on a scan detected through the stated-total check). The OCR clean-up fixed the
   systematic ones. The rest is the review queue doing its job.

**Still missing (and why):**
* Test conflict recall is 50%. Template-C applications don't parse offline, so there is no application
  value to compare against the SOV. Email-vs-application date conflicts need the
  email LLM call, which abstains offline (5 of 9 missed dev conflicts). PENDING a live run.
* Two planted name conflicts are missed *by design* of the subset rule.
  "Ironwood Logistics Distribution Inc." contains every token of "Ironwood Logistics LLC". The subset rule is what
  lets the email's "Harbor Point" match, so I kept it and listed the miss as a known limitation.
* Test silent-error rate is still 27.5%. Those are mostly *missing* critical fields (template C), which
  nothing flags yet. That is 4d.

---

## Stage 4d: Confidence scoring and review routing

**What:** `submitiq/confidence.py` scores every field:

`confidence = prior(extractor) × OCR line confidence`. Then:
* **Boost** when an independent reading agrees (another document or extractor; noisy-OR) and when the
  field passed a reconciliation check (SOV totals, row sums, loss-year totals).
* **Penalties:**
  * a different extractor read something else from the *same* document → ×0.5
  * the field failed a reconciliation check → ×0.5 and `invalid`
  * an implausible value (roof older than the building, PPC outside 1–10, a 9-digit
    "phone", "unsprinklered" with sprinkler % > 0, loss date outside its policy year, bad email/FEIN/ZIP) → ×0.3 and `invalid`
  * an LLM value whose evidence quote can't be found in the document → ×0.6
* Required fields the rules need (NAICS, and construction / year built / PPC / TIV per location, plus named insured,
  effective date, total TIV) that no document supplied are added as `missing`.

**Routing rule:** review if any *critical* field is flagged, or any field anywhere is `conflict` or `invalid`.
Low-confidence non-critical fields (a website, an OCR'd contact phone) are highlighted in the
UI but don't block. Infrastructure failures (model down, replay miss) are counted as `degraded`
and go to a retry queue, not to underwriters.

**Tuning (dev only, `scripts/tune_routing.py`):** I swept the threshold (0.6–0.9) and the OCR-confidence exponent (1 vs 2).
Silent critical errors were 0 on dev for every setting. Review rate was flat at 42.5% for thresholds
≤ 0.80 with exponent 1 and rose quickly above that. I chose threshold 0.80 and exponent 1, the most conservative setting
on the flat part. Squaring OCR confidence pushed correct OCR'd loss-run premiums into the queue
for no gain.

| variant | split | field F1 | review rate | silent crit. err. | wrong values stated → flagged | flag precision |
|---|---|---|---|---|---|---|
| v3 | dev | 99.2 | 35.0 | 1.2 | – | – |
| **v4** | dev | 99.2 | **42.5** | **0.0** | 4 → 4 (100%) | 16.7 |
| v3 | test | 96.1 | 25.0 | 27.5 | – | – |
| **v4** | test | 96.1 | **57.5** | **0.0** | 2 → 1 (50%) | 49.2 |

F1 doesn't change by design: routing never edits values.

**Reading it:**
* The point of this step: on test, **27.5% → 0%** of submissions carry a wrong or missing critical
  field without being routed. That costs review volume (25% → 57.5% on test). Most of the increase is
  template-C packages whose application fields are missing offline, and those *should* go to a person
  until the LLM path is measured. On the A/B-only dev split the cost is 35% → 42.5%.
* Flag precision looks low (16.7% dev). The metric only counts a flag as "right" when the value is
  wrong, but most flags here point at real business issues with correct values: the planted conflicts (stale
  application TIV, year built) and genuinely missing information that has to go back to the broker.
* **One silent wrong value remains on test:** an OCR'd contact email `jsiiva@…` (truth `jsilva@…`)
  scored 0.816, just above the threshold. It's a non-critical field, so I left the threshold alone. Catching it needs a threshold above 0.816, and 0.85 costs
  +5 points of review rate on dev (42.5% → 47.5%) to catch one contact email.

**What broke:**
1. Squared OCR confidence was too harsh (see tuning).
2. The SOV row check (building + contents + BI = TIV) failed on *honest* rows: brokers print `$1.12M` for
   1,125,000. I relaxed the tolerance to 0.5% (the precision "$x.xxM" implies). The row-level validation flags on
   dev went from 9 to 3 (scans with real misreads).
3. An OCR'd producer name ("Danie! Kim") was *caught* (a conflict with the email header) but not *fixed*.
   The application wins for broker fields by rule. Choosing by confidence for fields with no
   business source-of-truth rule is in "what I'd do next".

---

## Stage 5: Deterministic appetite rules and the cited triage summary

**What:**
* `submitiq/rules_engine.py` applies `rules/appetite.yaml` (class lists, location/account TIV, loss
  ratio, frequency, large loss, frame + PPC, PPC 10, hurricane and earthquake ZIP zones,
  sprinklers, building and roof age, missing information). Every triggered rule returns the field
  paths it used. If any of those fields is flagged for review, the reason says so ("depends on
  fields under review: …"). This replaces the LLM decision call.
* **Two implementations, cross-checked:** the generator's labeler (`data/synth/labels.py`) and the engine
  are written separately. `tests/test_rules_engine.py` asserts they agree on outcome **and**
  triggered rule IDs on all 120 ground-truth records, plus boundary tests (60% loss ratio exactly is not
  > 60%, $25,000,000 TIV is not > $25M, and so on).
* `submitiq/summary.py`: the LLM writes only the narrative, from `path = value` facts, the rules decision and the flags.
  `validate_summary` rejects any text that cites a field that doesn't exist or is empty, or that
  contains a number not supported by a cited field or a rule message. On rejection or model failure, a
  deterministic template summary (same citations) is used.

| variant | split | decision acc. | declines → accept | abstained | summary citation validity |
|---|---|---|---|---|---|
| v4 (LLM decides) | dev / test (offline) | 0.0 / 0.0 | 0 | 80 / 40 | – |
| v4 (LLM decides) | with Claude | **PENDING** | PENDING | | |
| **v5 (rules)** | dev (offline) | **100.0** | 0 | 0 | 100.0 (template) |
| **v5 (rules)** | test (offline) | **87.5** | 0 | 0 | 100.0 (template) |

The LLM call count drops by one per submission (no decision call). The LLM narrative itself is PENDING. Offline,
every summary is the template version.

**Reading it:**
* All 5 test decision errors are **template-C** packages (accept → refer ×4, decline → refer ×1). The NAICS
  code can't be read offline, so `MISSING_INFO` refers them. That is the right *failure direction*: an
  unknown class goes back to a human, never to an automatic accept. 0 of 33 declines were predicted accept on
  either split.
* With rules, decision quality becomes a pure function of extraction quality on the critical fields.
  This is why Stage 4 measured critical-field F1 and the silent-error rate separately.

**What broke:** my own citation validator rejected 100% of my own template summaries at first:
1. The number regex's `\s*` swallowed the newline after a number (`"332710\n"` ≠ `"332710"`).
2. The template cited fields that were empty (`[locations[2].protection_class]` on a missing PPC).
3. Claim dates were printed without citing `date_of_loss`.
4. Rule-message numbers kept a trailing comma (`2007,`).
5. Template-C packages fell back to the submission ID in the title (`SUB-0082`).

After the fixes, all 120 pass. I kept the validator strict. Loosening it to make the template pass would also have
let an LLM narrative with an invented number through.
