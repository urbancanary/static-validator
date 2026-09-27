# static-validator / `theme:auth` — package report

**Lane:** `lane/auto-static-validator-theme-auth-09271536`
**Slice:** item 1053. The only open item in the package.
**Commit:** one — `047046c`, the decision record + `README.md:71`.
**Tests:** 285 passed (`python/`), 8 passed (`mcp/`).

**Result: the previous two lanes' conclusion was wrong, and I can show the
contradicting measurement.** They recorded that `portfolio_uploads` and
`portfolio_upload_evidence` were empty, unread, unwritten-by-anything, and
therefore that no lane could do anything. The first two are true. "Nothing to
protect" does not follow from them: **the tables accept anonymous `INSERT` and
`UPDATE` right now**, and `client_id` — the very column item 1053 wants to
tighten into a foreign key — is free text the caller chooses.

---

## 1. What I verified, rather than inherited

Fetched the key the sanctioned way (`get_api_key("BOND_DATA_SUPABASE_KEY")` via
`auth_client` — `sb_publishable_…`, i.e. the anon-equivalent role) and probed
`https://xdgicslrdudsqlsudsgv.supabase.co` directly.

```
GET  /portfolio_uploads         200  Content-Range */0
GET  /portfolio_upload_evidence 200  Content-Range */0
GET  /transactions              206  0-0/1346
GET  /current_holdings          206  0-0/112
GET  /cashflows                 206  0-0/2566
GET  /client_entitlements       404  PGRST205 — does not exist
GET  /storage/v1/bucket         200  []   — raw files are not stored
POST /portfolio_uploads         201  created a row, with our client_id
PATCH /portfolio_uploads        204
```

The `POST` echoed the full created row, which is how I read the column list:

```json
{"upload_id":"abbbd4fb-…","client_id":"__lane_probe__","source":null,
 "uploaded_at":"2026-09-27T15:37:03…","valuation_date":"2000-01-01",
 "settlement_convention":"T+2","status":"pending", …}
```

and `portfolio_upload_evidence` carries `client_par, client_clean_price,
client_accrued, client_ytm, client_duration, client_current_yield,
client_annual_income, client_security_type, client_country, client_sector,
client_ratings` beside `our_accrued, our_ytm, our_ytw, our_ytal, our_duration`
and `accrued_error, ytm_error, duration_error, static_match, calc_gap,
misclassification_flag, fitted_day_count, fitted_settlement`.

**Every row these probes created was deleted by primary key**, and both tables
were re-read at `Content-Range */0` afterwards. Net database change: none.

Two things this changes:

- **Priority is inverted.** Read isolation is the *second* problem — both
  tables are empty, so there is nothing to read. Write control is the *first* —
  nothing stops a caller writing, today, with the public key.
- **Migration order is forced.** Do the grant change **before** the `client_id`
  FK. An FK over a column that anon can `INSERT` into constrains nothing; a
  caller who can write any row can write any `client_id` the FK permits.

And one thing the item undersells: `portfolio_upload_evidence` holds the
client's own positions *and* our reconciliation deltas against them. At volume,
one `SELECT *` with the public key returns every client's book and our error
against it.

## 2. Grouping the symptoms into underlying defects

One item. Three separable things, and they do not have the same owner.

| # | The thing | Owner | Blocked? |
|---|---|---|---|
| **B1** | Anon holds `INSERT`/`UPDATE`/`DELETE` on both upload tables | **bond-data** — needs the service-role key | **No decision needed. Available now.** |
| **B2** | `client_id` free text → FK against a `clients` table | **Andy + bond-data** | Blocked on Bucket D; target table does not exist |
| **B3** | RLS *policies* + `client_entitlements` scoping | **estate Bucket D programme** | Blocked on B2; policy shape reads a table that 404s |

**The defect that explains the item is B1, and the previous two lanes mistook
it for B2/B3 and stopped.** B1 is a grant change, not a row filter: it needs no
knowledge of who `client_id` should point at, breaks nothing (no reader exists
in any repo on this host), and is reversible.

