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


---

## 14. HMAC-protected hash tier — staged: single secret first, per-client when scale warrants (opened 2026-05-11)

**Why this matters first:** Bond static is low-entropy. `calc_hash_min` covers (coupon, maturity_date, frequency, day_count) ≈ 10^10 plausible tuples. A modern GPU does ~10^10 SHA-256/sec, so anyone with the public hash database can brute-force the canonical record for any ISIN in under a second. Plain SHA-256 hashes today are effectively a publishing of the canonical record. The "your data never leaves your network" claim is currently a half-truth.

**The headline capability HMAC unlocks: per-field hashes published safely.** Plain SHA-256 per-field is dangerous — `day_count` has 8 values (8 hashes to brute-force), `frequency` has 5, `coupon` has ~1,500 at bp precision. Publishing plain per-field hashes essentially publishes the field values. With HMAC, per-field hashing becomes safe AND enables **surgical disagreement reporting on the client side** — client SDK can tell the user "your `coupon` disagrees with canonical; everything else matches" without anyone seeing the values. Today's `bond_static_discrepancies` table becomes a client-side artifact, computed on their Railway against their data, with us never seeing the diff.

Three states the client SDK can report per field:
- ✓ MATCH — your hash equals canonical hash
- ✗ DISAGREE — your hash differs from canonical hash (client knows to investigate that field; canonical value never exposed)
- ? MISSING_LOCAL — canonical has a hash for this field but you didn't provide a value (consider adding; e.g. call_date the client never imported)

This is a stronger pitch than "we made brute-force harder" — it's "we made fine-grained drift detection POSSIBLE while keeping your data on your network".

**Fix:** swap SHA-256 for `HMAC-SHA256(secret, canonical_json)` for both tier hashes AND per-field hashes. Without the secret, brute force is infeasible.

**Deployment-topology context (re-confirmed 2026-05-11):**
The static-validator code is open-source and customers deploy it on **their own Railway / cloud / on-prem**. Their bond data only ever exists on their box. The only egress is `GET /hash/{isin}` to our public read API. The HMAC secret therefore has to be retrievable by the *customer's* deployed instance — it lives in their process memory after fetch from auth-mcp. We do not see their data; we do see when they fetch the secret.

**Threat model in this topology:**
- T-A: anonymous scraper of the public hash database brute-forces. → HMAC kills it, regardless of single or per-client secret.
- T-B: a fake "customer" registers, fetches the secret, brute-forces the public DB. → Single secret = all customers' hashes now decoded; per-client = only that fake account's slice.
- T-C: a legitimate customer's Railway is compromised, attacker pulls the secret from env vars. → Same blast-radius distinction.

**Staging plan:**

| Stage | Architecture | When |
|---|---|---|
| **v0.2 — Single shared secret** | One `STATIC_VALIDATOR_SECRET` in auth-mcp; client SDK fetches at init; HMAC over canonical JSON. One public hash database. | Ship now-ish. Fixes T-A immediately. For early design partners (5–20 contracted customers), T-B / T-C risk is manageable and the operational simplicity is a real benefit. |
| **v0.3 — Per-client secrets** | Random `SK_i` per `X-Client-ID`, generated on customer onboarding, stored in auth-mcp keyed by client_id. One hash database per client (`/hash/{client_id}/{isin}`). | When customer count reaches ~50, OR when any single customer is high-value enough that their compromise must not cascade. |

Per-client generation: option (B) of three considered — random 32-byte per client on onboarding, stored in auth-mcp by `X-Client-ID`. No master secret to protect. Rejected options: pre-allocating a pool of 1000 keys (wasteful, no benefit); KDF-from-master (master leak is catastrophic, needs HSM).

