# static-validator / `theme:auth` — package report

**Lane:** `proposal/static-validator-theme-auth-10041104`
**Slice:** item 1053 (the only open item in the package).
**Commit:** one, `b3918c1` — `README.md` Tier 2 bullet. **Tests:** 285 passed
(`python/`), 8 passed (`mcp/`).

---

## 1. Reading the item, and what four prior lanes already established

Item 1053 asks for two things against `portfolio_uploads` /
`portfolio_upload_evidence` in bond-data Supabase: (1) migrate `client_id`
from free text to a proper FK, (2) add RLS policies so the anon key cannot
read another client's uploads.

Four lanes have now been sent at this item. Their findings, which I re-checked
against the tree rather than inherited, all hold:

- **`.cmux/decisions/1053-tier2-upload-isolation.md`** (theme:auth,
  2026-09-27) fetched the key the sanctioned way and measured the live
  database: anon `GET` reads fine, `POST` returned `201` with a `client_id`
  the prober chose, `PATCH` returned `204`. `client_entitlements` 404s
  (`PGRST205`). Its conclusion — the exposure is a property of the database,
  and migration order is forced (grant first, FK second) — is the correct
  framing and I did not dispute it.
- **`static-validator__handoff-1053.md`** measured the repo: no Supabase URL,
  no key read, no `portfolio_uploads` reference, no HTTP or DB client anywhere
  in `python/src` or `mcp/src`. Tier 2 is a README row and a decision record.
  I re-verified this and it is still true — so nothing in this repo can move
  `client_id` or write an RLS policy.
- **`static-validator__theme-auth-10011132`** changed nothing and repeated a
  `bond_data_mcp` handoff.
- **`static-validator__theme-pricing`** fixed 1043 by *filing a decision
  card*. That is the precedent this lane follows for 1053 (§5), and it is why
  the card below is written rather than a fifth "handoff" block.

## 2. Grouping the symptoms into underlying defects

One item, four defects, sorted by who can close them. This is the same sort
`handoff-1053.md` made, and I reached the same four — with B1's scope
corrected upward:

| # | The defect | Who can close it | State after this lane |
|---|---|---|---|
| **B1** | Anon holds `INSERT`/`UPDATE`/`DELETE` on both upload tables, **and** on the wider bond-data surface — the same probe read `transactions` (1,295 / now 1,346 rows), `current_holdings` (112) and `cashflows` (2,566) with the publishable key | **bond-data + the holder of the service-role key** | Unchanged. Two of those tables are 1053; the rest is the estate Bucket D programme. No lane in this repo can apply a grant change. |
| **B2** | `client_id` is free text, so any writer asserts their own identity | **Andy + bond-data** | Unchanged. The identifier choice is real and undecided. |
| **B3** | RLS policies with `client_entitlements` scoping | **estate Bucket D programme** | Blocked on B2. The table the audit's policy shape reads from does not exist on bond-data. |
| **B4** | **Nothing in the product tells a reader that the Tier 2 upload path is unbuilt.** The roadmap line says so; the tier description contradicted it in present tense | **this repo** | **This commit.** |

B4 is the only one this repo owns, and it is not cosmetic. The `README.md`
Tier 2 bullets read:

> - You upload the portfolio file to `validator.x-trillion.com`. We process it
>   on our infrastructure.

while no code in this repo reads or writes either upload table. A reader —
including the next lane, and including whoever schedules the bond-data
migration — concludes the path is shipped, and the §1 ordering constraint
(grant change *before* the first row is written, FK *after*) then looks
already satisfied. `handoff-1053.md` §4 said exactly this about a previous
sentence ("the tier ships behind an isolation boundary"), and the tier
description was left behind when that one was corrected. This commit closes
the remaining half of that same fix, at the same producer.

## 3. What I changed

`README.md`, Tier 2 bullet 1 — present tense to not-built, pointing at the
v0.6 line that already carries the measured state and the ordering
constraint. Documentation only: no code, no schema, no migration, no wire
contract, no client-facing financial number (no price, yield, spread,
duration, NAV, cash or P&L is touched), and no settled trade re-derived.

## 4. Deliberately not changed

- **No SQL file here.** The grant change is prepared in bond-data's
  `migrations/006_PREPARED_portfolio_upload_rls.sql` and the standing rule is
  that no lane applies a migration. A second copy in this SDK is a second
  thing to drift, and a file nobody with the credentials opens
  (`.cmux/decisions/1053-tier2-upload-isolation.md` §4).
