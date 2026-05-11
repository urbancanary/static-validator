# Session Summary — 2026-05-11

> First end-to-end build of the static-validator audit pipeline against the
> WNBF (Wealthy Nations Bond Fund) holdings universe (30 bonds).

---

## Starting point

Hypothesis: *"Gemini Flash Lite knows enough about bond prospectuses from
training data to act as a cheap secondary check on vendor-supplied static."*

## What we proved

### 1. ISIN-only recall is a dead end at any tier

Tested gemini-3.1-flash-lite, gemini-3-flash-preview, and gemini-3.1-pro-preview
on the same 30 WNBF bonds, ISIN-only, no grounding:

| Model | Coupon match | Maturity match | Both | UNKNOWNs admitted |
|---|---:|---:|---:|---:|
| Flash Lite | 0/30 | 0/30 | 0/30 | 0/30 |
| Flash (thinking) | 0/30 | 0/30 | 0/30 | 0/30 |
| Pro | 2/18 | 1/18 | 1/18 | 12/30 |

Lite and Flash hallucinate 100% with `confidence: high`. Pro at least refuses
40% of the time. ISIN-only recall is **not the architecture**.

### 2. Pro + Google Search grounding produces real prospectus citations

Pro with grounding + clean descriptors (openfigi_ticker + bond_identity.issuer
+ figi) produces prospectus-quoted answers with verbatim sentences and page
references. EDGAR-indexed bonds (PEMEX, Panama, Mexico, Colombia, Ecopetrol)
work cleanly. Reg S Eurobonds with Final Terms on Luxembourg/ISE work
patchily.

### 3. The model's claimed evidence trail is NOT the same as its grounding metadata

The model will *fabricate* "Search 13: ..." quotes in output text even when
`n_queries = 0` in the API metadata. **Always trust API grounding metadata
over the prose evidence trail.** Baked into the trust scoring.

### 4. Even at temperature=0, Pro+grounding is non-deterministic

Different runs surface different web pages. Day-count classification was the
wobbliest. Argues for **ensemble** — run the prompt N times as separate
sources.

### 5. The LLM has a US-conventions bias

Default to `BOND_BASIS_30_360` for Reg S Eurobonds where the correct answer
is `ISDA_30E_360`. v3 prompt fix with explicit Reg S / English-law
disambiguation corrected 7 of 8 affected bonds.

### 6. Vendor data is sometimes WRONG, sometimes RIGHT — consensus shows which

**Panama 2047:** CBonds cashflow shows 31.75/31.75/36.51% paydowns. Prospectus
says three equal 33.33% installments. CBonds drifted. Audit HIGH-severity catch.

**Reg S Eurobond day_counts:** CBonds correctly classifies as `30E/360`; the
LLM defaulted to `BOND_BASIS_30_360`. CBonds is right. Discrepancy table
flags it; reviewer rejects the LLM finding.

### 7. The audit value is **source attribution**, not "we caught vendor errors"

Pitch shifted during the session from "we find vendor errors" to "every
published field carries which sources agree". Three-source-agreement is
genuinely verifiable. One-source-only is honest about what you've got.

### 8. Prospectus literal text ≠ market convention

The prospectus *literally says* `30/360` (the words on the page). The
*market-convention sub-variant* under ISDA rules + governing law +
listing-venue is `30E/360` for Reg S Eurobonds. They are both true and both
worth recording — separately. **bond_reference now carries both.**

### 9. AMORTIZING must be backed by an actual schedule

A model claim of "AMORTIZING" without ≥2 installment entries is now a CHECK
constraint violation. 6 bonds were pre-load-downgraded by the rule. The 2
surviving amortizers (Panama 2047/2060) each carry their full prospectus-
quoted schedules.

### 10. LLM verification against BBG holdings export (no peek): 13/13 par-call dates match

User pasted a 13-bond BBG holdings export. Cross-checked LLM's par_call_date
(from v2+v3 + a QPETRO solo retry) against BBG `Next Call Date`. **Every
single one matches**, despite the prompt never being told the answer.