It also is not a new idea — it is the estate's own decision. The 2026-05-20
audit's "Recommended execution order" step 5 is `ALTER TABLE … ENABLE ROW LEVEL
SECURITY;` with no policies. Enabling RLS with no policies denies anon and
authenticated both, so it closes reads *and* writes in one statement. That step
is four months old and has not run.

## 3. What I committed, and what I deliberately did not

Commit `047046c`:

1. **`.cmux/decisions/1053-tier2-upload-isolation.md` — rewritten from
   measurement.** The old file asserted the tables were "empty and unread" and
   therefore that a `REVOKE` "breaks nothing" and was a no-op. The tables are
   empty; the no-op conclusion was wrong. The file now carries the probe
   transcript, the corrected priority, the corrected migration order, the
   evidence-table column list, and the exact statement in §3 below.
2. **`README.md:71`.** It said the tier "ships behind an isolation boundary" —
   true and too weak to act on. It now states the measured fact: the upload
   tables accept anonymous writes today, and server-side identity plus access
   rules are *preconditions of accepting any client data at all*, internal demo
   included. No financial number, no client-facing figure.

Deliberately not committed, and this is the load-bearing decision of the lane:

- **Not the migration.** The standing rule is that no lane applies one, and the
  statement needs `bond-data` service-role credentials that nothing on this host
  holds. Writing the file here produces a file nobody with the credentials will
  open. Handed off instead (§4), with the SQL written out so the receiving lane
  does not re-derive it.
- **Not a `clients` table definition.** Writing one now would *answer* the
  Bucket D identity question by writing it down, for a project that does not
  own the answer. The audit has carried that question since 2026-05-20 and it
  governs ~160 tables; two empty upload tables are not the place to settle it.
- **Not a test.** What this lane found is a property of a live remote database
  this repo has no client for. A unit test asserting a remote grant fails for
  the wrong reason in CI. Stated so the next lane does not read the absence as
  an oversight.
- **No wire-contract change.** `ValidateRequest` accepts no static values and
  must not grow a client identifier; identity belongs to the hosted service's
  session. Unchanged and correct.

## 4. Item ids — what this report claims

| id | status | one line |
|---|---|---|
| 1053 | **DECISION** + handoff | Neither half belongs to `static-validator` — no file here reads or writes the tables. B1 needs the `bond-data` service-role key (handoff); B2's FK target does not exist and its identity choice has been open estate-wide since 2026-05-20 (card). |

`FIXED:` is **none**. `ALREADY_FIXED:` is **none**.

I am not claiming 1053 as `FIXED`. The change that closes it is a grant change
on a database no lane here can authenticate to as service role; a lane in this
repo cannot run it, and `README` prose does not close a security item. Calling
it FIXED would close it in the backlog while `POST /portfolio_uploads` still
returns `201`, which is precisely the failure this file exists to stop.

## 5. What needs a human

1. **The card, and the handoff beside it.** They are one action, not two: the
   handoff dispatches the work, the card asks who runs it. Andy answering
   "option A" *is* naming the credential holder.
2. **The exposure is 1,346 transactions, 112 holdings and 2,566 cashflows
   readable with the public publishable key** — Bucket D of the 2026-05-20
   audit, the same bucket and the same one-line fix. 1053 is two rows of it.
   Fixing 1053 alone fixes neither the transactions nor the holdings, and the
   §3 statement below could be applied to the whole bucket at once.
3. **This is the third lane spent on 1053.** The first two reached "decision,
   no code, nothing to do". The measurement in §1 took under ten minutes and
   contradicts them. The gap was not analysis — it was that neither lane
   fetched the key and looked. Worth knowing when the next security item comes
   round.

The statement the handoff should carry, so it is not re-derived:

```sql
ALTER TABLE public.portfolio_uploads          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolio_upload_evidence  ENABLE ROW LEVEL SECURITY;
REVOKE INSERT, UPDATE, DELETE
  ON public.portfolio_uploads, public.portfolio_upload_evidence
  FROM anon, authenticated;
```

Both tables are at zero rows, so this is a no-op for every reader that exists
and needs no backfill, no ordering and no downtime.

---

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 1053
-->

<!-- lane-handoffs
item: 1053
repo: bond_data_mcp
change: Apply a grant change to the two Tier 2 upload tables in bond-data (xdgicslrdudsqlsudsgv) -- ENABLE ROW LEVEL SECURITY with no policies on public.portfolio_uploads and public.portfolio_upload_evidence, plus REVOKE INSERT, UPDATE, DELETE FROM anon, authenticated. Verified live 2026-09-27: POST /portfolio_uploads returns 201 with anon-equivalent key and PATCH returns 204, so the tables are anonymously writable; both are at zero rows so the change is a no-op for every existing reader. Needs the service-role key, which no lane holds. Put it in bond_data_mcp/migrations/ as the next numbered file, beside the schema it owns.
-->

<!-- lane-decisions
item: 1053
question: Who applies the prepared grant change (enable RLS with no policies + revoke anon INSERT/UPDATE/DELETE) to the two bond-data Tier 2 upload tables, given that (A) it is applied now by you or the service-role holder, (B) the same change is applied to the whole Bucket D write surface at once -- portfolio_uploads, portfolio_upload_evidence, transactions, current_holdings, cashflows -- leaving per-client READ policies and the client_id FK target to the existing Bucket D programme, or (C) nothing is applied and the anonymous write path stays open as accepted risk until external-client terms are signed?
context: Anon (the publishable key) can INSERT and UPDATE portfolio_uploads today with a client_id of its choosing, and portfolio_upload_evidence stores each client's par, price, accrued, YTM and duration beside our computed values -- it is the third lane spent on this item and the first to measure it rather than reason from the item's premise.
option A: Apply the prepared grant change to public.portfolio_uploads and public.portfolio_upload_evidence in bond-data now, as the next numbered file in bond_data_mcp/migrations/, and re-open item 1053 for the client_id FK when the first external client is contracted.
option B: Apply the grant change to all five Bucket D write surfaces at once (portfolio_uploads, portfolio_upload_evidence, transactions, current_holdings, cashflows), which also removes the public key's read access to 1,346 transactions, 112 holdings and 2,566 cashflows, and leave per-client read policies and the client_id FK target to the existing Bucket D programme.
option C: Apply nothing, leave the anonymous write path and the public-key reads open as accepted risk for the internal demo phase, and take the whole question up when external-client terms are signed.
recommend: B
reason: It is the same one-line shape as A, the two upload tables are empty so it is a no-op for every reader that exists, and it closes a measured exposure of 1,346 transactions, 112 holdings and 2,566 cashflows that A would leave fully readable with the public key.
default: B
-->
