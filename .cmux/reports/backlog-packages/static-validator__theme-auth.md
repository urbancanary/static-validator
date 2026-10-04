# static-validator / `theme:auth` — package report

**Lane:** `lane/auto-static-validator-theme-auth-10042212`
**Slice:** item 1053 (the only open item in the package).
**Commits:** two — `79271a9` (`README.md`, `SCHEMA.md`), `fb56e62`
(`.cmux/decisions/1053-tier2-upload-isolation.md` §8). **Tests:** 285 passed
(`python/`), 8 passed (`mcp/`).

**Result: item 1053 is closed as a `DECISION`, and this lane can now put the
actual statement in front of Andy.** The card filed by the lane before this one
asked him to approve applying
`bond_data_mcp/migrations/006_PREPARED_portfolio_upload_rls.sql` — **a file that
does not exist on this host.** Ten lanes have read that file name; none has
opened it, because there is nothing to open. That is the defect this lane fixes,
and it is the reason the queue has been holding a question about an artefact
rather than about a grant change.

---

## 1. What changed, and why a seventh read of the item was not enough

The item is two sentences about `portfolio_uploads` / `portfolio_upload_evidence`
in bond-data: tighten `client_id` to a FK, add RLS so the anon key cannot read
another client's uploads. Six lanes have now been sent at it. Their findings all
hold and I re-verified them in the tree rather than inheriting them:

- No Supabase URL, no key read, no `portfolio_uploads` reference, no HTTP or DB
  client in `python/src` or `mcp/src`. `find . -name '*.sql'` returns nothing;
  there has never been a `migrations/` directory here. Tier 2 is two README
  lines and a decision record.
- The exposure is live and was measured, not inferred
  (`.cmux/decisions/1053-tier2-upload-isolation.md` §2, 2026-09-27): with the
  publishable key, `POST /portfolio_uploads` returned `201` and `PATCH` `204`,
  and the same key read `transactions` (1,346), `current_holdings` (112) and
  `cashflows` (2,566). I did **not** re-probe; re-running a write against a
  table with no write control would add risk to a measurement three lanes have
  already reproduced.

So the sixth "read the item again and report" would have produced nothing, and
reporting `DECISION: none` a fourth time is what kept 1053 on the board. What
this lane did instead was trace **the only artefact anyone has ever cited as
progress on it**:

| Commit / file | Says |
|---|---|
| `a778013` (2026-09-27) | "no SQL file anywhere", and in the same body: "Applying bond-data's `migrations/006_PREPARED_portfolio_upload_rls.sql` steps 1+2 *before* that path exists makes no wedge read nothing" |
| `64c524e` | first `lane-handoffs` block carrying the name `006_PREPARED…`, tagged `repo: bond_data_mcp` |
| `b181706` / `b3918c1` | two package reports state the file "is prepared and committed", "is written and committed on `proposal/portfolio-upload-rls-1053`" |
| the card delivered to Andy | "will they apply `migrations/006_PREPARED_portfolio_upload_rls.sql` steps 1+2?" |

`git log -S 006_PREPARED` over every branch in this checkout: the string appears
nowhere before `a778013`, and never in a `.sql` file. The two reports that say
it is "committed on a branch" do not name where; the migration's own repository
was never named either — the handoff says `bond_data_mcp` and the reports say
`bond-data`, which are different projects in this estate. **The provenance of
the file cannot be checked from here, and the credential holder Andy would have
to ask has never been told what to run.**

## 2. Grouping the symptoms into underlying defects

Same four defects as the previous two lanes, with the state of each corrected:

| # | The defect | Who closes it | State after this lane |
|---|---|---|---|
| **B1** | Anon holds `INSERT`/`UPDATE`/`DELETE` on both upload tables, and the publishable key reads the wider bond-data surface | **bond-data + the named service-role holder** | Unchanged — and now the only thing standing between it and being run is a name. §3 below is the statement, in full, in the card. |
| **B2** | `client_id` is free text, so any writer asserts their own identity | **Andy + bond-data** | Unchanged. Still the correct second step, still after B1: an FK over an anon-writable column constrains nothing. |
| **B3** | RLS policies scoped through `client_entitlements` | **estate Bucket D programme** | Unchanged, blocked on B2. `client_entitlements` 404s on bond-data. |
| **B4** | **The estate's written record points at a migration file that does not exist, and the README used it to advise delaying the one change nobody disputes** | **this repo** | **These commits.** |

