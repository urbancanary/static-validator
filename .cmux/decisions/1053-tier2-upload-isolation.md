# 1053 — Tier 2 upload isolation: the exposure is live, and it is an integrity hole

**Status:** re-verified live 2026-09-27. The earlier conclusion in this file
("empty tables, nothing to protect, no-op until later") was **wrong**, and the
measurement that refutes it is in §2.
**Owner question:** who holds the service-role key that can apply a one-line
grant change to two `bond-data` tables?
**Blocks:** the first external client upload. Nothing internal — but see §5,
because "internal" is not a security boundary.
**Related:** item 1046 (no renderer, no DNS), item 1049, and the estate RLS
programme in `codebase-mcp/docs/SUPABASE_RLS_AUDIT_2026_05_20.md`.

Two prior lanes read the item's two sentences and concluded the tables were
empty, unread and unexposed, so nothing could be fixed from here. Only the
first two of those are true. This file is rewritten from measurement.

---

## 1. What the repo guarantees, and what it does not

The package is `theme:auth`, so the first thing worth knowing is how little of
the product depends on auth. Almost none of it, deliberately:

- `schema/validate_request.schema.json` carries ISIN, locally computed tier
  hashes, a field-presence bitmap, and nothing else — `additionalProperties:
  false`. `python/tests/test_wire_contract.py::test_field_value_in_request_rejected`
  fails if anyone adds a field that accepts a static value.
- `mcp/src/static_validator_mcp/server.py` is local stdio with three tools and
  no notion of a caller.
- Neither `python/src` nor `mcp/src` contains a database client, a Supabase
  reference, or an API key read. Tier 0 and Tier 1 are complete without any of
  this; **Tier 2 is the only tier with a client identity problem**, and the
  reason is that Tier 2 stores what the client uploads.

## 2. What is actually live — measured 2026-09-27, not inherited

The key was fetched the sanctioned way (`get_api_key("BOND_DATA_SUPABASE_KEY")`
via `auth_client`; `sb_publishable_…`, i.e. the **anon-equivalent** role), and
all probes below were run against `https://xdgicslrdudsqlsudsgv.supabase.co`.
No row created by these probes survives — each was deleted by primary key and
the tables were confirmed back at count `0` afterwards.

```
GET  /portfolio_uploads          -> 200  Content-Range */0    (reads fine)
GET  /portfolio_upload_evidence  -> 200  Content-Range */0
GET  /transactions               -> 206  0-0/1346
GET  /current_holdings           -> 206  0-0/112
GET  /cashflows                  -> 206  0-0/2566
GET  /client_entitlements        -> 404  (PGRST205, does not exist)
GET  /storage/v1/bucket          -> 200  []   (no buckets: the raw files
                                               are not stored, only the row)
POST /portfolio_uploads          -> 201  row created, with a client_id we chose
PATCH /portfolio_uploads         -> 204
```

The `POST` returned the full created row:

```json
{"upload_id":"abbbd4fb-…","client_id":"__lane_probe__","source":null,
 "uploaded_at":"2026-09-27T15:37:03…","valuation_date":"2000-01-01",
 "settlement_convention":"T+2","raw_file_sha256":null,"n_bonds":null,
 "n_cash_rows":null,"status":"pending","notes":null}
```

and `portfolio_upload_evidence` carries the client-facing comparison:

```
upload_id, isin, client_par, client_clean_price, client_accrued, client_ytm,
client_duration, client_current_yield, client_annual_income,
client_security_type, client_country, client_sector, client_ratings,
our_accrued, our_ytm, our_ytw, our_ytal, our_duration,
accrued_error, ytm_error, duration_error, static_match, calc_gap,
misclassification_flag, fitted_day_count, fitted_settlement, notes
```

**Consequences, stated plainly:**

1. **The exposure is not hypothetical and not deferred.** Anyone holding the
   publishable key can insert an upload row today, naming any `client_id` they
   like. The value that item 1053 wants to become an FK is currently
   **client-asserted free text on a table with no write control**. Migration
   order is therefore forced: **grant first, FK second.** Tightening
   `client_id` to a proper FK while anon still holds `INSERT` buys nothing —
   a caller who can insert any row can insert any `client_id` the FK permits.
