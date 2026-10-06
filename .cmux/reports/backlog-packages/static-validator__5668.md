# static-validator / 5668 — write `validate_portfolio/persistence.py`

**Verdict: DECISION.** No code change lands from this lane. The file the card
names does not exist, the package it would live in does not exist, and the
hosted half of the ask depends on a key no lane holds.

## What the item asks for

> Hosted mode must write parent `portfolio_uploads` and child
> `portfolio_upload_evidence` rows to bond-data Supabase (migration applied
> 2026-05-12); `PERSISTENCE=local_file` must write a JSON snapshot beside the
> HTML.
> Wanted result: Both persistence paths implemented and tested; hosted rows
> verifiable in Supabase.

Reviewer location given: `validate_portfolio/persistence.py`.

## What is actually in the tree

Every one of these was checked in this working copy
(`proposal/mini-5668-1006232751`) on 2026-10-07:

- **The file does not exist.** There is no `validate_portfolio/` directory, and
  `grep -rn "validate_portfolio" .` returns nothing outside `.git`.
- **The package does not exist.** The repo's Python package is
  `python/src/static_validator/` (`adapter.py`, `canonicalize.py`, `cli.py`,
  `derivations.py`, `gemini_extractor.py`, `hashes.py`, `validate.py`,
  `wire.py`). There is no portfolio, report, renderer or upload module in it.
- **`PERSISTENCE` does not exist.** `grep -rn "PERSISTENCE" .` finds no env var,
  no mode switch and no `local_file` string anywhere in `python/`, `mcp/` or
  `schema/`.
- **No HTML to sit beside.** `grep -rln "portfolio" python mcp` returns no
  files. The "JSON snapshot beside the HTML" half has no producer to attach to.
- **No column spec to write against.** `schema/` holds only the validate wire
  schemas (`validate_request`, `validate_response`, `published_record`,
  `tier_hashes`, `structural_flags`, `source_reference`,
  `where_to_find`). There is no DDL for `portfolio_uploads` or
  `portfolio_upload_evidence`, and no migration file for them exists on this
  host — item 1053 established the same thing from the other direction
  (`.cmux/decisions/1053-tier2-upload-isolation.md`, and the README's note that
  "There is no `migrations/006` file: no lane has written one in any repo on
  this host").
- **The write path is unbuilt on purpose.** `README.md:97` states it plainly:
  "**The upload write path is not built** — no code in this repo reads or writes
  either table, so the exposure is a property of the database, not of shipped
  code."

So there is nothing to modify and no "already fixed" commit to cite: no commit
in this repo has ever touched `portfolio_uploads` from application code, and
`git log --grep 5668` is empty.

## Why this is a decision and not a FIX

The card presents "write persistence.py" as a self-contained coding task. It is
not, because the hosted path cannot be written safely *or* verified from here:

1. **It needs the bond-data service-role key.** `README.md:97` and decision 1053
   both fix the architecture: the write goes "through the same service under its
   service key, and the publishable key stays on the server." No lane holds the
   service-role key; that is the open owner question in 1053 ("who holds the
   service-role key that can apply a one-line grant change to two `bond-data`
   tables?").
2. **The tables accept anonymous writes today.** Decision 1053 measured
   `POST /portfolio_uploads -> 201` and `PATCH -> 204` with the
   anon-equivalent publishable key, with `client_id` free text. The grant change
   that closes this — `ENABLE ROW LEVEL SECURITY` + revoke on both tables — is
   written out in §3 of that decision, is **not blocked by anything**, and has
   not been run. Building a hosted writer now means either using a key no lane
   holds or holding the publishable key in a write path, which is precisely what
   the README forbids.
3. **"Verifiable in Supabase" is out of reach.** Verifying hosted rows requires
   the same service-role key. A lane that wrote the code could not meet the
   card's own wanted result.
4. **The local half is not self-contained either.** `PERSISTENCE=local_file`
   presumes an existing HTML producer and a caller that passes upload records in.
   Neither exists, and the evidence-row shape is undocumented in this repo, so a
   `persistence.py` would be a guessed schema in a new package with no caller and
   no test fixture — fabrication, not a fix.

The card's own precondition line is the tell: it cites a "migration applied
2026-05-12". No such migration exists in this repo, and 1053 recorded that the
grant change that *should* precede any writer has never been applied. The card
has been written as if a prerequisite that is still open were already done.

## The question, in one line

**Who holds the bond-data service-role key and will run the 1053 RLS/revoke
statement on `portfolio_uploads` and `portfolio_upload_evidence`, and in which
repo does the portfolio renderer live that `persistence.py` is supposed to sit
beside — because until both are named, a hosted writer either cannot exist or
would be an unauthenticated write path into client tables.**

## What remains (for whoever answers it)

- Hosted persistence path: unbuilt, blocked on key holder + RLS grant + a client
  (`POST /tools/client_portfolio_uploads` under the service key).
- Local JSON snapshot path: unbuilt, blocked on naming the package/HTML producer
  and the snapshot schema. This is the smaller ask and the only one that could be
  built without the key — but it still needs a home.
- Item 1053's grant change: still not applied; still needs the key holder.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 5668
-->
