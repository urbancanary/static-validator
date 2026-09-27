# static-validator — package `handoff:1053`

**Lane:** `lane/auto-static-validator-handoff-1053-09271654`
**Slice:** item 1053, the only open item. Handed to this repo by
`auto-bond-data-mcp-handoff-1053-09271642`.
**Commit:** one — `a778013`. **Tests:** 285 passed (`python/`), 8 passed (`mcp/`).
**Result: the handoff's premise does not hold against this repo. There is no read and no write
here to move.**

---

## 1. The handoff, and what it assumes

The bond-data lane handed over this, verbatim:

> portfolio_uploads and portfolio_upload_evidence are anonymously readable AND writable today
> (verified 2026-09-27: anon read 200, POST 201, PATCH 204). Before bond_data_mcp/migrations/006
> steps 1+2 (ENABLE ROW LEVEL SECURITY, REVOKE INSERT/UPDATE/DELETE FROM anon/authenticated) are
> applied, the validator's read and write of those two tables must move off the publishable key:
> read via POST bond-data /tools/client_portfolio_uploads ... and write via the service key
> through a bond-data endpoint. 006 is prepared and not applied, so nothing is broken today —
> but applying it before this move makes the validator read nothing.

Every sentence of that is true **except the subject of the last one**. "The validator" does not
read or write those tables, and cannot, because the code that would is not in this repository.

## 2. Verified, not inherited — the same check the last lane taught us to make

The `theme:auth` lane (`.cmux/reports/backlog-packages/static-validator__theme-auth.md` §5) ended
with: *"The gap was not analysis — it was that neither lane fetched the key and looked."* So this
lane looked, at the thing that can actually be looked at here.

```
grep -rn "supabase|SUPABASE|upload" python/ mcp/     -> one hit, and it is not a client
python/tests/test_adapter.py:440:  sources=[{"id": "supabase-bond_identity", ...}]
```

That is a source-id **string** in a wiring fixture. Against the whole repo:

| Searched | Found |
|---|---|
| Supabase URL / project ref `xdgicslrdudsqlsudsgv` | none |
| `get_api_key`, `auth_client`, any key read | none |
| `os.environ` for anything but `PORT`/`HOST`/`DATABASE_URL` | none |
| `portfolio_uploads`, `portfolio_upload_evidence` | none |
| any HTTP client, DB client or connection string in `python/src` or `mcp/src` | none |

The only other Supabase references are in `experiments/wnbf_audit_2026_05_11/` — a research
workspace that loads the **reference** corpus (`load_to_supabase.py`), writes no upload table, and
is not a product path. Tier 2 is a README row, a roadmap bullet and a decision record. The product
is Tier 0 / Tier 1, and `mcp/src/static_validator_mcp/server.py` is local stdio with three tools and
no notion of a caller.

I did **not** re-run the anon probes. The bond-data lane measured them on 2026-09-27 (anon read
`200`, `POST` `201`, `PATCH` `204`) and the `theme:auth` lane measured the same thing independently;
re-probing a live database would have produced a third identical measurement at the cost of writing
rows to a table with no write control. The exposure is real and I am not disputing it. What I am
disputing is that it has a fix in this repo.

## 3. Grouping the symptoms into underlying defects

One item, three defects, and they sort by **who can close them** — the same sort the previous lane
made, with the middle row now measured:

| # | The defect | Owner | State after this lane |
|---|---|---|---|
| **B1** | Anon holds `INSERT`/`UPDATE`/`DELETE` on both upload tables, and the publishable key reads the per-client surfaces | **bond-data** — needs the service-role key | Unchanged. Prepared as `migrations/006` steps 1+2. A lane in *this* repo cannot run it. |
| **B2** | `client_id` is free text | **Andy + bond-data** | Unchanged, decided in principle (006 step 3a). Card filed by the bond-data lane. |
| **B3** | RLS policies + `client_entitlements` scoping | **estate Bucket D programme** | Blocked on B2; the table it reads (`client_entitlements`) 404s on bond-data. |
| **B4** | **The Tier 2 read/write path does not exist in static-validator** | **this repo** | **This commit.** Stated in the README so the ordering constraint is written down where the path will be built. |

**B4 is the one this repo owns, and it is the reason the handoff cannot be executed here.** The
handoff is a *sequencing* instruction — "move the validator's read before 006 lands". You cannot
move a read that was never written. The bond-data lane wrote "the validator's read and write" as
though the wedge were shipped, and the `theme:auth` lane's README edit ("the tier ships behind an
isolation boundary") reinforced the same false impression from this side. Both are now corrected.

