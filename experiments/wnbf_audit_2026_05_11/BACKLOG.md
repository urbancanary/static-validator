# Backlog — opened 2026-05-11 during WNBF audit run

> codebase-mcp.remember was rejecting writes (`MCP error -32602` then HTTP 404 "Could not find session") when these were opened —
> if the service recovers, mirror these into codebase-mcp with tag `backlog`,
> `project_name='static-validator'`, then delete this file.

---

## 1. Consensus view: add `cbonds_cashflow_derived` source for `principal_repayment`  ✓ DONE 2026-05-11

Implemented as a UNION ALL leg in `bond_static_field_sources`. Bumps WNBF principal_repayment consensus from 0 medium → 23 medium.

---

## 2. Consensus view: normalise `call_date` values across sources

**What:** LLM emits `par_call_date` as text like `"November 15, 2046"`; `bond_reference.call_date` is a DATE column. In `bond_static_field_sources` they end up as different *string* values even though they refer to the same calendar date, so consensus mistakenly counts them as disagreement.

**How:** In `prosp_cd` CTE wrap LLM date string with `to_date(par_call_date, 'Month DD, YYYY')::text` (catch errors); in `br_cd` CTE keep `call_date::text` (already canonical YYYY-MM-DD).

**Expected impact:** Panama 2047 call_date jumps from "low non-unanimous" (2 dissenting sources) to "medium unanimous" (after manual promotion earlier today, bond_reference and prospectus_audit will agree on `2046-11-15`).

---

## 3. `canonical_day_count()` is missing ACT_365 mapping

**What:** `bond_validator_status.day_count_hypothesis` emits `ACT_365` (without the `_FIXED` suffix). The current `canonical_day_count()` function leaves it uncanonicalised, so etf_observation source values look different from prospectus_audit's `ACT_365_FIXED`.

**How:** Add `WHEN raw = 'ACT_365' THEN 'ACT_365_FIXED'` to the CASE in the function. Also worth running `SELECT DISTINCT day_count_hypothesis FROM bond_validator_status` and adding any other unmapped strings.

**Expected impact:** small — only affects floating-rate or rare-convention bonds. Mostly hygiene.

---

## 4. Load v3 audit results into bond_static_audit_findings  ✓ DONE 2026-05-11

Loaded as run `wnbf_2026_05_11_v3`. 6 v3 rows pre-load-downgraded by the AMORTIZING-requires-schedule rule. Day-count high-consensus jumped from 4 → 12 bonds.

---

## 5. Build `revert_promotion(id, reverter, reason)` function

**What:** Symmetric to `promote_discrepancy()`. Reads `promoted_old_value` from the discrepancy row, writes it back to the live column, stamps `reverted_at`/`reverted_by`/`revert_reason`, sets status='reverted'.

**Schema additions:** add `reverted_at TIMESTAMPTZ`, `reverted_by TEXT`, `revert_reason TEXT` to `bond_static_discrepancies`. Status enum gains `'reverted'`.

**Why:** completes the safety contract described in coordination.md §Reversibility. Without it, the only revert path is direct SQL on `*_source` columns — works for whole-batch undo but not for per-row mistakes.

---

## 6. Shadow-promotion backfill for 427 historical trace_mcp call_dates

**What:** The 2026-05-03 TRACE call-date batch wrote `bond_reference.call_date` directly with `call_date_source='trace_mcp_2026_05_03'`. These promotions never went through `bond_static_discrepancies`, so they're not revertable through the unified `revert_promotion()` function — only via the batch-undo SQL.

**How:** One-time migration script: for each row in bond_reference WHERE call_date_source='trace_mcp_2026_05_03', synthesize a bond_static_discrepancies row with status='promoted', promoted_by='trace_mcp_cron', promoted_old_value=NULL (they filled NULLs), promoted_at=<batch_date>.

**Why:** unified revert path. Also surfaces them in `bond_static_consensus` properly.

---

## 7. Smoke probe `etf-scrape-fresh` business-day fix