**Spec changes (v0.2):**
- `schema/published_record.schema.json`: add `calc_hash_*_hmac` fields alongside existing `calc_hash_*`. Both populated; client picks based on whether it has the secret. Schema version bump 0.1 → 0.2.
- `python/src/static_validator/hashes.py`: add `compute_hmac_tier_hash(record, tier, secret)`.
- `python/src/static_validator/validate.py`: accept optional `secret` param. With secret → uses HMAC tiers. Without → falls back to plain SHA (still useful for the "anyone can play" public demo, with documented caveat about brute-force).
- Hash format prefix: `sha256:<hex>` for plain; `hmac-sha256:<hex>` for HMAC. Mutually distinguishable.
- README: document the two modes and when to use which.

**Spec changes (v0.3):**
- Read API gains `/hash/{client_id}/{isin}` path (or `X-Client-ID` header on `/hash/{isin}`).
- Hash database becomes partitioned per client.
- Onboarding flow generates `SK_i` and writes to auth-mcp.

**Trade-off explicit:** v0.2 keeps the free "anyone can validate without auth" demo *with* a documented limitation (brute-forceable). v0.2-with-secret keeps the "your data never leaves your network" promise honestly. v0.3 adds defense-in-depth blast-radius bounds.

**Effort:**
- v0.2: ~30 min for schema + SDK changes + tests + README update.
- v0.3: ~2-3 hours for the per-client database + onboarding flow + auth-mcp integration.

**Why this matters:** without v0.2, the validator's headline privacy claim is incorrect, and the pitch breaks under a competent attacker. Without v0.3, scale is bounded by the trustworthiness of every individual customer.

---

## 15. Define canonical precision for amortization percentages in the spec (opened 2026-05-12)

**What:** The CBonds roleplay surfaced a "false-positive" disagreement on Panama 2060's final installment: CBonds reports redemptions as 66667 / 66667 / 66666 out of 200000 nominal = `33.3335 / 33.3335 / 33.3330%`; the prospectus quotes `33.33 / 33.33 / 33.34%`. Both sum to 100% and pay identical cash, but the rounding lands differently. Without a canonical precision, the hashes disagree even though the economics are equivalent.

**Fix:** define in `SCHEMA.md` §canonical-rules that amortization percentages are rounded to **2 decimal places** before hashing. Document that "33.3335 ≡ 33.33 ≡ 33.33000 at canonical precision". Same rule for any other quoted-percentage field (make-whole spread bps stays integer; coupon stays to whatever precision the prospectus quotes — usually 3 dp).

**Where to apply:**
- `python/src/static_validator/canonicalize.py` — pre-hash rounding hook for `amortization_schedule[*].pct`.
- Doc note in `schema/published_record.schema.json`.
- Updated test fixture covering the Panama 2060 case (rounding-induced quirk; should canonicalise to MATCH, not DISAGREE).

**Why it matters:** the validator's value depends on its disagreements being *meaningful*. A precision-quirk false-positive on every amortizing bond degrades the signal. 2-dp matches the prospectus's reporting standard for bond installments and is the natural Schelling point.

**Effort:** ~15 minutes — single function + schema doc + one test.

**Open question:** should the rule apply to currency values (e.g. cashflow redemption amounts as integers) the same way? Probably yes — round to 2 dp on percentage hashes; round to whole cents on currency hashes. Worth thinking through once for all numeric fields in the spec rather than piecemeal.


---

## 19. Fill the daily-write gap on `bond_rating_history` (opened 2026-05-15)

**Symptom:** `bond_rating_history` has only 83,148 rows across 37,543 ISINs — ~2.2 rows per ISIN, despite rating-mcp running daily. Saudi 2060 has exactly one `effective_date` (2026-04-29) for each of the four agencies, even though `bond_reference.instrument_rating_date` is today (2026-05-15). The table is snapshot-on-change at best, snapshot-on-bulk-load at worst.

**Impact:** the inspector cannot answer "what was the rating last Tuesday?" because the history isn't actually there — only the current `bond_reference` row plus a thin reference back to one historical point. Time-travel queries silently return whatever record happens to be present, which may be weeks or months stale.

