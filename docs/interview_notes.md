# Interview notes

How to talk about SubmitIQ: what I'd say, what I'd be asked, and where the evidence lives in the repo.

## The 60-second version

"A commercial underwriter spends most of the first hour on a broker submission re-keying data. I built the intake
agent: it reads the email, application, loss runs and SOV, produces a cited 70-field record, a deterministic appetite
decision and a triage note. I started with the domain notes and a synthetic dataset with realistic mess, then the eval
harness, and only then the system. I improved it one measured step at a time. The headline isn't F1. It's that the
share of submissions carrying a wrong or missing critical field *without being routed to a human* went from 67.5% to 0% on
the held-out test set, and that zero declines were ever auto-accepted. I didn't have API access while building, so I made the
system fully runnable offline with a replay backend, and every model-dependent number is marked pending, with a one-command
script to produce it."

## The 5 hardest bugs

1. **OCR never finished: CPU oversubscription.** The first full eval ran 8 worker processes, each calling Tesseract, whose
   OpenMP pool spawns a thread per core. On a 4-core box the load average hit 32, and single pages burned more than 5 CPU-minutes.
   *Diagnosis:* `ps` showed tesseract processes at 49% CPU each for minutes. Throughput was the problem; no page was simply slow.
   *Fix:* `OMP_THREAD_LIMIT=1` per process, parallelism across documents only, and an OCR cache keyed by file hash
   that stores the original duration (so latency metrics stay honest). A full run dropped to 54 s cold.
   *Lesson:* nested parallelism.

2. **A dataset bug that looked like a parser bug.** The per-field error breakdown showed `locations[1].*` missing in
   about 15% of PDF SOVs, and it was always location 1. pdfplumber was returning words like `"NAo.ddress"`: my *generator*
   printed a long header ("Location No.") that overflowed into the next column, and the extractor interleaved the
   overlapping characters, so the location-number column vanished. *Fix:* the renderer never lets a header overprint
   its neighbour. I regenerated the data and re-ran every variant. *Lesson:* look at errors per field, and suspect the
   data as much as the model. I logged it as a dataset change in the experiment log rather than hiding it.

3. **Fuzzy matching silently shifted two columns.** I added fuzzy header matching to survive OCR slips ("Bidg Limit").
   It also matched "Sprinklered %" to the two-word synonym "sprinkler %", which consumed the next header and moved every
   value one column right. Nothing crashed. It was only visible as a drop in two fields' F1. *Fix:* exact phrases first,
   fuzzy only as a fallback, plus a regression test. *Lesson:* every "tolerance" feature needs a test for what it must *not* match.

4. **My routing metrics were lying (infrastructure failures vs data quality).** Offline, every LLM call is a replay
   miss. I had routed "model unavailable" to human review, so the review rate was 100% for every variant and
   the silent-error metric was trivially 0. Routing logic I couldn't measure looked perfect. *Fix:* `degraded_reasons`
   (retry queue, counted separately, and an alarm on AWS) vs `needs_review` (field-level data quality only). Immediately the
   real problem showed: the v2 pipeline had **40% (dev) / 67.5% (test) silent critical errors**. *Lesson:* make sure
   a metric *can* fail before trusting it. The harness self-test (oracle = 1.0, empty = 0) exists for the same reason.

5. **The citation validator rejected my own summaries, then my own hand-written fixture.** The validator says every number in
   a summary must trace to a cited field. My deterministic template failed on 100% of packages: `\s*` in the number regex
   swallowed newlines, the template cited empty fields, and trailing commas broke tokens. After those fixes, my *hand-written*
   demo narrative failed because I wrote "$56.75M" for 56,745,000. *Fix:* compare numbers numerically within 0.5%
   instead of as strings. *Lesson:* test a validator on true positives, not just on the bad cases it should catch. A validator that
   rejects everything is as useless as one that accepts everything.

Honourable mentions: JSON round-trips turned dates into strings between Lambda steps, so I added `runstate._retype`
(caught by the test that a step-by-step run equals a local run). The SOV row-sum check flagged honest rows, because brokers print
"$1.12M" for 1,125,000. And "false positive" conflicts that turned out to be real OCR errors (`grace.hughes @x.com`).

## Key design trade-offs

### Rules vs LLM for the decision
* **Rules decide; the LLM explains.** An appetite decision has to be reproducible (same input, same output),
  auditable (which rule, which field), and changeable by the business (edit YAML, run the eval gate). An LLM
  decision is none of those, and in a regulated line, "the model thought so" is not a reason you can give a broker or a regulator.
