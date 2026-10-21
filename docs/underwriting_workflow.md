# Commercial Property Submission Triage: How It Works Today

This note covers the "learn the client's job" part of the project. It describes how a
commercial P&C underwriting team triages a new-business property submission from a
broker *before* any automation, which data actually drives the decision, and what
the written appetite guidelines look like. I wrote it from public knowledge of ACORD
forms and commercial-property underwriting practice. Every time estimate below is an
**assumption to validate with the client's underwriters in discovery**. None of them
is a measurement.

---

## 1. Who is involved

| Role | What they do in intake |
|---|---|
| **Retail broker / producer** | Collects data from the insured and sends the "submission package" to several carriers (or to a wholesaler) by email. |
| **Underwriting assistant / technician** | Opens the email, saves attachments to the policy admin or imaging system, keys the core data into the submission system, and chases missing items. |
| **Underwriter** | Reads the package, decides whether the risk is *in appetite*, and decides whether to quote, refer to a senior underwriter, or decline. |
| **Senior / referral underwriter** | Approves risks outside the underwriter's authority (large TIV, poor loss history, CAT exposure). |

## 2. What a submission package contains

| Document | Typical format | What it tells the underwriter |
|---|---|---|
| **Broker email** | Free text, sometimes with a short cover note | Which insured, which lines, requested effective date, when the quote is needed, broker contact, anything unusual ("renewal is due in 3 weeks", "incumbent non-renewed"). |
| **ACORD 125** (Commercial Insurance Application) | PDF, often filled in by the agency management system, sometimes scanned after signing | Applicant legal name, DBA, FEIN, entity type, mailing address, nature of business / NAICS, years in business, revenue, employees, policy dates, prior carrier, producer/agency details. |
| **ACORD 140** (Property Section) | PDF, attached to the 125 | Per-premises building data: construction, year built, stories, square footage, sprinklers, protection class, roof, alarms, plus requested limits (building, business personal property, business income), deductible, valuation, coinsurance, cause-of-loss form. For multi-location accounts it often just says "see attached SOV". |
| **Loss runs** | PDF from each prior carrier, frequently a scan or a print-to-PDF, 3–5 policy years | Claims by policy period: date of loss, cause, paid, reserve, incurred, open/closed status, and often earned premium. Valued "as of" a date. |
| **Statement of Values (SOV)** | Excel (most common) or PDF | One row per location/building: address, occupancy, construction, year built, square footage, sprinklers, protection class, building / contents / BI values, TIV. For multi-location accounts this is the system of record for location data. |

> The real ACORD forms are copyrighted. This project uses **look-alike** synthetic
> forms that ask for the same information under similar labels. It does not
> reproduce any actual ACORD layout.

## 3. The manual triage workflow today

| # | Step | What happens | Time (assumption) | Pain points |
|---|---|---|---|---|
| 1 | **Receive and log** | Assistant opens the shared submissions mailbox, creates a submission record, saves attachments. | 5–10 min | Duplicate submissions from several brokers; attachments named `scan0012.pdf`; package split across several emails. |
| 2 | **Clearance** | Check the insured isn't already quoted or bound through another broker (name/address search). | 5–10 min | Name variants ("Acme LLC" vs "ACME Holdings") cause both false matches and missed matches. |
| 3 | **Classify documents** | Work out which attachment is the application, the loss run, and the SOV. | 2–5 min | Combined PDFs; loss runs from 2–3 different carriers; screenshots of spreadsheets. |
| 4 | **Key core data** | Re-type insured, address, class, dates, limits, and location COPE data into the underwriting workbench. | 20–45 min (more for a big SOV) | The slowest and most error-prone step. Keying errors carry straight into rating. Scanned/rotated pages are hard to read. |
| 5 | **Reconcile across documents** | Compare TIV on the application vs the SOV, insured name on the loss runs vs the application, dates in the email vs the form. | 10–20 min | Often skipped under time pressure. A stale application TIV is one of the most common discrepancies. |
| 6 | **Loss analysis** | Total incurred by year, compute the 5-year loss ratio against earned premium, spot large or open claims, check the frequency trend. | 10–20 min | Loss-run tables split across pages; reserves vs paid; currency formatting. |
| 7 | **Appetite check** | Compare against the written underwriting guidelines (class, TIV, construction/protection, CAT zone, losses). | 5–15 min | Guidelines live in a PDF manual. Different underwriters apply them inconsistently. |
| 8 | **Decision and note** | Accept to quote, refer to senior UW, or decline, with a short file note explaining why. | 5–10 min | File notes vary in quality; reasons are hard to audit later. |
| 9 | **Chase missing info** | Email the broker for missing items (FEIN, protection class, roof year, signed application). | 5 min + wait | Each round trip adds days; the broker may place the risk elsewhere. |

**Assumed total: roughly 70–140 minutes of hands-on time per submission**, much
longer elapsed time. Public industry commentary often says that a large share of
submissions are never quoted, and that underwriters spend a large share of their
time on intake and data entry rather than on risk judgment. That is the business
case: the cost is in steps 1–7, and the scarce resource is underwriter attention.

### What automation should and should not do

* **Automate:** steps 1–7: reading, keying, reconciling, loss math, and a first-pass appetite check, with a citation for every value.
* **Keep human:** the final judgment on referrals, anything the system is unsure about, and any decision that leaves a binding quote. The system **recommends**; the underwriter decides.
* **Never:** silently guess. A wrong TIV or construction class mis-prices the risk. A missed open claim is a coverage problem. Being uncertain is acceptable, as long as the system says so.

