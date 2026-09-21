# static-validator / `theme:auth` — package report

**Lane:** `proposal/static-validator-theme-auth-09212136`
**Slice:** item 1053. It is the only open item in the package.
**Commits:** two — the decision record + README (this is the work), then this
report.

**Result: 1053 is a decision, and it is a decision somebody else already made
half of.** The estate decided the *shape* of this control four months ago and
never ran it. What this lane adds is the thing two prior lanes could not leave
behind: a written record, in the repo, of the part that code can settle — so
the next lane does not spend itself re-deriving the same three facts. **No
financial number, no endpoint and no test contract was touched.**

---

## 1. Reading the item, and what is already on the record

The item is a post-v1 note, not a defect. Its own text says both v1 shortcuts
were intentional, "not blocking for internal-only demos with Guinness etc.",
and become blocking only "before any external client lands".

The lane before this one (`...-09212102`, commit `f64df30`) already reported
1053 as a decision and left no change. It was right, and I have not re-litigated
its finding — I have tried to *file* it, because it was filed into a report
nobody re-reads. This lane was issued against the same item anyway, which is
itself the finding: **a `DECISION` disposition in a report does not reach
anyone, while a `lane-decisions` card does.** That is why this report ends with
a card again, and why the reasoning now also lives at a path a future lane will
find before it writes any code (`.cmux/decisions/1053-*.md`, the pattern item
1049 established for this repo).

## 2. Grouping the symptoms into underlying defects

One item, three separable things. Only one of them is anybody's to fix, and
none of them is this repo's.

| # | The thing | Owner | Status |
|---|---|---|---|
| **B0** | Client identity root of record — xt-auth email, or a `clients` table | **Andy** | Open since 2026-05-20 |
| **B1** | `REVOKE` anon write / enable RLS-with-no-policy on two empty tables | **bond-data**, and it needs no decision | Available now |
| **B2** | RLS *policies* on the upload tables + `client_entitlements` | **bond-data** | Blocked on B0 |

**B0 is not a new question.** The estate's own audit
(`codebase-mcp/docs/SUPABASE_RLS_AUDIT_2026_05_20.md`) put
`portfolio_uploads` and `portfolio_upload_evidence` in **Bucket D** — per-user,
"RLS-policy MUST be added" — together with `transactions`, `current_holdings`,
`cashflows` and ~25 `v_*` views, and gave the policy shape:

```sql
portfolio_id IN (SELECT portfolio_id FROM client_entitlements WHERE client_id = ...)
```

Its own blocker section, third bullet, reads: *"Bucket D needs the user-scoping
column (`tenant_id` / `client_id` / `portfolio_id`) confirmed per table before
policies can be written."* Dated 2026-05-20. Item 1053 is that question, asked
again four months later, about two rows of a 160-table audit. **The right target
for 1053 is the bucket, not the item** — and it is not a target this package can
reach.

Two facts I verified rather than inherited from the item's premise:

- `client_entitlements` does not exist on `bond-data` (`PGRST205`). The policy
  shape above reads a table that is not there, so B2 is blocked on more than
  the identifier choice. A draft for that table does exist in the estate, but
  scoped to a different project — `codebase-mcp/docs/rls_client_entitlements_migration.sql`,
  drafted 2026-06-07 against Orion, still marked `DO NOT APPLY BLINDLY`.
- **Nothing on this host reads or writes these tables.** `grep -rn
  "portfolio_upload"` across this repository and across `/opt/work` returns the
  audit doc and nothing else; `git ls-files '*.sql'` in this repo is empty;
  neither `python/src` nor `mcp/src` contains a database client or a Supabase
  reference. The Tier 2 service that would write them is the thing item 1046
  says has no renderer and no DNS.

## 3. What I changed, and why this and not more

**Commit 1 — the record, not the fix.**

1. `.cmux/decisions/1053-tier2-upload-isolation.md` (new). Written because two
   lanes have now been spent reading the same two sentences. It records: what
   the repo already guarantees and what it deliberately does not (§1); where
   Tier 2's data actually lives and that no checkout here touches it (§2);
   which half is a decision and which half was already decided estate-wide, on
   2026-05-20, with the enable-RLS-no-policy shape (§3); why a prepared SQL
   file is cheap and still wrong here — the migration belongs beside the
   bond-data code that owns the schema, and a `clients` table definition
   written now would *answer* the question on the card by writing it down
   (§4); what a Tier 2 service must do whichever way the decision goes (§6);
   and what is not in dispute (§7).