* The engine is implemented **twice** (the generator's labeler and the engine) and tested for agreement on all 120 records,
  so a bug in one can't hide inside circular labels.
* With rules, decision quality is a pure function of critical-field extraction quality. That's why the harness reports
  critical-field F1 and the silent-error rate separately from overall F1.
* Where the LLM *does* help is the long tail of extraction (unseen layouts, free text, damaged scans) and the
  narrative. The narrative is constrained: cite or be rejected, with a deterministic fallback.

### Where human review sits
* **Field level, not document level.** The reviewer sees *which* value is uncertain, why, the source snippet, and the
  alternative reading, so they don't have to re-read the package.
* **Route on critical fields + any conflict/invalid.** A low-confidence website shouldn't block a quote. A
  low-confidence protection class must. Tuned on dev only. The threshold sweep showed review rate flat up to
  0.80 and then rising fast, and silent errors were already 0, so I took the conservative end of the flat part.
* **Review is not the retry queue.** Model outages degrade to "parsers + rules + template summary", flagged, alarmed.
* **Corrections become eval cases** (`scripts/export_corrections.py` → `--split reviewed`), so the queue also produces test data.
* Accepted cost: the review rate went *up* (25% → 57.5% on test) when I made failures non-silent. I'd rather show an underwriter
  more flagged fields than let one wrong TIV through, but that trade-off is the client's to make with real data.

### Cost vs accuracy
* **Deterministic first, LLM where it earns its cost.** The table parsers vouch for their own output through reconciliation
  checks. The LLM only runs on a schedule when a check fails (3 fallbacks in about 260 documents offline). That is
  cheaper and also gives an independent second reading for confidence.
* **Per-document calls vs one call.** The baseline sends everything in one prompt: simple, but no citations, and one
  bad page affects everything. Per-document calls with strict schemas cost more calls but give page-level evidence and
  isolate failures.
* Model tokens are about 95% of the estimated AWS bill (`docs/deploy.md`). The levers, in order: avoid calls, prompt caching,
  a cheaper model for email/summary, batch. Each one has to be measured with `make eval-live` against the same gate.
  I didn't downgrade the model on a hunch.

### Other decisions I'd defend
* **Synthetic data with a held-out layout.** The parser is overfit by construction (I wrote both sides). Template C is
  test-only, so the overfitting is *measured* (84.5 vs about 99 F1) instead of hidden.
* **Replay keyed by document hash, not extracted text.** OCR output can drift with Tesseract versions. Keying on file
  bytes keeps recorded answers valid in CI. The trade-off is that a replayed answer may be for slightly different text.
* **Source-of-truth rules over "highest confidence wins"** for COPE (SOV) and entity facts (application), because those
  rules are what underwriters already apply. Confidence-based choice is next for fields with no business rule (broker contacts).
* **Step Functions with state in S3, container Lambdas.** The 256 KB payload limit means only pointers travel. Tesseract
  needs a binary, so container images it is. Each Lambda runs the *same* step function the evals measure, and a test proves
  serialization doesn't change the result.

## What I'd do next

1. **Run the live evals** (`make eval-live`) and fill the PENDING columns. Compare Opus vs Sonnet vs Haiku *per document type*:
   the email and summary likely don't need the largest model.
2. **Calibrate confidence** on real model output (reliability curve per extractor). Learn the priors from reviewer corrections
   instead of hand-setting them.
3. **Confidence-based source selection** for fields without a business rule (the OCR'd "Danie! Kim" was caught, not fixed).
4. **Real documents** (with the client's permission), plus active learning from the review queue. Add prompt-injection cases
   ("ignore the losses above") to the eval set, since broker emails are untrusted input.
5. Prompt caching for the static system prompt and schemas. Bedrock batch inference for non-urgent queues.
6. Clearance (duplicate submissions across brokers), multi-email threads and ZIP attachments.
7. Deploy the review UI on AWS behind SSO, in a VPC with endpoints. Measure human handling time in a pilot, because the
   "≈5–7 min" in the README is an assumption.

## Questions to expect

* *"Your F1 is 99%. Isn't that just your parser matching your generator?"* On dev, largely yes, and I say so. Look at template C
  and the silent-error rate, and at what's PENDING.
* *"Why not let Claude do everything?"* Measurability, cost, auditability, and a second independent reading. The LLM-only baseline is
  in the eval table for exactly that comparison once it runs live.
* *"What happens when Bedrock is down?"* Steps retry with backoff, then degrade: parsers plus rules plus a template summary, flagged, and the
  ModelDegraded alarm fires. Nothing is silently dropped: failed executions write `status=failed`.
* *"How do you know a change didn't break something?"* The CI gate on all 120 packages, 2-point tolerance, plus 51 unit tests,
  including engine-vs-labeler agreement and local-vs-Lambda equivalence.
