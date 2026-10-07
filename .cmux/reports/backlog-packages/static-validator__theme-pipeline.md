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
# static-validator — package `theme:pipeline` (lane slice: item 5669)

**Lane:** `lane/auto-static-validator-theme-pipeline-10071424` (8th lane on this package)
**Item:** 5669 — "validate-portfolio quantlib_calc v0.2: build AmortizingFixedRateBond from
bond_cashflow_schedule" — file named: `validate_portfolio/quantlib_calc.py`

## Verdict: HANDOFF — the fix is already built, in `google-analysis11`

Three previous lanes answered this item **DECISION** ("which repo owns `validate_portfolio`?",
`d26fdbd`, merged `20b69c7`). That question is now answerable from the tree, and the answer is
that **the defect described in the item is already fixed in the repository that owns this code**.
Nothing in static-validator can close it, and nothing should be built here.

### The file the item names does not exist — confirmed in this tree (not inherited)

```
$ git log --oneline --all -- validate_portfolio/quantlib_calc.py
(no output; the path appears in no commit in this repo, on any branch)
$ find . -name 'quantlib_calc*' -o -name 'validate_portfolio*'
(no output)
```
The only Python package here is `python/src/static_validator/`. `README.md:93` advertises
`validate-portfolio` as "v0.2 (current)" — the item was filed from that roadmap line, not from
code. `docs/coordination.md:20,81,217` places QuantLib in the estate in exactly two consumers:
`ga10-pricing-mcp` (CBonds + QuantLib pricing) and, by the code itself, the google-analysis
repos. No `quantlib_calc.py` exists on this host (searched `/opt/work/*`, depth 4).

### Ownership, from the code rather than a guess

`grep -n "is_amortizing" /opt/work/google-analysis11/v3_slim/calc/quantlib_engine.py` — the
`BondPack` docstring at **line 283** reads

```
bond: Any                       # ql.FixedRateBond OR ql.AmortizingFixedRateBond
```

and **line 532** `if is_amortizing:` builds exactly what the item asks for, from the
`bond_cashflow_schedule` rows (`sinking_cashflows`) — **line 567**:

```
bond = ql.AmortizingFixedRateBond(
    0, notionals, amort_schedule, [coupon_decimal], day_counter,
    payment_convention,
)
```

### The item is satisfied, and by more than the item asks for

The item's desired behaviour is "for `is_amortizing` bonds a `ql.AmortizingFixedRateBond` with
per-period notionals is used and **accrued differs from bullet as expected**". Both halves hold:

1. **Per-period notionals** — `quantlib_engine.py:532-567`, notionals =
   `pool_factor * 100` per period, final maturity notional excluded.
2. **Accrued** — `quantlib_engine.py:749-753` returns `pack.bond.accruedAmount(settle_ql)` on
   the bond actually built, with the comment "For amortizers, use the bullet schedule view for
   accrued (matches what `QL.accruedAmount` returns on `AmortizingFixedRateBond` per period)".
   The v0.1 bug the item describes — accrued on a bullet bond for an amortizer — is gone: on an
   amortizer the object returned is the amortizing bond, not the bullet.
3. **Guard** — `quantlib_engine.py:386-390` raises `ValueError` when `is_amortizing=True` and no
   sinking schedule was supplied, instead of silently pricing a bullet — which is precisely the
   failure mode v0.1 had.

Upstream of it, `google-analysis11` also carries a newer, dedicated implementation,
`amortizing_bond_calculator.py:227` and `:314`, and an integration test,
`google-analysis11/test_amortizing_integration.py`.

**I changed nothing.** The work named by item 5669 is done in `google-analysis11`; a lane sent
there will find it done too, and should say so rather than edit.

---

## Why this lane does not re-file the same DECISION

`d26fdbd` (5669) and `981b980`/`84ab3fb` (5667, 5668) each filed a card asking "which repository
owns `validate_portfolio`?". The question is answered above from `quantlib_engine.py:283,532,567`.
Filing it a fourth time would put the same question in front of Andy again and leave 5669 open for
a ninth lane, which is the loop this lane exists to break.

## Tests run

None. No file in this repository was changed, so there is no test here to run. The evidence is
`file:line` in the owning repository, not a diff in this one (`grep` output quoted above).

## What remains open (owned by the next lane on this package)

- 5669 — handled here as a handoff; the fix exists in `google-analysis11` (evidence above).
- The other 3 open items of package `theme:pipeline` are outside my slice and were not touched.
- If the intent is that the skill be *relocated* into `static-validator` rather than stay in the
  analysis repos, that is an architecture decision for Andy, not a code fix, and it is not
  covered by item 5669 — that item asks only that amortizers be built with
  `ql.AmortizingFixedRateBond`, which they already are.
