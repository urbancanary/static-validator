# static-validator / `theme:auth` — package report

**Lane:** `lane/auto-static-validator-theme-auth-10071438` (2026-10-07)
**Slice:** item 1053 — the only open item in the package. **Verdict: DECISION.**
No code change, and none is possible from this repo.

**Repo-wide test suite: not run, and that is deliberate** — nothing executable
was touched, no test in this repo can observe this item (see §4). Prior lanes
that ran the suite anyway reported 285 passed (`python/`) / 8 passed (`mcp/`).

---

## 1. What the item asks, and the three things that block it

Item 1053 asks for two schema changes on two tables (`portfolio_uploads`,
`portfolio_upload_evidence`) in the **bond-data** Supabase project
(`xdgicslrdudsqlsudsgv`):

1. tighten `client_id` from free text to a proper FK against an auth/clients
   identifier;
2. add RLS policies so the anon key cannot read other clients' uploads.

Neither can be done from a lane in this repository. Three independent reasons,
each verified in the tree this session:

**(a) The objects are not in this repo, and never have been.**
`find . -name '*.sql'` → nothing. `grep -rn "portfolio_uploads" --include=*.py
--include=*.sql` over `python/`, `mcp/`, `schema/` → no hit outside
`.cmux/` and `README.md`. There is no `migrations/` directory, no database
client (`python/src`, `mcp/src`: no Supabase ref, no `get_api_key`, no HTTP
client), and no write path. The upload tables are a property of the bond-data
project, whose migrations live beside the code that owns that schema — §4 of
`.cmux/decisions/1053-tier2-upload-isolation.md` already says so, and it is
still true today.

**(b) The identifier the FK would point at does not exist.**
`GET /client_entitlements` on bond-data returns `404 PGRST205` — the table is
not there (measured 2026-09-27 and recorded in
`.cmux/decisions/1053-tier2-upload-isolation.md` §2; not re-probed by this
lane). So there is no column for a policy to join through, and the FK target is
a question, not a lookup.

**(c) Writing the DDL here would be the same defect that has kept this item
open.** The previous lane traced it (§8 of the decision record): reports kept
citing `bond_data_mcp/migrations/006_PREPARED_portfolio_upload_rls.sql`, **a
file that exists on no branch of this repo and on no path on this host**
(`git log -S 006_PREPARED` finds the string only in prose). Six lanes reasoned
about that file without opening it. Adding a `.sql` file to this SDK produces a
second copy that the one person who can run it will not open.

## 2. What the previous lane already landed (verified in the tree, not inherited)

Both of the last lane's commits are ancestors of this branch's `HEAD`:

| commit | what it did | still present |
|---|---|---|
| `79271a9` | `README.md:97` — removed the phantom `006_PREPARED…` sentence, stated the grant change explicitly, said it is **not blocked** and needs the bond-data service-role key | yes — `grep -c 006_PREPARED README.md` → **0** |
| `fb56e62` | `.cmux/decisions/1053-tier2-upload-isolation.md` §8 — provenance trace, and the correction of §4 | yes — §8 present |

So there is **no doc defect left in this repo to fix**: the one thing this repo
owned (pointing at a file that does not exist) was closed on 2026-10-04. The
remaining work is a grant change against a database this repo does not own.

## 3. What is still wrong, stated plainly (unchanged by this lane)

Measured live 2026-09-27, recorded in the decision record §2, **not re-probed
here** — one of those measurements was a write (`POST /portfolio_uploads` →
`201`, `PATCH` → `204`) against a table with no write control, and re-running a
write to re-confirm a finding three lanes already reproduced adds risk and no
information:

```
GET  /portfolio_uploads          -> 200  Content-Range */0     (anon read)
GET  /portfolio_upload_evidence  -> 200  Content-Range */0
GET  /transactions               -> 206  0-0/1295..1346
GET  /current_holdings           -> 206  0-0/112
GET  /cashflows                  -> 206  0-0/2566
GET  /client_entitlements        -> 404  PGRST205 (does not exist)
POST /portfolio_uploads          -> 201  row created with a client_id we chose
```

Both upload tables are at **zero rows**, so the fix is a no-op for every reader
that exists today and a hard stop for every reader that should not exist.

## 4. Why no code, no SQL file, no test — the deliberate omissions

- **No `.sql` file here.** §1(c).
- **No `clients` table definition and no policy SQL.** A definition written in
  this repo *answers* the estate's open identifier question by accident, for a
  project that does not own it, and for two tables inside a 160-table audit
  dated 2026-05-20.
