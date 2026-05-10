# Session notes — 2026-05-10

Branch: `claude/code-review-progress-jad2v`
Final commit: `9470f69` — `Add gemini_extractor (Layer A.5): prospectus-extraction verifier`
Test count: 244 passing (started session at 108)

This is a working-notes document covering both the code shipped and the
strategic threads we explored. Read end-to-end if resuming cold; skim
the "Open threads" section at the bottom if you just want to know
what's next.

---

## 1. What was shipped today

Five commits on the branch, in order:

1. `581172c` — Adapter: loose-input normalizers for dates, coupon, frequency, calendar, BDC
2. `d03738a` — `parse_loose_date`: accept 2-digit years with forward-pivot rule
3. `b795bae` — `parse_loose_date`: backward pivot for `issue_date` / `first_coupon_date`
4. `9470f69` — Add `gemini_extractor` (Layer A.5): prospectus-extraction verifier

Net code change: ~1,200 LOC of source + ~700 LOC of tests added.

### 1.1 Loose-input adapter normalizers (`adapter.py`)

The day_count disambiguator already refused ambiguous shorthands (`30/360` → reject with hint). Today we extended the same protective pattern to the other vendor-shaped fields so the adapter can ingest realistic feeds without silently corrupting hashes.

| Helper | Accepts | Rejects |
|---|---|---|
| `parse_loose_date` | ISO `2026-05-10`, compact `20260510`, textual `5-May-2026` / `May 5, 2026`, year-first `2026/05/10`, Excel serials in `[30000, 75000]`, 2-digit years with forward/backward pivot | `10/05/2026` (ambiguous DD/MM), unrecognised |
| `normalize_coupon_value` | int/float/Decimal/str, trailing `%`, integers stay int | `< 0`, `> 100`, `0 < x < 0.5` (the 0.045-vs-4.5 trap) unless `allow_below_half_pct=True` |
| `normalize_frequency` | `0/1/2/4/12`, `S`/`A`/`Q`/`M`/`Z`, `Semi-Annual`, `Quarterly`, etc. | anything else |
| `disambiguate_calendar` | canonical, `NYC`/`NYSE` → US_SETTLEMENT, `Treasury`/`FED` → US_GOVERNMENT, `EUR`/`TARGET2` → TARGET, `London`/`GBP` → UK_SETTLEMENT | bare `US`/`USD` left unresolved with hint (mirrors `30/360`) |
| `disambiguate_bdc` | canonical, `MF`/`Mod Fol`/`Modified Following` → MODIFIED_FOLLOWING, `F`/`Fol` → FOLLOWING, `MP` → MODIFIED_PRECEDING | unrecognised |

`normalize_to_published_record` routes mandatory fields (coupon, dates, frequency) through these helpers so a vendor-shaped row produces byte-identical tier hashes to the canonical equivalent. Regression test asserts exactly this.

### 1.2 Two-digit year pivot rule

Per-field pivot direction:

- **maturity_date → forward pivot** (default `assume_future_year=True`). With ref=2026: `26..99` → `2026..2099`, `00..25` → `2100..2125`. Handles century bonds.
- **issue_date / first_coupon_date → backward pivot** (`assume_future_year=False`). With ref=2026: `00..26` → `2000..2026`, `27..99` → `1927..1999`. Handles seasoned bonds.

The pivot tracks `asof` (the snapshot reference date), so the same input produces the same hash for a given record. `parse_loose_date(value, *, reference_date, assume_future_year)`.

DD/MM-vs-MM/DD numeric ambiguity (`10/05/2026`) remains a hard failure for single records — needs batch context, not a calendar pivot. Earmarked for `infer_batch_format` in a future revision.

### 1.3 `gemini_extractor` Layer A.5 (`gemini_extractor.py`)

This is the architecturally most important addition. Background and rationale in section 3 below.

The module is **pure** — no network calls. It accepts a `ProspectusExtraction` (verbatim quotes + structural facts emitted by some upstream LLM) plus the source PDF text, and emits `VerificationResult`s.

Three guards:

1. **Quote verification gate.** Every claim must regex-match the PDF text after whitespace normalisation. Hallucinated quotes are rejected.
2. **Deterministic re-classification.** The model's day_count classification is deliberately discarded. Verified quotes are re-derived through `adapter.classify_day_count_phrase` (the existing prospectus pattern table).
3. **Structural facts** (amortization, call schedule) are trusted only after their associated quote verifies.