## 4. What I changed — one commit, `a778013`, README only

Two edits, no code:

1. **The Tier 2 table row** said we see "the portfolio you upload, under explicit terms of
   service" — present tense, as if the upload existed. It now says the upload path is **not built**:
   no code in this repo writes the Tier 2 upload tables.
2. **The v0.6 roadmap line** kept the 2026-09-27 measurement (anon `INSERT`/`UPDATE`, free-text
   `client_id`) and now adds the thing the next lane needs in order to do this correctly: the
   exposure is a property of the database, not of shipped code; the future path must not hold the
   publishable key — read goes through `POST /tools/client_portfolio_uploads`, write through the
   same bond-data service under its service key; and **applying 006 steps 1+2 before that path
   exists makes no wedge read nothing**, because there is no wedge.

No client-facing financial number, price, yield, spread, duration, NAV, cash or P&L is touched, and
no settled trade is re-derived.

**Deliberately not done:**

- **No client, endpoint or helper written here.** A `POST /tools/client_portfolio_uploads` client
  for a service that has no caller would be dead code on a security path, and dead security code
  reads as a control that exists. It belongs in the same change that builds the upload UI.
- **No test.** There is no code under test. A test asserting "this repo does not hold the
  publishable key" would pass today and pass tomorrow and would not have caught anything.
- **No `DATA_ACCESS.md` / policy document.** Writing a rule that the upload path must not hold the
  publishable key is worth something only when someone is about to write that path; the v0.6 line
  carries it there. A standalone doc is a file nobody reads, which is the failure the bond-data lane
  already refused to repeat in §4 of its own report.
- **No SQL file.** The statement is prepared in `bond_data_mcp/migrations/006_PREPARED_…` and the
  standing rule is that no lane applies a migration. A second copy here is a second thing to drift.

## 5. Item ids

| id | status | one line |
|---|---|---|
| 1053 | **still open** — `FIXED`, `ALREADY_FIXED` and `DECISION` are all none from this repo | Neither half has a fix in this repo (§2). The RLS half (B1) needs the bond-data service-role key and is prepared there; the FK half (B2) is Andy's identifier choice, carded by the bond-data lane and **not re-carded here** (§6). |

`FIXED: none`, `ALREADY_FIXED: none`, `DECISION: none`. This is a fourth lane on 1053 and it closes
nothing — deliberately. `POST /portfolio_uploads` still returns `201`, and a README sentence does
not close a security item; listing it as FIXED would shrink the package while the hole is open,
which is the exact failure `theme:auth` §4 was written to prevent.

**And no handoff block for `bond_data_mcp` this time.** The bond-data lane has already landed
`migrations/006_PREPARED_portfolio_upload_rls.sql` + `POST /tools/client_portfolio_uploads` on
`proposal/portfolio-upload-rls-1053`. Re-issuing that handoff would dispatch a second lane at work
that is already committed on a branch, which is how item 332 got re-dispatched (see
`static-validator__handoff-332.md`). The migration needs the **service-role key**, which is a
credential, not a lane: that is the card the bond-data lane filed, and it is the only thing standing
between 006 and applied.

## 6. What needs a human — and why this lane filed no card

The bond-data lane filed the card on 1053 (service-role holder / scope of the grant change). The
`theme:auth` lane filed the bigger Bucket D one. Both are in the queue and both are the right
question. **This lane files nothing**, because every question it can see is already carded:

- *Who applies 006 steps 1+2?* — carded by the bond-data lane under 1053.
- *Which identifier does `client_id` point at?* — carded by the bond-data lane under 1053.
- *Do the other three Bucket D surfaces get the same treatment?* — carded by the `theme:auth` lane.

A second card under the same id would split one question across two queue entries, and the queue's
own rule is group-by-decision for exactly that reason.

The one thing worth naming to a human, and it is a *reporting* problem rather than a decision:

**Three lanes have now been sent at 1053 and none of them changed any code in the product.** The
first two reasoned from the item text; the third measured the database and found the exposure real;
this one measured the repo and found the code absent. The item is filed against `static-validator`
and its fix lives entirely in `bond-data`'s database and in a credential nobody has named. Until
someone is named as the service-role holder, the next lane will reach the same three conclusions.

---

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: none
-->