2. `README.md:96`. The v0.6 Tier 2 roadmap line now states that the tier ships
   **with** an isolation boundary — server-side upload identity plus database
   access rules. The README was already honest ("the convenience option, not
   the security option", README:71); what it never said is that the tier's own
   perimeter is a build deliverable rather than a post-v1 follow-up. One
   sentence, no behaviour change, and it kills the reading under which 1053 is
   a nice-to-have.

**No SQL file, no schema change, no source change.** Deliberate. A policy set
needs the scoping column; a `clients` table needs the identity model; both are
the decision. Writing either here would take the decision, not complete the
item — and it would take it in a repository with no migrations directory, which
is where the migration would go to be forgotten.

## 4. Item ids — what this report claims

| id | status | one line |
|---|---|---|
| 1053 | **DECISION** | Two halves and two owners. The identity root (B0) is Andy's and has been open since 2026-05-20; the write-grant half (B1) is decision-free and is option A on the card. Neither belongs to `static-validator`: no file here reads or writes the tables. |

`FIXED:` is **none**, and `ALREADY_FIXED:` is **none**. The item's own text
says both shortcuts were intentional v1 choices; nothing has regressed; no
test is red because of it. This repo has no migrations directory and no
database client, so it has nothing to fix.

## 5. Deliberately not fixed, and why

| Not fixed | Why |
|---|---|
| 1053, half 1 — `client_id` → FK | Needs a target that does not exist on `bond-data` (`clients`, `client_entitlements`). Choosing the root of record is a human decision, and the audit has been waiting on it since 2026-05-20. |
| 1053, half 2 — RLS policies | Same decision, plus the policy reads a table that is not there. The migration belongs to `bond-data`, not to a repo with no SQL and no Supabase client. |
| 1053 as a handoff to `bond_data_mcp` | Considered and **declined**, on the brief's own test. A handoff "goes straight to a lane in that repo" and exists to dispatch work already decided. Option A (enable RLS with no policies) requires no schema decision, but it also requires the tables to exist and to *have* a client-facing consumer — and no repository on this host writes them, no client has landed on the tier, and item 1046 says the tier itself is unbuilt. Dispatching a lane against a table nobody writes is a lane spent on nothing. The action is the card, which puts it in front of the one person who can run it. |
| (adjacent, out of scope) the other ~25 Bucket D tables | `transactions`, `current_holdings`, `cashflows` are readable with the public publishable key today. Named here so the next lane does not mistake 1053 for the whole exposure — 1053 is two rows of it. |

## 6. Tests run

```
$ cd python && PYTHONPATH=src python3 -m pytest tests/ -q
285 passed in 0.31s

$ cd mcp && PYTHONPATH=src:../python/src python3 -m pytest tests/ -q
8 passed, 1 warning in 0.50s
```

Both suites green and unchanged. **This is a baseline, not evidence for the
change** — no source file was modified, so no test could have moved. Stated so
the next lane knows the inherited tree is green. (`test_wire_contract.py`
depends on the optional `jsonschema` extra and skips without it; it is
installed here and ran.) I issued **no live database probes** — the previous
lane's readings of `bond-data` are on the record and I had no need to repeat
them to reach a conclusion about this repository.

## 7. What needs a human

1. **The card below.** It has one question on it, and it has been asked twice.
   The recommendation is A because A is not really a choice — it is the half of
   this item that nobody has to decide, sitting undone inside a question that
   has been blocking it since May.
2. **Answer the bucket, not the item.** The exposure the audit measured —
   `gcrift`, `gdbft`, `wnbf`, `wnbftest` across `transactions`,
   `current_holdings`, `cashflows`, readable by anyone holding the public key —
   is Bucket D, and 1053 is two rows of it. Fixing 1053 alone fixes neither the
   transactions nor the holdings.
3. **`DECISION` in a report does not reach Andy; a card does.** This is the
   second consecutive lane spent on 1053, and the first one reached the correct
   answer. Something in the loop has to prefer the card.

---

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: 1053
-->

<!-- lane-decisions
item: 1053
question: For the hosted tier's upload tables, do we (A) enable RLS with no policies and revoke anonymous write on portfolio_uploads and portfolio_upload_evidence now, leaving client_id's FK target and read isolation to the estate-wide Bucket D programme, (B) build a clients table and client_entitlements in bond-data and scope reads through them before any external client lands, or (C) leave both tables open as accepted risk for the internal demo phase?
context: The FK target the item names, client_entitlements, does not exist on bond-data, both upload tables are empty and written by no repository on this host, and the estate's own 2026-05-20 audit already decided the enable-RLS-no-policy step and has not run it.
option A: Enable RLS on portfolio_uploads and portfolio_upload_evidence with no policies and revoke anon INSERT/UPDATE/DELETE from the API roles; re-file client_id's FK target and per-client read isolation into the existing Bucket D programme that already owns transactions, current_holdings and cashflows; re-open 1053 when the first external client is contracted.
option B: Build a clients table plus client_entitlements in bond-data, migrate client_id to an FK against clients.id, and ship RLS policies on the upload tables and on transactions/current_holdings/cashflows, as one scoped migration run by Andy or the service-role holder.
option C: Leave both tables open as they are, treat the exposure as accepted for the internal demo phase, and do no revocation and no policy work until external-client terms are signed.
recommend: A
reason: Neither table has ever held a row and no repository writes them, so enabling RLS with no policies is a no-op for every reader that exists, closes the anonymous write path today, and does not pre-empt the identity question the Bucket D programme must answer anyway.
default: A
-->