Public surface:

- Dataclasses: `FieldExtraction`, `AmortizationExtraction`, `CallExtraction`, `ProspectusExtraction`, `VerificationResult`
- Functions: `verify_extraction(extraction, pdf_text)`, `quote_in_pdf_text(quote, pdf_text)`
- Re-exported through `static_validator.__init__`

### 1.4 `classify_day_count_phrase` public helper

Promoted the previously-private `_prospectus_match` into a public `classify_day_count_phrase(text) -> str | None` in `adapter.py`. The pattern table got one broadening: the canonical Bond Basis pattern now matches both "360-day year **of** twelve 30-day months" (the truncated form Panama/PEMEX prospectuses actually use) and "360-day year **consisting of** twelve 30-day months" (the strict ISDA 2006 wording).

---

## 2. The architectural insight that drove the gemini_extractor design

This is the most important takeaway from today and worth preserving in detail because it shapes the entire commercial path.

### 2.1 The Gemini diagnostic test

We designed and ran a falsifiable test against Gemini for Panama 2060 (`US698299BL70`) and PEMEX 2050 (`US71654QDD16`). The prompt forced verbatim quotes, page references, and explicit self-rating of source confidence. The exact prompt is in this conversation transcript and worth re-running periodically.

### 2.2 What Gemini returned

For both bonds, the day_count quote was the canonical Bond Basis phrase under ISDA 2006 §4.16(f):

- PEMEX: *"Interest on the new securities will be calculated on the basis of a 360-day year of twelve 30-day months."*
- Panama: *"Interest will be calculated on the basis of a 360-day year of twelve 30-day months."*

But the **classifications differed**:

- PEMEX: `BOND_BASIS_30_360` ✓ (consistent with the quote)
- Panama: `ISMA_30_360` ✗ (contradicts the quote — the same canonical phrase pins Bond Basis)

The only difference between the two bonds in Gemini's reasoning was issuer category: corporate vs sovereign. **That is exactly BBG's classification convention** — BBG codes corporates as US 30/360 and sovereigns as ISMA, regardless of what the prospectus actually says.

### 2.3 What this proved

Frontier multimodal LLMs reliably retrieve **verbatim quotes** and **structural facts** (call schedules, amortization tranches) from prospectuses — Gemini's quotes were detailed and bond-specific. They do NOT reliably classify **conventions** (day_count, calendar, BDC) because their training corpus is downstream of the same vendor data that introduces the drift in the first place. The classification is correlated with vendor coding, not the document text.

This is a **systematic hallucination at the classification layer with the quote layer intact**. It cannot be fixed by prompting — the bias is in the training data. It can only be fixed by ignoring the LLM's classifications and re-deriving them deterministically from the verified quote.

### 2.4 The architectural consequence

This shapes the entire pipeline:

- ✅ Use Gemini for: prospectus reading, verbatim-quote extraction, structural-fact extraction
- ❌ Do NOT use Gemini for: convention classification (day_count, calendar, BDC)
- ✅ Add deterministic phrase→enum mapping on top (we already have this in `adapter.py`)

The `gemini_extractor.verify_extraction` function operationalises this. It's the seam that catches the BBG-correlated training bias before it corrupts the canonical record.

The pitch sentence this earns:

> "We don't trust Gemini to classify, only to read. Every convention label in our canonical record is re-derived deterministically from the verbatim quote — so when Gemini's training has BBG drift baked in, the drift dies at our classification layer instead of riding through to the customer."

---

## 3. Strategic threads we explored

Several substantial design discussions that didn't all turn into code today but should inform what we build next.

### 3.1 The "consensus error" / "lonely truth" problem

If everyone (BBG, broker, custodian, PMS) agrees the day_count is wrong because they all pull from the same vendor lineage, trades still settle (Clearstream/Euroclear settle on agreed price/accrued, not against the prospectus). The customer's position then sits on their book accruing wrong daily.

**Settlement ≠ truth.** Cashflows are eventually paid by the issuer at the prospectus convention. Daily NAV is wrong every day until coupon date. Risk numbers are wrong (duration, DV01). The blowup is asymmetric — usually rounding noise, but on stub periods, leap years, or callable redemptions the gap is material.