- **No `clients` table definition.** Writing one down *answers* the estate's
  Bucket D identifier question by accident, for a project that does not own
  it.
- **No client, endpoint or helper for the upload path.** There is no caller
  yet; dead security code reads as a control that exists.
- **No `Data_Access.md`-style policy document.** The rule belongs where the
  path will be built, which is the v0.6 line, and it is already there.
- **No test.** No executable file changed. A test asserting "this repo does
  not hold the publishable key" would pass today and tomorrow and catch
  nothing.

## 5. Item ids

| id | status | one line |
|---|---|---|
| 1053 | **still open, and now filed as a decision** | Half of it (B1) is a credential nobody has named; the other half (B2) is the identifier choice. Neither is a code defect in this repo — five lanes have now confirmed that. The card below is the mechanism that closes it. |

`FIXED: none`, `ALREADY_FIXED: none`. Listing 1053 as FIXED would shrink the
package while `POST /portfolio_uploads` still returns `201` and `client_id`
is still free text. A README sentence does not close a security item.

**No `lane-handoffs` block this time, and that is deliberate.** The theme:auth
lane at `10011132` re-issued the `bond_data_mcp` handoff, but the bond-data
lane had already landed `migrations/006_PREPARED_portfolio_upload_rls.sql` and
`POST /tools/client_portfolio_uploads` on `proposal/portfolio-upload-rls-1053`.
Re-issuing it dispatches a second lane at work that is already on a branch —
the exact re-dispatch that cost a whole lane in `static-validator__handoff-332.md`.
Nothing in bond-data needs a lane; it needs a credential.

## 6. Tests run

```
cd python && PYTHONPATH=src python3 -m pytest tests -q     ->  285 passed
cd mcp && PYTHONPATH=src:../python/src python3 -m pytest tests -q  ->  8 passed
```

Run because the change is in `README.md` only and the package claims a
passing tree; nothing executable was touched. The `mcp/` suite needs
`python/src` on `PYTHONPATH` in this environment (`ModuleNotFoundError:
static_validator` otherwise) — worth knowing for the next lane, not a defect.

## 7. What needs a human

The reporting problem, and it is the fifth time it has been worth saying:
**five lanes have been sent at 1053 and none of them changed any code in the
product**, because the fix is not in this repo and cannot be. Item 1053 is
filed against `static-validator`; its fix lives in bond-data's database, and
the thing standing between it and the fix is a **named holder of the
service-role key**. Until someone is named, the sixth lane will reach the same
conclusions.

A second thing, which is a reading correction rather than a decision: the
item's disposition recommends a new `clients` table over the xt-auth email
as the FK target. I agree with the recommendation and it changes nothing
about ordering — **the grant change is still first**. Tightening `client_id`
to a FK while `anon` holds `INSERT` buys nothing, because a caller who can
insert any row can insert any `client_id` the FK permits. Whoever applies
`006` should apply steps 1+2 and not wait for the identifier to be settled.

---

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 1053
-->

<!-- lane-decisions
item: 1053
question: Who is the named holder of the bond-data service-role key, and will they apply bond-data migrations/006_PREPARED_portfolio_upload_rls.sql steps 1+2 (ENABLE ROW LEVEL SECURITY on portfolio_uploads and portfolio_upload_evidence, REVOKE INSERT/UPDATE/DELETE FROM anon, authenticated) to https://xdgicslrdudsqlsudsgv.supabase.co?
context: The file is written and committed on proposal/portfolio-upload-rls-1053, and a live probe on 2026-09-27 returned 201 from an anonymous POST to portfolio_uploads, so five lanes have now been sent at item 1053 without any of them being able to run the one statement that closes it.
option A: Name the service-role holder and apply 006 steps 1+2 now, leaving client_id as free text until the identifier is decided; the FK and client-scoped policies follow and are not blocked by this.
option B: Apply 006 steps 1+2 only when the client_id FK target (xt-auth email vs a new clients table) is settled, so identity and isolation land in one migration.
recommend: A
reason: Enable-RLS-with-no-policies is a no-op for every reader that exists today and a hard stop for every reader that should not, while the FK choice buys nothing until the anonymous write is closed.
default: A
-->