**B4 is the one this repo owns, and it is not cosmetic.** The README's v0.6
line ended with *"Applying bond-data's `migrations/006_PREPARED_…` steps 1+2
**before that path exists** makes no wedge read nothing."* Read as advice —
which is how a conditional attached to a file name gets read — it says: do not
apply the grant change yet, there is a wedge to break. There is no wedge. A path
that does not exist cannot be broken by RLS, and enable-RLS-with-no-policies is
a no-op for every reader that exists today (there are none) and a hard stop for
every reader that should not. The sentence was, in effect, a reason to leave
anonymous `INSERT`/`UPDATE`/`DELETE` open on both tables and the publishable key
reading 1,346 transactions, on the strength of a file that is not there.

## 3. What I changed

1. **`README.md`**, v0.6 line — the phantom `006_PREPARED…` sentence is gone.
   It now states the grant change explicitly (enable RLS on both tables with no
   policies; revoke `INSERT`/`UPDATE`/`DELETE` from `anon`, `authenticated`),
   says it **is not blocked** by the missing write path or the identifier
   question and should not wait for either, points at §3 of the decision record
   where the statement is written out, names the one thing it needs (the
   bond-data service-role key, which no lane holds), and records that no
   `migrations/006` file exists. The surrounding sentences were kept to the
   narrowest true claim: "no code reads or writes either table" rather than "no
   code in this repo".
2. **`SCHEMA.md` §8** — one bullet: **client identity is out of scope for the
   protocol**. `validate_request.schema.json` sets `additionalProperties: false`
   for exactly this reason, so this is where the server-side-identity rule stops
   being a preference and becomes a consequence of the wire contract.
3. **`.cmux/decisions/1053-tier2-upload-isolation.md` §8** — the provenance
   trace above, so the next lane does not re-derive it or cite the file again,
   and a correction of §4, which said the statement was "handed off instead,
   verbatim, below" when nothing was below. §3 (the SQL) is unchanged and still
   governs.

Documentation only. No code, no SQL file committed, no migration applied or
prepared, no endpoint, no client-facing financial number (no price, yield,
spread, duration, NAV, cash or P&L touched), no settled trade re-derived.

## 4. Deliberately not changed

- **No `.sql` file in this repo.** Writing `006_PREPARED_…` here would create
  the very artefact whose absence caused this item — a second copy, in a repo
  with no migration runner, that no credential holder would open. The statement
  lives in §3 of the decision record, which is a file a person reads.
- **No `clients` table definition, no policy SQL.** Writing either down
  *answers* the estate's Bucket D identifier question by accident, for a project
  that does not own it, for two tables that are two rows of a 160-table audit.
- **No client, endpoint or helper for the upload path.** There is no caller. A
  `POST /tools/client_portfolio_uploads` client for a service nobody has
  confirmed exists is dead code on a security path, and dead security code reads
  as a control that exists.
- **No test.** No executable file changed. A test asserting "this repo does not
  hold the publishable key" passes today and passes tomorrow and catches
  nothing.
- **No re-probe of the live database.** Three lanes have measured it; one of the
  measurements was a write to a table with no write control.

## 5. Item ids

| id | status | one line |
|---|---|---|
| 1053 | **DECISION — the card is filed below and is now answerable** | Neither half has a fix in this repo (§1) and no lane in this repo can apply one: B1 needs a credential nobody has named, B2 is the estate-wide identifier choice. There is no code defect left to find here; there is one grant change waiting on one person. |

`FIXED: none`, `ALREADY_FIXED: none`. Listing 1053 as FIXED would shrink the
package while `POST /portfolio_uploads` still returns `201` and `client_id` is
still free text. A README sentence does not close a security item — but a card
that names the statement instead of a missing file is what lets Andy close it.

