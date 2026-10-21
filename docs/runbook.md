# SubmitIQ Operator Runbook

For underwriting assistants, underwriters and operations staff who use SubmitIQ every day. No programming needed.

## What SubmitIQ does

A broker sends a submission package: an email, an application, loss runs from prior insurers, and a
schedule of locations (the SOV). SubmitIQ reads all of it, fills in the submission record, checks it against the
appetite guidelines, and writes a one-page summary. It **recommends** accept, refer or decline. A person makes the final call.

Every value on screen shows **where it came from** (document and page, with the quoted text) and **how sure the system is**
(a confidence bar from 0 to 1).

## Submission statuses

| Status | What it means | What you do |
|---|---|---|
| **needs review** | At least one important value is missing, uncertain, contradicts another document, or failed a check. | Open it, work through the highlighted fields (see below), then **Approve**. |
| **auto cleared** | All important values were read cleanly and agree across documents. | Spot-check the summary and the recommendation. Nothing is blocked. |
| **approved** | A person reviewed it. The record and recommendation are final. | Nothing. Corrections you made are saved and used to test future versions. |
| **failed** | The system could not process the package at all (for example, a corrupt file). | Ask the broker to resend. If it keeps happening, tell the support team (alarm "WorkflowFailures"). |

The review queue lists "needs review" submissions with the most flagged fields first.

## The review page

Highlighted rows at the top of the field table need your attention. Each has a status:

| Field status | Plain meaning | What to do |
|---|---|---|
| **missing** | The guidelines need this value (for example protection class, year built, NAICS) and no document has it. | Ask the broker for it, or find it in the documents yourself. Type it in and press **Save**. If it truly isn't available, leave it blank: the recommendation will stay **refer**. |
| **conflict** | Two documents disagree (for example, the application says TIV $52.0M and the SOV adds up to $56.7M). The system kept the value from the more reliable source and shows the other one underneath as "alt". | Check which is current, usually with the broker. Correct the value if needed. |
| **invalid** | The value fails a check: numbers that don't add up, a roof older than its building, a 9-digit phone number, an email with a space in it. Often a scanning error. | Open the source document (click its name) and type the right value. |
| **low confidence** | The value was read from a poor scan, or two readers inside the system disagree. | Compare with the document snippet shown. Correct it, or leave it as is if it is right. |

**Save** on a row fixes that field immediately: the recommendation and summary update straight away.
**Approve submission** confirms *every remaining highlighted value* as correct. Don't press it until you have looked at each one.

Critical fields are marked *critical*. They drive the recommendation (class, construction, year built, protection
class, sprinklers, TIV, losses, effective date).

## Reading the recommendation

* **decline**: a hard guideline is broken (prohibited class; frame building in a hurricane zone; frame building with
  very poor fire protection; loss ratio over 100%; a location over $50M).
* **refer**: needs a senior underwriter or more information (refer classes, large values, poor loss history, old
  buildings or roofs, earthquake or hurricane exposure, unsprinklered large locations, or missing information).
* **accept**: inside appetite, so go ahead and quote.

Each reason lists the fields it depends on. If a reason says *"depends on fields under review"*, the recommendation can
change once you fix those fields.

The summary on the right was written from the record. Every fact links to its field (blue tags). If the AI-written
summary fails its own fact-check, a standard template summary is shown instead. The page says which one you're looking at.

## Common situations

| You see | Likely cause | What to do |
|---|---|---|
| Insured name is blank, and many fields are missing | An application layout the system doesn't know (a wholesaler's own form) and the AI reader was unavailable | Key the main fields from the application. Tell support the form name so it can be added to the test set. |
| A name **conflict** between the application and a loss run | The loss run may belong to a different company (sister or parent) | Confirm with the broker that the loss history is for this insured. |
| Total TIV **conflict** | The application was filled from an older SOV | Ask the broker which schedule is current. |
| Location values marked **invalid** after a scanned SOV | A row was misread or dropped (the total no longer matches) | Compare row by row with the scan. Fix or add values. |
| "Degraded: LLM extraction unavailable" at the top | The AI service was down or slow. SubmitIQ still read what it could with its standard readers. | Review as usual. Expect more missing fields. If many arrive like this, support gets the *ModelDegraded* alarm. |
| Email date and application effective date disagree | Broker typo, or the dates changed | The application value is used. Confirm with the broker. |
| A document shows the wrong type (for example the SOV listed as "other") | Unusual file | Tell support. The fields from that document will be missing. |

## Alarms (for the support team)

| Alarm | Meaning | First steps |
|---|---|---|
| WorkflowFailures | A package could not be processed | Step Functions console → failed execution → which step failed. The submission is marked *failed* in the table. |
| ModelDegraded | 5+ packages in 15 minutes ran without the AI service | Check the Bedrock service health page and model quotas. Processing continues in degraded mode. |
| ReviewRateHigh | More than 80% of packages need review for 3 hours | A new broker form, scan-quality issue or a regression. Compare with the dashboard and tell engineering. |

## What not to do

* Don't approve a submission just to clear the queue. Approval confirms every highlighted value.
* Don't edit the appetite guidelines in the system. They live in `rules/appetite.yaml` and are owned by underwriting
  leadership. Every change is tested against the evaluation set before release.
* Don't upload packages for a real insured into a test environment.