The day-count column from BBG read `30E/360` for all 13 — including 9 US-
prefix bonds where `bond_reference.day_count` is `30/360`. The 9-bond
divergence is the literal-vs-conventional-drift finding (§8).

---

## What's live in bond-data Supabase (xdgicslrdudsqlsudsgv)

### Tables

```
bond_static_audit_runs       (3 rows: v2 + v3 + qpetro_solo)
bond_static_audit_findings   (61 rows; CHECK constraint enforces AMORTIZING-requires-schedule)
bond_static_discrepancies    (27 rows: v2=19, v3=8)
```

### bond_reference schema additions (this session)

```
prospectus_day_count           TEXT          -- what the legal doc LITERALLY says
prospectus_day_count_source    TEXT          -- 'static_validator_audit:<run_id>'
accrued_day_count_basis        TEXT          -- 'bbg_matching' | 'prospectus' | 'admin_override' | 'unspecified'
locked, locked_at, locked_by, lock_reason    -- on bond_static_audit_findings
```

### bond_reference schema additions that were DROPPED this session

```
bbg_day_count, bbg_call_date, bbg_composite_rating, bbg_data_source, bbg_data_updated_at
```

**Dropped for licensing reasons.** Bloomberg's data agreement forbids
redistribution. Storing raw BBG values in a table that may feed public APIs
or be incorporated into published hashes violates the license. The
analytical finding (the 9 US-prefix divergences) is preserved in this
session's analysis and in `bond_static_audit_findings` without persisting
the BBG raw values. **Going forward: any BBG comparison must be ephemeral
(in-memory at validation time) or under an explicit redistribution license.**

### Functions

```sql
review_discrepancy(id, status, reviewer, notes)
  → status ∈ {pending, under_review, approved, rejected, noted, no_action}

promote_discrepancy(id, promoter, p_basis DEFAULT 'audit_record_only')
  → p_basis ∈ {audit_record_only, replace_for_accrued, prospectus, bbg_matching, admin_override}
  → audit_record_only (default): writes prospectus_day_count, LEAVES day_count alone (preserves BBG-matching)
  → replace_for_accrued/prospectus: overwrites day_count too
  → Cashflow promotions still raise (pool_factor cascade requires manual handling)
```

### Views

```
bond_static_field_sources     UNION across 7 sources per (isin, field, value)
                              including cbonds_cashflow_derived for principal_repayment

bond_static_consensus         Per (isin, field): modal_value, n_agreeing,
                              consensus_level (high≥3 / medium=2 / low=1)
```

### Helper functions

```
canonical_day_count(text)     '30/360' / '30E/360' / etc. → ISDA enum form
```

---

## Final WNBF consensus snapshot

| field | high (3+) | medium (2) | low (1) | Notes |
|---|---:|---:|---:|---|
| day_count | **12** | 14 | 4 | 3x lift after v3 + cbonds layered in |
| call_date | 0 | 8 | 9 | call_date was sparse in vendor data; v2+v3 agreement boosted 8 |
| principal_repayment | 0 | 23 | 7 | cbonds_cashflow_derived gave 2nd source |

**WNBF amortizers (CHECK-constraint-survived):**
- US698299BG85 PANAMA 2047 — 3 installments, high trust, CBonds schedule drift flagged HIGH
- US698299BL70 PANAMA 2060 — 3 installments, high trust, CBonds matches prospectus

**WNBF call-date verification vs BBG export:** 13/13 exact match (after QPETRO solo retry).

---

## Architectural decisions captured

1. **`locked` boolean on every layer** — curated rows protect themselves from automated reparses.
2. **AMORTIZING-without-schedule is rejected at the DB level** (CHECK constraint).
3. **Promotion is gated on `status='approved'` AND `target.locked=FALSE`.** No silent write-back.
4. **Consensus follows the static-validator §5 spec** — high=3+ sources, medium=2, low=1.
5. **Trust metadata uses grounding API, not LLM prose.**
6. **Three day-count columns** — `day_count` (accrued), `prospectus_day_count` (literal text), `accrued_day_count_basis` (why we chose). BBG values are NOT persisted (licensing).
7. **`p_basis` parameter on `promote_discrepancy`** — default writes prospectus_day_count only, never silently changes accrued.