**Decision required:**
- **Option A — full daily snapshot:** rating-mcp writes one row per (isin, agency) per day, regardless of change. Storage cost: 37,543 ISINs × 4 agencies × 365 days ≈ 55M rows/year. Manageable but not trivial — needs an index on `(isin, effective_date)` and probably partitioning by year.
- **Option B — strict change-detection write:** rating-mcp diffs against last-known value per (isin, agency) and writes only on change. Smaller, but requires reliable change detection (today's broken state suggests this isn't currently happening).

Option B is the correct database-design choice; Option A is the operationally-simpler one. Recommend B with a unit test that confirms a write happens when (and only when) the rating changes.

**Effort:** ~2h to wire change-detection in rating-mcp + tests; ~30 min to backfill a one-time snapshot of current state to seed the history.

---

## 18. Capture `applied_rating`, `rating_rule`, `nfa_stars` in `bond_rating_history` (opened 2026-05-15)

**Symptom:** `bond_rating_history` captures the four raw per-agency ratings (moodys, sp, fitch, bbg) but NOT the NFA-composite output (`applied_rating`, `rating_rule`, `nfa_stars`). So we can re-derive what S&P said on a given date — but not what Athena displayed as the bond's rating on that date, because the composite derivation isn't versioned.

**Impact for inspector and audit:** "show me what we displayed on this date" cannot be answered for the composite. The rule logic itself (sovereign vs issuer vs best/worst) may also have evolved over time without versioning — so even re-running today's rule against historic agency rows won't necessarily reproduce what was actually shown.

**Schema fix:**
```sql
ALTER TABLE bond_rating_history ADD COLUMN applied_rating  TEXT;
ALTER TABLE bond_rating_history ADD COLUMN applied_rating_numeric INTEGER;
ALTER TABLE bond_rating_history ADD COLUMN rating_rule     TEXT;
ALTER TABLE bond_rating_history ADD COLUMN nfa_stars       INTEGER;
ALTER TABLE bond_rating_history ADD COLUMN rule_version    TEXT;  -- version of the NFA rule logic in force when this row was written
```

The applied-rating row is conceptually one per `(isin, effective_date)`, not per `(isin, agency, effective_date)` — could live in a sibling table `bond_applied_rating_history` instead. Two-table split is cleaner schemata; one-table-with-NULL-agency is operationally simpler. Recommend the split.

**Coordination with #19:** both fixes belong to the same rating-mcp write path, so do them together.

**Effort:** ~30 min DDL + ~1h to wire the write + ~30 min backfill.

---

## 17. Bond Data Inspector — UI + thin HTTP layer over existing validator views (opened 2026-05-15, REFRAMED)

> Supersedes codebase-mcp memory #322 (which had this living in a new standalone service or cbonds_mcp — both wrong; cbonds is gated to the watchlist subset, not the universe). codebase-mcp.remember and update_memory both rejecting calls today — see #12 — so logged here.

**Use cases driving this — REFRAMED 2026-05-15 after pre-flight checks:**