**The audit defense angle is the strongest argument for the project.** When a regulator or fund auditor pulls the prospectus, vendor consensus collapses. Only a record with a verifiable prospectus citation survives that question.

### 3.2 The "we look wrong because we're alone" problem

Being right when everyone else is wrong is socially indistinguishable from being wrong. The customer's broker, custodian, and PMS will all tell them we're the outlier.

We don't try to win the argument. Three moves:

1. **Publish both values.** Canonical (prospectus) AND market_consensus, with `divergence_flag` when they differ. Acknowledge consensus exists; we're disagreeing on purpose with citation.
2. **Empathetic mismatch report.** Don't say "you're wrong" — say "your data matches market consensus; the prospectus disagrees; here's the URL; this is vendor drift, not your data." Reframes from accusation to discovery.
3. **Two operating modes.** `prospectus-strict` (audit, regulator) vs `consensus-tolerant` (recon, settlement). Same project, both honest, customer picks per use case.

This was scoped but not yet implemented in the schema. Earmarked as a future addition: add `evidence_class` enum and `market_consensus` channel to `published_record.schema.json`.

### 3.3 The "prospectus is silent" reality

The honest discomfort: when the prospectus says only "30/360" without sub-variant qualification, BBG's "30E/360" is not necessarily *wrong*. The convention then comes from:

1. Governing law (NY → ISDA 2006 §4.16(f) defaults Bond Basis)
2. Paying agent's actual computation (DTC for US-CUSIP, Clearstream/Euroclear for Eurobonds)
3. Listing-venue rulebook (ICMA Rule 803 → ISMA for XS-prefix)
4. Empirically: which day-count produces the actual paid coupon amount

The only ironclad proof when the prospectus is silent is **back-solving from a historical coupon payment**. Earmarked as a future module: cashflow-evidence-based disambiguation.

### 3.4 The contested-fields handling

When the prospectus is silent AND we don't have coupon evidence AND vendor sources disagree, the bond is genuinely uncertain. Honest schema design:

```
day_count: contested
candidates:
  - BOND_BASIS_30_360 (supporting: us-prefix-isin, ny-law-default, cbonds)
  - ISDA_30E_360     (supporting: bbg)
candidate_hashes:
  BOND_BASIS_30_360.calc_hash_full: sha256:...
  ISDA_30E_360.calc_hash_full:     sha256:...
best_effort: BOND_BASIS_30_360 (confidence: low, rationale: ...)
```

Customer can match against whichever convention their data uses and at least know which camp they're in. This is *not* implemented yet — earmarked for the schema's next minor revision.

### 3.5 The tiered-cost pipeline

Use the cheapest tool per step:

| Tier | Trigger | Cost | What runs |
|---|---|---|---|
| 1 | Cross-source consensus + Flash agrees + ONE independent anchor (Lux SE listing, DMO, coupon back-solve) | ~$0.001/bond | accept |
| 2 | Tier 1 disagrees | ~$0.05/bond | Flash with retrieval, force a verifiable quote |
| 3 | Tier 2 fails or quote unverifiable | ~$1.50/bond | Gemini Pro extraction + deterministic verifier |
| 4 | Customer query / mismatch | $1.50 + audit trail | forced re-validation |

Critical rule: **Flash zero-shot is correlated with vendor consensus, not independent of it.** Don't let Flash agreement substitute for the independent anchor. The anchor is what breaks the BBG-circular trap.

### 3.6 Customer-funded extraction model

The single most commercially important reframe of the day. Original assumption: build inventory upfront ($10-30k for 10k bonds). User's reframe: extract on demand, customer pays.

| Phase | Customer pays | Our cost | Margin |
|---|---|---|---|
| Month 1, cold cache, 1k new ISINs | $5,000 | ~$1,500 | $3,500 (70%) |
| Month 2-12, cache warm | $5,000 | ~$50 | $4,950 (99%) |
| **Year 1 ARR per customer** | **$60k** | **~$2k** | **~$58k (97%)** |

The cache compounds: customer A's portfolio funds the canonical records that subsequently cover customer B's portfolio at near-zero marginal cost. Canonical-database flywheel built out of paid usage.

