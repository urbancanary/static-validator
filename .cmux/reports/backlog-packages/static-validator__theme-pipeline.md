# static-validator — package `theme:pipeline` (lane slice: item 5668)

**Lane:** `lane/auto-static-validator-theme-pipeline-10071420`
**Package:** theme:pipeline — 4 open items; my slice is 1.
**Item 5668:** "validate-portfolio: write persistence.py (portfolio_uploads +
portfolio_upload_evidence, local JSON fallback)" — file: `validate_portfolio/persistence.py`
**Verdict: DECISION — the file, the package and the pipeline the item assumes do not exist in
this checkout. No code change can close it here. No new card filed; see §3.**

---

## 1. What the item asks for

Hosted mode must write parent `portfolio_uploads` and child `portfolio_upload_evidence` rows to
bond-data Supabase (item says the migration was applied 2026-05-12); `PERSISTENCE=local_file`
must write a JSON snapshot beside the HTML. Both paths implemented and tested.

That assumes, in *this* repository:

1. a package directory `validate_portfolio/` containing `persistence.py`;
2. a `PERSISTENCE` setting with a `local_file` mode;
3. an HTML renderer for the JSON snapshot to sit beside;
4. a hosted Supabase write path this repo can reach.

## 2. Verified against the tree, independently of the earlier lane

```
$ find . -path ./.git -prune -o \( -name 'validate_portfolio*' -o -name 'persistence.py' \) -print
(no output)

$ git grep -n "validate_portfolio"
only .cmux/reports/backlog-packages/static-validator__5667.md — a report, not code

$ git grep -n "PERSISTENCE"
only .cmux/ reports — the string occurs in no tracked source file

$ git log --oneline -5 -- validate_portfolio/
(no output — no commit in this repo has ever touched that path)
```

| The item assumes | In this repo |
|---|---|
| package `validate_portfolio/` | **absent.** Only Python packages: `python/src/static_validator/`, `mcp/src/static_validator_mcp/` |
| `validate_portfolio/persistence.py` | **absent** — no `persistence.py` anywhere in the tree |
| `PERSISTENCE=local_file` JSON snapshot beside an HTML render | **absent** — no config module, no renderer, no HTML output. `README.md:97` lists the report renderer and hosted Tier 2 under **v0.6, unbuilt** |
| hosted write of `portfolio_uploads` / `portfolio_upload_evidence` | **no code in this repo reads or writes either table** — `README.md:20`, `README.md:97` |
| "migration applied 2026-05-12" | no migration file and no `migrations/` directory exists anywhere on this host (`.cmux/decisions/1053-tier2-upload-isolation.md` §8) |

The item is one third of the unbundling of item 1057, *"validate-portfolio skill: complete cli.py
+ config.py + persistence.py"* — a skill the roadmap line `README.md:93` describes as **v0.2
(current)** while `README.md:97` describes the same pipeline's storage and renderer as **v0.6,
unbuilt**. The backlog items in this package were filed by reading the roadmap as though it
described the tree.

Two sibling slices of the same parent were already read and reached the same finding by the same
route: item 5667 (`cli.py` + `config.py`) in commit `981b980` / report
`.cmux/reports/backlog-packages/static-validator__5667.md`, and item 5669 (`quantlib_calc.py`) in
`.cmux/reports/backlog-packages/static-validator__5669.md`. Item 5668 is the `persistence.py`
slice and inherits that finding exactly. The previous lane on this package
(`…-10071400`, commit `84ab3fb`, merged as `c56cee1`) reached the same verdict; I re-derived it
rather than inheriting it, with the greps above.

## 3. Why DECISION and not FIX

A FIX is "one small, clear change you can finish and test inside your budget". There is no such
change here. To satisfy 5668 I would have to invent, from nothing: the `validate_portfolio`
package, the `TRUST_MODE`/`ENRICHMENT_SOURCE`/`PERSISTENCE`/`RENDER_TARGET` config semantics, the
JSON snapshot schema, an HTML renderer for the snapshot to sit beside, and a Supabase write path
for two tables this repo does not own and cannot reach. Every one of those is a guess about a
design no artifact in this checkout records. That is authoring a new program, not closing a
backlog defect.

There is also a hard rule in the way, independent of the missing package. Item 5668 asks the
hosted path to write **child `portfolio_upload_evidence` rows**, and the shape of that table is
the client's own par, clean price, accrued, YTM, duration and income. Writing those rows *is* a
change to client-facing financial numbers; a lane that would make it stops and hands back for
independent Claude review. I did not write it.

### The one question that closes this

> **Which repository or project owns `validate_portfolio` — and is a hosted write path against
> the bond-data upload tables in scope at all?**

Everything else in the item is downstream of that answer. Three outcomes, none of them mine to
take: if the pipeline lives in another repo, this is a handoff; if it is meant to live *here*, the
pipeline must be specified first, because the six existing stages the parent item assumes are not
present; if it was only ever a roadmap entry, the item should be closed as not-planned.

### No card filed, deliberately

The item's one live fact is that the two upload tables exist and are **anonymously writable**
(measured 2026-09-27: anonymous `POST /portfolio_uploads` returns `201`). That is item **1053**,
in the sibling package `theme:auth`, and a card for it already sits in
`.cmux/reports/backlog-packages/static-validator__theme-auth.md`, which reaches Andy when that
branch lands. Per the grouping rule ("group by decision, not by item id") I am not filing a second
card for the same decision under 5668. 5668 also cannot be closed by *that* answer: only a code
change against a specified pipeline can close it, so the id does not belong under `DECISION:`
either. It is left in neither list, which is why this section exists.

## 4. What I did not do

- I did not create `validate_portfolio/`, `persistence.py`, a config module, a `SKILL.md`, or a
  sample TSV. Doing so would make the item look closed while shipping a pipeline invented to match
  the wording of the item.
- I did not write any hosted Supabase path for the two upload tables, and did not author the
  `portfolio_upload_evidence` row shape.
- I did not apply, prepare or name a migration.
- I touched no file outside this report. No test run is reported because no code changed.

## 5. Resume point for the next lane

Nothing to resume in code. The item stays open until §3's question is answered; the answer is a
repository name or a "not planned". If the answer is "another repo", re-file as a handoff to that
repo (project name from the backlog), naming `validate_portfolio/persistence.py` there.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: none
-->