1. **Saudi 2060 rating** — Athena shows "A+" but `applied_rating` is **AA-**. Pre-flight confirmed no Gemini fallback exists in `bond_reference`; the A+ is `instrument_sp_rating`. Two parallel fixes:
   - Direct Athena bug fix (`athena_html_v3/BACKLOG.md` #1): render `applied_rating` not S&P.
   - Inspector value: surface all four rating fields + `rating_rule` + source on a single "Data Sources" view so future divergence is visible to a human in seconds.
2. **Nakilat search** — Athena's search returns nothing, but `bond_reference` has 2 Nakilat bonds. Pre-flight confirmed it's a search-scope bug, not a coverage gap. Two parallel fixes:
   - Direct Athena fix (`athena_html_v3/BACKLOG.md` #2): broaden search to query `bond_reference` universe with `pg_trgm`.
   - Inspector value: same `pg_trgm` index serves the inspector `/search`. Universe-wide search is its job.

**Net effect of reframing:** the MVP is still right, but it's a *complementary* tool to the Athena bug fixes, not a replacement. The Athena fixes are smaller and more direct; the inspector adds the "show me every opinion across every source for any bond" diagnostic that no display-side fix can deliver.

**What:** Inspector is a UI + thin HTTP layer over artefacts that already exist in static-validator:
- `bond_static_field_sources` (view) — every opinion per `(isin, field, source)`
- `bond_static_consensus` (view) — modal value + consensus level
- `bond_static_discrepancies` + `review_discrepancy()` + `promote_discrepancy()`
- `fetch_canonical_record(isin)` — already returns confidence + sources + where_to_find
- `list_known_isins` — coverage boundary
- Planned v0.3 `GET /bond/{isin}` read API at `validator.x-trillion.com`

**Delta endpoints (new on validator):**
- `GET /search?q=` — fan-out across cbonds-mcp, trace-mcp (FINRA), openfigi-mcp, etf-scraper for "unknown but found upstream"
- `GET /bond/{isin}/sources` — HTTP shell over `bond_static_field_sources`
- `GET /bond/{isin}/discrepancies` — HTTP shell over `bond_static_discrepancies`
- `GET /coverage` — global rollup (% canonical per field, # Gemini-fallback ratings, # low-consensus `principal_repayment`)
- `POST /enrich` (internal, gated) — adds to CBONDS_WATCHLIST, enqueues audit, fans out producers
- `POST /override` (internal, gated) — UI wrapper around `promote_discrepancy()`

**Schema additions to support ratings** (model on existing `conventions_source` / `call_date_source` pattern):
```sql
ALTER TABLE bond_reference ADD COLUMN moodys_rating          TEXT;
ALTER TABLE bond_reference ADD COLUMN moodys_rating_source   TEXT;
ALTER TABLE bond_reference ADD COLUMN sp_rating              TEXT;
ALTER TABLE bond_reference ADD COLUMN sp_rating_source       TEXT;
ALTER TABLE bond_reference ADD COLUMN nfa_composite          TEXT;
ALTER TABLE bond_reference ADD COLUMN nfa_composite_source   TEXT;
```
Ratings then participate in `bond_static_field_sources` / `bond_static_consensus` like every other producer. Specificity tiers (#16) automatically rank vendor-direct above Gemini fallback — closes the Saudi 2060 case.

**Key screen change:** the per-bond inspector pivots from "value + source" rows to "live value + every opinion ranked by `specificity_tier`", with inline `[promote tier-1]` / `[override]`. Makes the existing reconciliation infrastructure visible to humans. Example:

```
Field: nfa_composite                                        [override] [promote]

  LIVE          A+         rating_mcp:gemini_2026-05-15 (tier 4, low trust)
  ─────────────────────────────────────────────────────────────────────────
  Other opinions
  ✓ trace_mcp  A          trace_mcp_2026-05-15           (tier 2, vendor direct)
  ✓ s_p_direct A          rating_mcp:sp_lookup           (tier 1, vendor authoritative)
    nfa_calc   A          policy_engine                   (tier 3, derived)

  Specificity rule says S&P-direct should be live. [promote tier-1] to switch.
```

**Overlap with existing backlog:** touches #5 (`revert_promotion`), #8/#10 (per-source `day_count` columns — exact pattern for ratings), #14 (HMAC + per-field disagreement signal), #16 (specificity tier ranking).

**Open decisions:**
1. **Public-vs-internal split** — validator's hosted Tier 2 is public per its README; enrichment/override controls are internal-only. Where does the line sit on the read views (`/sources`, `/discrepancies`)?
2. **Database Register update** for the new rating columns — must check the register (per `mcp_central/CLAUDE.md`) before any ALTER TABLE.
3. **Search backend topology** — validator fans out to cbonds/trace/openfigi directly, or is there a thin gateway in front?

**MVP scope when picked up:** `GET /search` + `GET /bond/{isin}/sources` + the per-bond inspector screen. Defers `/enrich`, `/override`, `/coverage`, and public-API hardening to v2. Builds entirely on existing validator tables/views — no new producer pipelines needed for MVP (just the rating columns once decision 2 lands).

**Awaiting user go-ahead before any code is written.**

---

## 16. Canonical reconciliation must weigh source-specificity, not just recency (opened 2026-05-12)

**What happened:** Greensaif (XS2542166231) sits in `bond_cashflow_schedule` with 18 explicit redemption rows from CBonds — unambiguous evidence of a sinker structure. The 2026-05-11 Pro+grounding audit read the **Base Offering Circular** (which only carries the *programme conditions* and a *Form of Final Terms template*, not the executed 2038-Notes Final Terms) and could not find the schedule. The DB `AMORTIZING-requires-schedule` CHECK constraint then downgraded the audit row's `principal_repayment` to BULLET. The `bond_static_consensus` view weights both sources but the audit's "high_trust" tag pulled rank, so canonical ended up BULLET — **wrong**, against fact-based vendor data we already had.

**Why this is the bug, not a one-off:** the audit pipeline's "high trust" for prospectus_quoted findings is justified for *generic* prospectus claims (day-count, MW spread definition) where the Base OC is authoritative. It is NOT justified for *bond-specific* fields (per-tranche schedule, par-call date) where the Base OC cannot speak — only the Final Terms can. Today we have no way to distinguish "audit looked at the right document and found nothing" from "audit looked at the wrong document and predictably found nothing." Both produce the same downgrade.

**Fix — source-specificity ladder:**
Adjust the trust ranking in `bond_static_consensus` so that for any bond-specific field (`principal_repayment`, `amortization_schedule[*]`, `par_call_date`, `make_whole_spread_bp`), source specificity beats audit recency:

```
SPECIFICITY tier 1: pricing_supplement_audit, final_terms_audit  (bond-specific doc seen)
SPECIFICITY tier 2: cbonds_cashflow, cbonds_explicit            (vendor reporting bond-specific facts)
SPECIFICITY tier 3: prospectus_audit (Base OC only),
                    admin_recon_empirical                        (derived from accrued, not from the doc)
SPECIFICITY tier 4: etf_observation, llm_inference              (anything else)
```

A tier-2 source disagreeing with a tier-3 source wins. A tier-1 source disagreeing with tier-2 wins again. Today every source goes into the same "n_agreeing" bucket — we need stratified comparison.

**Where to apply:**
- `bond_static_field_sources` view: add a `specificity_tier` column derived from `source`.
- `bond_static_consensus` view: pick modal value from the highest-specificity tier that has any entries, NOT from the most-populous bucket.
- `promote_discrepancy()`: when canonical and a higher-specificity source disagree, the discrepancy table should flag the canonical as the disputed side, not the higher-specificity source.

**Audit-pipeline change (companion):** the Tier 3 (PDF) prompt should refuse to claim BULLET for an EMTN bond unless the model has seen a Pricing Supplement or Final Terms PDF (not a Base OC). Add a `pdf_type_identified` field to the model's structured output — `"base_oc"`, `"pricing_supplement"`, `"prospectus_supplement"`, `"final_terms"` — and require `pdf_type_identified IN ('pricing_supplement','final_terms','prospectus_supplement')` for a `principal_repayment` claim to be eligible to write canonical.

**Greensaif specifically:** in addition to fixing the rule above, source the actual Final Terms PDF (LSE ISM filing 2023-02; or BNP Paribas Taiwan / TPEx mirror). Pro+grounding hallucinated two BNP URLs trying to find it — manual sourcing required. Once the PDF is in hand, re-run Tier 3 to get image proof.

**Why it matters:** without this, the pipeline's failure mode is silent — canonical gets the wrong answer and looks confident about it. Other EMTN bonds where we only have the Base OC will get the same treatment by default.