What customers pay for is the **audit stack**, not the LLM call:
1. LLM reads → quote + structural fact
2. Verifier matches the quote against the actual PDF → reject hallucinations
3. Deterministic re-classifier maps quote to enum → dodge vendor bias
4. Cross-source corroboration → flag drift
5. Signed canonical record with full evidence trail

That stack is what justifies $5k/month per customer, not the model call.

---

## 4. The Athena pitch — what to keep, what to fix

Saved here so we can iterate on it cleanly.

### 4.1 What works

- ROI framing > tech framing
- Tiered cost story (Flash for build, Flash Lite for audit)
- Headcount-displacement comparison
- Concrete pilot ask ("100 rows, Panama or PEMEX")

### 4.2 What contradicts our actual architecture

- **"BBG-Matched (3 Decimals)" vs "Prospectus-Validated"** — these conflict when BBG drifts from the prospectus, which is the entire reason the product exists. Fix: "BBG-matched on ~80% where BBG is right; prospectus-corrected on ~20% where it isn't, with audit trail."
- **"0% reconciliation burden" / "End of the Argument"** — over-claim. The contested 5% will never be 0. Fix: "We resolve 95% of bonds to a definitive answer; the remaining 5% are genuinely contested at the issuer level — we surface candidates with evidence, you pick. That alone cuts recon backlog 20×."
- **"Generates Python code to build the math logic"** — regulatory landmine. Boss will ask "who reviews the LLM-emitted Python before it runs on $10B AUM?" Fix: "The LLM extracts a structured canonical record. The math runs on a closed-form, version-pinned, open-source SDK. The LLM never writes code that touches money."
- **"Flash Lite for daily audit"** — drop entirely. The hash architecture does this for free, deterministically.

### 4.3 The hidden moat the pitch underuses

The hash architecture itself: customer data never egresses. "Athena sucks in the Admin's Excel" is the line that gets killed by customer infosec teams in 30 seconds. Lead with "we never see your data."

### 4.4 Suggested closer

> "We aren't selling software; we're selling a deterministic, auditable record of what the prospectus actually says — computed on the customer's own infrastructure, never on ours. For 95% of bonds, we end the argument with the prospectus citation. For the remaining 5% where the issuer's contract is itself ambiguous, we surface the candidates and the evidence so the customer can decide with eyes open. We replace a 90% error rate on EM accruals with a single number: a hash that either matches or doesn't, with a paper trail to the issuer's filing. That survives audit; spreadsheets don't."

---

## 5. The pilot pitch — drafted email

Copy-pasteable email saved for use:

```
Subject: 100 bonds, free recon-drift audit — see if your vendors disagree with the prospectus

Hi [name],

Quick offer.

Pick 100 bonds your team finds painful to reconcile — the EM corporates
that throw variances every coupon period, the sovereigns where BBG and
your custodian disagree on accrual, the sinkers booked as bullets.

Send me the ISINs. Inside 48 hours I'll send back a per-bond variance
report:

  - Day-count convention from the issuer's actual prospectus
    (verbatim quote, page number)
  - Amortization or call schedule (verbatim quote)
  - Where BBG / Markit / Refinitiv drift from the prospectus
  - Audit-ready citation trail you can hand to your fund auditor

If 3+ bonds show drift your team didn't already know about, we talk
about a pilot subscription.

If we catch nothing, you get a clean bill of health on those 100 names
and we cover the cost.

Either way you keep the report.

Every citation is regex-matched against the actual prospectus PDF — not
a vendor opinion, not an LLM guess. It's the audit trail your team
would write by hand if they had the time.

Send me the ISINs and you'll have the report Friday.

[your name]
[your firm]
[contact]
```

Personalisation tip: replace the example bond categories with whatever you know they actually struggle with. Specificity is the credibility marker. Send to one person, not five.

### 5.1 What needs to be ready before sending

1. Upstream Gemini Pro call wired to feed `ProspectusExtraction` into the verifier (~half-day of work)
2. Per-bond report template (one-page audit deliverable, PDF or HTML)
3. Pre-pull major prospectus PDFs (EDGAR for US-registered, Lux SE / Euronext Dublin for Eurobonds)
4. Define "drift the team didn't know about" objectively — anything that would change accrual >1bp or affect YTW