**What:** Probe alerts at `age_days > 3` (calendar days). iShares publishes T-2 BD, so any time the probe runs Sat/Sun/Mon for Thursday's data, age_days exceeds 3 even though data is current.

**How:** Replace with `age_business_days <= 2` logic. Lives in `smoke-test-mcp` (Cloudflare Worker). Affected probe definition file likely `probes/etf_scrape_fresh.ts` or similar.

**Status today:** Acked once this session (suppressed for 1h); has since re-fired at fail_count=3.

---

## 11. Image-proof evidence layer for Tier 3 prospectus audit (opened 2026-05-11)

**What:** Extend Tier 3 (PDF-in-context) so that Gemini returns page number + bounding-box coordinates alongside the verbatim quote. We render the page crop locally (pdf2image / pdftoppm), store as PNG in Cloudflare R2 or Supabase Storage, link from `bond_static_audit_findings.evidence_image_url`. The crop becomes cryptographic-grade proof a customer can verify with their own eyes — much stronger than any text quote.

**Why:** A text quote can in principle be paraphrased or fabricated (we saw a model invent "Search 13" results earlier today). A page-crop image cannot. For "audit-grade" pitch claims, the image is the final word.

**Marginal cost: ~$0/bond.** We're already paying for Tier 3 PDF reads (~$0.15/bond). Adding bbox extraction is a structured-output change to the existing call, not a new LLM call. Storage is trivial (~1.4GB for 9k bonds, ~$0.02/mo on R2).

**How:**
1. Schema: add `evidence_image_url TEXT` and `evidence_page INT` + `evidence_bbox JSONB` to `bond_static_audit_findings`.
2. Tier 3 harness change: pass PDF as `inlineData`, prompt instructs the model to return `{verbatim, page, bbox}` for each A/B/C section.
3. Post-processing: for each finding, `pdftoppm -f <page> -l <page>` to extract that page as image, crop to bbox, upload to R2, write URL back to the finding row.
4. UI: any review/promote interface should show the image when present.

**Limitations:**
- Tier 3 only — Tier 2 grounded search doesn't have a single source PDF.
- Many EM Eurobonds (the EMTN/GMTN cluster) have prospectuses behind paywalls — image proof unreachable until vendor feed integration.
- Storage governance — prospectus excerpts need internal-only access, NOT on the public read API.

**Worth doing for:** the SEC-registered cluster (PEMEX, Panama, Mexico, Colombia, Ecopetrol, Codelco). Concrete first deliverable: page-crop image proof for each AMORTIZING flag on Panama 2047 + 2060, plus each prospectus-quoted call-date date. That'd be the pitch slide that's literally unfalsifiable.

---

## 10. Add `verbatim_contains_classification` check to audit findings (opened 2026-05-11)  ✓ DONE 2026-05-11

Implemented as the `bond_static_audit_findings_evaluated` view. Auto-downgrades 8 audit findings (across v2+v3) from prospectus_quoted to `medium_prospectus_quoted_subvariant_inferred` where the verbatim only contains generic "360-day year, twelve 30-day months" wording without the literal convention name.

**What:** The LLM's `self_rated_a = 'prospectus_quoted'` is not always reliable for sub-variant claims. Concrete evidence from this run:
- **XS2159975882 KSA 2060** v2: model claimed `A4: Pinpointed` and classified `ISMA_30_360`, but the verbatim A1 quote contains only `"30/360"` and the math formula — never the literal string "ISMA". The sub-variant tag is the model's inference layered on top of the prospectus text, and A4's "Pinpointed" claim is misleading.
- Most real prospectuses give the formula or "360-day year, twelve 30-day months" wording without ever literally saying "Bond Basis" / "ISMA" / "30E/360". The sub-variant comes from governing law / programme convention.

**How:** Add a generated column on `bond_static_audit_findings`:

```sql
ALTER TABLE bond_static_audit_findings
  ADD COLUMN verbatim_contains_classification BOOLEAN
  GENERATED ALWAYS AS (
    CASE day_count_class
      WHEN 'BOND_BASIS_30_360' THEN day_count_quote ILIKE '%bond basis%'
      WHEN 'ISDA_30E_360'      THEN day_count_quote ILIKE '%30e/360%' OR day_count_quote ILIKE '%eurobond basis%'
      WHEN 'ISMA_30_360'       THEN day_count_quote ILIKE '%isma%'
      WHEN 'ACT_ACT_ICMA'      THEN day_count_quote ILIKE '%act/act%' AND day_count_quote ILIKE '%icma%'
      ELSE NULL
    END
  ) STORED;
```

Auto-downgrade trust when `self_rated_a = 'prospectus_quoted'` AND `verbatim_contains_classification = FALSE`. Trust drops from `high_prospectus_quoted_with_chunks` to a new `medium_prospectus_quoted_subvariant_inferred` tier.

**Why:** formalises the "prospectus rarely names sub-variants" observation into a structural check, so any LLM run going forward gets corrected automatically. Surfaces the user's intuition as a data property, not a manual review step.

**Effort:** ~15 min — ALTER TABLE + add a `trust_class_recomputed` view that applies the downgrade rule on top of the existing trust_score logic, or rebuild trust_score in SQL.

---

## 9. ga10-pricing-mcp repo git-hygiene cleanup (opened 2026-05-11)

**What:** `mcp_central/ga10-pricing-mcp/` has 15+ files untracked in git at the repo root (`README.md`, `package.json`, `schema.sql`, `DEPLOYMENT_GUIDE.md`, `PROJECT_SUMMARY.md`, etc.). None are in `.gitignore`. They've just never been added.

**Why it matters:** A `git add -A` on this repo by anyone unfamiliar with the state would sweep in a large unrelated change set alongside the intended edits. Also makes `git status` noisy.

**How:** One `git add` + commit pass to clear untracked files that belong in the repo, plus `.gitignore` entries for anything that doesn't (node_modules is already covered).

**Effort:** ~10 minutes triage + commit. Not urgent, but should happen before the next person works on this repo.

---

## 8. Split `prospectus_day_count` from `bond_reference.day_count` (opened 2026-05-11)

**What:** `bond_reference.day_count` is currently used for three distinct purposes — what we feed QuantLib for accrued, what CBonds reported, and what the prospectus says. For Reg S Eurobonds these can differ: BBG/admin use 30E/360 while strict prospectus says 30/360 or vice versa. We lose the legal-doc value when we choose BBG-matching, and lose BBG-matching when we choose legal.

**Proposed columns on bond_reference:**

```sql
prospectus_day_count           TEXT  -- what the legal doc strictly says (from audit)
prospectus_day_count_source    TEXT  -- usually 'static_validator_audit:<run_id>'
accrued_day_count_basis        TEXT  -- 'bbg_matching' | 'prospectus' | 'admin_override'
```

Semantics:
- `bond_reference.day_count` stays as **what we use for accrued** (BBG-matching by default).
- `prospectus_day_count` is **the strict legal text**, populated from audit. Informational, not pricing.
- `accrued_day_count_basis` explains *why* `day_count` is what it is.

**Effect on hash:** Published canonical hash continues to compute on `bond_reference.day_count` (BBG-matching), so customers' accrued ties to BBG ties to our hash. Optional fourth tier `prospectus_hash` (computed on `prospectus_day_count`) for strict-legal-compliance customers — punt for v1.

**Wired into `promote_discrepancy()`:** For day-count findings, populate `prospectus_day_count` instead of overwriting `day_count` directly. Only update `day_count` if `accrued_day_count_basis='prospectus'` is being explicitly chosen.

**Worked example (UAE 2052 today):**
- `day_count = '30E/360'` (matches BBG)
- `prospectus_day_count = '30/360'` (Pricing Supplement Item 14(e) literally says "30/360")
- `prospectus_day_count_source = 'static_validator_audit:wnbf_2026_05_11_v3'`
- `accrued_day_count_basis = 'bbg_matching'`

**Effort:** ~20 min — `ALTER TABLE` + small update to `promote_discrepancy()` to dispatch on `accrued_day_count_basis`.

