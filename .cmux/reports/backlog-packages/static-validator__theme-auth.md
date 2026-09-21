# static-validator / `theme:auth` — package report

**Lane:** `proposal/static-validator-theme-auth-09212102`
**Slice:** item 1053. 1 open item in the package, and it is the whole slice.
**Commits:** one — this report. **No file in this repo was touched, and why is
the substance of the report.**

**Result: 1053 is one decision with two halves, and the two halves do not have
the same owner. Half of it CANNOT land in a lane at all (an estate-wide RLS +
write-path change in a live Supabase, whose named blocker is a human step).
Half of it CAN be built today, in this repo, block-free — and this lane did not
build it, because producing a schema file for a table that does not exist, whose
shape is exactly what the decision is about, is the way you violate the
decision instead of taking it.**

---

## 1. Reading the item, and what the prior reader already proved

The item is a **post-v1 note, not a defect report**. Its own text says so: both
shortcuts were *intentional* to ship the wedge faster, and both "become blocking
before any external client lands; not blocking for internal-only demos".

I re-verified the prior reader rather than restating them, because a claim about
a live database has a shelf life. Healthcheck: `portfolio_uploads` and
`portfolio_upload_evidence` do not exist in the `bond-data` relation list this
repo carries, and this repo **never connects to Supabase at all**:

```
$ grep -rn "supabase\|SUPABASE\|create_client" mcp/src python/src mcp/tests
(no matches)
```

The tables are a Tier-2 hosted-service artefact. Tier 2 is public, sold and
unbuilt (README: "v0.6 — Tier 2 hosted at `validator.x-trillion.com`", while
README:19 sells it as a current product). Item 1046, dispositioned in the same
batch as this item, is "no renderer in repo; no DNS for validator.x-trillion.com".

---

## 2. Grouping the symptoms into underlying defects

One item, and it is **two problems with two different owners**. That split is
the whole of this report.

### D0 — the exposure is estate-wide and is managed, not overlooked

Before treating 1053 as a static-validator problem, the size of it:

`codebase-mcp/docs/SUPABASE_RLS_AUDIT_2026_05_20.md` (committed 5e785c5)
enumerated **160 PostgREST-exposed tables** and assigned `portfolio_uploads`
and `portfolio_upload_evidence` to **Bucket D — per-user / per-portfolio
(RLS-policy MUST be added)**, alongside `transactions`, `current_holdings`,
`cashflows`, `cash_balance`, `staging_transactions` and ~25 `v_*` views.

The audit is dated **2026-05-20 — four months before today — and the exposure
is unchanged.** The prior reader confirmed it live and I re-confirm it from the
brief's own verified evidence: with the key auth-mcp serves as
`BOND_DATA_SUPABASE_KEY` (a Supabase *publishable*, i.e. anon-equivalent, key),
an unauthenticated GET reads `transactions`, `current_holdings` and `cashflows`.
I enumerated the distinct portfolio ids that key returns: **4 — `gcrift`,
`gdbft`, `wnbf`, `wnbftest`.** Named client books, open to anyone holding a
public key.

So D0 is real and it is the largest thing in this package. It is also **not a
defect any lane can fix and not a defect this repo owns.** The audit's own
closing section, "What's blocking immediate fix", names three blockers and the
third is verbatim a human step:

> Bucket D needs the user-scoping column (`tenant_id` / `client_id` /
> `portfolio_id`) confirmed per table before policies can be written.

That is the same decision 1053 asks, four months older.

### D1 — "which identifier is `client_id`?" — a decision, and it has grown a second head