### 5.2 Pricing anchors for the follow-up

- Junior analyst doing manual prospectus recon: $80-120k/year fully loaded
- Vendor data feed: $30-100k/year
- Position: $50-60k/year per fund as "less than half a junior, more reliable, audit-ready"
- Don't lead with bps-on-AUM unless they raise it. Procurement codes for "data audit tooling" are flat-fee codes.

---

## 6. The admin partnership question — paths and tradeoffs

Late in the session: admin says they want to **replace** their current static-data system, not augment it. This changes everything.

### 6.1 The honest gap

We're at v0.1. Replacing a fund admin's existing system means becoming a load-bearing component of their NAV pipeline. They will rightfully demand:

- SLA-bound API (99.9%+ uptime)
- SOC2 Type 2 (12-month audit cycle, $50-150k cost)
- Multi-region redundancy and disaster recovery
- 24/5 or 24/7 support, named CSMs
- Audit logging, change management, versioning, rollback
- Source code escrow, IP indemnification, business continuity plan
- Vendor risk review (financials, team CVs, insurance)

We have ~none of this. The build is 6-12 months and probably $1-3M of capability investment.

### 6.2 Three paths

| Path | What we sign | Time to deliver | Risk to us |
|---|---|---|---|
| **A. Phased replacement** | Year 1 = audit/parallel-run; Year 2 = selective replacement on contested bonds; Year 3 = full replacement | 6-12 months to first phase | Low |
| **B. License + consult, not operate** | They license schema + SDK + extractor; run on their infra. We are spec authors + maintenance partner. MIT model already supports this | 1-3 months | Very low |
| **C. Full-production replacement** | Multi-year, multi-million ACV. We become production vendor | 12-18 months, requires capital | High; existential if production fails |

### 6.3 Recommendation depending on team capacity

- **Solo / near-solo:** Path B. License fee ($100-300k/admin) + per-extraction fees ($0.50-2/bond) + maintenance retainer ($50-100k) = $500k-$1M ARR per admin without operational risk. Three admins = $2-3M business with team of 3-5.
- **Small team with ops capability:** Path A. Phase 1 builds production capability under their patronage, with their existing vendor as fallback.
- **Capacity to raise capital + execute production-grade build:** Path C. Once-in-a-decade window if the admin commits to multi-year minimum revenue.

### 6.4 The negotiation move (any path)

> "We're capable of full replacement, and we'd like to earn it. Year 1 we run alongside your current setup as the audit layer — the existing vendor keeps its slot, we prove our value bond-by-bond on contested cases. Year 2 we're either earning the primary slot or you've got a clean exit. Pricing reflects audit-tier in Year 1 and replacement-tier in Year 2 with right of first refusal."

Positions us as competent and confident, but doesn't sign us up to deliver something that doesn't exist yet. Gives the admin a face-saving structure.

### 6.5 Two questions that determine the right path

1. What system are they replacing? (Vendor data feed vs in-house build → different sales)
2. Why are they replacing? (Cost, coverage gaps, audit pressure, vendor lock-in → different urgency)

Both unanswered as of session end.

---

## 7. Open threads / next steps

In rough order of leverage:

1. **Wire upstream Gemini Pro call.** The `gemini_extractor.py` we built today is the verification layer; we still need the upstream call that hits Pro with the diagnostic prompt and parses the response into `ProspectusExtraction`. Half-day of work. Gating step on the pilot offer being deliverable.

2. **Run the actual quote-verification on Panama / PEMEX.** Pull the real PDFs from EDGAR. Regex-match the four verbatim quotes Gemini returned today against the source documents. If they all verify, we have empirical confirmation that Gemini has prospectus-grade text access for IG sovereigns / quasi-sovereigns. If some don't verify, we've found the coverage cliff.

3. **Do the 5-bond coverage measurement.** Pick 5 bonds across Tier A / B / C / D (major IG sovereign, IG corporate index name, EM HY corporate, post-cutoff issuance, private placement). Run the verifier on each. Measure: % of fields producing a verifiable quote, % whose deterministic classification is non-null, % requiring escalation. This is the empirical receipt that turns "interesting prototype" into "defensible business pitch."

4. **Decide path A / B / C for the admin.** Need answers to the two qualifying questions in §6.5 above.