2. **Read isolation is the *second* problem, not the first.** Both upload
   tables are empty, so there is nothing to read *today*. There is nothing to
   stop anyone writing *today*. The item's own framing ("add RLS policies so
   the anon key can't read other clients' uploads") inverts the priority.
3. **`portfolio_upload_evidence` is a client-confidentiality leak in waiting,
   and a worse one than the item names.** The client's own par, clean price,
   accrued, YTM, duration and income sit in one row beside our computed values
   and the deltas between them. At ten thousand rows, a single `SELECT *` with
   the public key returns every client's positions *and* our reconciliation
   gaps against them. The raw uploaded files are **not** in Supabase Storage
   (no buckets exist), so the table is the whole of the exposure, and it is
   enough.
4. **The table is also a free integrity channel.** It is the corpus that will
   tune `fitted_day_count` and `fitted_settlement`. An anon writer can plant
   rows that make a *wrong* day-count or settlement convention look fitted.
   Nothing in the product reads that corpus yet, so nothing is corrupted
   today — but the corpus must not become anon-writable before it does.

## 3. Which half is a decision, and which half is not

**The half that needs nobody's opinion.** Supabase grants `INSERT`/`UPDATE`/
`DELETE` to the API roles by default, and that is the entire cause of §2. The
fix is a grant change, not a row filter, and it needs no knowledge of who
`client_id` should point at:

```sql
ALTER TABLE public.portfolio_uploads          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolio_upload_evidence  ENABLE ROW LEVEL SECURITY;
REVOKE INSERT, UPDATE, DELETE
  ON public.portfolio_uploads, public.portfolio_upload_evidence
  FROM anon, authenticated;
```

Enable-RLS-with-no-policies denies anon and authenticated both, and unlike a
bare `REVOKE` it also closes reads — so it is simultaneously the write fix and
the read fix. It is a **no-op for every reader that exists today** (there are
none) and a hard stop for every reader that should not. The estate already
decided this: the 2026-05-20 audit's "Recommended execution order" step 5 is
exactly `ALTER TABLE … ENABLE ROW LEVEL SECURITY;` with no policies. That step
is four months old and has not run.

**The half that does need a decision — but not the one the item asks about.**
The item asks *which identifier* `client_id` should be an FK against: the
xt-auth email, or a new `clients` table. That framing assumes the target
exists. It does not: **neither `clients` nor `client_entitlements` exists on
`bond-data`** (`client_entitlements` returns `PGRST205`; the audit's Bucket D
policy shape reads from it regardless). A draft exists in the estate —
`codebase-mcp/docs/rls_client_entitlements_migration.sql`, 2026-06-07, drafted
against a *different* project (Orion), still marked `DO NOT APPLY BLINDLY`.

So the identifier question is real but **it is the estate-wide Bucket D
question, dated 2026-05-20, and 1053 is two rows of a 160-table audit.** The
audit names its own blocker: the user-scoping column must be confirmed per
table before policies can be written. Answering it here and now, for two empty
tables, takes a decision that governs 160. It should not be taken in this repo.

What *can* be decided here is smaller and genuinely this lane's to ask: the
`client_id` FK target is a **schema migration**, and a schema migration needs
the `bond-data` owner's credentials. Andy can make it unreachable by simply not
naming that owner — which is what has happened for four months.

## 4. Why this repo is still not writing the migration

Ownership, not effort. The tables belong to `bond-data`; the estate's SQL homes
are beside the code that owns the schema (`bond_data_mcp/migrations/`, four
numbered files). A `bond-data` grant change placed in this SDK is a file nobody
with the database credentials will ever open — and on the standing rule that no
lane applies a migration, a lane in *this* repo cannot run the one thing that
closes the hole. The statement is written out in full in §3 above, which is
where it lives; there is no separate SQL file to point at, and the
`006_PREPARED_portfolio_upload_rls.sql` that later reports cite is not on this
host (see §8).

## 5. The one thing this lane changed, and what it deliberately did not