---

## Open backlog (BACKLOG.md)

| # | What | Effort | Status |
|--:|---|---|---|
| 1 | cbonds-cashflow source for principal_repayment | | ✓ DONE |
| 2 | Normalise call_date strings across sources | small | open |
| 3 | Extend canonical_day_count for ACT_365 | trivial | open |
| 4 | Load v3 audit results | | ✓ DONE |
| 5 | Build `revert_promotion()` function | medium | open |
| 6 | Backfill trace_mcp historical call_dates as synthetic discrepancies | medium | open |
| 7 | Fix smoke probe etf-scrape-fresh to use business-day math | small | open (firing all session) |
| 8 | Split prospectus_day_count from accrued day_count | | ✓ DONE |
| 9 | ga10-pricing-mcp repo git-hygiene cleanup | small | open |
| 10 | verbatim_contains_classification check | | ✓ DONE |
| 11 | Image-proof evidence layer for Tier 3 (page crops with bboxes) | medium | open |

**New backlog opened by this session that did NOT make it into BACKLOG.md:**

- **codebase-mcp.remember broken** (-32602 then HTTP 404 "Could not find session") — blocks cross-project continuity convention. Investigate codebase-mcp service.
- **BBG comparison architecture** — we want to compare vs BBG ephemerally without persisting. Define the ephemeral-comparison API + how to keep findings without raw values.

---

## Where to pick up next

1. **The 9 day_count discrepancies are now characterized** as "prospectus literal text vs market convention drift". Disposition pattern is `rejected` with shared note explaining the convention divergence. Bulk-review them out of the discrepancy backlog.
2. **Galaxy + Greensaif amortization** — both flagged AMORTIZING by LLM but downgraded by the schedule rule. Their prospectuses confirm they amortize but without exposing the schedule. Tier 3 (PDF in context) is the path.
3. **Run v2/v3 a third time** as an ensemble member (true majority-vote per field). The 4 low-consensus day_count bonds would likely resolve.
4. **Image-proof evidence layer** (backlog #11) — the demo-defining upgrade. Marginal cost ~$0 because Tier 3 is already paid. Six page-crop images on Panama 2047/2060 + PEMEX par-call = unfalsifiable slide.
5. **Smoke probe #7** — keeps firing. Real fix is the business-day logic in the Cloudflare Worker.

---

## Files in this experiment dir

| File | Purpose |
|---|---|
| README.md | Pipeline overview |
| BACKLOG.md | Open items |
| SESSION_SUMMARY.md | This file |
| descriptors_clean.json | 30 bonds × {openfigi_ticker, issuer, figi} |
| harness_v2.py | Pro+grounding A/B/C/D, clean descriptors |
| harness_v3.py | v2 + day-count disambiguation rule |
| parse_to_canonical.py | Prose → structured fields |
| load_to_supabase.py | PostgREST POST to findings table |
| reparse_amortization.py | Pulls schedule from B2 block only |
| reparse_principal.py | First-sentence + negation-aware classification |
| v2_canonical.json | 30-row parsed dataset |
| /tmp/qpetro_solo.json | QPETRO single-bond agentic retry result |

---

## Note on BBG data handling (added end-of-session)

During this session we briefly loaded a 13-bond BBG holdings export into
`bond_reference.bbg_*` columns to compare against our LLM audit + our
accrued values. The user (rightly) flagged this as a licensing exposure —
Bloomberg's data agreement forbids redistribution, and persisting raw BBG
values in a table that may eventually feed a public static-validator API
violates that.

**Action taken:** dropped the bbg_* columns from `bond_reference` (no data
retained). The analytical finding from the comparison — that 9 US-prefix
bonds have a literal-prospectus-text vs market-convention divergence — is
captured in this summary and in `bond_static_audit_findings`. Those are
INTERNAL analytical records, not derived from licensed BBG redistribution.

**Going forward:** any BBG comparison should be ephemeral (in-memory at
validation time, on the user's own machine, not persisted), OR done under
an explicit BBG redistribution license. Same applies to any other licensed
vendor (Refinitiv, ICE, Markit).