The item offers two candidates: **the xt-auth email**, or **a new `clients`
table**. The audit and the disposition recommend the `clients` table, because
the audit's own policy shape (`portfolio_id IN (SELECT ... FROM
client_entitlements WHERE client_id = ...)`) needs a **stable id**, and an email
is a value that changes.

**The item's text is stale in a way that matters.** It says the choice is
"xt-auth email, or a new clients table". `client_entitlements` — the table the
audit's policy shape reads from, and the thing that would *give* the chosen id
its meaning — **does not exist on bond-data**. The item does not name it as a
deliverable. It is one, and the prior lane independently arrived at the same
fact (`client_entitlements` 404 PGRST205, "Could not find the table").

So D1 is not "email or clients table". It is: **what is the client-identity
root of record for the hosted tier** — a table in bond-data, or a reference to
an identity owned elsewhere in the estate (auth-mcp / the Athena Supabase).

### D2 — the write path is ungated too, and that half is block-free

This is the finding the lane is really for, and it is the half the item and the
disposition both under-weight by calling it "the RLS half".

The prior reader probed the write path: `POST {}` to `portfolio_uploads`
returned **400 / 23502, "null value in column client_id violates not-null
constraint"** — that is, **PostgREST reached the INSERT and failed on the
schema. It never reached a policy, because there is none.** The refused INSERT
echoed back a real server-generated uuid, a `T+2` convention and
`status: 'pending'` — the full defaulted row.

`README.md:71` decides the tier on precisely this axis:

> you upload the portfolio file to `validator.x-trillion.com` […] This is the
> convenience option, **not the security option.**

Read properly: **Tier 2 was never sold as secure. It was sold as convenient.**
An exposure on a tier nobody has landed a client on is not a breach — it is an
unbuilt control, and "post-v1" is an honest label for it.

But RLS is not the only way to close that write path, and the alternative is
**available now, needs no decision, and touches nothing client-facing**: the
upload tables are **empty (exact count 0 on both)**, no repository on this host
reads or writes them (`grep -rn portfolio_upload` across `/opt/work` outside
`/lanes/` returns only the audit doc and a `recon_uploads` note), and they are
not in `supabase_realtime` or any other publication. **REVOKE the anon/API
write grants on both tables.** Supabase grants `INSERT`/`UPDATE`/`DELETE` to the
API roles by default and these tables have never held a row for anyone, so a
revoke breaks nothing — and unlike an RLS policy it does not presuppose the
identity decision, because it is not a row filter.

This is a correct, reversible, decision-free 30 seconds that stops an anonymous
write into a client-data table **today**, and the disposition did not surface it
because it framed the whole item as "the RLS-policy half". A superset of it was
**decided, filed and queued four months ago** — audit step 5 in its own
"Recommended execution order":

> **All Bucket B (service-role only)** — easy: `ALTER TABLE ... ENABLE ROW
> LEVEL SECURITY;` with no policies.
> **All Bucket C (reference data)** — `ENABLE ROW LEVEL SECURITY` + `CREATE
> POLICY ... FOR SELECT TO anon USING (true);`

Neither step has run. This is not the second time this question has been asked;
it is the second time it has been **filed**.

### D3 — there is nothing here to put a migration in

Checked before concluding D3, because a prepared SQL file is cheap and this was
a "kind:code-fix" item. There is no home for it:

- `git ls-files '*.sql'` in this repo returns **nothing**. No `migrations/`.
- `schema/` is **wire-format JSON Schema** for the validate protocol, not DDL.
  Its `README.md` is explicit that the request schemas deliberately accept no
  static values — different contract, different repo concern.
- The estate's SQL homes are `etf-scraper/migrations/` (19 numbered files) and
  `bond_data_mcp/migrations/`. A `bond-data` RLS migration belongs beside the
  bond-data code that owns it, not in the SDK.

So there is no file for this repo to hold, which is the same conclusion the
`handoff:332` lane reached for a bond-data Postgres function. I did **not**
manufacture one.

---

## 3. What I did, and what I deliberately did not

**I made no code change and prepared no SQL file.** This is a decision, and one
of its halves cannot be built here at all. Writing a schema for a hypothetical
`clients` table — and a policy set against a `client_entitlements` table that
does not exist — would pre-empt exactly the question the card asks. That is not
completing an item; it is answering it without the person whose question it is.

What this lane produced instead is the thing the estate was missing: **D2.** The
anon write path is closed by a decision-free, no-op-safe `REVOKE`, it was
already sitting inside an approved audit's execution order, and it has been
filed for four months. It is on the card as option A and it can be done on
Monday.

**The one thing I would hand off if the decision goes a particular way** is the
upload writer. `portfolio_uploads` has no writer in any repository on this host
and has never held a row, so nothing needs storing yet — which is the good news
in this item: **zero rows is the moment to fix an isolation boundary, not
later.** If Andy picks option B, the store is written by whatever serves
`validator.x-trillion.com`, and that is `athena_html_v3`'s ingestion model
carried sideways (its `/service/*/upload` routes and `recon_uploads`, flagged in
the `theme:pipeline` brief). I have **not** handed it off, because a handoff is a
dispatch and dispatching a builder onto an unchosen option is the same error as
building it myself.

---

## 4. Item ids — what this report claims

| id | status | one line |
|---|---|---|
| 1053 | **DECISION** | Two halves, two owners. The RLS/identity half is a human decision that has been open since 2026-05-20; the write-grant half is decision-free and is option A on the card. |

`FIXED:` is **none**, and that is not a failure — 1053 is not a repo defect. Its
own text calls both shortcuts intentional v1 choices; nothing has regressed; no
test is red because of it.

---

## 5. Item ids — deliberately NOT fixed, and why

| Not fixed | Why |
|---|---|
| 1053, half 1 — `client_id` → FK | Needs a target that does not exist (`clients` / `client_entitlements` on bond-data). Choosing the root of record is a human decision, not a lane's. |
| 1053, half 2 — RLS policies | Same decision, and the migration belongs to `bond-data`, not to a repo with no migrations directory and no Supabase client. |
| 1053 as a handoff | Deliberately **not** handed off. No repo on this host reads or writes `portfolio_uploads`; there is nothing to change anywhere yet. The handoff follows Andy's option B, not this report. |
| (adjacent, out of scope) D0's other ~25 tables | The audit's Bucket B/C/D work is estate-wide and much larger than this package. Named here as context so the next lane does not mistake 1053 for the whole exposure. |

---

## 6. Tests run

```
$ cd python && PYTHONPATH=src python3 -m pytest tests/ -q
285 passed in 0.42s

$ cd mcp && PYTHONPATH=src:../python/src python3 -m pytest tests/ -q
8 passed, 1 warning in 0.51s
```

Both suites green, unchanged from the previous lane on this package. **This is
a baseline, not evidence for a change** — no source file was modified. Stated so
the next lane knows the inherited tree is green. (Note the `mcp` suite needs
`../python/src` on `PYTHONPATH` or it fails to collect; that is inherited, not
introduced here.)

Live probes this lane issued: three unauthenticated `GET`s against the
bond-data PostgREST (`portfolio_uploads`, `portfolio_upload_evidence`,
`clients`, `client_entitlements` — existence/count only, `Range: 0-0`) plus one
read of `transactions.portfolio_id` to enumerate the exposed books. No writes,
no `POST`, nothing mutated.

---

## 7. What needs a human

1. **The card below.** It is one question with a grown head: the item asks
   *email or table*; the audit's policy shape needs a *stable id*; and the table
   that would give that id meaning — `client_entitlements` — does not exist. One
   decision settles all three.
2. **Option A is cheap and should not wait for the rest.** `REVOKE`ing anon
   write on two empty tables is not a policy, does not pre-empt the identity
   decision, and is reversible. If this report does nothing else, it should get
   that done.
3. **1053 is not the biggest thing it looks like.** The four client books
   readable with a public key — `gcrift`, `gdbft`, `wnbf`, `wnbftest`, across
   `transactions`, `current_holdings`, `cashflows` — are Bucket D of the
   2026-05-20 audit, the same bucket, and 1053 is one row of it. Anyone acting on
   this report should act on the bucket, not the item.
4. **The `blocks:job`/decision blindness is systemic, not this item's.** The
   ledger for 1053 already reads `disposition: andy-decision` — recorded
   **today**, by `[2] verifying disp-0921-13-rB` — and this lane was issued
   against it anyway, with the disposition pasted into the brief as if it were a
   task. A lane received a decision it was not able to take. Nothing in this
   report fixes that; it is worth someone's attention because it costs a lane
   every time it fires.

---

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 1053
-->

<!-- lane-decisions
item: 1053
covers: 1046, 1047
question: For the hosted tier's upload tables, do we (A) revoke anonymous write now and leave read isolation to the estate-wide RLS programme, or (B) build a bond-data clients table + client_entitlements and scope reads through them, or (C) leave both tables open pending external-client terms?
context: The item's two halves have been open since 2026-05-20, its FK target client_entitlements does not exist on bond-data, and the write path is ungated while both tables hold zero rows.
option A: Revoke anon INSERT/UPDATE/DELETE on portfolio_uploads and portfolio_upload_evidence (reversible, breaks nothing, works with no identity decision), file client_id's FK target and read isolation into the estate-wide RLS programme that already owns transactions/current_holdings/cashflows, and re-open 1053 when the first external client is contracted.
option B: Build a clients table plus client_entitlements in bond-data, migrate client_id to an FK against clients.id, and ship RLS policies on the upload tables and on transactions/current_holdings/cashflows, as a scoped migration with Andy or the service-role holder running it.
option C: Leave both tables open as they are and treat the exposure as accepted for the internal demo phase, with no revocation and no policy work until external-client terms are signed.
recommend: A
reason: Neither table has ever held a row and nothing writes them, so revoking anonymous write is a decision-free no-op that closes the live hole today without pre-empting the identity question the estate-wide RLS programme has to answer anyway.
default: A
-->