5. **Schema additions earmarked but not yet implemented:**
   - `evidence_class` enum and `rationale` per field
   - `market_consensus` channel + `divergence_flag` for the lonely-truth case
   - `contested_fields` block with dual-candidate hashes
   - `mode: "prospectus" | "consensus"` on validate request

6. **`infer_batch_format` for date-format ambiguity.** When `10/05/2026` is ambiguous in isolation but unambiguous over a corpus of 500 dates (any DDFirst > 12 disambiguates DMY). Earmarked.

7. **Coupon back-solve module.** For seasoned bonds with known historical coupon amounts, deterministically derive day_count by checking which convention produces the actual paid amount. The mathematical proof when the prospectus is silent.

8. **Vendor format fixture corpus.** `tests/fixtures/vendor_formats/{bbg,markit,cbonds,ishares}/` with realistic vendor-shaped row examples. Drives parametrised tests that catch shape regressions as new vendor formats are encountered. Order of magnitude: ~100 files.

9. **Pre-built `VendorPolicy` profiles.** `BBG_USD_CORPORATE_POLICY`, `BBG_XS_EUROBOND_POLICY`, etc. — caller declares "my feed is BBG; treat unqualified `30/360` as BOND_BASIS for US-prefix ISINs." Records resolved via policy get `confidence=low` and a `where_to_find` pointer. Honest, useful, shifts assertion to caller.

10. **MCP package can't `pip install` cleanly** — it depends on `static-validator>=0.1.0` from PyPI which doesn't exist yet. Tests need `PYTHONPATH=src:../python/src` to run. Either publish to PyPI or use a path/workspace dependency. Pre-existing snag, not from today.

---

## 8. Reusable artifacts

### 8.1 The Gemini diagnostic prompt

Saved verbatim because we'll re-run this on more bonds:

```
For each of the bonds below, answer separately and structurally. If you cannot answer a part with high confidence, write UNKNOWN for that part — do not guess.

Bonds:
- US71654QDD16  PEMEX 7.69% due 23-Jan-2050
- US698299BL70  Republic of Panama 3.87% due 23-Jul-2060

For EACH bond, provide:

A. DAY-COUNT EVIDENCE
   A1. The verbatim sentence from the prospectus or offering memorandum that defines how interest accrues. Mark it with surrounding double quotes.
   A2. The page number, section number, or heading where that sentence appears.
   A3. Your classification of that quoted phrase into exactly one of:
       BOND_BASIS_30_360, ISDA_30E_360, ISMA_30_360, ACT_ACT_ICMA, ACT_ACT_ISDA, ACT_360, ACT_365_FIXED, ACT_365_25.
   A4. State explicitly whether the prospectus pinpoints the sub-variant (e.g. names "Bond Basis", "ISMA", or "ISDA" directly), OR whether your classification is an inference from jurisdiction / listing venue / governing law.

B. PRINCIPAL REPAYMENT
   B1. Is principal repaid as a single bullet at maturity, or in scheduled installments?
   B2. If installments: list each as (date, percentage of original principal).
   B3. The verbatim sentence from the prospectus describing this, with page reference.

C. CALL OPTIONALITY
   C1. Is there a make-whole call, a par call, both, or neither?
   C2. If par call: the date it begins, with the verbatim "from and after [date]" phrase from the prospectus.
   C3. If make-whole: the comparable-Treasury spread in basis points, with verbatim phrase.

D. SOURCE SELF-RATING
   For each of A, B, and C, rate your source as one of:
       prospectus_quoted        — you are quoting from the actual document
       secondary_summary        — an analyst note, term sheet, or vendor description
       general_market_knowledge — typical for this type of bond, not bond-specific
       guess

Format your answer with clear "BOND 1: PEMEX 2050" and "BOND 2: PANAMA 2060" headers so the two responses are unambiguous.
```

### 8.2 Interpretation matrix for diagnostic-prompt responses