- **No test.** No executable file in this repo can express "a remote table has
  no RLS policy". Any assertion that could be written here (e.g. "this repo
  holds no publishable key") passes today, passes tomorrow, and catches
  nothing — and it would need a live credential in CI, which the house rules
  forbid.
- **No client, endpoint or helper for the upload path.** No caller exists. Dead
  security code reads, to the next lane, as a control that is already in place.
- **No re-probe of the live database**, and no write of any kind.

## 5. What this lane found that the previous six did not

**The card the 2026-10-04 lane filed to Andy has not reached the queue.**

That lane replaced its in-report card with an abbreviated one that dropped the
`recommend:` and `reason:` lines, and its report is only three commits deep in
the branch named by this lane's brief ("last went out 2026-10-04"). Whatever
the cause — merge policy, or a card that did not parse — the observable result
is that the 1053 card is in **no** copy of `ANDY_DECISION_QUEUE.md` on this
host:

```
grep -c "service-role holder" /var/tmp/workload5450-oct5-candidate/ANDY_DECISION_QUEUE.md  -> 0
grep -c "portfolio_uploads"   /opt/work/loop_serve/ANDY_DECISION_QUEUE.md                  -> 0
grep -c "1053"                (all four queue copies)                                      -> 0
```

So the item is not "waiting on Andy" — it is **not in front of him**, which is
why an eighth lane was issued at it. This lane re-files the card **complete**
(all eight fields, `recommend: A`, `default: A`) rather than in the abbreviated
form. That is the whole of what a lane in this repo can contribute to 1053, and
it is worth a lane: every other sentence of §1–§4 has been established by six
prior lanes and does not need establishing again.

## 6. Item ids

| id | status | one line |
|---|---|---|
| 1053 | **DECISION** | Not a code defect and not fixable from this repo: the DDL belongs to bond-data, there is no FK target (`client_entitlements` 404s), and the only thing standing between the estate and the eight-line grant change is a name — who holds the bond-data service-role key. Card filed below. |

`FIXED: none`, `ALREADY_FIXED: none`. Listing 1053 as FIXED would shrink the
package while `POST /portfolio_uploads` still returns `201` and `client_id` is
still free text the caller chooses. A report does not close a security item.

**No `lane-handoffs` block, deliberately.** Two prior lanes re-issued a
`bond_data_mcp` handoff for this work and it dispatched a lane at eight lines of
SQL that nobody in that repo holds the credential to run either. What the item
lacks is a credential holder, not a lane.

## 7. Tests run

None, and none is appropriate: no executable file was changed, and §4 explains
why no test can be written here that observes this item. The suite was not run
because running it would say nothing about any change made by this lane.

## 8. What needs a human

One thing: **the name in §1(c)'s card.** Everything else about 1053 is already
written down — the statement is §3 of `.cmux/decisions/1053-tier2-upload-isolation.md`,
its safety is established (no-op at zero rows), and the README no longer advises
against it.

---

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 1053
-->

<!-- lane-decisions
item: 1053
covers: 1053
question: Will you name the holder of the bond-data service-role key and have them run the grant statement (ENABLE ROW LEVEL SECURITY on public.portfolio_uploads and public.portfolio_upload_evidence, plus REVOKE INSERT, UPDATE, DELETE FROM anon, authenticated) against https://xdgicslrdudsqlsudsgv.supabase.co?
context: The statement is eight lines, it is written out in full in section 3 of .cmux/decisions/1053-tier2-upload-isolation.md, and a live probe on 2026-09-27 returned 201 from an anonymous POST to portfolio_uploads while the same publishable key read 1,295 transactions, 112 holdings and 2,566 cashflows - so eight lanes have now been sent at item 1053 without any being able to run it, and the card filed on 2026-10-04 did not reach this queue.
option A: Name the service-role holder now and have them run the statement as written; client_id stays free text and per-client RLS policies stay with the estate Bucket D programme. Both upload tables are at zero rows, so this is a no-op for every reader that exists today.
option B: Leave the grant change until the client_id FK target is settled (xt-auth email vs a new clients table), so identity and isolation land in one migration, and accept that anonymous INSERT/UPDATE/DELETE on the upload tables and public reads of transactions, current_holdings and cashflows stay open meanwhile.
recommend: A
reason: Turning RLS on with no policies closes the anonymous write and the public read in the same eight lines, while the FK choice buys nothing until that anonymous write is closed and it governs 160 tables in an audit dated 2026-05-20.
default: A
-->