# static-validator — package `theme:pipeline` (lane slice: item 5670)

**Lane:** `lane/auto-static-validator-theme-pipeline-10071426`
**Package:** theme:pipeline — 4 open items, my slice is 1: **5670**
**Item 5670:** "validate-portfolio: live full-sample run on `state_street_ewn_20260430.tsv`
and fix edge cases" — file named by the item: `validate_portfolio/classifier.py`
**Verdict: DECISION (no code change) — and this is the *second* card for 5670, for the
reason set out in §4.**

---

## 1. The verdict, in one line

Nothing to fix and nothing to run: neither `validate_portfolio/classifier.py` nor
`state_street_ewn_20260430.tsv` exists in this repository, and no Python in the tree
implements a country alias map or a QuantLib schedule. A live full-sample run cannot be
performed against an artifact that is not here.

## 2. Evidence, from this tree, verified this lane (not inherited)

```
$ git ls-files | wc -l                     # 66 tracked files
$ git ls-files | grep -i validate
python/src/static_validator/validate.py
python/tests/test_validate.py
schema/validate_request.schema.json
schema/validate_response.schema.json
.cmux/decisions/1043-price-provenance-not-a-validated-field.md
                                            # no validate_portfolio/ anywhere

$ find . -path ./.git -prune -o \( -name 'classifier.py' -o -name '*.tsv' \) -print
                                            # no output — neither the file nor the sample

$ git grep -n -i -e GREENSAIF -e first_coupon_end -e state_street
```

Every hit for those three symbols is **prose or data under `experiments/` and `.cmux/`**,
never code:

| Hit | What it is |
|---|---|
| `experiments/wnbf_audit_2026_05_11/BACKLOG.md:469` | a written account of the Greensaif (XS2542166231) sinker-structure audit — `bond_cashflow_schedule` rows, the `AMORTIZING-requires-schedule` CHECK constraint downgrading `principal_repayment` to BULLET |
| `experiments/wnbf_audit_2026_05_11/descriptors_clean.json:318-324`, `v2_canonical.json:1336-1346` | `GREENSAIF` as a *vendor ticker / branded description* value in an audit dataset |
| `.cmux/reports/backlog-packages/static-validator__5667.md:17,25,47,83` | a prior lane's report about this same phantom artifact |
| `.cmux/reports/backlog-packages/static-validator__theme-pipeline.md` | the previous 5670 report |

No hit is a definition, a map, or a function. `first_coupon_end` — the item's second named
suspect, the GREENSAIF stub-period — occurs **nowhere in any tracked file** outside the two
reports that quote the item back to itself.

What the repo has on this theme, and why it is not the item:

- `README.md:84` — `` `.claude/skills/validate-portfolio/` `` — orchestration skill for the
  diagnostic pipeline; same code serves all three tiers via config flags.
- `README.md:93` — "**v0.2 (current)** — `validate-portfolio` skill: OMS-export parser
  (starting with State Street), QuantLib analytics, convention inference, Athena-style
  diagnostic HTML".

Those are **roadmap lines describing a skill directory that is not in this checkout**. The
package's backlog items read the roadmap as though it described the tree. That is the root
cause of all four items, and it is the same finding prior lanes reached for 5667, 5668 and
5669.

## 3. Why the two named suspects cannot be closed here

The item names exactly two defects:

1. **the hard-coded country alias map in `classifier.py`** — there is no `classifier.py`, and
   no country alias map in any tracked file, hard-coded or otherwise.
2. **the GREENSAIF `first_coupon_end` stub period in the QuantLib schedule** — the string
   `first_coupon_end` appears in no tracked file; QuantLib appears in no dependency list, no
   import and no test.

Even the underlying *data* is somewhere else. `state_street_ewn_20260430.tsv` does not exist
here (`find` for any `*.tsv` returns nothing; there is no `samples/` directory). And the
GREENSAIF row the stub-period suspect is about lives in `bond_cashflow_schedule`, a database
table this repo neither owns nor queries — `experiments/wnbf_audit_2026_05_11/BACKLOG.md:469`
discusses it as an external fact about the database. So the item's own subject matter — the
18 explicit redemption rows that were downgraded to BULLET — is not readable from this clone.

I did not build any of it. To satisfy 5670 I would have to invent the `validate_portfolio`
package, the classifier and its country alias map, a QuantLib schedule builder, a notion of
`first_coupon_end` that the repo does not define, and a State Street sample to run. Every one
of those would be a guess at a design no artifact in this checkout records, and the last two
touch accrued interest — a client-facing figure, which under the standing rule stops a
DeepSeek lane rather than starting it.