**Changed:** `README.md:71` (Tier 2). The earlier roadmap sentence said the
tier "ships behind an isolation boundary" — true, and too weak to act on. It
now states the measured state: writes are open to the public key today, and the
boundary is a precondition of accepting any client data, including the internal
demo, not a v0.6 deliverable. Nothing client-facing and no financial number is
touched.

**Deliberately not changed:**

- No SQL file committed here (§4), and **no `clients` table definition** — a
  definition written now *answers* the Bucket D question by writing it down,
  for a project that does not own it.
- The wire contract is untouched, and should stay that way: `ValidateRequest`
  accepts no static values, so whatever identity Tier 2 adopts must not appear
  in it. Identity belongs to the hosted service's session, not to this
  protocol. See §6.
- No test added here. What this lane found is a property of a live database
  this repo does not own and cannot reach from its code; a unit test asserting
  a remote grant would be a test that fails for the wrong reason in CI.

## 6. What a Tier 2 service must do, whichever way the decision goes

1. Resolve the caller's identity **server-side** at upload, never from a body
   field. A `client_id` that arrives in the request payload is client-asserted
   and isolatable by nobody — which §2 shows is the situation *right now*.
2. Store the upload against the resolved identity — an FK to whatever §3
   settles, not free text.
3. Enforce reads at the database, not in application queries. Application-side
   filtering of an anon-readable table is not a boundary.
4. Keep the validator's wire contract unchanged (§5).
5. Apply the §3 grant change **before** the first row is written, not before
   the first client is signed. Every row written first is a row whose
   `client_id` nobody can be sure of.
6. Treat `portfolio_upload_evidence` as client data, not as our telemetry. It
   contains the client's positions.

## 7. What is NOT in dispute

- Both v1 shortcuts were **intentional**, and the item says so.
- It is **not blocking** for internal demos *as a matter of record*. It is
  blocking as a matter of practice the moment a real portfolio file is pushed
  at it, because the write is anonymous and the `client_id` is a lie the
  caller chooses.
- The larger exposure — `transactions` (1,346 rows), `current_holdings` (112),
  `cashflows` (2,566) readable with the public publishable key — is **Bucket D
  of the 2026-05-20 audit**, the same bucket, the same decision, and this repo
  cannot fix it either. It is named here so the next lane does not mistake
  1053 for the whole exposure. 1053 is two rows of it; the fix in §3 is the
  same one-line shape and could be applied to all of Bucket D at once.

## 8. Provenance correction, 2026-10-04 — `migrations/006` does not exist

§4 used to say the statement was "handed off instead, verbatim, below". There
was nothing below. Later lanes and reports filled that gap with a file name —
`bond_data_mcp/migrations/006_PREPARED_portfolio_upload_rls.sql` — and the
name is now cited in two package reports, in the README's v0.6 line and in the
question on the decision card. **No lane has written that file, in this repo
or any other on this host.** Traced over every branch of this checkout: the
name appears first in commit `a778013` (2026-09-27), whose own commit body
says there is no SQL file anywhere; the first `lane-handoffs` block naming it
is `64c524e`; `find . -name '*.sql'` returns nothing and there has never been
a `migrations/` directory here.

Two consequences, and the second is the one that mattered:

1. The question on the card ("will they apply `006_PREPARED_…` steps 1+2?")
   references an artefact the person answering it cannot open. The statement
   itself is §3 above, which is why §3 is written as SQL rather than described.
2. The README's v0.6 line said applying the grant change before the write path
   exists "makes no wedge read nothing" — which reads as *do not apply it yet*.
   The conditional does not hold: a path that does not exist cannot be broken
   by RLS. Leaving the sentence as written was advice to keep anonymous
   `INSERT`/`UPDATE`/`DELETE` on both upload tables, and to keep the
   publishable key reading `transactions` (1,346), `current_holdings` (112) and
   `cashflows` (2,566), on the strength of a file that is not there.

Corrected in `README.md` and `SCHEMA.md` in the same commit as this section.
The reading in §3 is unchanged and still governs: **grant change first, FK
second, policies in the estate's Bucket D programme** — and none of it is
blocked by the identifier question, by the absence of the write path, or by
the absence of this file.