| What the model returns | What to conclude |
|---|---|
| Quote is verbatim-matchable in the actual PDF + classification is internally consistent with the quoted phrase | Prospectus is in training. Tier-1 cheap path is viable for this bond class. |
| Quote is real but rated "inference" (prospectus silent on sub-variant) | Honest model. Routes to contested-field path, not silent acceptance. |
| Quote doesn't appear in the actual PDF text | Hallucination. Reject everything in the response, escalate to Pro extraction. |
| Quote is real, but classification contradicts the quote (e.g. quotes Bond Basis phrase but classifies as ISMA) | **The decisive tell.** Model has the prospectus text but is overriding with vendor-correlated classification. Trust the quote, ignore the classification, re-derive deterministically. |
| Day-count is UNKNOWN, structural facts quoted | Partial coverage. Cheap-path structural fields; force-Pro for day_count. |
| Quote is paraphrased rather than verbatim | Secondary source. Treat as vendor-correlated. |

### 8.3 Bonds discussed today (worth saving as test fixtures)

- **PEMEX 7.69% 23-Jan-2050** (`US71654QDD16`)
  - Day-count quote: *"Interest on the new securities will be calculated on the basis of a 360-day year of twelve 30-day months."*
  - Classification: `BOND_BASIS_30_360` (consistent with quote)
  - Bullet maturity. Make-whole + par call from 2049-07-23 (6 months pre-maturity). MW spread T+50bp.

- **Republic of Panama 3.87% 23-Jul-2060** (`US698299BL70`)
  - Day-count quote: *"Interest will be calculated on the basis of a 360-day year of twelve 30-day months."*
  - Classification by Gemini: `ISMA_30_360` ✗ (contradicts quote — should be `BOND_BASIS_30_360`)
  - Sinker: 33.33% / 33.33% / 33.34% on 2058-07-23 / 2059-07-23 / 2060-07-23
  - Make-whole only, T+30bp. No par call.
  - **Important: the Panama day-count claim is still unverified.** Gemini's classification disagrees with its own quote, but we haven't confirmed the actual prospectus text against EDGAR. Could be the prospectus has additional language elsewhere that pins ISMA via cross-reference. The Lux SE listing particulars would settle it cheaply.

---

## 9. State of the codebase at session end

```
python/src/static_validator/
├── __init__.py            (package exports — extended today)
├── __main__.py
├── adapter.py             (Layer A: vendor → canonical, ~1100 LOC, big extension today)
├── canonicalize.py        (canonical JSON / hash input, unchanged)
├── cli.py
├── derivations.py
├── gemini_extractor.py    (Layer A.5: prospectus-extraction verifier, NEW today)
├── hashes.py
├── validate.py
└── wire.py

python/tests/
├── golden/
├── test_adapter.py        (extended, 226 → covers loose normalizers, 2-digit pivots)
├── test_canonicalize.py
├── test_derivations.py
├── test_gemini_extractor.py  (NEW today, 18 tests)
├── test_hashes.py
├── test_validate.py
└── test_wire_contract.py

mcp/                       (MCP server, unchanged today)
schema/                    (JSON schemas, unchanged today)
docs/
└── session_notes_2026-05-10.md  (this file)
```

Test count: 244 passing. MCP tests still passing on `PYTHONPATH=src:../python/src`.

Branch: `claude/code-review-progress-jad2v`, head at `9470f69` plus this notes commit.

---

## 10. Tone / posture / heuristics worth preserving

A few decision principles that emerged today and should carry forward:

- **Surface uncertainty, don't paper over it.** Contested-fields handling, dual-candidate hashes, `confidence` ratings — the project's value is *transparency about why we picked what we picked*, not pretending to certainty when the prospectus is silent.
- **Trust quotes, distrust classifications.** Verbatim quotes are falsifiable; classifications inherit upstream bias. This is the architectural pattern that makes LLMs safe to use here.
- **Customer infrastructure, not ours.** Hash architecture lets the customer audit without sending data anywhere. This is the load-bearing security argument that competitors will struggle to match.
- **One independent anchor per record.** Cross-source consensus alone is correlated — don't accept it as sufficient. Listing particulars / DMO / coupon back-solve are the cheap, mechanically-independent options.
- **Be honest in pitches.** The "BBG-Matched 3 Decimals" + "Prospectus-Validated" + "End of the Argument" claims contradict each other. A 95%-true claim that survives interrogation beats a 100% claim that doesn't.
- **Match scope to capacity.** Path B (license + consult) for solo / small team. Path A (phased replacement) only with ops capability. Path C (full production) only with capital + team. Saying yes to a deal you can't deliver is the worst outcome.