**No `lane-handoffs` block, and that is deliberate.** Two prior lanes re-issued
a `bond_data_mcp` handoff for this work; the work is eight lines of SQL in the
decision record, it is already written, and what it lacks is a credential, not a
lane. Re-issuing it would dispatch a third lane at the same eight lines — the
re-dispatch that cost a whole lane in `static-validator__handoff-332.md`.

**Decision cards.** The prior lane's card on 1053 was written against the
missing file, so it is superseded below rather than duplicated: a card is filed
under `covers: 1053` naming the statement and the credential question. **I did
not re-file the identifier question** — `DISPOSITION 20260921-13` already
records it (new `clients` table over the xt-auth email, because a policy keyed
on an email that can change is not a stable id) and it is the estate's Bucket D
question, dated 2026-05-20, governing 160 tables. Carding it here would split
one question across two queue entries, which is what the queue's group-by-
decision rule exists to prevent.

## 6. Tests run

```
cd python && PYTHONPATH=src python3 -m pytest tests -q                  ->  285 passed
cd mcp    && PYTHONPATH=src:../python/src python3 -m pytest tests -q    ->  8 passed
```

Run because the package claims a passing tree and the next lane should inherit a
green one; nothing executable was touched. The `mcp/` suite needs `python/src`
on `PYTHONPATH` in this environment (`ModuleNotFoundError: static_validator`
otherwise) — a known environment quirk, not a defect. I did not run any suite
outside this package.

## 7. What needs a human

**Seven lanes have now been sent at 1053 and none has changed a line of
product code**, because the fix is eight lines of SQL against a database this
repo does not own, and the thing standing between the estate and those eight
lines is a **name**: who holds the bond-data service-role key. The card below is
the seventh attempt to get that name, and it is a better one than the sixth,
because it no longer asks Andy to approve something he cannot look at.

Two smaller things worth naming, both reporting problems rather than decisions:

- **The `bond_data_mcp` / `bond-data` ambiguity in the handoff blocks.** The
  migration is cited under one project name and claimed to live in the other,
  and neither has been checked. If a `bond_data_mcp` lane does hold a written
  `006`, then the file exists there and the note in `README.md` and §8 of the
  decision record is wrong for that repo — the statement is the same either way,
  which is why both now point at the SQL rather than at a path.
- **How the file name entered the record.** Commit `a778013` warned in the same
  breath that there was no SQL file, and three later documents cited the file
  without opening it. That is the mechanism worth watching: a name repeated in a
  report reads as a landed artefact to the next lane, and it took a lane whose
  only job was to check to find that it was not one.

---

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 1053
-->

<!-- lane-decisions
item: 1053
covers: 1053
question: Will you name the holder of the bond-data service-role key and have them run this statement against https://xdgicslrdudsqlsudsgv.supabase.co: ALTER TABLE public.portfolio_uploads ENABLE ROW LEVEL SECURITY; ALTER TABLE public.portfolio_upload_evidence ENABLE ROW LEVEL SECURITY; REVOKE INSERT, UPDATE, DELETE ON public.portfolio_uploads, public.portfolio_upload_evidence FROM anon, authenticated;
context: The statement is eight lines, it is written out in full in section 3 of .cmux/decisions/1053-tier2-upload-isolation.md, and a live probe on 2026-09-27 returned 201 from an anonymous POST to portfolio_uploads while the same publishable key read 1,346 transactions, 112 holdings and 2,566 cashflows - so seven lanes have been sent at item 1053 without any of them being able to run it, and the card previously filed against this item asked you to approve a migration file that does not exist on this host.
option A: Name the service-role holder now and have them run the statement as written, leaving client_id as free text and per-client RLS policies to the estate Bucket D programme; the statement is a no-op for every reader that exists today because both upload tables are at zero rows.
option B: Leave the grant change until the client_id FK target (xt-auth email vs a new clients table) is settled, so identity and isolation land in one migration, and accept that anonymous INSERT/UPDATE/DELETE and public reads of transactions, current_holdings and cashflows stay open meanwhile.
recommend: A
reason: Turning RLS on with no policies closes the anonymous write and the public read in the same eight lines, while the FK choice buys nothing until the anonymous write is closed and it governs 160 tables in an audit dated 2026-05-20.
default: A
-->