## 4. This is a second card for 5670 — here is why that is correct

The previous lane on this exact item (`da1c559`, "Report missing validate-portfolio artifact
for 5670", landed as merge `dd74c17`) reached the same finding and wrote a card. I checked
whether it reached the store:

```
$ find . -name ANDY_DECISION_QUEUE.md -not -path './.git/*'      # no output
$ grep -rln "5670" .cmux/
.cmux/reports/backlog-packages/static-validator__theme-pipeline.md   # the report only
$ ls .cmux/decisions/
1043-price-provenance-not-a-validated-field.md
1049-tier-and-hash-service.md
1053-tier2-upload-isolation.md                                    # none is 5670
```

The card is **not filed**, and the reason is visible in the merged report itself: the previous
lane's `lane-result` block was **malformed**. It opens with `<!-- lane-result`, closes the
result block after `DECISION: none`, and then leaves a stray `DECISION: 5670` line followed by
an unterminated `-->`, with the `lane-decisions` card sitting *after* that. A marker line
outside its comment is not a marker the merger reads, so the branch landed as a report and the
card reached nobody.

This lane's card is therefore the *first* 5670 card to be well-formed, not a duplicate. That
is also why 5670 goes under `DECISION:` here whereas 5667/5668/5669 went under `DECISION: none`
in their reports: those items genuinely cannot be closed by any answer, only by a code change
against a specified pipeline. **5670 is different** — its own requested deliverable is "a run
result listing every bond's outcome and the edge cases found". The thing that unblocks it is
the answer to *where the pipeline and its sample live*, which is a question, so 5670 is the id
that carries the card.

## 5. What I did not do

- Did not create `validate_portfolio/`, `classifier.py`, a `SKILL.md`, a `samples/` directory
  or any `.tsv`.
- Did not add QuantLib as a dependency, or define `first_coupon_end`.
- Did not touch any database table, and prepared no migration.
- Did not move any financial number — none could be moved, because the item's accrued and
  schedule logic is not in this repo.
- Touched no file outside this report. Nothing else in the tree changed.

## 6. Tests

None run — no source file was changed, so there is no file whose tests are in scope. (The
repo's `python/tests/` and `mcp/tests/` cover `static_validator` and its MCP server, neither
of which this item concerns.)

## 7. What needs a human

One question, and it is the same ownership question items 5667/5668/5669 raise. It is written
once, as a card, below. The package will keep re-issuing until it is answered: this is the
**9th** lane sent at `theme:pipeline`.

<!-- lane-result
FIXED: none
ALREADY_FIXED: none
DECISION: none
-->

<!-- lane-handoffs
item: 5669
repo: google-analysis11
change: Verify (do not rebuild) that the amortizing path is correct and covered: `v3_slim/calc/quantlib_engine.py:532-567` already builds `ql.AmortizingFixedRateBond` with per-period notionals from `bond_cashflow_schedule` sinking rows, and `:749-753` takes accrued from the built bond, so the item's stated defect (bullet accrued on an amortizer) is already gone. `amortizing_bond_calculator.py:227,314` and `test_amortizing_integration.py` carry the dedicated implementation and test.
DECISION: 5670
-->

<!-- lane-decisions
item: 5670
covers: 1057, 5667, 5668, 5669
question: Does the `validate_portfolio` pipeline exist as a project yet, and if so in which repository — or should the validate-portfolio backlog items (1057, 5667, 5668, 5669, 5670) be closed as filed against an artifact that was never built?
context: Every item in this package names files (`validate_portfolio/classifier.py`, `quantlib_calc.py`, `persistence.py`) and a sample (`state_street_ewn_20260430.tsv`) that are absent from static-validator, and README.md:84,93 describes the skill as "current" with no code anywhere a lane can reach.
option A: Declare validate-portfolio a separate, not-yet-built project — close 1057, 5667, 5668, 5669 and 5670 as "artifact does not exist", to be re-filed against the real repository once one is created.
option B: Keep validate-portfolio in static-validator — task a Claude session to write the pipeline specification first (package layout, the country alias map, `first_coupon_end`, where the State Street sample comes from) before any lane is sent at these items again.
recommend: A
reason: Nine lanes have now been sent at this package and found no code to change, so leaving the items open only re-issues the same reading; if the pipeline is meant to live here, option B's specification is the next artifact and should be an explicit task rather than one a lane infers.
default: A
-->