**Why it matters:** Without this, audit-driven corrections to day-count either (a) silently break BBG-matching accrued, or (b) get rejected by reviewer because they'd break BBG-matching — but we never record the legal-doc value either way. With this, the legal-doc value is captured even when we don't promote it.

---

## 10. Add `cbonds_day_count` column family to `bond_reference` (opened 2026-05-11)

**What:** Symmetric to backlog #8 (prospectus_day_count). Currently `bond_reference.day_count` is "what we use for accrued"; we have no separate field for CBonds' explicit day_count value. When `conventions_source = 'cbonds-confirmed'` we know `day_count` came from CBonds, but otherwise CBonds' opinion is lost.

**Proposed columns on bond_reference:**

```sql
cbonds_day_count        TEXT
cbonds_day_count_source TEXT   -- e.g. 'cbonds_fetch:2026-05-11'
cbonds_is_amortizing    BOOLEAN -- direct from /cbonds/cashflows
cbonds_data_updated_at  TIMESTAMPTZ
```

Combined with #8, `bond_reference` then carries four day-count views per bond: accrued (we use), prospectus (legal doc), cbonds (vendor), admin (implicit when source='admin-recon-empirical-*'). This becomes the fully-attributed canonical record the static-validator spec describes.

**Backfill plan:** call cbonds-mcp `/cbonds/fetch` for each watchlist bond, parse the day_count field, write back. ALSO populate `cbonds_is_amortizing` from `/cbonds/cashflows` which we know works today.

**Effort:** ~30 min — `ALTER TABLE` + a Python loader that calls cbonds-mcp per ISIN and POSTs to Supabase.

**Blocked by:** backlog #11 (cbonds-mcp fetch returns "Bond not found" for all WNBF ISINs today).

**Interim option:** even without #11 resolved, we can populate `cbonds_is_amortizing` from `/cbonds/cashflows` immediately (it works). Also we can derive day-count *family* (30/360 vs ACT/ACT vs ACT/365) from `bond_cashflow_schedule.days_in_period` patterns — 180 across all periods = 30/360 family, etc.

---

## 11. cbonds-mcp `/cbonds/fetch` returns "Bond not found" for cached watchlist ISINs (opened 2026-05-11)

**What:** `POST /cbonds/fetch` returns `{"error":"Bond not found in CBonds","isin":"<isin>","timestamp":"..."}` for every WNBF ISIN tested, including the example ISIN `US87973RBC34` from cbonds-mcp's own root-page docs.

**Inconsistency:**
- `/cbonds/cashflows` works for the SAME ISINs (tested PEMEX 2050 — returns full cashflow data with `is_amortizing: false` and 59 cashflows)
- `/cbonds/watchlist` lists ~1724 ISINs including the bonds that `/fetch` claims are "not found"
- `/health` reports the service is healthy

**Likely cause:** the `/fetch` endpoint probably hits live CBonds (rate-limited, auth-required) rather than the local cache. `/cashflows` reads cached pre-fetched data. The two paths got out of sync. Or auth credentials expired (CBONDS_USERNAME / CBONDS_PASSWORD in auth-mcp may be stale).

**How to investigate:**
1. Read `urbancanary/cbonds-mcp` worker source (`src/handlers/fetch.ts` or equivalent).
2. Check whether `/fetch` checks the cache before going to CBonds API.
3. Verify CBONDS_USERNAME / CBONDS_PASSWORD in auth-mcp are current.
4. Compare the failing flow against `/cashflows` which works.

**Why it matters:** blocks backlog #10. Also means the cbonds-mcp surface is misleadingly broken — clients hitting `/fetch` get wrong "bond not found" errors when the bond IS in the watchlist cache.

**Effort:** investigation 30 min; fix probably trivial once root cause known.

---

## 12. codebase-mcp `remember` / `add_backlog_item` outage (opened 2026-05-11)