## 4. Fields that matter (and why)

The output schema groups fields the way an underwriter reads them. "Critical" fields
drive the appetite decision or pricing directly. If a critical field is missing or
low-confidence, the submission must go to human review.

| Group | Fields | Critical? | Why it matters |
|---|---|---|---|
| **Insured** | legal name, DBA, FEIN, entity type, mailing address, business description, NAICS code, years in business, revenue, employees, website, contact | name, NAICS | Clearance, class eligibility, financial size. |
| **Broker** | agency, producer name, email, phone | – | Who to send the quote or decline to. |
| **Policy** | effective / expiration date, new vs renewal, prior carrier, quote-needed-by date, received date | effective date | Workload prioritisation; roof-age and loss-run currency are measured against the effective date. |
| **Coverage** | building limit, BPP limit, BI limit, deductible, valuation (RC/ACV), coinsurance, cause-of-loss form, flood / earthquake requested | – | What is being asked for; used for pricing later. |
| **Locations (COPE)** | address, occupancy, **C**onstruction (ISO class 1–6), year built, stories, square feet, sprinklered / % sprinklered, **P**rotection class (ISO PPC 1–10), roof type / year, alarm, building / contents / BI values, TIV; **E**xposure via address (CAT zone) | construction, year built, protection class, TIV | COPE is the core of property underwriting. |
| **Loss history** | per claim: number, policy year, date of loss, cause, status, paid, reserve, incurred; per year: carrier, earned premium, claim count, total incurred | yes | Frequency, severity, open reserves, loss ratio. |
| **Totals** | total TIV, location count, 5-year incurred, 5-year premium | total TIV | Authority limits and the loss ratio. |

### ISO construction classes (used in the schema)

| ISO | Name | Notes |
|---|---|---|
| 1 | Frame | Combustible walls and roof (wood). The worst fire and wind performance. |
| 2 | Joisted Masonry (JM) | Masonry walls, combustible (wood-joisted) floors and roof. |
| 3 | Non-Combustible (NC) | Metal walls/roof on a metal frame. Doesn't burn, but weakens in fire. |
| 4 | Masonry Non-Combustible (MNC) | Masonry walls with a non-combustible roof deck. |
| 5 | Modified Fire Resistive (MFR) | Fire-resistive materials, rated below 2 hours. |
| 6 | Fire Resistive (FR) | 2+ hour rated; typical of high-rise concrete. |

### Protection class (ISO PPC)

PPC runs 1 (best municipal fire protection) to 10 (no recognised protection,
for example more than 5 road miles from a fire station). Split classes such as
"8B" exist in practice. The synthetic data uses whole numbers only.

## 5. Source-of-truth rules when documents disagree

Underwriters already apply these rules informally. The system makes them explicit
and still flags every disagreement for a person to see:

1. **Location-level values (COPE, building/contents/BI values, TIV): the SOV wins.** The application is often filled from an older SOV.
2. **Entity-level facts (legal name, FEIN, dates, limits requested): the signed application wins** over the email.
3. **Loss history: the carrier loss run wins** over anything the broker or applicant states.
4. A disagreement is **never resolved silently**. The chosen value is recorded together with the losing value and its source, and the field goes to the review queue.

## 6. Appetite guidelines (the "written rules")

The client's (synthetic) guidelines are encoded as data in `rules/appetite.yaml`
and applied by a deterministic rules engine. Outcomes have a strict order:
**decline > refer > accept**. The most severe triggered rule wins, and every
triggered rule is listed as a reason.

| Rule | Trigger | Outcome |
|---|---|---|
| Prohibited class | NAICS in the prohibited list (explosives, recycling/salvage, drinking places, …) | Decline |
| Referral class | NAICS in the referral list (habitational, hotels, restaurants, chemical mfg, …) | Refer |
| Unknown class | NAICS not on any list | Refer |
| Location TIV | Any location > $25M | Refer. Over $50M: Decline |
| Account TIV | Total > $100M | Refer |
| Loss ratio (5-yr incurred / earned premium) | > 60% | Refer. Over 100%: Decline |
| Loss frequency | ≥ 5 claims in 5 years | Refer |
| Large loss | Any single claim incurred > $250K | Refer |
| Construction + protection | Frame with PPC 9–10 | Decline |
| Poor protection | PPC 10 (any construction) | Refer |
| Hurricane zone | Tier-1 coastal ZIP prefixes: Frame → Decline; any location TIV > $5M → Refer | Decline / Refer |
| Earthquake zone | CA EQ ZIP prefixes: Joisted Masonry built before 1980 → Refer | Refer |
| Sprinklers | Location TIV > $10M and not sprinklered | Refer |
| Building age | Year built before 1950 | Refer |
| Roof age | Roof older than 25 years at the effective date | Refer |
| Missing information | Any critical field missing (NAICS, construction, year built, protection class, TIV) | Refer (back to broker) |

The rules decide the **appetite outcome**. The LLM never decides it. The LLM only
writes the narrative triage summary, and that summary must cite the fields it uses.
See `docs/interview_notes.md` for why I made this split.

## 7. Success measures for the client

* **Hands-on triage time** per submission (target: under 15 minutes of human time, spent on reviewing the flagged fields only).
* **Field accuracy** on the critical fields (precision matters more than recall: a blank is better than a wrong value).
* **Silent-error rate:** submissions that contain an extraction error *and* were not routed to review. This should go toward zero.
* **Decision agreement** with the written guidelines, plus zero "should have declined but accepted" outcomes.
* **Time-to-first-response** to the broker (quote, referral, or decline with reasons).
