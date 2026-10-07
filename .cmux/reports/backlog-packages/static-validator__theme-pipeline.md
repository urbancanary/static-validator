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
# static-validator — package `theme:pipeline` (lane slice: item 5669)

**Lane:** `lane/auto-static-validator-theme-pipeline-10071406`
**Package:** theme:pipeline — 4 open items, my slice is 1.
**Item:** 5669 — "validate-portfolio quantlib_calc v0.2: build AmortizingFixedRateBond from
bond_cashflow_schedule"
**File named by the item:** `validate_portfolio/quantlib_calc.py`
**Verdict: DECISION — the file, the function and the repository the item assumes are all absent
from this checkout. No code can close it here.**

---

## 1. What the item says, and what it assumes exists

> v0.1 treats every bond as a bullet FixedRateBond even when canonical.is_amortizing is True, so
> accrued is wrong for amortizers.
>
> Desired behaviour: For is_amortizing bonds a `ql.AmortizingFixedRateBond` with per-period
> notionals is used and accrued differs from bullet as expected.
>
> File: `validate_portfolio/quantlib_calc.py`

That assumes, in this repository:

1. a package directory `validate_portfolio/` with a module `quantlib_calc.py` in it;
2. a v0.1 of that module that builds `ql.FixedRateBond` unconditionally;
3. a `bond_cashflow_schedule` (the item's title) to build per-period notionals from;
4. QuantLib as an importable dependency of this repo.

## 2. Verified against the tree, not inherited

```
$ git log --oneline -5 -- validate_portfolio/quantlib_calc.py
(no output — no commit in this repo has ever touched that path)

$ find . -path ./.git -prune -o \( -name 'quantlib_calc*' -o -name 'validate_portfolio*' \) -print
(no output)

$ grep -rn "quantlib\|QuantLib" . --exclude-dir=.git
(no output — the word QuantLib appears nowhere in any tracked file, not in code,
 not in a dependency list, not in a test)
```

| The item assumes | In this repo |
|---|---|
| `validate_portfolio/` package | **absent.** The only Python package is `python/src/static_validator/` (`adapter.py`, `canonicalize.py`, `cli.py`, `derivations.py`, `gemini_extractor.py`, `hashes.py`, `validate.py`, `wire.py`) |
| `validate_portfolio/quantlib_calc.py` | **absent** — no `quantlib_calc.py` anywhere; the substring `quantlib` occurs in no tracked file |
| a v0.1 bullet `FixedRateBond` builder to amend | **absent** — nothing to amend |
| `bond_cashflow_schedule` | **absent** — no such field, function or schema node |
| QuantLib dependency | **absent** — not imported, not declared, never named |

The upstream this item is a child of is item **1057, "validate-portfolio skill: complete cli.py +
config.py + persistence.py"** — the same phantom package. It was already worked and reported on:
`.cmux/reports/backlog-packages/static-validator__5667.md` (commit `981b980`, merged as `3ea9e6d`,
"Report: static-validator / 5667 — validate_portfolio does not exist in this repo") reaches the
same finding for the sibling item and cites the same evidence: no `validate_portfolio/`, no
`SKILL.md`, no `samples/`, no `config.py`.

`README.md:93` explains where the phrase comes from — "**v0.2 (current)** — `validate-portfolio`
skill: OMS-export parser (starting with State Street), QuantLib analytics, convention inference,
Athena-style diagnostic HTML". That is a **roadmap line describing an unbuilt skill**, not a
description of code in this repo. The backlog items in this package were filed by reading the
roadmap as though it described the tree.

## 3. What the repo *does* have on this theme, and why it is not the item

This repo does model amortization, in three places, all reported not priced:

- `schema/structural_flags.schema.json:11` — `"is_amortizing": {"type": "boolean",
  "description": "Principal amortizes evenly across coupon dates."}` — a published structural flag.
- `python/src/static_validator/wire.py:45` — `is_amortizing: bool` on the wire record.
- `python/src/static_validator/validate.py:49` — the flag raises the warning *"bond is amortizing
  — principal repays before maturity; bullet-mode pricing will be wrong"*.

That last line is the repo's current answer to exactly the defect item 5669 describes: it
**detects** the bullet-mode mispricing and **says so in the diagnostic**, without computing a
price. `README.md:34` is explicit that this is the product design, not a gap — the customer's
reported yield matching our bullet model *is the finding*: "The customer's reported yield matches
our bullet model exactly — so we know their system is pricing them as bullets — but the bonds are
amortizers, and their numbers are wrong." Building an `AmortizingFixedRateBond` to re-price
amortizers is the v0.2 pipeline's job, and that pipeline does not exist in this repo.

I deliberately did not build it here. The named file is not here, `bond_cashflow_schedule` has no
definition anywhere, and every decision in the item — where the schedule comes from, how per-period
notionals are derived for an *evenly*-amortizing flag, whether the schema can even express them —
would be invented by me to match the wording of the item. That is authoring a module and shipping
an amortization formula that nothing in this repo specifies.

## 4. What is not being changed

No file was modified. In particular I did **not**:

- create `validate_portfolio/` or `quantlib_calc.py`;
- add QuantLib as a dependency;
- touch `validate.py:49`, `wire.py:45` or `schema/structural_flags.schema.json:11` — the flag,
  the warning and the schema are correct as they stand and are not the item;
- change any financial number. (None could be moved: this item touches accrued, which is a
  client-facing figure — had the module existed and had I built the amortizer, that would have
  been a STOP-and-hand-back under the standing rule, since a first amortizing accrual
  implementation is exactly the kind of change that needs independent review by a Claude session.)

## 5. Tests

None run. No file was changed, so there is no file to run tests for.

## 6. What needs a human

One question, and it is the same one item 5667 already raised — I am not re-asking it as a second
card, and `covers:` names 5669 so the two are settled together:

> **Does `validate_portfolio` exist as a project at all — and if so, in which repository?**
> The v0.2 skill behind items 1057 / 5667 / 5669 (CLI, config, persistence, QuantLib analytics,
> `bond_cashflow_schedule`, State Street sample) is described in `README.md:93` as "current" but no
> artifact of it is present in `static-validator`, and no sibling repo named in
> `docs/coordination.md` owns it. Until that is answered, every item in this package is
> unactionable by a lane and will keep coming back.

If the answer is "it is this repo", the pipeline must be **specified** before it is coded: the
package, the module layout, the `bond_cashflow_schedule` structure, and where per-period notionals
come from. That specification is a decision, not a fix.

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
DECISION: 5669
-->

<!-- lane-decisions
item: 5669
covers: 1057, 5667
question: Does `validate_portfolio` exist as a project, and if so in which repository — or should every validate-portfolio backlog item (1057, 5667, 5669 and the rest of the theme) be closed as filed against an artifact that was never built?
context: Item 5669 names `validate_portfolio/quantlib_calc.py`, which is not in static-validator; no tracked file in this repo contains the string "quantlib", and README.md:93 describes the validate-portfolio skill as "v0.2 (current)" while no code for it exists anywhere a lane can reach.
option A: Declare validate-portfolio a separate, not-yet-built project — close 1057/5667/5669 and their package siblings as "artifact does not exist", to be re-filed against the real repo once one is created.
option B: Keep validate-portfolio in static-validator — task a Claude session to write the pipeline specification first (package layout, bond_cashflow_schedule, where per-period notionals come from) before any lane is sent at the code items again.
recommend: A
reason: Four lanes have now been sent at this package and found no code to change, so leaving the items open only re-issues the same reading; if the pipeline is meant to live here, option B's specification is the next artifact and should be an explicit task rather than an inferred one.
default: A
-->

<!-- lane-handoffs
item: 5669
repo: athena_html_v3
change: If the validate-portfolio v0.2 pipeline (QuantLib analytics, amortizing-bond accrued) is in fact served from athena_html_v3 rather than static-validator, this item's fix belongs there, in whatever module builds the QuantLib bond object for a cashflow schedule — but no such module or route was verifiable from this clone, so confirm ownership before sending a lane.
-->
