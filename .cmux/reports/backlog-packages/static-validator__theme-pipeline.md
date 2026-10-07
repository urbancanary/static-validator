# static-validator — package `theme:pipeline`, item 5668

**Lane:** `lane/auto-static-validator-theme-pipeline-10071400` (branch `proposal/*`)
**Package:** theme:pipeline — 4 open items, my slice is 1: **5668**
**Item 5668:** "validate-portfolio: write persistence.py (portfolio_uploads +
portfolio_upload_evidence, local JSON fallback)" — file: `validate_portfolio/persistence.py`
**Verdict: DECISION. No code change. The premise of the item does not hold against this repo,
and the one live fact in it is another package's open decision (1053).**

---

## 1. What I checked, and what is there

Three checks, in order.

**(a) The named file and its package.** `validate_portfolio/persistence.py` does not exist, and
neither does the package that would contain it:

```
$ find . -name validate_portfolio -not -path './.git/*'        # no output
$ find . -not -path './.git/*' -name "SKILL.md" -o -name "*.tsv" -o -name samples -o -name migrations
                                                               # no output
$ git ls-files | wc -l                                          # 65 tracked files
```

`grep -rn validate_portfolio . --exclude-dir=.git -l` returns exactly one file —
`.cmux/reports/backlog-packages/static-validator__5667.md`, a report, not code.

**(b) The git history.** The item names no commit:

```
$ git log --oneline --grep 5668      # no output
$ git log --oneline --grep 1057      # no output
```

The sibling item 5667 (same unbundled parent 1057: *"complete cli.py + config.py +
persistence.py"*) was already read by the immediately preceding lane. Commit `981b980`
"Report: static-validator / 5667 — validate_portfolio does not exist in this repo", merged as
`3ea9e6d`. That lane reached the same finding by the same route and wrote it up in
`.cmux/reports/backlog-packages/static-validator__5667.md`. My item is the `persistence.py`
third of that same unbundling, so it inherits that finding exactly.

**(c) The words in the item.** `PERSISTENCE`, `persistence.py`, `portfolio_upload_evidence` as
a *string in code* — none of them occur in any tracked source file. The two names appear only
in `.cmux/` prose (the 1053 decision file, three reports, `README.md:97`).

What *does* exist in this repo, next to the assumed one:

| Item 5668 assumes | In this repo |
|---|---|
| package `validate_portfolio/` | absent. Only Python package: `python/src/static_validator/` |
| `validate_portfolio/persistence.py` | absent; no `persistence.py` anywhere |
| hosted mode writing parent/child upload rows | **no code in this repo reads or writes either table** — `README.md:20`, `README.md:97` |
| `PERSISTENCE=local_file` JSON snapshot beside an HTML render | absent — there is no renderer and no HTML output (`README.md:97` lists the renderer under v0.6, unbuilt) |
| "migration applied 2026-05-12" | no migration file, no `migrations/` directory, ever (`.cmux/decisions/1053-…md` §8) |

`python/src/static_validator/cli.py:1` is a two-subcommand per-record tool (`hash`,
`canonical`); `mcp/src/static_validator_mcp/server.py` is local stdio with three tools. Neither
is a portfolio pipeline and neither has a persistence layer to write.

## 2. Why this is DECISION and not FIX

A FIX is "one small, clear change you can finish and test inside your budget". There is no
such change here. To satisfy item 5668 I would have to invent, from nothing: the
`validate_portfolio` package, the `TRUST_MODE`/`ENRICHMENT_SOURCE`/`PERSISTENCE`/`RENDER_TARGET`
config semantics, an HTML renderer for the local-file snapshot to sit beside, and a Supabase
write path for two tables this repo does not own and cannot reach. Every one of those is a guess
about a design no artifact in this checkout records. That is authoring a new program, not
closing a backlog defect.

There is also a hard rule in the way, independent of the missing package. Item 5668 asks the
hosted path to write **child `portfolio_upload_evidence` rows**, and the schema of that table is
the client's own par, clean price, accrued, YTM, duration and income. The standing rule for this
lane is that a change which would move a client-facing financial number stops and goes back for
review by a Claude session. Writing those rows *is* that change; a DeepSeek lane must not author
it.

**One person has to answer one question, and it is the same question that closed 5667:**

> **Which repository or project owns `validate_portfolio` — and is a hosted write path against
> the `bond-data` upload tables in scope at all?**

Everything else in the item is downstream of that answer. If the pipeline lives in another repo,
this is a HANDOFF for the next lane and no card is needed; if it is meant to live here, it must
be specified first, because the six existing stages the item's parent assumes are not present.

## 3. What is real in the item, and whose decision it is

The item's one live fact is "migration applied 2026-05-12", i.e. that
`portfolio_uploads` and `portfolio_upload_evidence` exist and are writable. They do, and the
measured state is worse than the item assumes: `.cmux/decisions/1053-tier2-upload-isolation.md`
§2 records a live probe on 2026-09-27 returning `201` from an anonymous `POST` to
`portfolio_uploads`, i.e. both tables accept anonymous `INSERT`/`UPDATE` today.

That is **not 5668's decision to file.** It is item 1053, in the sibling package
`theme:auth`, and a card for it is already in
`.cmux/reports/backlog-packages/static-validator__theme-auth.md` and reaches Andy when that
branch lands. Filing the same question a second time under 5668 would put two cards in the one
list Andy reads for one decision. Per the grouping rule ("group by decision, not by item id"),
I am deliberately not filing a card and am leaving 5668 out of `DECISION:` — it cannot be closed
by *that* answer anyway; only a code change against a specified pipeline could close it.

## 4. What I did not do

- I did not create `validate_portfolio/`, `persistence.py`, a `SKILL.md`, or a sample TSV.
- I did not write any hosted Supabase path for the two upload tables, and did not author the
  `portfolio_upload_evidence` row shape.
- I touched no file outside this report. No test run is reported because no code changed.
- I did not apply, prepare, or name a migration.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: none
-->

## Handoff to the next lane on this package (resume point)

Item 5668 is **not closed** and should not be re-issued to another lane until the ownership
question above is answered — two lanes have now read the same sentence against the same tree
and reached the same finding (981b980 for 5667, this report for 5668).

- Next item in package `theme:pipeline` after 5668: the remaining 3 open items (my slice was 1
  of 4; the ids are not in this lane's brief — read them from the package card).
- The finding they will hit is already written down: `.cmux/reports/backlog-packages/static-validator__5667.md`
  §2 (the assumption-vs-tree table) and §1 of this report.
- The one live database fact, and the card that already carries it, is at
  `.cmux/decisions/1053-tier2-upload-isolation.md` §3 (the eight-line SQL statement).