**What:** Throughout this session, `mcp__codebase-mcp__remember` and `mcp__codebase-mcp__add_backlog_item` rejected every call. First with `MCP error -32602: Invalid request parameters`, later with `HTTP 404 "Could not find session"`. Even minimal payloads (`title="test", content="test"`) failed.

**Impact:** Blocks cross-project continuity convention from ~/.claude/CLAUDE.md. Backlog items #8–#11 (and #12, #13 below) had to be written to a local BACKLOG.md instead. The convention is "log deferred work immediately to codebase-mcp" so other agents in other projects can see it — local files don't satisfy that.

**Likely causes (in order of priority to check):**
1. Session token expired or rotated — the HTTP 404 "Could not find session" suggests the MCP client lost its session binding mid-session. Possibly recovery just requires reconnecting the MCP client.
2. Schema drift on the API side — the earlier `-32602` "invalid request parameters" came on payloads that worked previously, hinting the server-side schema may have changed without the MCP wrapper being updated.
3. Worker deploy issue on `codebase-mcp` Cloudflare Worker — the `/health` endpoint wasn't tested.

**How to investigate:**
1. Hit `codebase-mcp` Worker's `/health` to confirm it's responding.
2. Try a direct POST to `/api/remember` (or equivalent) with a known-good payload to see if the server itself works.
3. Read the MCP wrapper code on the Claude side — check whether the session token is being passed correctly.
4. Cross-reference with `/Users/andyseaman/Notebooks/mcp_central/codebase-mcp/` repo for recent commits.

**Once fixed:** mirror BACKLOG.md items #8 through #13 into codebase-mcp with tag `backlog`, `project_name='static-validator'`. Then delete BACKLOG.md.

**Effort:** investigation 30 min; fix probably in codebase-mcp Worker or MCP client.

---

## 13. Ephemeral-BBG comparison API design (opened 2026-05-11)

**What:** The static-validator wants to compare audited bond static against BBG-reported values, but BBG's data license forbids redistribution. We cannot persist `bbg_day_count` / `bbg_call_date` etc. on our server (today's session attempted this and reverted — see SESSION_SUMMARY.md §"Note on BBG data handling"). We need a comparison architecture that gives the user the verification benefit without our side ever storing BBG raw values.

**Design pattern (client-side comparison, same as the validator's "hash, don't redistribute" trust model):**

```
customer (has BBG license)                  static-validator server
  ┌──────────────────────────┐                ┌──────────────────────────┐
  │ BBG export on the desk   │                │ canonical record         │
  │ (their license, their    │                │ - day_count = 30E/360    │
  │  network)                │                │ - prospectus_day_count = 30/360
  └─────────┬────────────────┘                │ - call_date = 2049-07-23 │
            │                                 └────────────┬─────────────┘
            │  GET /hash/{isin}                            │
            │  ←──────────────────────────────────────────┤
            │                                             │
  ┌─────────▼────────────────┐                            │
  │ customer's local SDK     │                            │
  │ computes BBG-side hash + │                            │
  │ compares against our     │                            │
  │ canonical hash           │                            │
  │ reports mismatch fields  │                            │
  │ LOCALLY                  │                            │
  └──────────────────────────┘                            │
            │                                             │
            │ (NO BBG VALUES SENT BACK)                   │
```

The customer publishes only a per-field MATCH/MISMATCH signal, never the BBG value itself. Our side never sees or stores the BBG number. Same as the existing "your data never leaves your network" pattern — just applied per-field.

**Schema additions (none on our side; client-only):**
- Customer SDK adds a `compare_against_bbg(local_static, our_canonical)` helper that returns a per-field diff struct.
- We can OPTIONALLY accept an OPAQUE "did BBG agree" signal per field (boolean), if the customer wants to volunteer that signal back to us for aggregate stats. Storing booleans, not values, sidesteps licensing.

**Why this matters for the pitch:** the comparison story works the same way as the rest of the validator — the customer can see "we agree, vendor X agrees, BBG agrees" without anyone redistributing licensed data. The architecture stays clean.

**Effort:** spec ~1 hour; SDK extension 2-3 hours; documentation update. None of it requires server changes today.

