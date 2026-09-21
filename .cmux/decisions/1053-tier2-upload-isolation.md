# 1053 — Tier 2 upload isolation: what governs a client-facing data boundary

**Status:** the code half is recorded here; one decision is outstanding.
**Owner question:** what is the root client identifier of record for the
hosted tier?
**Blocks:** any external client landing on Tier 2. Nothing internal.
**Related:** item 1046 (no renderer in repo; no DNS for the tier's host),
item 1049 (this repo's existing decision-record pattern), and the estate's
RLS programme in `codebase-mcp/docs/SUPABASE_RLS_AUDIT_2026_05_20.md`.

This file is written because item 1053 keeps being issued to lanes as if it
were an ordinary code fix, and it is not one. Two lanes have now been spent
reading the same two sentences. What is recorded here is the part that could
be settled by reading code, so the next reader starts from it instead of
re-deriving it.

---

## 1. What the repo already guarantees, and what it does not

The package is named `theme:auth`, so the first thing worth knowing is how
little of the product depends on auth. In this repository, **almost none of
it does**, and that is deliberate rather than an omission:

- `schema/validate_request.schema.json` carries ISIN, locally computed tier
  hashes, a field-presence bitmap, and nothing else — `additionalProperties:
  false`. `schema/README.md` calls this property load-bearing, and
  `python/tests/test_wire_contract.py::test_field_value_in_request_rejected`
  fails if anyone ever adds a field that accepts a static value.
- `mcp/src/static_validator_mcp/server.py` is local stdio with three tools
  (`list_known_isins`, `fetch_canonical_record`, `validate_bond_static`) and
  no notion of a caller.
- Neither `python/src` nor `mcp/src` contains a database client, a Supabase
  reference, or an API key read. The SDK computes hashes; it does not know
  who the user is, and story-wise it never should.

So Tier 0 and Tier 1 are complete without any of this. **Tier 2 is the only
tier with a client identity problem**, and the reason is not that auth is
missing from the code — it is that Tier 2 stores what the client uploads.

## 2. Where Tier 2's data actually lives, verified

Item 1053 names `portfolio_uploads` and `portfolio_upload_evidence` as
`bond-data` Supabase tables. That is correct, and it is the whole of the
repo-side surprise: **nothing in this repository reads or writes them.**

```
$ grep -rn "portfolio_upload" \
    python/src mcp/src python/tests mcp/tests schema docs experiments
(no matches)
```

Nor does any other repository on this host: a `grep -rn portfolio_upload`
across `/opt/work` returns the `bond-data` RLS audit and nothing else. The
write path for these tables is the Tier 2 service — the thing envisioned at
`validator.x-trillion.com` — and that service does not exist in any checkout
here (item 1046 says the same about its renderer). The tables are a hosted
artefact with no code behind them yet.

That single fact decides most of this item:

- **1053 cannot be fixed in `static-validator`.** There is no file to change.
  This repo has no migrations directory (`git ls-files '*.sql'` is empty) and
  no database client. `schema/` is wire-format JSON Schema, a different
  contract entirely.
- **1053 cannot be handed to a build lane either.** A handoff dispatches a
  builder, and there is no builder to dispatch: the consumer does not exist.
- **But 1053 is also cheap to satisfy later**, because the tables are empty
  and unread. Fixing an isolation boundary at zero rows is a schema change;
  fixing it at ten thousand rows is a migration plus a disclosure question.

## 3. Which half is a decision, and which half is not

The item bundles two changes. They are not equally blocked.

**The half that needs a human decision.** The item offers two targets for
`client_id`: the xt-auth email, or a new `clients` table. The first is
attractive because something already exists to key against; it is also the
wrong shape for an access-control key, because emails change and entitlements
history does not. This is not a new observation — the estate already leans
the other way. The audit's Bucket D policy shape is:

```sql
portfolio_id IN (SELECT portfolio_id FROM client_entitlements WHERE client_id = ...)
```

and it groups `portfolio_uploads` and `portfolio_upload_evidence` with
`transactions`, `current_holdings`, `cashflows` and the `v_holdings_*` /
`v_portfolio_*` views. The audit then names its own blocker, section "What's
blocking immediate fix", third bullet:

> Bucket D needs the user-scoping column (`tenant_id` / `client_id` /
> `portfolio_id`) confirmed per table before policies can be written.

That bullet is dated **2026-05-20**. Item 1053 is the same question, asked
four months later, about two of the same tables. The table the policy shape
reads from — `client_entitlements` — does not exist on `bond-data`
(PostgREST returns `PGRST205`, "Could not find the table"). A draft migration
for a `client_entitlements` table does exist in the estate, but for a
different project: `codebase-mcp/docs/rls_client_entitlements_migration.sql`,
drafted 2026-06-07 against Orion (`ttkcqogfbklodhgfmiac`), still marked
`DO NOT APPLY BLINDLY`. So the estate has a precedent for the shape, and no
decision for the identifier.

**The half that is not blocked at all.** Read isolation is not the only
control on those tables, and it is not the one to reach for first. Supabase
grants `INSERT`/`UPDATE`/`DELETE` to the API roles by default. A plain
`REVOKE` on the two upload tables:

- closes anonymous *writes* today, independent of who `client_id` eventually
  points at, because it is a grant change and not a row filter;
- breaks nothing, because both tables are empty and nothing on this host
  writes them;
- does not pre-empt the identity decision, and is reversible.

A superset of it was already *decided*: the audit's "Recommended execution
order" step 5 is "All Bucket B (service-role only) — easy: `ALTER TABLE ...
ENABLE ROW LEVEL SECURITY;` with no policies." Enabling RLS with no policies
denies anon and authenticated both, which is exactly the shape wanted here —
and unlike a `REVOKE` it also closes reads. It does not need the scoping
column, because it has no policy that would use one. The audit is four months
old and that step has not run.

So: **RLS-enable with no policy, not a policy set, is the decision-free half.**
Enabling RLS on an empty table with no policies is a no-op for every reader
that currently exists (there are none) and a hard stop for every reader that
should not exist.

## 4. Why this repo is not writing the migration

A prepared SQL file is cheap, and a lane could commit one. It should not, for
a reason that is about ownership rather than effort:

- The tables belong to `bond-data`. The estate's SQL homes are beside the
  code that owns the schema — `bond_data_mcp/migrations/` (four numbered
  files) and `etf-scraper/migrations/` — and a `bond-data` RLS migration
  belongs in one of those, next to the bond-data code, where the person
  applying it is already working. Put in this SDK it is a file nobody with
  the database credentials will ever open.
- Preparing a `clients` table definition or an RLS *policy* now would answer
  the question on the card by writing it down. A policy needs the scoping
  column; a `clients` table needs the identity model. Both are what is being
  decided.

What this repo *did* do is record the constraint that any such migration must
not break: the SDK's request contract accepts no bond values, so whatever
identity the hosted tier adopts must not appear in `ValidateRequest`. See
§5, and the test that enforces it.

## 5. The one thing this lane changed

Two decisions get cheap with a line written down, so they are written down.

**(a) `.cmux/decisions/` is the right home for a documented decision**, and
this file is it, in the form item 1049's record already established for this
repo. It is committed beside the code, so the next lane reads it instead of
re-reading the item.

**(b) Tier 2's roadmap line now states that it carries the isolation
boundary with it.** `README.md` sold Tier 2 as "the convenience option, not
the security option" — honest, and still true. What was missing is that the
tier's *own* perimeter is a build deliverable rather than a post-v1
follow-up, because Tier 2 is the only tier where we hold client data at all.
That sentence costs nothing, changes no behaviour, and removes the reading
under which 1053 is "a nice-to-have we'll get to".

## 6. What a Tier 2 service must do, whichever way the decision goes

Stated so a builder in any repo has it, and so it does not have to be
re-derived:

1. Resolve the caller's identity **server-side** at upload, never from a body
   field. A `client_id` that arrives in the request payload is client-asserted
   and isolatable by nobody.
2. Store the upload against the resolved identity — an FK to whatever §3
   settles, not free text.
3. Enforce reads at the database, not in application queries. Application-side
   filtering of an anon-readable table is not a boundary.
4. Keep the validator's wire contract unchanged. `ValidateRequest` accepts no
   static values and must not grow a client identifier; identity belongs to
   the hosted service's own session, not to this protocol. The test in
   `python/tests/test_wire_contract.py` guards the value half; this note
   guards the identity half.
5. Ship the enable-RLS-with-no-policy step as soon as the tables exist. Do
   not wait for entitlements.

## 7. What is NOT in dispute

- Both v1 shortcuts were **intentional**, and the item says so. Nothing has
  regressed; no test is red because of this. It is a pre-landing control, not
  a defect report.
- It is **not blocking** for internal demos, and it does not block anything
  in this package.
- The larger exposure — `transactions`, `current_holdings` and `cashflows`
  readable with the public publishable key — is real, measured, and is
  **Bucket D of the 2026-05-20 audit**, i.e. the same bucket and the same
  decision. Item 1053 is two rows of a 160-table audit. Acting on the item
  instead of the bucket is the mistake worth avoiding, and it is not a
  mistake this repo can fix.
