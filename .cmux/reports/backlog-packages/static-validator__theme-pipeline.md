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
